# =============================================================================
# app/components/combined_view.py — Graph + Query gộp chung một màn hình
#
# Layout: cột trái (query controls + results) | cột phải (NeoVis graph)
#
# Cột trái là Streamlit-native (text_area, button, metrics, markdown).
# Cột phải là iframe NeoVis — render với highlight IDs từ session_state.
# Sau mỗi lần Retrieve, Streamlit rerender toàn bộ trang → NeoVis tự
# cập nhật highlight mà không cần round-trip thêm.
# =============================================================================

from __future__ import annotations

import json
import os
import sys

import streamlit as st

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from app.neo4j_client import client
from app.components.graph_view import _render_neovis
from app.components.query_view import (
    _load_current_instance,
    _file_status_icon,
)
from pipeline.retriever import GraphRetriever
from pipeline.generator import generate_stream, _extract_files_from_answer


def render_combined_view() -> None:
    """
    Render màn hình gộp Graph + Query.

    Cột trái (~38%): issue input, nút Retrieve, kết quả.
    Cột phải (~62%): NeoVis graph với highlight từ kết quả query.
    """
    modules = client.get_modules()
    if not modules:
        st.warning("Không có dữ liệu trong Neo4j. Chạy build_graph.py trước.")
        return

    state    = _load_current_instance()
    gt_files = state.get("gt_files", [])
    problem  = state.get("problem_statement", "")
    instance = state.get("instance_id", "—")

    with st.sidebar:
        st.divider()
        st.caption(f"**Instance:** {instance}")
        if gt_files:
            st.caption(f"**GT files ({len(gt_files)}):**")
            for f in gt_files:
                st.caption(f"  🎯 `{f}`")

    # ── Graph (full width, chiều cao cố định) ────────────────────────────────
    seed_ids = st.session_state.get("query_seed_ids", [])
    sub_ids  = st.session_state.get("query_subgraph_ids", [])
    cypher   = "MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 2000"
    _render_neovis(cypher, query_seed_ids=seed_ids, query_sub_ids=sub_ids, height=520)

    st.divider()

    # ── Query UI (bên dưới graph) ─────────────────────────────────────────────
    st.subheader("Issue Query")

    col_input, col_controls = st.columns([3, 1], gap="medium")
    with col_input:
        issue_text = st.text_area(
            "Issue / Problem Statement",
            value=problem,
            height=120,
            placeholder="Dán nội dung issue vào đây...",
            label_visibility="collapsed",
        )
    with col_controls:
        depth   = st.selectbox("Depth BFS", [1, 2, 3], index=1)
        run_llm = st.checkbox("Gọi LLM", value=True)
        do_query = st.button("🔍  Retrieve", use_container_width=True)

    _render_query_results(
        do_query=do_query,
        issue_text=issue_text,
        depth=depth,
        run_llm=run_llm,
        gt_files=gt_files,
    )


# ── Query logic (tách để col_query gọn) ──────────────────────────────────────

def _render_query_results(
    do_query: bool,
    issue_text: str,
    depth: int,
    run_llm: bool,
    gt_files: list[str],
) -> None:
    """Thực hiện retrieval + generation và render kết quả vào cột trái."""

    if not do_query:
        if not st.session_state.get("query_seed_ids"):
            st.info("Nhấn **Retrieve + Generate** để bắt đầu.")
        else:
            # Đã có kết quả từ lần query trước — hiện lại từ session_state
            _render_cached_results(gt_files)
        return

    if not issue_text.strip():
        st.warning("Vui lòng nhập issue text.")
        return

    with st.spinner("Đang truy xuất Knowledge Graph..."):
        retriever = GraphRetriever()
        result    = retriever.retrieve(issue_text, depth=depth)
        retriever.close()

    candidates      = result["candidates"]
    seed_nodes      = result["seed_nodes"]
    subgraph        = result["subgraph"]
    context         = result["context"]
    candidate_files = result["candidate_files"]

    # Dùng custom string ID (n.identity) thay vì Neo4j internal integer (neo_id)
    # để tránh type mismatch giữa Python int và vis-network node ID
    st.session_state["query_seed_ids"]     = [n["identity"] for n in seed_nodes if n.get("identity")]
    st.session_state["query_subgraph_ids"] = [n["identity"] for n in subgraph["nodes"] if n.get("identity")]

    # ── Retrieval metrics ─────────────────────────────────────────────────────
    m1, m2, m3 = st.columns(3)
    m1.metric("Identifiers", len(candidates))
    m2.metric("Seed nodes",  len(seed_nodes))
    m3.metric("Subgraph",    len(subgraph["nodes"]))
    token_ph = st.empty()

    st.divider()

    # ── Predicted files placeholder + LLM stream ──────────────────────────────
    col_a, col_b = st.columns([1, 1], gap="large")

    with col_a:
        st.markdown("**Predicted Files**")
        files_ph   = st.empty()
        metrics_ph = st.empty()

    with col_b:
        st.markdown("**LLM Answer**")
        meta = {}
        if run_llm and context:
            full_answer = st.write_stream(
                generate_stream(issue_text, context, candidate_files, meta)
            )
        else:
            full_answer = ""
            st.info("LLM bị tắt hoặc không có context để gửi.")

    # ── Fill placeholders after stream ────────────────────────────────────────
    predicted_files = _extract_files_from_answer(full_answer) if full_answer else candidate_files
    llm_result = {
        "answer":          full_answer,
        "predicted_files": predicted_files,
        "finish_reason":   meta.get("finish_reason", ""),
        "input_tokens":    meta.get("input_tokens", 0),
        "output_tokens":   meta.get("output_tokens", 0),
    } if run_llm else None

    with files_ph.container():
        if not predicted_files:
            st.warning("Không tìm được file nào.")
        else:
            lines = []
            for f in predicted_files:
                icon = _file_status_icon(f, gt_files, predicted_files)
                lines.append(f"{icon}  `{f}`")
            for f in gt_files:
                if f not in predicted_files:
                    lines.append(f"🎯  `{f}` *(GT — missed)*")
            st.markdown("\n\n".join(lines))

    if gt_files and predicted_files:
        tp        = len(set(predicted_files) & set(gt_files))
        precision = tp / len(predicted_files) if predicted_files else 0
        recall    = tp / len(gt_files) if gt_files else 0
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) > 0 else 0)
        with metrics_ph.container():
            st.divider()
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Precision", f"{precision:.0%}")
            mc2.metric("Recall",    f"{recall:.0%}")
            mc3.metric("F1",        f"{f1:.0%}")

    if meta:
        with token_ph.container():
            t1, t2 = st.columns(2)
            t1.metric("Input tokens",  meta.get("input_tokens", 0))
            t2.metric("Output tokens", meta.get("output_tokens", 0))
            reason = meta.get("finish_reason", "")
            if reason and reason not in ("FinishReason.STOP", "STOP", "INTERRUPTED"):
                st.warning(f"⚠️ finish_reason: `{reason}`")

    # ── Cache for re-renders ───────────────────────────────────────────────────
    st.session_state["last_result"] = {
        "candidates":      candidates,
        "seed_nodes":      seed_nodes,
        "subgraph_size":   len(subgraph["nodes"]),
        "candidate_files": candidate_files,
        "predicted_files": predicted_files,
        "llm_result":      llm_result,
        "context":         context,
    }


