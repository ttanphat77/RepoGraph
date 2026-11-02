# =============================================================================
# pipeline/run_record.py — Bản ghi một lần chạy (theo dõi và nghiên cứu)
#
# Mỗi lần hỏi có một run_id và một thư mục {INDEX_ROOT}/{repo}/runs/<run_id>/:
#   record.json  bản ghi đầy đủ, 8 khối: run, index, config, retrieval, llm,
#                citations, timing, warnings
#   prompt.txt   nguyên văn system instruction và nội dung đã gửi cho LLM
#   answer.md    nguyên văn câu trả lời
# và một dòng tóm tắt trong {INDEX_ROOT}/{repo}/runs/index.jsonl.
#
# Trích dẫn (parse_citations): mã item [C2], [D1, H3] và `symbol` in `path:line`.
# Trích dẫn không hợp lệ: mã không có trong phần K(p) đã gửi cho LLM, hoặc path:line
# không nằm trong một item [C]/[E] có vị trí.
# =============================================================================

from __future__ import annotations

import hashlib
import json
import re
import secrets
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import config

_ITEM_GROUP_RE = re.compile(r"\[([ECDHI]\d+(?:\s*[,;]\s*[ECDHI]\d+)*)\]")
_ITEM_RE = re.compile(r"[ECDHI]\d+")
_SYMBOL_RE = re.compile(r"`([^`\n]+)`\s+in\s+`([^`\n]+?):(\d+)(?:-\d+)?`")
SECTIONS = {"E": "entities", "C": "code", "D": "doc", "H": "hist", "I": "issue"}

APP_ROOT = Path(__file__).resolve().parent.parent


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)


def app_commit() -> dict:
    """Commit của code app và cờ có thay đổi chưa commit."""
    def _git(*a):
        return subprocess.run(["git", "-C", str(APP_ROOT), *a], capture_output=True, text=True).stdout.strip()
    return {"sha": _git("rev-parse", "HEAD") or None, "dirty": bool(_git("status", "--porcelain", "--", "*.py"))}


def sha1_text(*texts: str) -> str:
    return hashlib.sha1("\n\x00\n".join(texts).encode("utf-8")).hexdigest()


def config_block(prompt_template_sha: str) -> dict:
    """Tham số của lần chạy. Hai lần chạy cùng config_sha thì so sánh được với nhau."""
    block = {
        "rrf_k": config.RRF_K, "list_depth": config.AST_DEPTH,
        "code_n": config.CODE_N, "file_n": config.FILE_N, "entity_limit": config.ENTITY_LIMIT,
        "entity_source_n": config.ENTITY_SOURCE_N, "neighbor_limit": config.NEIGHBOR_LIMIT,
        "quota": {"doc": config.DOC_QUOTA, "hist": config.HIST_QUOTA, "issue": config.ISSUE_QUOTA},
        "evid_pool_n": config.EVID_POOL_N, "hist_rank_source": config.HIST_RANK_SOURCE,
        "locus_lambda": config.LOCUS_LAMBDA, "locus_beta1": config.LOCUS_BETA1,
        "hist_years": config.HIST_YEARS, "hist_max_touch": config.HIST_MAX_TOUCH,
        "issue_link_types": ["fixed"], "embed_model": config.EMBED_MODEL_ID,
        "llm_model": config.GEMINI_MODEL, "llm_thinking": "model default",
        "prompt_template_sha": prompt_template_sha,
    }
    block["config_sha"] = sha1_text(json.dumps(block, sort_keys=True))[:12]
    return block


def parse_citations(answer: str, kp: dict | None) -> dict:
    """
    Mã item và symbol được trích trong câu trả lời, đối chiếu với K(p).

    Returns:
        {"cited_items", "cited_symbols", "invalid_items", "invalid_symbols",
         "cited_per_section", "uncited_per_section"}
    """
    shown: dict[str, str] = {}          # mã item → phần, chỉ phần tử đã gửi cho LLM
    spans: list[tuple[str, int, int]] = []
    if kp:
        for e in kp["entities"]["items"]:
            shown[e["tag"]] = "entities"
            if e.get("start_line"):
                spans.append((e["file"], e["start_line"], e["end_line"] or e["start_line"]))
        for c in kp["code"]:
            shown[c["tag"]] = "code"
            spans.append((c["file"], c["start_line"], c["end_line"]))
        for sec in ("doc", "hist", "issue"):
            for it in kp[sec]:
                if it["in_context"]:
                    shown[it["tag"]] = sec

    items = []
    for m in _ITEM_GROUP_RE.finditer(answer):
        items += _ITEM_RE.findall(m.group(1))
    items = list(dict.fromkeys(items))
    symbols = [{"symbol": s, "path": p, "line": int(l)} for s, p, l in _SYMBOL_RE.findall(answer)]
    for s in symbols:
        s["valid"] = any(f == s["path"] and a <= s["line"] <= b for f, a, b in spans)

    per, unc = {}, {}
    for sec in ("entities", "code", "doc", "hist", "issue"):
        tags = [t for t, s in shown.items() if s == sec]
        per[sec] = sum(t in items for t in tags)
        unc[sec] = len(tags) - per[sec]
    return {"cited_items": items, "cited_symbols": symbols,
            "invalid_items": [t for t in items if t not in shown],
            "invalid_symbols": [s for s in symbols if not s["valid"]],
            "cited_per_section": per, "uncited_per_section": unc}


