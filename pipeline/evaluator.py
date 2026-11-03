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
        llm_result      = generate(issue_text, context)
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


# ═════════════════════════════════════════════════════════════════════════════
# App đa nguồn, giai đoạn 1: một lần prompting trên K(p)
#
#   run_prompt(prompt)
#       │  Engine (nạp một lần): RepoIndex, LocusIndex, MsgIndex, IssueIndex
#       ▼
#   retrieve_kp()  → K(p): [E] thực thể, [C] code, file, [D] doc, [H] commit, [I] báo cáo cũ
#       ▼
#   build_kp_messages() → stream_answer()  (một lần gọi LLM) ∥ count_section_tokens()
#       ▼
#   parse_citations() → bản ghi 8 khối → {INDEX_ROOT}/{repo}/runs/<run_id>/
# ═════════════════════════════════════════════════════════════════════════════

import json
import subprocess
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import config
from pipeline.context import format_sections, retrieve_kp
from pipeline.generator import (
    KP_SYSTEM, KP_USER_TMPL, build_kp_messages, count_section_tokens, kp_token_parts, stream_answer,
)
from pipeline.ranking import _MD_CODEBLOCK_RE, embed_query_text, tokenize_code
from pipeline.run_record import (
    app_commit, config_block, latest_index_dir, new_run_id, parse_citations, retrieval_block, sha1_text,
    write_run,
)


class Engine:
    """Các chỉ mục truy hồi của một repo đã build, nạp một lần cho nhiều lần hỏi."""

    def __init__(self, index_dir, ri, locus, msg, issue, units, reports, load_ms):
        self.index_dir = Path(index_dir)
        self.ri, self.locus, self.msg, self.issue = ri, locus, msg, issue
        self.state = ri.state
        self.units_by_sha = {u["h"]: u for u in units}
        self.reports_by_n = {r["n"]: r for r in reports}
        self.load_ms = load_ms

    @classmethod
    def load(cls, index_dir) -> "Engine":
        from pipeline.history import LocusIndex, MsgIndex, _read_jsonl, graph_names
        from pipeline.issues import IssueIndex, commit_texts, load_issue_data
        from pipeline.ranking import RepoIndex
        t0 = time.perf_counter()
        index_dir = Path(index_dir)
        ri = RepoIndex.load(index_dir)
        prefix = ri.state.get("id_prefix", "local")
        fc = {n["id"] for n in ri.nodes if n["label"] in ("Function", "Class")}
        units = _read_jsonl(index_dir / "history" / "history.jsonl")
        hunks = _read_jsonl(index_dir / "history" / "hunks.jsonl")
        reports, links = load_issue_data(index_dir)
        cache = index_dir / "history"   # ma trận đếm từ lưu ở đây, lần nạp sau chỉ đọc file
        locus = LocusIndex(units, hunks, fc, graph_names(ri.nodes), prefix, cache) if units else None
        msg = MsgIndex(units, fc, prefix, commit_texts(units, reports, links), cache) if units else None
        issue = IssueIndex(reports, units, links, fc, prefix) if reports else None
        return cls(index_dir, ri, locus, msg, issue, units, reports,
                   round((time.perf_counter() - t0) * 1000, 1))


_ENGINES: dict[str, tuple[str, Engine]] = {}
_ENGINES_LOCK = threading.Lock()   # bot và Streamlit gọi từ nhiều luồng: chỉ một luồng nạp engine


def get_engine(index_dir) -> Engine:
    """Engine của index_dir, nạp lại khi index được build lại (built_at đổi)."""
    key = str(Path(index_dir).resolve())
    built = json.loads((Path(index_dir) / "index_state.json").read_text(encoding="utf-8")).get("built_at", "")
    with _ENGINES_LOCK:
        cached = _ENGINES.get(key)
        if cached is None or cached[0] != built:
            _ENGINES[key] = (built, Engine.load(index_dir))
        return _ENGINES[key][1]


def _index_block(engine: Engine) -> dict:
    """Trạng thái index lúc hỏi, kèm cờ index cũ hơn HEAD hiện tại của repo."""
    st = engine.state
    repo_path = st.get("repo_path")
    head_now = subprocess.run(["git", "-C", repo_path, "rev-parse", "HEAD"], capture_output=True,
                              text=True).stdout.strip() if repo_path else ""
    hist, iss = st.get("history") or {}, st.get("issues") or {}
    return {
        "repo_path": repo_path, "remote": st.get("remote"), "head_sha": st.get("head_sha"),
        "head_time": st.get("head_time"), "built_at": st.get("built_at"),
        "last_update": (st.get("last_update") or {}).get("head_after"), "id_prefix": st.get("id_prefix"),
        "nodes": st.get("nodes"), "edges": st.get("edges"), "doc_cov": st.get("doc_cov"),
        "history": {k: hist.get(k) for k in ("commits", "with_touch", "hunks", "commit_nodes")},
        "issues": {"reports": iss.get("reports"), "prs": iss.get("prs"), "links": iss.get("links"),
                   "fetch_complete": (iss.get("fetch") or {}).get("complete")},
        "embedding": {k: (st.get("embedding") or {}).get(k) for k in ("model", "encoders", "dim")},
        "repo_head_now": head_now or None,
        "stale": bool(head_now and st.get("head_sha") and head_now != st["head_sha"]),
        "engine_load_ms": engine.load_ms,
    }


