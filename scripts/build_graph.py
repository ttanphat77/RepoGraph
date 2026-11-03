"""
scripts/build_graph.py — CLI entrypoint để xây dựng Knowledge Graph

Bốn chế độ:
  swe-lite <index>  — Lấy instance thứ <index> trong SWE-bench Lite,
                      clone repo tại đúng base_commit, parse và nạp vào Neo4j.
  local <path>      — Parse một thư mục local (không cần dataset).
  url <url>         — Clone từ git URL bất kỳ (GitHub/GitLab/...) và build graph.
  update <path>     - Repo đã build: kéo commit mới (git pull --ff-only) rồi build lại.
                      Cache embedding, history, hunk và issue chỉ xử lý phần mới.

Pipeline gồm 4 stage:
  Stage 1 — Parallel AST Extraction:
      Mỗi file .py được parse bởi ASTEngine trong ProcessPoolExecutor.
      Dùng multiprocessing (không phải threading) vì CPython GIL.

  Stage 2 — Cross-File Resolution:
      ASTEngine.resolve_cross_file() nhận kết quả tất cả files,
      xây index toàn cục, resolve call/inherit refs thành cạnh cụ thể.

  Stage 2b - Doc layer (chỉ repo Python):
      Document/DocChunk + cạnh HasChunk, Documents, References (pipeline/doc_extractor.py).

  Stage 2c - Embeddings:
      Function/Class/DocChunk → {INDEX_ROOT}/{repo}/node_vectors.npy, cache theo nội dung.

  Stage 2d - History layer (chỉ repo Python có git):
      Commit nhánh chính trong HIST_YEARS năm trước HEAD, touch set và chỉ mục hunk
      (pipeline/history.py) → {INDEX_ROOT}/{repo}/history/. Commit sửa ít nhất một
      hàm/lớp của graph thành node Commit, kèm cạnh Modifies tới hàm/lớp đó.

  Stage 2e - Issue layer (repo trên GitHub):
      Tải issue/PR đã đóng (pipeline/issues.py), nối báo cáo với commit
      → {INDEX_ROOT}/{repo}/issues/. Issue được commit trong graph sửa thành node
      Issue, kèm cạnh Fixes (Commit → Issue).

  Stage 3 — Community Detection (optional):
      Leiden algorithm trên igraph. Gán community ID cho mỗi node.
      Tắt mặc định vì chậm trên repo lớn (ENABLE_COMMUNITY_DETECTION).

  Stage 4 — Bulk Ingestion:
      MERGE nodes vào Neo4j → flush → MERGE edges (thứ tự bắt buộc).
      Clear graph trước mỗi lần build để tránh data cũ lẫn vào.

  Cuối cùng ghi {INDEX_ROOT}/{repo}/index_state.json: HEAD, thời điểm build,
  số node/cạnh theo loại, độ phủ doc, thống kê embedding và thời gian từng stage.
"""

import argparse
import sys
import os
import json
import logging
import time
import concurrent.futures
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# Thêm project root vào sys.path để import pipeline từ bất kỳ thư mục nào
sys.path.append(str(Path(__file__).parent.parent))

from pipeline.dataset_loader import load_swe_bench_lite, save_cache, load_cache
from pipeline.repo_manager import (
    clone_and_checkout, get_python_files, clone_from_url, get_source_files, index_dir_of,
)
from pipeline.ast_engine import ASTEngine
from pipeline.schemas import load_schema
from pipeline.neo4j_ingester import Neo4jIngester
import config

def _load_lang_config(lang: str) -> dict:
    if lang == "python":
        from pipeline.languages.python import python_extractor
        return {"extractor": python_extractor, "extensions": (".py",)}
    if lang == "swift":
        from pipeline.languages.swift import swift_extractor
        return {"extractor": swift_extractor, "extensions": (".swift",)}
    if lang == "javascript":
        from pipeline.languages.javascript import javascript_extractor
        return {"extractor": javascript_extractor, "extensions": (".js", ".mjs", ".cjs")}
    raise ValueError(f"Unsupported language: {lang}")

