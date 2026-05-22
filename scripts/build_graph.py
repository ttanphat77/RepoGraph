"""
scripts/build_graph.py — CLI entrypoint để xây dựng Knowledge Graph

Ba chế độ:
  swe-lite <index>  — Lấy instance thứ <index> trong SWE-bench Lite,
                      clone repo tại đúng base_commit, parse và nạp vào Neo4j.
  local <path>      — Parse một thư mục local (không cần dataset).
  url <url>         — Clone từ git URL bất kỳ (GitHub/GitLab/...) và build graph.

Pipeline gồm 4 stage:
  Stage 1 — Parallel AST Extraction:
      Mỗi file .py được parse bởi ASTEngine trong ProcessPoolExecutor.
      Dùng multiprocessing (không phải threading) vì CPython GIL.

  Stage 2 — Cross-File Resolution:
      ASTEngine.resolve_cross_file() nhận kết quả tất cả files,
      xây index toàn cục, resolve call/inherit refs thành cạnh cụ thể.

  Stage 3 — Community Detection (optional):
      Leiden algorithm trên igraph. Gán community ID cho mỗi node.
      Tắt mặc định vì chậm trên repo lớn (ENABLE_COMMUNITY_DETECTION).

  Stage 4 — Bulk Ingestion:
      MERGE nodes vào Neo4j → flush → MERGE edges (thứ tự bắt buộc).
      Clear graph trước mỗi lần build để tránh data cũ lẫn vào.
"""

import argparse
import sys
import os
import json
import logging
import concurrent.futures
from pathlib import Path

# Thêm project root vào sys.path để import pipeline từ bất kỳ thư mục nào
sys.path.append(str(Path(__file__).parent.parent))

from pipeline.dataset_loader import load_swe_bench_lite, save_cache, load_cache
from pipeline.repo_manager import clone_and_checkout, get_python_files, clone_from_url, get_source_files
from pipeline.ast_engine import ASTEngine
from pipeline.schemas import load_schema
from pipeline.neo4j_ingester import Neo4jIngester
from pipeline.languages.python import python_extractor
from pipeline.languages.swift import swift_extractor
import config

