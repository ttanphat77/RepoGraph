# =============================================================================
# app/components/combined_view.py — Graph + Query gộp chung một màn hình
#
# Layout: graph NeoVis (trên) | query (dưới)
#
# Query là một lần prompting trên K(p) (pipeline.evaluator.run_prompt): truy hồi
# đa nguồn (code, doc, commit, báo cáo cũ), gọi LLM một lần, ghi bản ghi lần chạy.
# Node của K(p) được tô trên graph qua session_state (query_seed_ids = phần Code và
# thực thể; query_subgraph_ids = thêm caller/callee, chunk doc, commit, issue).
# =============================================================================

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from app.neo4j_client import client
from app.components.graph_view import _render_neovis
from app.components.query_view import (
    _load_current_instance,
    _file_status_icon,
)
from pipeline.context import qualified
from pipeline.evaluator import run_prompt
from pipeline.generator import extract_files_from_answer


def render_combined_view() -> None:
    """
    Render màn hình gộp Graph + Query.

    Trên: NeoVis graph với highlight từ K(p) của lần hỏi gần nhất.
    Dưới: ô nhập prompt, nút chạy, câu trả lời, bảng K(p) và số liệu.
    """
    modules = client.get_modules()
    if not modules:
        st.warning("Không có dữ liệu trong Neo4j. Chạy build_graph.py trước.")
        return

    state    = _load_current_instance()
    gt_files = state.get("gt_files", [])
    problem  = state.get("problem_statement", "")
    instance = state.get("instance_id", "—")

    # ── Instance info ────────────────────────────────────────────────────────
    with st.expander(f"Instance: {instance}" + (f"  —  {len(gt_files)} GT files" if gt_files else ""), expanded=False):
        if gt_files:
            for f in gt_files:
                st.caption(f"🎯 `{f}`")
        else:
            st.caption("Không có GT files.")

    # ── Graph (full width, chiều cao cố định) ────────────────────────────────
    seed_ids = st.session_state.get("query_seed_ids", [])
    sub_ids  = st.session_state.get("query_subgraph_ids", [])
    cypher   = "MATCH (n)-[r]->(m) RETURN n, r, m"
    _render_neovis(cypher, query_seed_ids=seed_ids, query_sub_ids=sub_ids, height=700)

    st.divider()

    # ── Query UI (bên dưới graph) ─────────────────────────────────────────────
    st.subheader("Prompt")

    col_input, col_controls = st.columns([3, 1], gap="medium")
    with col_input:
        issue_text = st.text_area(
            "Issue / question",
            value=problem,
            height=120,
            placeholder="Dán issue hoặc câu hỏi về repo vào đây...",
            label_visibility="collapsed",
        )
    with col_controls:
        st.caption("Một lần truy hồi K(p) + một lần gọi LLM")
        do_query = st.button("🔍  Retrieve + Generate", use_container_width=True)

    _render_query_results(do_query=do_query, issue_text=issue_text, gt_files=gt_files)


# ── Query logic ──────────────────────────────────────────────────────────────

def _render_query_results(do_query: bool, issue_text: str, gt_files: list[str]) -> None:
    """Chạy run_prompt và render kết quả. Không bấm nút → hiện lại kết quả gần nhất."""
    if not do_query:
        if st.session_state.get("kp_result"):
            _render_result(st.session_state["kp_result"], gt_files)
        else:
            st.info("Nhấn **Retrieve + Generate** để bắt đầu.")
        return

    if not issue_text.strip():
        st.warning("Vui lòng nhập prompt.")
        return

    with st.spinner("Đang truy hồi K(p) và gọi LLM..."):
        rec, run_dir = run_prompt(issue_text)
    answer = (run_dir / "answer.md").read_text(encoding="utf-8")

    r = rec.get("retrieval") or {}
    code = r.get("code", [])
    seed = [c["id"] for c in code] + [e["id"] for e in r.get("entities", {}).get("items", [])]
    sub = (seed + [x["id"] for c in code for x in c["callers"] + c["callees"]]
           + [d["id"] for d in (r.get("doc") or {}).get("items", []) if d["in_context"]]
           + [f"commit:{h['h']}" for h in r.get("hist", []) if h["in_context"]]
           + [f"issue:{i['n']}" for i in r.get("issue", []) if i["in_context"]])
    st.session_state["query_seed_ids"]     = list(dict.fromkeys(seed))
    st.session_state["query_subgraph_ids"] = list(dict.fromkeys(sub))

    result = {"rec": rec, "run_dir": str(run_dir), "answer": answer}
    st.session_state["kp_result"] = result
    _render_result(result, gt_files)