LANG_CONFIG = {
    "python":     {"extensions": (".py",)},
    "swift":      {"extensions": (".swift",)},
    "javascript": {"extensions": (".js", ".mjs", ".cjs")},
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


def _head_info(repo_path: str) -> dict:
    """Commit HEAD và remote của repo. Thư mục không phải git repo → các giá trị None."""
    try:
        from git import Repo
        repo = Repo(repo_path)
        head = repo.head.commit
        try:
            remote = repo.remotes.origin.url
        except Exception:
            remote = None
        return {
            "remote": remote,
            "head_sha": head.hexsha,
            "head_time": datetime.fromtimestamp(head.committed_date, timezone.utc).isoformat(),
        }
    except Exception:
        return {"remote": None, "head_sha": None, "head_time": None}


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
    extractor = _load_lang_config(lang)["extractor"]
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

    # Import ở đây, không ở đầu file: trên Windows mỗi worker của ProcessPoolExecutor import lại
    # file này, và các module dưới đây kéo theo scipy, scikit-learn, nltk, torch → hết RAM.
    from pipeline.doc_extractor import extract_docs
    from pipeline.embeddings import embed_nodes
    from pipeline.history import build_history, build_hunks
    from pipeline.issues import fetch_reports, github_slug, issue_links, load_issue_data, save_links

    schema = load_schema(config.ACTIVE_SCHEMA)
    logging.info(f"Active schema: {config.ACTIVE_SCHEMA!r}, lang: {lang!r}")
    timing: dict[str, float] = {}
    t_stage = time.perf_counter()

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
    timing["parse_resolve"] = time.perf_counter() - t_stage

    code_nodes = list({n["id"]: n for res in all_results for n in res["nodes"]}.values())

    # ── Stage 2b: Doc layer (chỉ repo Python) ────────────────────────────────
    # Cạnh Documents nối tên trong role/directive Sphinx với Function/Class Python.
    t_stage = time.perf_counter()
    docs = {"nodes": [], "edges": [], "stats": {}}
    if lang == "python":
        logging.info("Stage 2b: Extracting documentation layer...")
        docs = extract_docs(repo_path, code_nodes)
        s = docs["stats"]
        logging.info(f"Docs: {s['doc_files']} files, {s['chunks']} chunks, "
                     f"Documents {s['documents_edges']}/{s['pending_links']} resolved, "
                     f"References {s['references_edges']}")
    timing["docs"] = time.perf_counter() - t_stage

    # ── Stage 2c: Embeddings ─────────────────────────────────────────────────
    logging.info("Stage 2c: Embedding Function/Class/DocChunk nodes...")
    t_stage = time.perf_counter()
    idx_dir = index_dir_of(repo_path)
    embed_stats = embed_nodes(code_nodes + docs["nodes"], idx_dir)
    logging.info(f"Embeddings: {embed_stats['n']} nodes "
                 f"({embed_stats['encoded']} encoded, {embed_stats['reused']} from cache)")
    timing["embed"] = time.perf_counter() - t_stage

    # ── Stage 2d: History layer (chỉ repo Python có git) ─────────────────────
    t_stage = time.perf_counter()
    hist = {"nodes": [], "edges": [], "stats": {}}
    units = []
    head = _head_info(repo_path)
    if lang == "python" and head["head_sha"]:
        logging.info("Stage 2d: Building history layer (commits, touch sets, hunks)...")
        units, h_stats = build_history(repo_path, idx_dir)
        _, k_stats = build_hunks(repo_path, idx_dir, units)
        graph_fc = {n["id"] for n in code_nodes if n["labels"][0] in ("Function", "Class")}
        for u in units:
            targets = [f"{base_commit}:{k}" for k in u["touch"] if f"{base_commit}:{k}" in graph_fc]
            if not targets:
                continue
            cid = f"commit:{u['h']}"
            hist["nodes"].append({"labels": ["Commit"], "id": cid, "properties": {
                "sha": u["h"], "parent": u["p"], "merge": u["merge"], "message": u["msg"],
                "time": datetime.fromtimestamp(u["t"], timezone.utc).isoformat(),
                "n_touch": len(u["touch"]),
            }})
            hist["edges"] += [{"type": "Modifies", "source": cid, "target": t} for t in targets]
        hist["stats"] = {**h_stats, "hunks": k_stats["hunks"], "hunk_new_commits": k_stats["new_commits"],
                         "hunk_seconds": k_stats["seconds"], "commit_nodes": len(hist["nodes"])}
        logging.info(f"History: {h_stats['commits']} commits ({h_stats['new']} new), "
                     f"{h_stats['with_touch']} touch a function/class, {k_stats['hunks']} hunks, "
                     f"{len(hist['nodes'])} Commit nodes")
    timing["history"] = time.perf_counter() - t_stage

    # ── Stage 2e: Issue layer (repo trên GitHub) ─────────────────────────────
    t_stage = time.perf_counter()
    issues = {"nodes": [], "edges": [], "stats": {}}
    slug = github_slug(head["remote"])
    if units and slug:
        logging.info(f"Stage 2e: Fetching closed issues/PRs of {slug} and linking them to commits...")
        try:
            fetch = fetch_reports(slug, idx_dir)
        except Exception as e:                      # mạng lỗi: dùng báo cáo đã tải trước đó (nếu có)
            logging.warning(f"Issue fetch failed: {e}")
            fetch = {"complete": False, "error": str(e)}
        reports, _ = load_issue_data(idx_dir)
        links = issue_links(units, reports, slug)
        save_links(idx_dir, links)
        commit_ids = {n["id"] for n in hist["nodes"]}
        rep = {r["n"]: r for r in reports if not r["pr"]}
        seen = set()
        for (n, h), _ty in sorted(links.items()):
            if n not in rep or f"commit:{h}" not in commit_ids:
                continue
            iid = f"issue:{n}"
            if iid not in seen:
                seen.add(iid)
                r = rep[n]
                issues["nodes"].append({"labels": ["Issue"], "id": iid, "properties": {
                    "number": n, "title": r["title"], "body": r["body"], "url": r.get("url", ""),
                    "created": datetime.fromtimestamp(r["created"], timezone.utc).isoformat(),
                }})
            issues["edges"].append({"type": "Fixes", "source": f"commit:{h}", "target": iid})
        issues["stats"] = {"slug": slug, "fetch": fetch, "reports": len(reports),
                           "prs": sum(r["pr"] for r in reports), "links": len(links),
                           "issue_nodes": len(issues["nodes"]), "fixes_edges": len(issues["edges"])}
        logging.info(f"Issues: {len(reports)} reports ({issues['stats']['prs']} PRs), "
                     f"fetch complete={fetch.get('complete')}, {len(links)} links, "
                     f"{len(issues['nodes'])} Issue nodes")
    timing["issues"] = time.perf_counter() - t_stage
    t_stage = time.perf_counter()

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
    timing["community"] = time.perf_counter() - t_stage

    # ── Stage 4: Bulk Ingestion vào Neo4j ────────────────────────────────────
    logging.info("Stage 4: Bulk Loading to Neo4j...")
    t_stage = time.perf_counter()
    ingested = False
    try:
        ingester = Neo4jIngester()
        clear_graph(ingester)  # xóa graph cũ trước

        # Nạp tất cả nodes trước
        for res in all_results:
            for node in res["nodes"]:
                ingester.add_node(node)
        for node in docs["nodes"] + hist["nodes"] + issues["nodes"]:
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

        # Doc edges (HasChunk, Documents, References), history (Modifies) và issue (Fixes)
        for edge in docs["edges"] + hist["edges"] + issues["edges"]:
            ingester.add_edge(edge)

        ingester.flush()
        ingester.ensure_fulltext_index()
        ingester.close()
        ingested = True
        logging.info("Graph construction complete.")

    except Exception as e:
        logging.error(f"Failed to ingest to Neo4j: {e}")
    timing["ingest"] = time.perf_counter() - t_stage

    # ── Trạng thái index ─────────────────────────────────────────────────────
    all_nodes = code_nodes + docs["nodes"] + hist["nodes"] + issues["nodes"]
    all_edges = ([e for res in all_results for e in res["definite_edges"]]
                 + semantic_edges + docs["edges"] + hist["edges"] + issues["edges"])
    # Đếm cạnh như Neo4j lưu: MERGE bỏ cạnh trùng (type, source, target), MATCH bỏ cạnh
    # có đầu mút không phải node (vd import tới module ngoài repo).
    node_ids = {n["id"] for n in all_nodes}
    uniq_edges = {(e["type"], e["source"], e["target"]) for e in all_edges
                  if e["source"] in node_ids and e["target"] in node_ids}
    n_code = sum(1 for n in code_nodes if n["labels"][0] in ("Function", "Class"))
    documented = {e["target"] for e in docs["edges"] if e["type"] == "Documents"}
    state = {
        "repo_path": str(Path(repo_path).resolve()),
        **head,
        "id_prefix": base_commit,
        "lang": lang,
        "schema": config.ACTIVE_SCHEMA,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "neo4j_ingested": ingested,
        "files": {"source": len(source_files), "parsed": len(all_results),
                  "failed": len(files_to_parse) - len(all_results)},
        "nodes": dict(Counter(n["labels"][0] for n in all_nodes)),
        "edges": dict(Counter(t for t, _, _ in uniq_edges)),
        "edges_raw": len(all_edges),   # trước khi bỏ trùng và bỏ cạnh treo
        "docs": docs["stats"],
        "history": hist["stats"],
        "issues": issues["stats"],
        "doc_cov": round(len(documented) / n_code, 6) if n_code else 0.0,
        "embedding": embed_stats,
        "timing_s": {k: round(v, 1) for k, v in timing.items()},
    }
    idx_dir.mkdir(parents=True, exist_ok=True)
    (idx_dir / "index_state.json").write_text(json.dumps(state, indent=2, ensure_ascii=False),
                                             encoding="utf-8")
    logging.info(f"Index state → {idx_dir / 'index_state.json'}")


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


def handle_update(path: str) -> None:
    """
    Đưa repo đã build lên trạng thái mới nhất của nhánh hiện tại rồi build lại.

    Build lại dùng cache: embedding theo nội dung, history và hunk theo sha commit,
    issue theo tham số since. Kết quả của lần cập nhật được ghi thêm vào
    index_state.json ở khối last_update.
    """
    import subprocess
    idx_dir = index_dir_of(path)
    state_path = idx_dir / "index_state.json"
    if not state_path.exists():
        logging.error(f"{path} has not been built yet (no {state_path}). Run 'local' or 'url' first.")
        return
    old = json.loads(state_path.read_text(encoding="utf-8"))

    def _git(*args) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", path, *args], capture_output=True, text=True)

    before = _git("rev-parse", "HEAD").stdout.strip()
    if _git("remote").stdout.strip():
        pull = _git("pull", "--ff-only")
        if pull.returncode != 0:
            logging.error(f"git pull --ff-only failed, index not updated:\n{pull.stderr.strip()}")
            return
    else:
        logging.info("No git remote: building the working tree as it is.")
    after = _git("rev-parse", "HEAD").stdout.strip()
    n_new = _git("rev-list", "--count", "--first-parent", f"{before}..{after}").stdout.strip() \
        if before and after and before != after else "0"
    logging.info(f"HEAD {before[:8]} → {after[:8]} ({n_new} new first-parent commits)")

    write_current_state({"instance_id": old.get("remote") or path, "gt_files": []})
    build_graph_from_repo(path, base_commit=old.get("id_prefix", "local"), lang=old.get("lang", "python"))

    new = json.loads(state_path.read_text(encoding="utf-8"))
    emb = new.get("embedding", {})
    hist = new.get("history", {})
    fetch = new.get("issues", {}).get("fetch", {})
    new["last_update"] = {
        "head_before": before, "head_after": after, "new_first_parent_commits": int(n_new),
        "history_new_commits": hist.get("new"), "hunk_new_commits": hist.get("hunk_new_commits"),
        "embed_encoded": emb.get("encoded"), "embed_reused": emb.get("reused"),
        "embed_reuse_rate": round(emb["reused"] / emb["n"], 4) if emb.get("n") else None,
        "issue_new_rows": fetch.get("new_rows"), "issue_pages": fetch.get("pages"),
        "issue_fetch_complete": fetch.get("complete"),
    }
    state_path.write_text(json.dumps(new, indent=2, ensure_ascii=False), encoding="utf-8")
    logging.info(f"Update summary: {new['last_update']}")


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

    # Subcommand: update
    p_upd = subparsers.add_parser("update", help="Pull new commits of a built repo and rebuild incrementally")
    p_upd.add_argument("path", type=str, help="Path to the repo directory that was built before")

    args = parser.parse_args()
    if args.command == "update":
        handle_update(args.path)
    elif args.command == "swe-lite":
        handle_swe_lite(args.index)
    elif args.command == "local":
        handle_local(args.path, lang=args.lang)
    elif args.command == "url":
        handle_url(args.url, branch=args.branch, token=args.token, lang=args.lang)


if __name__ == "__main__":
    main()
