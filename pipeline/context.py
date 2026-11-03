# =============================================================================
# pipeline/context.py - Ghép K(p): tập ngữ cảnh đa nguồn cho một prompt
#
# K(p) gồm các phần theo thứ tự (mỗi item có mã để trích dẫn):
#   [E] Thực thể được nhắc trong prompt  - node trùng tên/đường dẫn (RepoIndex.find_entities)
#   [C] Code   - CODE_N hàm/lớp đầu của RRF(AST, HIST), kèm caller/callee một bước
#   Files      - FILE_N file đầu, điểm file = điểm cao nhất của hàm/lớp trong file (SweRank)
#   [D] DOC    - pool chunk (RepoIndex.doc_pool), DOC_QUOTA phần tử đầu đưa cho LLM
#   [H] HIST   - pool commit theo phần lời (MsgIndex), HIST_QUOTA phần tử đầu
#   [I] ISSUE  - pool báo cáo cũ (IssueIndex), ISSUE_QUOTA phần tử đầu
#
# DOC, HIST, ISSUE không trộn vào phần Code: ở v4-L8, +DOC và +ISSUE kém AST khi trộn
# ngang hàng, còn bằng chứng của chúng hữu ích chủ yếu vì thông tin không phải vị trí code.
# Phần tử bằng chứng dùng định dạng v5 (mục 6.18.2 planning.md): chỉ nội dung vốn có của
# artifact, không đưa thông tin do pipeline suy ra (đích cạnh, hàm/lớp bị sửa).
# =============================================================================

from __future__ import annotations

import time
from datetime import datetime, timezone

import config
from pipeline.ranking import file_rank, rrf_fuse

_FC = ("Function", "Class")


def qualified(node_id: str) -> str:
    """'local:src/flask/app.py:Flask:url_for' → 'Flask.url_for'. Module → đường dẫn file."""
    parts = node_id.split(":", 2)          # [tiền tố, đường dẫn, tên lồng nhau]
    return parts[2].replace(":", ".") if len(parts) == 3 else parts[-1]


def _day(t: float | int | None) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d") if t else "unknown date"


def _tag_pool(items: list[dict], prefix: str, quota: int) -> list[dict]:
    """Gắn mã D1.., H1.., I1.. theo vị trí trong pool; quota phần tử đầu là phần đưa cho LLM."""
    return [{**it, "tag": f"{prefix}{k}", "pos": k, "in_context": k <= quota}
            for k, it in enumerate(items, 1)]


