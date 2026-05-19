# =============================================================================
# app/components/query_view.py — Issue Query Tab (RAG End-to-End)
#
# Luồng hoàn chỉnh từ issue text đến dự đoán file:
#
#   1. User nhập issue text (hoặc load sẵn từ current_instance.json)
#   2. GraphRetriever.retrieve() :
#        a. Entity Resolution (regex) → identifier candidates
#        b. Seed Lookup (Neo4j) → matching nodes
#        c. Neighborhood BFS → subgraph context
#   3. Generator.generate() : LLM phân tích context → predicted files
#   4. Hiển thị kết quả:
#        - Predicted files với icon ✅/❌/🎯 so với GT
#        - Precision / Recall / F1 nếu có GT files
#        - LLM answer (markdown)
#        - Debug expanders (identifiers, seed nodes, context preview)
#
# st.cache_data không dùng ở đây vì mỗi query có thể khác nhau.
# =============================================================================

from __future__ import annotations

import json
import os
import sys

import streamlit as st

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from pipeline.retriever import GraphRetriever
from pipeline.generator import generate


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
    Trả về icon thể hiện kết quả dự đoán cho một file:
      ✅ — True Positive  : dự đoán đúng (cả trong GT lẫn predicted)
      ❌ — False Positive : dự đoán sai (predicted nhưng không phải GT)
      🎯 — False Negative : bỏ sót (GT nhưng không predicted)
    """
    in_gt   = file in gt_files
    in_pred = file in predicted
    if in_gt and in_pred:   return "✅"
    if in_pred and not in_gt: return "❌"
    if in_gt and not in_pred: return "🎯"
    return "  "


def render_query_view():
    """Render tab Issue Query — full RAG pipeline UI."""

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
            value=problem,          # pre-fill từ current_instance.json
            height=260,
            placeholder="Dán nội dung issue vào đây...",
        )

        c1, c2 = st.columns([1, 1])
        # depth BFS: 1=chỉ seed, 2=neighbor của seed, 3=neighbor của neighbor
        depth   = c1.selectbox("Depth BFS", [1, 2, 3], index=1)
        # Tắt LLM để xem chỉ retrieval (không tốn token)
        run_llm = c2.checkbox("Gọi LLM", value=True)

        do_query = st.button("🔍  Retrieve + Generate", use_container_width=True)

    if not do_query:
        with col_right:
            st.info("Nhấn **Retrieve + Generate** để bắt đầu.")
        return

    if not issue_text.strip():
        st.warning("Vui lòng nhập issue text.")
        return

    # ── Retrieval ─────────────────────────────────────────────────────────────
    with st.spinner("Đang truy xuất Knowledge Graph..."):
        retriever = GraphRetriever()
        result    = retriever.retrieve(issue_text, depth=depth)
        retriever.close()  # đóng connection sau mỗi request

    candidates      = result["candidates"]
    seed_nodes      = result["seed_nodes"]
    subgraph        = result["subgraph"]
    context         = result["context"]
    candidate_files = result["candidate_files"]

    # ── LLM Generation ────────────────────────────────────────────────────────
    llm_result = None
    if run_llm and context:
        with st.spinner("Đang gọi LLM..."):
            llm_result = generate(issue_text, context, candidate_files)
        predicted_files = llm_result.get("predicted_files", candidate_files)
    else:
        # Không gọi LLM → dùng candidate_files từ graph làm prediction
        predicted_files = candidate_files

    # ── Metrics summary ───────────────────────────────────────────────────────
    with col_right:
        m1, m2, m3 = st.columns(3)
        m1.metric("Identifiers", len(candidates))
        m2.metric("Seed nodes",  len(seed_nodes))
        m3.metric("Subgraph",    len(subgraph["nodes"]))

        if llm_result:
            t1, t2 = st.columns(2)
            t1.metric("Input tokens",  llm_result["input_tokens"])
            t2.metric("Output tokens", llm_result["output_tokens"])

    st.divider()

    # ── Results: predictions + LLM answer ────────────────────────────────────
    col_a, col_b = st.columns([1, 1], gap="large")

    with col_a:
        st.markdown("### Predicted Files")

        if not predicted_files:
            st.warning("Không tìm được file nào.")
        else:
            lines = []
            for f in predicted_files:
                icon = _file_status_icon(f, gt_files, predicted_files)
                lines.append(f"{icon}  `{f}`")
            # Thêm GT files bị miss vào cuối để thấy rõ false negatives
            for f in gt_files:
                if f not in predicted_files:
                    lines.append(f"🎯  `{f}` *(GT — missed)*")
            st.markdown("\n\n".join(lines))

        # Tính Precision / Recall / F1 nếu có GT files để so sánh
        if gt_files and predicted_files:
            tp        = len(set(predicted_files) & set(gt_files))
            precision = tp / len(predicted_files) if predicted_files else 0
            recall    = tp / len(gt_files) if gt_files else 0
            f1 = (
                2 * precision * recall / (precision + recall)
                if (precision + recall) > 0 else 0
            )
            st.divider()
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Precision", f"{precision:.0%}")
            mc2.metric("Recall",    f"{recall:.0%}")
            mc3.metric("F1",        f"{f1:.0%}")

    with col_b:
        st.markdown("### LLM Answer")
        if llm_result:
            st.markdown(llm_result["answer"])
        else:
            st.info("LLM bị tắt hoặc không có context để gửi.")

    # ── Debug expanders ───────────────────────────────────────────────────────
    # Dùng expander để không chiếm không gian màn hình mặc định

    with st.expander(f"Identifiers trích xuất ({len(candidates)})"):
        st.write(candidates)

    with st.expander(f"Seed nodes ({len(seed_nodes)})"):
        for n in seed_nodes:
            st.markdown(
                f"**[{n['label']}]** `{n['name']}` — `{n['file']}:{n['start_line']}`"
            )

    with st.expander(f"Context gửi LLM ({len(context)} chars)"):
        # Hiển thị tối đa 6000 ký tự để tránh lag browser
        st.code(
            context[:6000] + ("..." if len(context) > 6000 else ""),
            language="markdown",
        )