def _rows(items: list[dict], cols: dict) -> list[dict]:
    """Bảng của một phần K(p): chỉ phần tử đã gửi cho LLM; cols = {tên cột: hàm lấy giá trị}."""
    return [{name: fn(it) for name, fn in cols.items()} for it in items if it.get("in_context", True)]


def _render_result(result: dict, gt_files: list[str]) -> None:
    """Số liệu, câu trả lời, cảnh báo, bảng K(p), file dự đoán (P/R/F1 khi có GT) và bản ghi."""
    rec, answer = result["rec"], result["answer"]
    r, llm = rec.get("retrieval") or {}, rec.get("llm") or {}
    cit = rec.get("citations") or {}

    m = st.columns(5)
    m[0].metric("Tokens in", f"{llm.get('prompt_token_count') or 0:,}")
    m[1].metric("Tokens out", f"{llm.get('candidates_token_count') or 0:,}")
    m[2].metric("Thinking", f"{llm.get('thoughts_token_count') or 0:,}")
    m[3].metric("Time", f"{(rec['timing'].get('total_ms') or 0) / 1000:.1f} s")
    m[4].metric("Cited", f"{sum((cit.get('cited_per_section') or {}).values())}"
                         f"/{sum((cit.get('cited_per_section') or {}).values()) + sum((cit.get('uncited_per_section') or {}).values())}")

    st.markdown("**LLM Answer**")
    st.markdown(answer or "_(no answer)_")
    for w in rec.get("warnings", []):
        st.warning(w)

    yes = lambda it: "✓" if it.get("cited") else ""
    sections = [
        ("[E] Entities named in the prompt", r.get("entities", {}).get("items", []),
         {"id": lambda e: e["tag"], "element": lambda e: qualified(e["id"]),
          "location": lambda e: f"{e['file']}:{e.get('start_line') or ''}", "match": lambda e: e["matched"],
          "cited": yes}),
        ("[C] Code", r.get("code", []),
         {"id": lambda c: c["tag"], "element": lambda c: qualified(c["id"]),
          "location": lambda c: f"{c['file']}:{c['start_line']}", "fused": lambda c: round(c["fused_score"], 4),
          "AST": lambda c: c["ast_rank"], "HIST": lambda c: c["hist_rank"],
          "callers/callees": lambda c: f"{c['n_callers']}/{c['n_callees']}", "cited": yes}),
        (f"[D] Documentation ({(r.get('doc') or {}).get('pool')})", (r.get("doc") or {}).get("items", []),
         {"id": lambda d: d["tag"], "file": lambda d: d["file"], "section": lambda d: d["heading"],
          "rrf": lambda d: round(d["score"], 4), "cos": lambda d: round(d["cos"], 3),
          "links code": lambda d: ",".join(d["linked_code"]), "cited": yes}),
        ("[H] Past commits", r.get("hist", []),
         {"id": lambda h: h["tag"], "commit": lambda h: h["h"][:8], "s": lambda h: round(h["s"], 4),
          "cos": lambda h: round(h["cos"], 3), "AST rank": lambda h: h["ast_r"],
          "linked reports": lambda h: ",".join(f"#{n}" for n in h["links"]), "cited": yes}),
        ("[I] Past bug reports", r.get("issue", []),
         {"id": lambda i: i["tag"], "report": lambda i: f"#{i['n']}", "title": lambda i: i["title"],
          "cos": lambda i: round(i["cos"], 3), "fixed elements": lambda i: len(i["fix"]), "cited": yes}),
    ]
    for title, items, cols in sections:
        rows = _rows(items, cols)
        with st.expander(f"{title} — {len(rows)} items", expanded=title.startswith("[C]")):
            if rows:
                st.dataframe(rows, use_container_width=True, hide_index=True)
            else:
                st.caption("(none)")

    # ── Predicted Files (từ FILE: lines trong câu trả lời) ───────────────────
    st.markdown("**Predicted Files**")
    predicted_files = extract_files_from_answer(answer) if answer else []
    if not predicted_files:
        st.caption("Câu trả lời không có dòng FILE:.")
    else:
        lines = [f"{_file_status_icon(f, gt_files, predicted_files)}  `{f}`" for f in predicted_files]
        lines += [f"🎯  `{f}` *(GT — missed)*" for f in gt_files if f not in predicted_files]
        st.markdown("\n\n".join(lines))

    if gt_files and predicted_files:
        tp        = len(set(predicted_files) & set(gt_files))
        precision = tp / len(predicted_files)
        recall    = tp / len(gt_files)
        f1        = (2 * precision * recall / (precision + recall)
                     if (precision + recall) > 0 else 0)
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Precision", f"{precision:.0%}")
        mc2.metric("Recall",    f"{recall:.0%}")
        mc3.metric("F1",        f"{f1:.0%}")

    st.caption(f"Record: `{Path(result['run_dir'])}`")