def _render_cached_results(gt_files: list[str]) -> None:
    """Render lại kết quả đã cache trong session_state (không re-query)."""
    r = st.session_state.get("last_result")
    if not r:
        return
    _render_result_body(
        candidates      = r["candidates"],
        seed_nodes      = r["seed_nodes"],
        subgraph_size   = r["subgraph_size"],
        predicted_files = r["predicted_files"],
        gt_files        = gt_files,
        llm_result      = r["llm_result"],
        context         = r["context"],
    )


def _render_result_body(
    candidates: list,
    seed_nodes: list,
    subgraph_size: int,
    predicted_files: list[str],
    gt_files: list[str],
    llm_result: dict | None,
    context: str,
) -> None:
    """Render metrics, predicted files, LLM answer, debug expanders."""

    # Metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("Identifiers", len(candidates))
    m2.metric("Seed nodes",  len(seed_nodes))
    m3.metric("Subgraph",    subgraph_size)

    if llm_result:
        t1, t2 = st.columns(2)
        t1.metric("Input tokens",  llm_result["input_tokens"])
        t2.metric("Output tokens", llm_result["output_tokens"])
        reason = llm_result.get("finish_reason", "")
        if reason and reason not in ("FinishReason.STOP", "STOP", "INTERRUPTED"):
            st.warning(f"⚠️ finish_reason: `{reason}`")

    st.divider()

    # Predicted files
    st.markdown("**Predicted Files**")
    if not predicted_files:
        st.warning("Không tìm được file nào.")
    else:
        lines = []
        for f in predicted_files:
            icon = _file_status_icon(f, gt_files, predicted_files)
            lines.append(f"{icon}  `{f}`")
        for f in gt_files:
            if f not in predicted_files:
                lines.append(f"🎯  `{f}` *(GT — missed)*")
        st.markdown("\n\n".join(lines))

    if gt_files and predicted_files:
        tp        = len(set(predicted_files) & set(gt_files))
        precision = tp / len(predicted_files) if predicted_files else 0
        recall    = tp / len(gt_files) if gt_files else 0
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) > 0 else 0)
        st.divider()
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Precision", f"{precision:.0%}")
        mc2.metric("Recall",    f"{recall:.0%}")
        mc3.metric("F1",        f"{f1:.0%}")

    # LLM answer
    if llm_result:
        st.divider()
        st.markdown("**LLM Answer**")
        st.markdown(llm_result["answer"])
    else:
        st.info("LLM bị tắt hoặc không có context để gửi.")

    # Debug expanders
    with st.expander(f"Identifiers ({len(candidates)})"):
        st.write(candidates)

    with st.expander(f"Seed nodes ({len(seed_nodes)})"):
        for n in seed_nodes:
            st.markdown(
                f"**[{n['label']}]** `{n['name']}` — `{n['file']}:{n['start_line']}`"
            )

    with st.expander(f"Context ({len(context)} chars)"):
        st.code(
            context[:6000] + ("..." if len(context) > 6000 else ""),
            language="markdown",
        )
