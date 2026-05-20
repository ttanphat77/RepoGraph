# =============================================================================
# app/components/query_view.py — Issue Query Tab (UI render only)
#
# Nguyên tắc: file này KHÔNG chứa business logic.
#
# Nhiệm vụ:
#   1. Đọc trạng thái instance (cache/current_instance.json)
#   2. Render input controls
#   3. Gọi pipeline/evaluator.py cho retrieval và metrics
#   4. Gọi pipeline/generator.py cho streaming LLM (UI concern — st.write_stream)
#   5. Render kết quả
#
# Tại sao streaming ở đây thay vì evaluator?
#   st.write_stream() là Streamlit-specific — không thể đặt trong pipeline/.
#   Nhưng generate_stream() (generator function) nằm trong pipeline/generator.py,
#   evaluator không cần biết về streaming.
# =============================================================================

from __future__ import annotations

import json
import os
import sys

import streamlit as st

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from pipeline.evaluator import run_retrieval_only, compute_metrics
from pipeline.generator import generate_stream, _extract_files_from_answer


def _load_current_instance() -> dict:
    """
    Đọc trạng thái instance hiện tại từ cache/current_instance.json.
    File này được ghi bởi build_graph.py sau mỗi lần build.
    """
    path = os.path.join(
        os.path.dirname(__file__), "..", "..", "cache", "current_instance.json"
    )
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _file_status_icon(file: str, gt_files: list[str], predicted: list[str]) -> str:
    """
    ✅ True Positive  — dự đoán đúng
    ❌ False Positive — dự đoán sai
    🎯 False Negative — bỏ sót
    """
    in_gt   = file in gt_files
    in_pred = file in predicted
    if in_gt and in_pred:      return "✅"
    if in_pred and not in_gt:  return "❌"
    if in_gt and not in_pred:  return "🎯"
    return "  "


def render_query_view():
    """Render tab Issue Query."""

    # ── Load instance state ───────────────────────────────────────────────────
    state    = _load_current_instance()
    gt_files = state.get("gt_files", [])
    problem  = state.get("problem_statement", "")
    instance = state.get("instance_id", "—")

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.divider()
        st.caption(f"**Instance:** {instance}")
        if gt_files:
            st.caption(f"**GT files ({len(gt_files)}):**")
            for f in gt_files:
                st.caption(f"  🎯 `{f}`")

    # ── Header ────────────────────────────────────────────────────────────────
    st.subheader("Issue Query")
    st.caption("Nhập mô tả issue → GraphRAG truy xuất code liên quan → LLM dự đoán file cần sửa.")

    # ── Input controls ────────────────────────────────────────────────────────
    col_left, col_right = st.columns([1, 1], gap="medium")

    with col_left:
        issue_text = st.text_area(
            "Issue / Problem Statement",
            value=problem,
            height=260,
            placeholder="Dán nội dung issue vào đây...",
        )
        c1, c2  = st.columns([1, 1])
        depth   = c1.selectbox("Depth BFS", [1, 2, 3], index=1)
        run_llm = c2.checkbox("Gọi LLM", value=True)
        do_query = st.button("🔍  Retrieve + Generate", use_container_width=True)

    if not do_query:
        with col_right:
            st.info("Nhấn **Retrieve + Generate** để bắt đầu.")
        return

    if not issue_text.strip():
        st.warning("Vui lòng nhập issue text.")
        return

    # ── Bước 3: Retrieval (via evaluator) ────────────────────────────────────
    with st.spinner("Đang truy xuất Knowledge Graph..."):
        retrieval = run_retrieval_only(issue_text, depth=depth)

    candidates      = retrieval["candidates"]
    seed_nodes      = retrieval["seed_nodes"]
    subgraph        = retrieval["subgraph"]
    context         = retrieval["context"]
    candidate_files = retrieval["candidate_files"]

    # Lưu node IDs để graph_view highlight khi user chuyển sang tab Graph
    st.session_state["query_seed_ids"]     = [n["neo_id"] for n in seed_nodes]
    st.session_state["query_subgraph_ids"] = [n["neo_id"] for n in subgraph["nodes"]]

    # ── Retrieval metrics ─────────────────────────────────────────────────────
    with col_right:
        m1, m2, m3 = st.columns(3)
        m1.metric("Identifiers", len(candidates))
        m2.metric("Seed nodes",  len(seed_nodes))
        m3.metric("Subgraph",    len(subgraph["nodes"]))
        token_ph = st.empty()  # điền sau khi stream xong

    st.divider()

    col_a, col_b = st.columns([1, 1], gap="large")

    with col_a:
        st.markdown("### Predicted Files")
        files_ph   = st.empty()  # điền sau khi stream xong
        metrics_ph = st.empty()  # điền sau khi stream xong

    # ── Bước 4: Streaming LLM (UI concern — st.write_stream) ─────────────────
    with col_b:
        st.markdown("### LLM Answer")
        meta = {}
        if run_llm and context:
            full_answer = st.write_stream(
                generate_stream(issue_text, context, candidate_files, meta)
            )
        else:
            full_answer = ""
            st.info("LLM bị tắt hoặc không có context để gửi.")

    # ── Post-stream: extract files + compute metrics (via evaluator) ──────────
    predicted_files = _extract_files_from_answer(full_answer) if full_answer else candidate_files
    metrics         = compute_metrics(predicted_files, gt_files)

    # ── Render: predicted files ───────────────────────────────────────────────
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

    # ── Render: P/R/F1 (từ evaluator.compute_metrics) ────────────────────────
    if gt_files and predicted_files:
        with metrics_ph.container():
            st.divider()
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Precision", f"{metrics['precision']:.0%}")
            mc2.metric("Recall",    f"{metrics['recall']:.0%}")
            mc3.metric("F1",        f"{metrics['f1']:.0%}")

    # ── Render: token usage ───────────────────────────────────────────────────
    if meta:
        with token_ph.container():
            t1, t2 = st.columns(2)
            t1.metric("Input tokens",  meta.get("input_tokens", 0))
            t2.metric("Output tokens", meta.get("output_tokens", 0))
            reason = meta.get("finish_reason", "")
            if reason and reason not in ("FinishReason.STOP", "STOP", "INTERRUPTED"):
                st.warning(f"⚠️ finish_reason: `{reason}`")

    # ── Debug expanders ───────────────────────────────────────────────────────
    with st.expander(f"Identifiers trích xuất ({len(candidates)})"):
        st.write(candidates)

    with st.expander(f"Seed nodes ({len(seed_nodes)})"):
        for n in seed_nodes:
            st.markdown(
                f"**[{n['label']}]** `{n['name']}` — `{n['file']}:{n['start_line']}`"
            )

    with st.expander(f"Context gửi LLM ({len(context)} chars)"):
        st.code(
            context[:6000] + ("..." if len(context) > 6000 else ""),
            language="markdown",
        )
