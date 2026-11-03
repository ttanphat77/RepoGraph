# tui/kp_render.py - Bảng item RAG của K(p) và dòng số liệu, dùng chung cho TUI và scripts/ask.py
#
# Đầu vào là khối "retrieval" của bản ghi lần chạy (pipeline.run_record.retrieval_block),
# nên cùng một hàm hiển thị được kết quả của run_prompt và của retrieve_kp.

from pathlib import Path

from rich.table import Table

from pipeline.context import qualified


def _check(it: dict) -> str:
    return "✓" if it.get("cited") else ""


def _table(title: str, *columns: str) -> Table:
    t = Table(title=title, title_justify="left", title_style="bold", box=None, header_style="dim",
              pad_edge=False)
    for c in columns:
        t.add_column(c)
    return t


def kp_tables(r: dict) -> list[Table]:
    """Một bảng cho mỗi phần của K(p): [E], [C], [D], [H], [I]. Chỉ phần tử đã gửi cho LLM."""
    out = []
    t = _table("[E] Entities named in the prompt", "id", "element", "location", "match", "cited")
    for e in r.get("entities", {}).get("items", []):
        t.add_row(e["tag"], qualified(e["id"]), f"{e['file']}:{e.get('start_line') or ''}",
                  f"{e['match']} `{e['matched']}`" + (f" = [{e['in_code']}]" if e.get("in_code") else ""), _check(e))
    out.append(t)

    t = _table("[C] Code", "id", "element", "location", "fused", "AST", "HIST", "callers/callees", "cited")
    for c in r.get("code", []):
        t.add_row(c["tag"], qualified(c["id"]), f"{c['file']}:{c['start_line']}", f"{c['fused_score']:.4f}",
                  str(c["ast_rank"] or "-"), str(c["hist_rank"] or "-"), f"{c['n_callers']}/{c['n_callees']}",
                  _check(c))
    out.append(t)

    t = _table(f"[D] Documentation ({(r.get('doc') or {}).get('pool')})",
               "id", "file", "section", "rrf", "bm25", "cos", "links code", "cited")
    for d in (r.get("doc") or {}).get("items", []):
        if d["in_context"]:
            t.add_row(d["tag"], d["file"], d["heading"][:40], f"{d['score']:.4f}", f"{d['bm25']:.1f}",
                      f"{d['cos']:.3f}", ",".join(d["linked_code"]), _check(d))
    out.append(t)

    t = _table("[H] Past commits", "id", "commit", "s", "cos", "AST rank", "linked reports", "cited")
    for h in r.get("hist", []):
        if h["in_context"]:
            t.add_row(h["tag"], h["h"][:8], f"{h['s']:.4f}", f"{h['cos']:.3f}", str(h["ast_r"] or "-"),
                      ",".join(f"#{n}" for n in h["links"]), _check(h))
    out.append(t)

    t = _table("[I] Past bug reports", "id", "report", "title", "cos", "fixed elements", "cited")
    for i in r.get("issue", []):
        if i["in_context"]:
            t.add_row(i["tag"], f"#{i['n']}", i["title"][:50], f"{i['cos']:.3f}", str(len(i["fix"])), _check(i))
    out.append(t)
    return out


def metrics_line(rec: dict, run_dir: Path | None = None) -> str:
    """Token vào theo phần, token ra, thinking, thời gian, số item được trích, trích dẫn sai, bản ghi."""
    llm, cit, tm = rec.get("llm") or {}, rec.get("citations") or {}, rec.get("timing") or {}
    st = llm.get("section_tokens") or {}
    parts = " · ".join(f"{k} {st[k]:,}" for k in ("code", "entities", "doc", "hist", "issue") if k in st)
    cited = sum((cit.get("cited_per_section") or {}).values())
    n_items = cited + sum((cit.get("uncited_per_section") or {}).values())
    inval = len(cit.get("invalid_items", [])) + len(cit.get("invalid_symbols", []))
    line = (f"tokens in {llm.get('prompt_token_count') or 0:,} ({parts}) · out {llm.get('candidates_token_count') or 0:,}"
            f" · thinking {llm.get('thoughts_token_count') or 0:,} · {(tm.get('total_ms') or 0) / 1000:.1f} s"
            f" · cited {cited}/{n_items}" + (f" · invalid citations {inval}" if inval else ""))
    return line + (f"\nrecord: {run_dir}" if run_dir else "")
