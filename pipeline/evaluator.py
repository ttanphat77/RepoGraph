"""
pipeline/evaluator.py — RAG Pipeline Orchestrator

Tầng trung gian duy nhất giữa pipeline/ và mọi caller bên ngoài (UI, batch scripts, tests).

Nguyên tắc thiết kế:
  - Không import bất kỳ thứ gì từ Streamlit hoặc app/
  - Trả về dict thuần — caller tự quyết định làm gì với kết quả
  - Mọi business logic của RAG pipeline nằm ở đây, không nằm trong UI

Luồng:
  issue_text
      │
      ▼
  run_retrieval_only()        ← Retrieval thuần (không LLM) — dùng bởi streaming UI
      │
      ▼  (hoặc full pipeline)
  run_rag_pipeline()          ← Retrieval + generate() + compute_metrics()
      │
      ▼
  dict kết quả thuần

Lưu ý về streaming:
  UI có thể gọi run_retrieval_only() + generate_stream() riêng biệt.
  generate_stream() là generator yield từng chunk — inherently UI concern
  (st.write_stream). compute_metrics() vẫn gọi từ evaluator sau khi stream xong.
"""

from __future__ import annotations

import logging

from pipeline.retriever import GraphRetriever
from pipeline.generator import generate

logger = logging.getLogger(__name__)


def run_retrieval_only(issue_text: str, depth: int = 2) -> dict:
    """
    Chỉ chạy bước Retrieval — không gọi LLM.

    Dùng khi UI muốn stream LLM riêng (st.write_stream) thay vì gọi qua
    run_rag_pipeline(). Caller tự gọi generate_stream() và compute_metrics() sau.

    Returns:
        dict với keys: candidates, seed_nodes, subgraph, context, candidate_files
    """
    retriever = GraphRetriever()
    try:
        return retriever.retrieve(issue_text, depth=depth)
    finally:
        retriever.close()


def compute_metrics(predicted_files: list[str], gt_files: list[str]) -> dict:
    """
    Tính Precision / Recall / F1 cho bài toán File Localization.

    Định nghĩa:
      TP = file vừa trong predicted vừa trong GT
      Precision = TP / |predicted|  — trong những file dự đoán, bao nhiêu đúng?
      Recall    = TP / |GT|         — trong những file cần sửa, tìm được bao nhiêu?
      F1        = harmonic mean của Precision và Recall

    Args:
        predicted_files: Danh sách file hệ thống dự đoán cần sửa
        gt_files:        Ground-truth files từ patch (developer đã thực sự sửa)

    Returns:
        dict với keys: tp, precision, recall, f1
        Trả về toàn 0.0 nếu một trong hai list rỗng.
    """
    if not predicted_files or not gt_files:
        return {"tp": 0, "precision": 0.0, "recall": 0.0, "f1": 0.0}

    tp        = len(set(predicted_files) & set(gt_files))
    precision = tp / len(predicted_files)
    recall    = tp / len(gt_files)
    f1        = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0 else 0.0
    )

    return {"tp": tp, "precision": precision, "recall": recall, "f1": f1}


def run_rag_pipeline(
    issue_text: str,
    depth: int = 2,
    run_llm: bool = True,
    gt_files: list[str] | None = None,
) -> dict:
    """
    Chạy full GraphRAG pipeline từ issue text đến kết quả và metrics.

    Đây là hàm duy nhất mà UI (query_view.py) và batch scripts cần gọi.
    Không có Streamlit dependency — có thể gọi từ bất kỳ context nào.

    Args:
        issue_text: Nội dung issue/bug report gốc
        depth:      Số bước BFS mở rộng subgraph (1-3)
        run_llm:    True = gọi LLM để phân tích; False = chỉ graph ranking
        gt_files:   Ground-truth files để tính metrics. None = bỏ qua metrics.

    Returns:
        dict gồm các nhóm key:

        [Retrieval]
          candidates      — list identifier trích từ issue text
          seed_nodes      — list node Neo4j khớp với candidates
          subgraph        — {"nodes": [...], "edges": [...]}
          context         — chuỗi source code đã format cho LLM
          candidate_files — file paths xếp hạng theo graph relevance score

        [Generation]  (answer rỗng nếu run_llm=False hoặc không có context)
          answer          — câu trả lời đầy đủ từ LLM (markdown)
          predicted_files — file LLM dự đoán; fallback = candidate_files
          input_tokens    — token đầu vào (để monitor chi phí API)
          output_tokens   — token đầu ra

        [Metrics]  (toàn 0.0 nếu gt_files=None hoặc rỗng)
          tp              — số True Positives
          precision       — TP / |predicted|
          recall          — TP / |gt|
          f1              — harmonic mean
    """
    gt_files = gt_files or []

    # ── Bước 3: Retrieval ─────────────────────────────────────────────────────
    retriever = GraphRetriever()
    try:
        retrieval = retriever.retrieve(issue_text, depth=depth)
    finally:
        # Đảm bảo đóng Neo4j driver dù retrieve() có raise exception hay không
        retriever.close()

    candidates      = retrieval["candidates"]
    seed_nodes      = retrieval["seed_nodes"]
    subgraph        = retrieval["subgraph"]
    context         = retrieval["context"]
    candidate_files = retrieval["candidate_files"]

    # ── Bước 4: Generation ────────────────────────────────────────────────────
    # Mặc định dùng candidate_files từ graph làm predicted (không cần LLM)
    answer          = ""
    predicted_files = candidate_files
    input_tokens    = 0
    output_tokens   = 0

    if run_llm and context:
        llm_result      = generate(issue_text, context, candidate_files)
        answer          = llm_result["answer"]
        predicted_files = llm_result["predicted_files"]
        input_tokens    = llm_result["input_tokens"]
        output_tokens   = llm_result["output_tokens"]
    elif run_llm and not context:
        logger.warning("run_llm=True nhưng context rỗng — bỏ qua LLM call.")

    # ── Metrics ───────────────────────────────────────────────────────────────
    metrics = compute_metrics(predicted_files, gt_files)

    return {
        # Retrieval
        "candidates":      candidates,
        "seed_nodes":      seed_nodes,
        "subgraph":        subgraph,
        "context":         context,
        "candidate_files": candidate_files,
        # Generation
        "answer":          answer,
        "predicted_files": predicted_files,
        "input_tokens":    input_tokens,
        "output_tokens":   output_tokens,
        # Metrics
        **metrics,
    }
