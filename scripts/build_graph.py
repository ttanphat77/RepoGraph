import argparse
import sys
import os
import json
import logging
import concurrent.futures
from pathlib import Path

# Add the project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from pipeline.dataset_loader import load_swe_bench_lite, save_cache, load_cache
from pipeline.repo_manager import clone_and_checkout, get_python_files
from pipeline.ast_engine import ASTEngine
from pipeline.schemas import load_schema
from pipeline.neo4j_ingester import Neo4jIngester
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None


def write_current_state(state: dict):
    path = Path("cache/current_instance.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f)


def clear_graph(ingester: Neo4jIngester) -> None:
    logging.info("Clearing existing graph data...")
    with ingester.driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    logging.info("Graph cleared.")


def _parse_one_file(args):
    """Top-level function so ProcessPoolExecutor can pickle it."""
    rel, repo_path, base_commit, schema_name = args
    schema = load_schema(schema_name)
    engine = ASTEngine(
        file_path=str(Path(repo_path) / rel),
        repo_path=repo_path,
        base_commit=base_commit,
        schema=schema,
    )
    return engine.parse()


def build_graph_from_repo(repo_path: str, base_commit: str = "local"):
    schema = load_schema(config.ACTIVE_SCHEMA)
    logging.info(f"Active schema: {config.ACTIVE_SCHEMA!r}")

    py_files = get_python_files(repo_path)
    logging.info(f"Found {len(py_files)} Python files in {repo_path}")

    max_files = config.MAX_FILES_PARSED if config.MAX_FILES_PARSED > 0 else len(py_files)
    files_to_process = py_files[:max_files]

    # ── STAGE 1: Parallel Extraction ──────────────────────────────────────────
    logging.info(f"Stage 1: Parsing {len(files_to_process)} files in parallel...")

    parse_args = [(f, repo_path, base_commit, config.ACTIVE_SCHEMA) for f in files_to_process]
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

    # ── STAGE 2: Cross-File Resolution ────────────────────────────────────────
    logging.info("Stage 2: Resolving cross-file semantic edges...")
    semantic_edges = ASTEngine.resolve_cross_file(all_results, schema)

    # ── STAGE 3: Community Detection ──────────────────────────────────────────
    if config.ENABLE_COMMUNITY_DETECTION:
        logging.info("Stage 3: Community Detection (Louvain)...")
        try:
            import networkx as nx
            from networkx.algorithms.community import louvain_communities

            G = nx.Graph()
            node_map = {}

            for res in all_results:
                for node in res["nodes"]:
                    G.add_node(node["id"])
                    node_map[node["id"]] = node

            all_edges_flat = [e for res in all_results for e in res["definite_edges"]]
            all_edges_flat.extend(semantic_edges)

            for e in all_edges_flat:
                if e["source"] in node_map and e["target"] in node_map and e["source"] != e["target"]:
                    G.add_edge(e["source"], e["target"])

            communities = louvain_communities(G, seed=42)
            logging.info(f"Found {len(communities)} communities.")
            for cid, members in enumerate(communities):
                for nid in members:
                    if nid in node_map:
                        node_map[nid]["properties"]["community"] = cid

        except ImportError:
            logging.warning("networkx not installed — skipping community detection.")
    else:
        logging.info("Stage 3: Community Detection skipped (ENABLE_COMMUNITY_DETECTION=False).")

    # ── STAGE 4: Atomic Bulk Ingestion ────────────────────────────────────────
    logging.info("Stage 4: Bulk Loading to Neo4j...")
    try:
        ingester = Neo4jIngester()
        clear_graph(ingester)

        for res in all_results:
            for node in res["nodes"]:
                ingester.add_node(node)

        # Flush all nodes to Neo4j before writing edges — MATCH requires endpoints to exist
        ingester.flush()

        for res in all_results:
            for edge in res["definite_edges"]:
                ingester.add_edge(edge)

        for edge in semantic_edges:
            ingester.add_edge(edge)

        ingester.flush()
        ingester.close()
        logging.info("Graph construction complete.")
    except Exception as e:
        logging.error(f"Failed to ingest to Neo4j: {e}")


def handle_swe_lite(index: int):
    logging.info("Fetching SWE-bench-lite dataset...")
    try:
        instances = load_cache(config.DATASET_CACHE)
    except FileNotFoundError:
        instances = load_swe_bench_lite()
        save_cache(instances, config.DATASET_CACHE)

    unique_repos = []
    for inst in instances:
        if inst["repo"] not in unique_repos:
            unique_repos.append(inst["repo"])

    if index < 1 or index > len(unique_repos):
        logging.error(f"Index out of range. Provide 1–{len(unique_repos)}.")
        return

    repo_name = unique_repos[index - 1]
    logging.info(f"Target Repo: {repo_name}")
    write_current_state({"instance_id": f"{repo_name}:latest", "gt_files": []})
    repo_path = clone_and_checkout(repo_name, base_commit="latest")
    build_graph_from_repo(repo_path, base_commit="latest")


def handle_local(path: str):
    if not Path(path).exists():
        logging.error(f"Path does not exist: {path}")
        return
    write_current_state({"instance_id": "local", "gt_files": []})
    build_graph_from_repo(path, base_commit="local")


def main():
    parser = argparse.ArgumentParser(description="GraphRAG POC Graph Builder")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_swe = subparsers.add_parser("swe-lite", help="Build graph from SWE-bench-lite instance")
    p_swe.add_argument("index", type=int)

    p_local = subparsers.add_parser("local", help="Build graph from a local folder")
    p_local.add_argument("path", type=str)

    args = parser.parse_args()
    if args.command == "swe-lite":
        handle_swe_lite(args.index)
    elif args.command == "local":
        handle_local(args.path)


if __name__ == "__main__":
    main()