def retrieve_kp(engine, prompt: str, t_query: float, timing: dict) -> dict:
    """
    Truy hồi K(p) cho prompt. Tất định với cùng index, cùng prompt và cùng t_query.

    Args:
        engine:  pipeline.evaluator.Engine (ri, locus, msg, issue, units_by_sha, reports_by_n).
        t_query: thời điểm hỏi (giây UNIX), dùng cho thành phần Fix của Locus.
        timing:  dict ghi thời gian từng bước (ms).
    """
    ri = engine.ri

    def _clock(name, fn):
        t0 = time.perf_counter()
        out = fn()
        timing[name] = round((time.perf_counter() - t0) * 1000, 1)
        return out

    ast = _clock("ast_ms", lambda: ri.ast_rank(prompt))
    ast_ids = [x["id"] for x in ast]
    loc = _clock("locus_ms", lambda: engine.locus.rank(prompt, t_query) if engine.locus
                 else {"items": [], "alpha": 0.0, "ce_terms": []})
    mr = _clock("hist_msg_ms", lambda: engine.msg.rank(prompt, ast_ids) if engine.msg
                else {"items": [], "pool": []})
    hist_items = loc["items"] if config.HIST_RANK_SOURCE == "locus" else mr["items"]
    fused = _clock("fuse_ms", lambda: rrf_fuse(ast_ids, {"HIST": [x["id"] for x in hist_items]}))
    ir = _clock("issue_ms", lambda: engine.issue.rank(prompt) if engine.issue else {"items": [], "pool": []})
    dp = _clock("doc_ms", lambda: ri.doc_pool(prompt))
    ent = _clock("entities_ms", lambda: ri.find_entities(prompt))

    t0 = time.perf_counter()
    ast_by = {x["id"]: x for x in ast}
    ast_pos = {x: i for i, x in enumerate(ast_ids, 1)}
    hist_score = {x["id"]: x["score"] for x in hist_items}

    code = []
    for k, f in enumerate(fused[:config.CODE_N], 1):
        a = ast_by.get(f["id"], {})
        nb = ri.neighbors(f["id"], ast_pos)
        code.append({
            "tag": f"C{k}", **ri.brief(f["id"]), "source": ri.by_id[f["id"]].get("source") or "",
            "fused_score": f["score"], "ast_rank": f["ranks"]["AST"], "hist_rank": f["ranks"].get("HIST"),
            "hist_score": hist_score.get(f["id"]), "bm25_rank": a.get("bm25_rank"),
            "bm25_score": a.get("bm25_score"), "vec_rank": a.get("vec_rank"), "cos": a.get("cos"),
            **nb,
        })
    code_tag = {c["id"]: c["tag"] for c in code}

    files = [{**f, "best_tag": code_tag.get(f["best_id"])} for f in file_rank(fused, ri.file_of, config.FILE_N)]

    ents, with_src = [], 0
    for k, e in enumerate(ent["items"], 1):
        show = e["label"] in _FC and e["id"] not in code_tag and with_src < config.ENTITY_SOURCE_N
        with_src += show
        ents.append({**e, "tag": f"E{k}", "in_code": code_tag.get(e["id"]), "with_source": show,
                     "source": (ri.by_id[e["id"]].get("source") or "") if show else ""})

    doc = _tag_pool(dp["items"], "D", config.DOC_QUOTA)
    hist = _tag_pool([{**c, "msg": engine.units_by_sha.get(c["h"], {}).get("msg", ""),
                       "linked": [{"n": n, "pr": engine.reports_by_n[n]["pr"],
                                   "title": engine.reports_by_n[n]["title"],
                                   "body": engine.reports_by_n[n]["body"]}
                                  for n in c["links"] if n in engine.reports_by_n]}
                      for c in mr["pool"]], "H", config.HIST_QUOTA)
    issue = _tag_pool(ir["pool"], "I", config.ISSUE_QUOTA)

    # Liên kết bằng chứng ↔ phần Code, theo cấu trúc graph (đích Documents, touch, Fix(b′))
    targets = {"doc": ("targets", doc), "hist": ("touch", hist), "issue": ("fix", issue)}
    for c in code:
        for sec, (field, items) in targets.items():
            c[f"linked_{sec}"] = [it["tag"] for it in items if it["in_context"] and c["id"] in it.get(field, [])]
    for sec, (field, items) in targets.items():
        for it in items:
            it["linked_code"] = [code_tag[x] for x in it.get(field, []) if x in code_tag]

    def _ratio(items):
        shown = [it for it in items if it["in_context"]]
        return round(sum(bool(it["linked_code"]) for it in shown) / len(shown), 4) if shown else None

    hist_reports = {n for it in hist if it["in_context"] for n in it["links"]}
    metrics = {
        "ast_top10_overlap": len(set(ast_ids[:10]) & {f["id"] for f in fused[:10]}),
        "evidence_linked_ratio": {"doc": _ratio(doc), "hist": _ratio(hist), "issue": _ratio(issue)},
        "hist_issue_overlap": len(hist_reports & {it["n"] for it in issue if it["in_context"]}),
        "empty_reason": _empty_reasons(engine, ent, doc, dp["pool"], hist, issue),
    }
    timing["assemble_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return {"ast": ast, "hist_list": hist_items, "hist_list_source": config.HIST_RANK_SOURCE,
            "fused": fused, "locus": {"alpha": loc["alpha"], "ce_terms": loc["ce_terms"]},
            "entities": {"candidates": ent["candidates"], "total": ent["total"], "items": ents},
            "code": code, "files": files, "doc_pool_name": dp["pool"],
            "doc": doc, "hist": hist, "issue": issue, "metrics": metrics}