def retrieval_block(kp: dict, cited: set[str]) -> dict:
    """Khối retrieval của bản ghi: danh sách đầy đủ, item của từng phần (không kèm toàn văn)."""
    def _drop(d, *keys):
        return {k: v for k, v in d.items() if k not in keys}
    return {
        "ast": kp["ast"],
        "hist_list": {"source": kp["hist_list_source"], "items": kp["hist_list"]},
        "fused": [{"id": f["id"], "score": f["score"], "ranks": f["ranks"]} for f in kp["fused"]],
        "locus": kp["locus"],
        "entities": {**_drop(kp["entities"], "items"),
                     "items": [{**_drop(e, "source"), "chars": len(e["source"]), "cited": e["tag"] in cited}
                               for e in kp["entities"]["items"]]},
        "code": [{**_drop(c, "source"), "chars": len(c["source"]), "cited": c["tag"] in cited} for c in kp["code"]],
        "files": kp["files"],
        "doc": {"pool": kp["doc_pool_name"],
                "items": [{**_drop(d, "text"), "chars": len(d["text"]), "cited": d["tag"] in cited}
                          for d in kp["doc"]]},
        "hist": [{**_drop(h, "msg", "linked"), "chars": len(h["msg"]) + sum(len(r["title"]) + len(r["body"])
                                                                            for r in h["linked"]),
                  "cited": h["tag"] in cited} for h in kp["hist"]],
        "issue": [{**_drop(i, "body"), "chars": len(i["title"]) + len(i["body"]), "cited": i["tag"] in cited}
                  for i in kp["issue"]],
        **kp["metrics"],
    }


def summary_line(rec: dict) -> dict:
    """Dòng tóm tắt cho runs/index.jsonl."""
    r, llm, cit = rec.get("retrieval") or {}, rec.get("llm") or {}, rec.get("citations") or {}

    def _n(sec):
        v = r.get(sec)
        if isinstance(v, dict):
            v = v.get("items", [])
        return sum(1 for x in v or [] if x.get("in_context", True))
    return {
        "run_id": rec["run"]["run_id"], "started_at": rec["run"]["started_at"],
        "prompt": rec["run"]["prompt"][:200], "head_sha": (rec.get("index") or {}).get("head_sha"),
        "config_sha": (rec.get("config") or {}).get("config_sha"),
        "items": {s: _n(s) for s in ("entities", "code", "doc", "hist", "issue")},
        "tokens": {"in": llm.get("prompt_token_count"), "out": llm.get("candidates_token_count"),
                   "thinking": llm.get("thoughts_token_count")},
        "total_ms": (rec.get("timing") or {}).get("total_ms"),
        "cited": len(cit.get("cited_items", [])),
        "invalid": len(cit.get("invalid_items", [])) + len(cit.get("invalid_symbols", [])),
        "finish_reason": llm.get("finish_reason"), "warnings": len(rec.get("warnings") or []),
    }


def write_run(index_dir: str | Path, rec: dict, system: str, user: str, answer: str) -> Path:
    """Ghi record.json, prompt.txt, answer.md và một dòng vào runs/index.jsonl. Trả thư mục của lần chạy."""
    runs = Path(index_dir) / config.RUNS_DIRNAME
    d = runs / rec["run"]["run_id"]
    d.mkdir(parents=True, exist_ok=True)
    (d / "record.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (d / "prompt.txt").write_text(f"=== SYSTEM ===\n{system}\n\n=== USER ===\n{user}", encoding="utf-8")
    (d / "answer.md").write_text(answer or "", encoding="utf-8")
    with open(runs / "index.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(summary_line(rec), ensure_ascii=False) + "\n")
    return d


def latest_index_dir(root: str | Path = config.INDEX_ROOT) -> Path | None:
    """Thư mục index có lần build gần nhất (theo built_at trong index_state.json)."""
    best = None
    for p in Path(root).glob("*/index_state.json"):
        try:
            t = json.loads(p.read_text(encoding="utf-8")).get("built_at", "")
        except Exception:
            continue
        if best is None or t > best[0]:
            best = (t, p.parent)
    return best[1] if best else None