LANG_CONFIG = {
    "python": {"extractor": python_extractor, "extensions": (".py",)},
    "swift":  {"extractor": swift_extractor,  "extensions": (".swift",)},
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# tqdm là optional — nếu không cài thì bỏ qua progress bar
try:
    from tqdm import tqdm
except ImportError:
    tqdm = None


def write_current_state(state: dict) -> None:
    """
    Ghi trạng thái instance hiện tại ra cache/current_instance.json.

    File này được đọc bởi Streamlit UI để:
      - Biết instance nào đang active
      - Lấy problem_statement để hiển thị sẵn trong Issue Query tab
      - Lấy gt_files để tô màu 🎯 và tính Precision/Recall
    """
    path = Path("cache/current_instance.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f)


def clear_graph(ingester: Neo4jIngester) -> None:
    """
    Xóa toàn bộ graph hiện tại trước khi build mới.

    DETACH DELETE cũng xóa tất cả relationships trước khi xóa nodes.
    Cần thiết để tránh data từ repo cũ lẫn vào graph mới.
    """
    logging.info("Clearing existing graph data...")
    with ingester.driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    logging.info("Graph cleared.")


def _parse_one_file(args: tuple) -> dict | None:
    """
    Hàm top-level để ProcessPoolExecutor có thể pickle.

    Phải là top-level function (không phải lambda hoặc method) vì
    Python multiprocessing dùng pickle để truyền function giữa processes,
    và pickle không serialize được closure hoặc lambda.

    Mỗi worker process tạo ASTEngine + SchemaPlugin riêng — an toàn với multiprocessing.
    """
    rel, repo_path, base_commit, schema_name, lang = args
    schema = load_schema(schema_name)
    extractor = LANG_CONFIG[lang]["extractor"]
    engine = ASTEngine(
        file_path=str(Path(repo_path) / rel),
        repo_path=repo_path,
        base_commit=base_commit,
        schema=schema,
        extractor=extractor,
    )
    return engine.parse()


def build_graph_from_repo(repo_path: str, base_commit: str = "local", lang: str = "python") -> None:
    """
    Pipeline chính: parse repo → resolve cross-file → community detect → ingest.

    Args:
        repo_path:   Đường dẫn đến thư mục repo đã clone
        base_commit: Commit hash hoặc "local" — dùng làm prefix cho node IDs
        lang:        Ngôn ngữ lập trình ("python" hoặc "swift")
    """
    if lang not in LANG_CONFIG:
        logging.error(f"Unsupported language: {lang!r}. Choose from: {list(LANG_CONFIG)}")
        return

    schema = load_schema(config.ACTIVE_SCHEMA)
    logging.info(f"Active schema: {config.ACTIVE_SCHEMA!r}, lang: {lang!r}")

    extensions = LANG_CONFIG[lang]["extensions"]
    source_files = get_source_files(repo_path, extensions)
    logging.info(f"Found {len(source_files)} {lang} files in {repo_path}")

    max_files      = config.MAX_FILES_PARSED if config.MAX_FILES_PARSED > 0 else len(source_files)
    files_to_parse = source_files[:max_files]

    # ── Stage 1: Parallel AST Extraction ─────────────────────────────────────
    logging.info(f"Stage 1: Parsing {len(files_to_parse)} files in parallel...")

    parse_args  = [(f, repo_path, base_commit, config.ACTIVE_SCHEMA, lang) for f in files_to_parse]
    all_results = []

    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = {executor.submit(_parse_one_file, a): a[0] for a in parse_args}

        if tqdm:
            pbar = tqdm(total=len(futures), desc="Extracting AST")

        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res:
                all_results.append(res)
            if tqdm:
                pbar.update(1)

        if tqdm:
            pbar.close()

    # ── Stage 2: Cross-File Resolution ───────────────────────────────────────
    # Phải chạy sau khi có kết quả của TẤT CẢ files (cần index toàn cục)
    logging.info("Stage 2: Resolving cross-file semantic edges...")
    semantic_edges = ASTEngine.resolve_cross_file(all_results, schema)

    # ── Stage 3: Community Detection (Leiden) ────────────────────────────────
    if config.ENABLE_COMMUNITY_DETECTION:
        logging.info("Stage 3: Community Detection (Leiden)...")
        try:
            import igraph as ig
            import leidenalg

            # Xây dựng node index: node_id string → integer index cho igraph
            node_map: dict[str, dict] = {}
            for res in all_results:
                for node in res["nodes"]:
                    node_map[node["id"]] = node

            node_ids  = list(node_map.keys())
            node_index = {nid: i for i, nid in enumerate(node_ids)}

            # Gom tất cả edges (definite + semantic) để xây graph cho Leiden
            all_edges_flat = [e for res in all_results for e in res["definite_edges"]]
            all_edges_flat.extend(semantic_edges)

            edges   = []
            weights = []
            for e in all_edges_flat:
                src, tgt = e["source"], e["target"]
                # Chỉ lấy edge có cả hai endpoint trong node_index (bỏ cross-repo)
                if src in node_index and tgt in node_index and src != tgt:
                    edges.append((node_index[src], node_index[tgt]))
                    # Trọng số theo loại edge — xem COMMUNITY_EDGE_WEIGHTS trong config
                    weights.append(config.COMMUNITY_EDGE_WEIGHTS.get(e["type"], 1.0))

            # Leiden trên undirected graph (treat edges as undirected cho clustering)
            G         = ig.Graph(n=len(node_ids), edges=edges)
            partition = leidenalg.find_partition(
                G,
                leidenalg.RBConfigurationVertexPartition,
                weights=weights,
                seed=42,  # seed cố định để reproducible
            )

            logging.info(f"Found {len(partition)} communities.")
            # Gán community ID vào properties của mỗi node
            for cid, members in enumerate(partition):
                for idx in members:
                    node_map[node_ids[idx]]["properties"]["community"] = cid

        except ImportError:
            logging.warning("leidenalg/igraph not installed — skipping community detection.")
    else:
        logging.info("Stage 3: Community Detection skipped (ENABLE_COMMUNITY_DETECTION=False).")

    # ── Stage 4: Bulk Ingestion vào Neo4j ────────────────────────────────────
    logging.info("Stage 4: Bulk Loading to Neo4j...")
    try:
        ingester = Neo4jIngester()
        clear_graph(ingester)  # xóa graph cũ trước

        # Nạp tất cả nodes trước
        for res in all_results:
            for node in res["nodes"]:
                ingester.add_node(node)

        # FLUSH NODES TRƯỚC — bắt buộc vì edge query dùng MATCH endpoint
        # Nếu không flush, MATCH sẽ fail khi node chưa commit vào DB
        ingester.flush()

        # Nạp edges sau khi nodes đã có trong DB
        for res in all_results:
            for edge in res["definite_edges"]:
                ingester.add_edge(edge)

        # Cross-file semantic edges (Calls, Inherits)
        for edge in semantic_edges:
            ingester.add_edge(edge)

        ingester.flush()
        ingester.ensure_fulltext_index()
        ingester.close()
        logging.info("Graph construction complete.")

    except Exception as e:
        logging.error(f"Failed to ingest to Neo4j: {e}")


def handle_swe_lite(index: int) -> None:
    """
    Build graph từ instance thứ <index> trong SWE-bench Lite.

    Dùng cache JSON nếu đã tải trước; tải mới từ HuggingFace nếu chưa có.
    Index bắt đầu từ 1 (không phải 0) để user-friendly hơn.
    """
    logging.info("Fetching SWE-bench-lite dataset...")
    try:
        instances = load_cache(config.DATASET_CACHE)
    except FileNotFoundError:
        # Lần đầu chạy — tải từ HuggingFace và lưu cache
        instances = load_swe_bench_lite()
        save_cache(instances, config.DATASET_CACHE)

    if index < 1 or index > len(instances):
        logging.error(f"Index out of range. Provide 1–{len(instances)}.")
        return

    instance         = instances[index - 1]
    repo_name        = instance["repo"]
    base_commit      = instance["base_commit"]
    gt_files         = instance.get("gt_files", [])
    problem_statement = instance.get("problem_statement", "")

    logging.info(f"Instance: {instance['instance_id']}  repo: {repo_name}  commit: {base_commit}")
    logging.info(f"GT files: {gt_files}")

    # Lưu trạng thái để Streamlit UI đọc được gt_files và problem_statement
    write_current_state({
        "instance_id":       instance["instance_id"],
        "repo":              repo_name,
        "base_commit":       base_commit,
        "problem_statement": problem_statement,
        "gt_files":          gt_files,
    })

    repo_path = clone_and_checkout(repo_name, base_commit=base_commit)
    build_graph_from_repo(repo_path, base_commit=base_commit, lang="python")


def handle_local(path: str, lang: str = "python") -> None:
    """
    Build graph từ một thư mục code local.
    """
    if not Path(path).exists():
        logging.error(f"Path does not exist: {path}")
        return

    write_current_state({
        "instance_id": "local",
        "gt_files":    [],
    })
    build_graph_from_repo(path, base_commit="local", lang=lang)


def handle_url(url: str, branch: str | None = None, token: str | None = None, lang: str = "python") -> None:
    """
    Clone từ git URL bất kỳ và build graph.
    """
    try:
        repo_path = clone_from_url(url, branch=branch, token=token)
    except Exception:
        return

    write_current_state({
        "instance_id": url,
        "gt_files":    [],
    })
    build_graph_from_repo(repo_path, base_commit="local", lang=lang)


def main() -> None:
    """Entry point CLI — parse args và dispatch đến handler phù hợp."""
    parser = argparse.ArgumentParser(description="GraphRAG POC Graph Builder")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: swe-lite
    p_swe = subparsers.add_parser("swe-lite", help="Build graph from SWE-bench-lite instance")
    p_swe.add_argument("index", type=int, help="Instance index (1-based)")

    # Subcommand: local
    p_local = subparsers.add_parser("local", help="Build graph from a local folder")
    p_local.add_argument("path", type=str, help="Path to local repo/directory")
    p_local.add_argument("-l", "--lang", default="python", choices=list(LANG_CONFIG), help="Programming language")

    # Subcommand: url
    p_url = subparsers.add_parser("url", help="Clone from a git URL and build graph")
    p_url.add_argument("url", type=str, help="Git URL (https or ssh)")
    p_url.add_argument("-b", "--branch", default=None, help="Branch name (default: repo default branch)")
    p_url.add_argument("--token", default=None, help="Access token for private repos (HTTPS only)")
    p_url.add_argument("-l", "--lang", default="python", choices=list(LANG_CONFIG), help="Programming language")

    args = parser.parse_args()
    if args.command == "swe-lite":
        handle_swe_lite(args.index)
    elif args.command == "local":
        handle_local(args.path, lang=args.lang)
    elif args.command == "url":
        handle_url(args.url, branch=args.branch, token=args.token, lang=args.lang)


if __name__ == "__main__":
    main()