def _empty_reasons(engine, ent, doc, doc_pool_name, hist, issue) -> dict:
    """Lý do một phần của K(p) rỗng (None khi phần đó có item)."""
    ri = engine.ri
    return {
        "entities": None if ent["items"] else
        ("no identifier extracted from the prompt" if not ent["candidates"]
         else "no extracted identifier matches a node name or file"),
        "doc": None if doc else ("the repository has no documentation chunks" if not ri.chunks
                                 else "no documentation chunk scored for the prompt"),
        "hist": None if hist else ("history layer not built" if engine.msg is None
                                   else "no commit touches a function/class of the graph" if not engine.msg.units
                                   else "no commit text matches and no commit touches the AST list"),
        "issue": None if issue else ("issue layer not built (no GitHub remote or fetch failed)" if engine.issue is None
                                     else "no closed report is linked to a commit" if not (engine.issue.nfix > 0).any()
                                     else "no linked report shares terms with the prompt"),
    }


# ── Định dạng cho LLM ────────────────────────────────────────────────────────
def _loc(it: dict) -> str:
    return f"{it.get('file')}:{it.get('start_line')}"


def _neighbor_line(title: str, items: list[dict], total: int) -> str:
    if not items:
        return f"{title}: none found in the call graph"
    names = ", ".join(f"`{qualified(x['id'])}` ({_loc(x)})" for x in items)
    more = f" (+{total - len(items)} more)" if total > len(items) else ""
    return f"{title}: {names}{more}"


def format_code(c: dict) -> str:
    return (f"[{c['tag']}] {c['label']} `{qualified(c['id'])}` in `{c['file']}:{c['start_line']}-{c['end_line']}`\n"
            f"{_neighbor_line('Called by', c['callers'], c['n_callers'])}\n"
            f"{_neighbor_line('Calls', c['callees'], c['n_callees'])}\n"
            f"```python\n{c['source']}\n```")


def format_entity(e: dict) -> str:
    where = f"`{e['file']}:{e['start_line']}`" if e.get("start_line") else f"`{e['file']}`"
    head = f"[{e['tag']}] {e['label']} `{qualified(e['id'])}` in {where} (matched `{e['matched']}`)"
    if e["in_code"]:
        return f"{head}, same element as [{e['in_code']}]"
    if e["with_source"]:
        return f"{head}\n```python\n{e['source']}\n```"
    return head


def format_doc(d: dict) -> str:
    """Định dạng v5 của phần tử DOC."""
    return f"[{d['tag']}] Documentation passage\nFile: {d['file']}\nSection: {d['heading']}\nText:\n{d['text']}"


def format_hist(h: dict) -> str:
    """Định dạng v5 của phần tử HIST: commit, message đầy đủ, ticket/PR liên kết theo số tăng dần."""
    out = f"[{h['tag']}] Past commit {h['h'][:8]}, committed {_day(h['t'])}\nCommit message:\n{h['msg']}"
    for r in sorted(h["linked"], key=lambda r: r["n"]):
        out += f"\nLinked ticket or pull request #{r['n']}: {r['title']}\n{r['body']}"
    return out


def format_issue(i: dict) -> str:
    """Định dạng v5 của phần tử ISSUE."""
    return f"[{i['tag']}] Past bug report #{i['n']}, created {_day(i['created'])}: {i['title']}\n{i['body']}"


def format_sections(kp: dict) -> dict[str, str]:
    """Văn bản của từng phần K(p) đưa cho LLM. Phần rỗng → "(none)"."""
    def _join(parts):
        return "\n\n".join(parts) if parts else "(none)"
    return {
        "entities": _join([format_entity(e) for e in kp["entities"]["items"]]),
        "code": _join([format_code(c) for c in kp["code"]]),
        "files": _join([f"{i}. `{f['file']}` (best element [{f['best_tag']}])" if f["best_tag"]
                        else f"{i}. `{f['file']}`" for i, f in enumerate(kp["files"], 1)]),
        "doc": _join([format_doc(d) for d in kp["doc"] if d["in_context"]]),
        "hist": _join([format_hist(h) for h in kp["hist"] if h["in_context"]]),
        "issue": _join([format_issue(i) for i in kp["issue"] if i["in_context"]]),
    }
