# =============================================================================
# app/components/query_view.py — Issue Query Tab (UI render only)
#
# Nguyên tắc: file này KHÔNG chứa business logic.
# Mọi RAG pipeline logic đều được delegate đến pipeline/evaluator.py.
#
# Nhiệm vụ duy nhất của file này:
#   1. Đọc trạng thái instance hiện tại (cache/current_instance.json)
#   2. Render input controls (text area, selectbox, checkbox, button)
#   3. Gọi run_rag_pipeline() với params từ UI
#   4. Render kết quả trả về
# =============================================================================

from __future__ import annotations

import json
import os
import sys

import streamlit as st

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from pipeline.evaluator import run_rag_pipeline


def _load_current_instance() -> dict:
    """
    Đọc trạng thái instance hiện tại từ cache/current_instance.json.

    File này được ghi bởi build_graph.py sau mỗi lần build.
    Trả về dict rỗng nếu chưa có file (lần đầu chạy).
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
    Icon thể hiện kết quả dự đoán cho một file:
      ✅ True Positive  — dự đoán đúng (cả trong GT lẫn predicted)
      ❌ False Positive — dự đoán sai (predicted nhưng không phải GT)
      🎯 False Negative — bỏ sót (GT nhưng không predicted)
    """
    in_gt   = file in gt_files
    in_pred = file in predicted
    if in_gt and in_pred:      return "✅"
    if in_pred and not in_gt:  return "❌"
    if in_gt and not in_pred:  return "🎯"
    return "  "


def render_query_view():
    """Render tab Issue Query — delegates toàn bộ logic đến pipeline/evaluator.py."""

    # ── Load instance state ───────────────────────────────────────────────────
    state    = _load_current_instance()
    gt_files = state.get("gt_files", [])
    problem  = state.get("problem_statement", "")
    instance = state.get("instance_id", "—")

    # ── Sidebar: instance info + GT files ────────────────────────────────────
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
        c1, c2   = st.columns([1, 1])
        depth    = c1.selectbox("Depth BFS", [1, 2, 3], index=1)
        run_llm  = c2.checkbox("Gọi LLM", value=True)
        do_query = st.button("🔍  Retrieve + Generate", use_container_width=True)

    if not do_query:
        with col_right:
            st.info("Nhấn **Retrieve + Generate** để bắt đầu.")
        return

    if not issue_text.strip():
        st.warning("Vui lòng nhập issue text.")
        return

    # ── Gọi pipeline (toàn bộ logic nằm ở pipeline/evaluator.py) ─────────────
    with st.spinner("Đang chạy RAG pipeline..."):
        result = run_rag_pipeline(
            issue_text=issue_text,
            depth=depth,
            run_llm=run_llm,
            gt_files=gt_files,
        )

    # ── Render: summary metrics ───────────────────────────────────────────────
    with col_right:
        m1, m2, m3 = st.columns(3)
        m1.metric("Identifiers", len(result["candidates"]))
        m2.metric("Seed nodes",  len(result["seed_nodes"]))
        m3.metric("Subgraph",    len(result["subgraph"]["nodes"]))

        if run_llm:
            t1, t2 = st.columns(2)
            t1.metric("Input tokens",  result["input_tokens"])
            t2.metric("Output tokens", result["output_tokens"])

    st.divider()

    # ── Render: predicted files + P/R/F1 ─────────────────────────────────────
    col_a, col_b = st.columns([1, 1], gap="large")

    with col_a:
        st.markdown("### Predicted Files")

        predicted_files = result["predicted_files"]
        if not predicted_files:
            st.warning("Không tìm được file nào.")
        else:
            lines = []
            for f in predicted_files:
                icon = _file_status_icon(f, gt_files, predicted_files)
                lines.append(f"{icon}  `{f}`")
            # GT files bị miss — hiển thị ở cuối để thấy rõ false negatives
            for f in gt_files:
                if f not in predicted_files:
                    lines.append(f"🎯  `{f}` *(GT — missed)*")
            st.markdown("\n\n".join(lines))

        if gt_files and predicted_files:
            st.divider()
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Precision", f"{result['precision']:.0%}")
            mc2.metric("Recall",    f"{result['recall']:.0%}")
            mc3.metric("F1",        f"{result['f1']:.0%}")

    # ── Render: LLM answer ────────────────────────────────────────────────────
    with col_b:
        st.markdown("### LLM Answer")
        if result["answer"]:
            st.markdown(result["answer"])
        else:
            st.info("LLM bị tắt hoặc không có context để gửi.")

    # ── Render: debug expanders ───────────────────────────────────────────────
    candidates = result["candidates"]
    seed_nodes = result["seed_nodes"]
    context    = result["context"]

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