def run_prompt(prompt: str, index_dir=None, engine: Engine | None = None, on_text=None,
               llm=None, counter=None, t_query: float | None = None, model: str | None = None):
    """
    Một lần prompting: truy hồi K(p), gọi LLM một lần, ghi bản ghi. Lỗi ở bước nào cũng
    vẫn ghi bản ghi đủ 8 khối, với lỗi ở khối warnings và llm.

    Args:
        index_dir: {INDEX_ROOT}/{repo}. None → index build gần nhất.
        on_text:   callback nhận từng đoạn chữ của câu trả lời (stream).
        llm, counter: hàm gọi LLM và hàm đếm token. None → stream_answer và count_section_tokens
                   với `model` (thay được khi test).
        t_query:   thời điểm hỏi (giây UNIX) cho Fix của Locus. None → lúc gọi.
        model:     model Gemini dùng cho lần chạy, ghi vào khối config. None → config.GEMINI_MODEL.

    Returns:
        (record, thư mục của lần chạy)
    """
    t_start = time.perf_counter()
    model = model or config.GEMINI_MODEL
    llm = llm or (lambda system, user, cb: stream_answer(system, user, cb, model=model))
    counter = counter or (lambda parts: count_section_tokens(parts, model=model))
    index_dir = Path(index_dir) if index_dir else (engine.index_dir if engine else latest_index_dir())
    if index_dir is None:
        raise FileNotFoundError("No built index found. Run scripts/build_graph.py first.")
    t_query = t_query or time.time()
    stripped = _MD_CODEBLOCK_RE.sub(" ", prompt)
    timing: dict = {}
    warnings: list[str] = []
    rec = {
        "run": {"run_id": new_run_id(), "started_at": datetime.now(timezone.utc).isoformat(),
                "app": app_commit(), "mode": "prompt", "prompt": prompt, "prompt_chars": len(prompt),
                "query_bm25_tokens": len(tokenize_code(prompt)),
                "query_embed_chars": len(embed_query_text(prompt)),
                "query_embed_cut": len(stripped) > config.EMBED_QUERY_CHARS,
                "t_query": t_query},
        "index": None, "config": config_block(sha1_text(KP_SYSTEM, KP_USER_TMPL), model), "retrieval": None,
        "llm": None, "citations": None, "timing": timing, "warnings": warnings,
    }
    system = user = ""
    kp, meta = None, {"answer": "", "finish_reason": "NOT_RUN"}

    try:
        t0 = time.perf_counter()
        engine = engine or get_engine(index_dir)
        timing["engine_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        rec["index"] = _index_block(engine)
        warnings += engine.ri.warnings
        if rec["index"]["stale"]:
            warnings.append(f"index is older than the repository HEAD "
                            f"({rec['index']['head_sha'][:8]} vs {rec['index']['repo_head_now'][:8]}); run update")
        kp = retrieve_kp(engine, prompt, t_query, timing)
        warnings += [f"section {s} is empty: {why}" for s, why in kp["metrics"]["empty_reason"].items() if why]
        sections = format_sections(kp)
        repo = engine.state.get("remote") or engine.state.get("repo_path") or str(index_dir)
        commit = (engine.state.get("head_sha") or "unknown")[:8]
        system, user = build_kp_messages(prompt, sections, repo, commit)
    except Exception as e:
        warnings.append(f"retrieval failed: {type(e).__name__}: {e}")
        rec["run"]["traceback"] = traceback.format_exc()

    if user:
        counts, t0 = None, time.perf_counter()
        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(counter, kp_token_parts(prompt, sections, repo, commit))
            meta = llm(system, user, on_text)
            try:
                counts = fut.result()
            except Exception as e:
                warnings.append(f"token counting failed: {type(e).__name__}: {e}")
        timing["llm_wall_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        total = sum(counts.values()) if counts else None
        ptc = meta.get("prompt_token_count")
        rec["llm"] = {**{k: v for k, v in meta.items() if k != "answer"},
                      "answer_chars": len(meta.get("answer") or ""), "section_tokens": counts,
                      "section_tokens_sum": total,
                      "section_tokens_gap": round((ptc - total) / ptc, 4) if ptc and total is not None else None}
        if meta.get("error"):
            warnings.append(f"LLM call failed: {meta['error']}")
        elif meta.get("finish_reason") not in (None, "STOP"):
            warnings.append(f"LLM finish_reason = {meta['finish_reason']}")
    else:
        rec["llm"] = {"finish_reason": "NOT_RUN", "error": "retrieval failed, LLM not called"}

    answer = meta.get("answer") or ""
    cit = parse_citations(answer, kp)
    rec["citations"] = cit
    if cit["invalid_items"] or cit["invalid_symbols"]:
        warnings.append(f"invalid citations: {len(cit['invalid_items'])} item ids, "
                        f"{len(cit['invalid_symbols'])} symbols")
    if kp:
        rec["retrieval"] = retrieval_block(kp, set(cit["cited_items"]))
    timing["total_ms"] = round((time.perf_counter() - t_start) * 1000, 1)
    run_dir = write_run(index_dir, rec, system, user, answer)
    return rec, run_dir
