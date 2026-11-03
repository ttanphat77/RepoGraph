# =============================================================================
# pipeline/ranking.py - Index truy hồi và xếp hạng cho một repo đã build
#
# RepoIndex nạp node code và cạnh Calls từ Neo4j, cùng vector từ
# {index_dir}/node_vectors.npy, rồi dựng chỉ mục trong RAM.
#
#   ast_rank()      Xếp hạng AST (mục 4 pipeline_design.md): BM25Okapi trên mọi node
#                   code, cosine embedding trên Function/Class, gộp RRF, giữ hàm/lớp.
#   find_entities() Phần "Thực thể được nhắc": node trùng tên/đường dẫn mà regex
#                   trích từ prompt (kỹ thuật tra tên của retriever hiện có).
#   neighbors()     Caller và callee một bước qua cạnh Calls của một node.
#   doc_pool()      Pool bằng chứng DOC (mục 5): chunk có cạnh Documents xếp bằng RRF của
#                   BM25 và cosine, tính bên trong tập chunk đó. Graph không có cạnh
#                   Documents nào → xét mọi chunk (chưa được judge chấm).
#
# rrf_fuse() trộn danh sách AST với danh sách của các nguồn (mục 8): RRF gốc,
# mọi danh sách có trọng số 1. file_rank() xếp file theo điểm cao nhất của
# hàm/lớp trong file (SweRank).
#
# Mọi thứ tự đều tất định: node nạp theo id, sort ổn định, hòa điểm xếp theo id.
# =============================================================================

from __future__ import annotations

import json
import logging
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Callable

import numpy as np
from rank_bm25 import BM25Okapi

import config
from pipeline.retriever import extract_identifiers

logger = logging.getLogger(__name__)

CODE_LABELS = ("Module", "Class", "Function")
FC_LABELS = ("Function", "Class")
_LABEL_PRIORITY = {"Function": 0, "Class": 1, "Module": 2}

_CAMEL_RE = re.compile(r"([A-Z])")
_ALPHANUM_RE = re.compile(r"[a-zA-Z0-9]+")
_MD_CODEBLOCK_RE = re.compile(r"```.*?```", re.S)


def tokenize_code(text: str) -> list[str]:
    """Tách camelCase, đưa về chữ thường, lấy chuỗi chữ-số. "getUserName_v2" → get, user, name, v2."""
    return _ALPHANUM_RE.findall(_CAMEL_RE.sub(r" \1", text).lower())


def embed_query_text(query: str) -> str:
    """Query cho embedding: bỏ khối ``` (code dán trong issue), cắt ở EMBED_QUERY_CHARS ký tự."""
    return _MD_CODEBLOCK_RE.sub(" ", query)[:config.EMBED_QUERY_CHARS]


def _bm25_text(node: dict) -> str:
    """Văn bản BM25 của một node: source; source gần rỗng (Module) → label, name, file."""
    text = node.get("source") or ""
    if len(text.strip()) < 5:
        text = f"{node['label']} {node.get('name') or ''} {node.get('file') or ''}"
    return text


def _top_order(scores: np.ndarray, k: int) -> np.ndarray:
    """Chỉ số của k điểm cao nhất, giảm dần. Sort ổn định: hòa điểm giữ thứ tự node (theo id)."""
    return np.argsort(-scores, kind="stable")[:k]


def rrf_fuse(ast_ids: list[str], sources: dict[str, list[str]],
             k: int = config.RRF_K, limit: int = config.AST_DEPTH) -> list[dict]:
    """
    RRF gốc (Cormack, Clarke, Büttcher, SIGIR 2009), trọng số bằng nhau.

    score(d) = 1/(k + r_AST(d)) + Σ_s 1/(k + r_s(d)), hạng r bắt đầu từ 1.
    d không có trong một danh sách thì không nhận điểm từ danh sách đó.
    Hòa điểm xếp theo hạng AST (node ngoài AST đứng sau), rồi theo id.

    Returns:
        tối đa limit phần tử {"id", "score", "ranks": {"AST": r|None, <nguồn>: r|None}}.
    """
    lists = {"AST": ast_ids, **sources}
    rank = {name: {x: i for i, x in enumerate(lst, 1)} for name, lst in lists.items()}
    cand = list(dict.fromkeys(x for lst in lists.values() for x in lst))
    scored = []
    for x in cand:
        s = sum(1.0 / (k + r[x]) for r in rank.values() if x in r)
        scored.append((-s, rank["AST"].get(x, math.inf), x))
    scored.sort()
    return [{"id": x, "score": -neg, "ranks": {name: rank[name].get(x) for name in lists}}
            for neg, _, x in scored[:limit]]


def check_graph_matches(index_dir: Path, state: dict, neo4j_counts: dict[str, int]) -> None:
    """
    Báo lỗi khi Neo4j không giữ graph của index_dir: lần build không nạp xong vào Neo4j,
    hoặc số node theo nhãn trong Neo4j khác số node mà lần build đó ghi trong index_state.json.
    """
    if not state:
        raise ValueError(f"{index_dir} has no index_state.json. Build the repo first.")
    if not state.get("neo4j_ingested"):
        raise ValueError(f"The last build of {index_dir} did not load into Neo4j. Rebuild the repo.")
    if neo4j_counts != state.get("nodes"):
        raise ValueError(f"Neo4j holds a different graph than {index_dir} "
                         f"(Neo4j {neo4j_counts}, index {state.get('nodes')}). Rebuild or update this repo.")


def file_rank(items: list[dict], file_of: Callable[[str], str], limit: int | None = None) -> list[dict]:
    """
    Xếp file theo điểm cao nhất của hàm/lớp trong file (SweRank). items đã xếp giảm dần,
    nên thứ tự file là thứ tự xuất hiện đầu tiên.

    Returns:
        [{"file", "score", "best_pos" (vị trí 1-based của hàm/lớp tốt nhất), "best_id"}]
    """
    seen, out = set(), []
    for pos, it in enumerate(items, 1):
        f = file_of(it["id"])
        if f not in seen:
            seen.add(f)
            out.append({"file": f, "score": it["score"], "best_pos": pos, "best_id": it["id"]})
    return out[:limit] if limit else out


class RepoIndex:
    """Chỉ mục truy hồi trong RAM của một repo đã build."""

    def __init__(self, nodes: list[dict], call_edges: list[tuple[str, str]],
                 vec_ids: list[str], vecs: np.ndarray, state: dict | None = None,
                 encode_query: Callable[[str], np.ndarray] | None = None,
                 chunks: list[dict] | None = None, doc_edges: list[tuple[str, str]] | None = None):
        """
        Args:
            nodes:        node code {"id", "label", "name", "file", "start_line", "end_line", "source"}.
            call_edges:   cặp (caller, callee) của cạnh Calls.
            vec_ids, vecs: id và vector chuẩn hóa (node_ids.json, node_vectors.npy).
            state:        index_state.json của lần build.
            encode_query: hàm text → vector chuẩn hóa. Mặc định dùng model embedding của build.
            chunks:       DocChunk {"id", "file", "heading", "text"}.
            doc_edges:    cặp (chunk, hàm/lớp) của cạnh Documents.
        """
        self.state = state or {}
        self.warnings: list[str] = []
        self.nodes = sorted((n for n in nodes if n["label"] in CODE_LABELS), key=lambda n: n["id"])
        self.by_id = {n["id"]: n for n in self.nodes}
        self._encode = encode_query or _default_encoder
        self._q_memo: tuple[str, np.ndarray] | None = None

        code_corpus = [tokenize_code(_bm25_text(n)) for n in self.nodes]
        self.bm25 = BM25Okapi(code_corpus) if code_corpus else None   # BM25Okapi([]) chia cho 0

        # DOC: BM25 trên tập node code + chunk (như search_full của notebook), lấy điểm của chunk
        self.chunks = sorted(chunks or [], key=lambda c: c["id"])
        self.chunk_by_id = {c["id"]: c for c in self.chunks}
        self.doc_targets: dict[str, list[str]] = defaultdict(list)
        for c, t in sorted(doc_edges or []):
            if c in self.chunk_by_id and t in self.by_id:
                self.doc_targets[c].append(t)
        self.bm25_full = None
        if self.chunks:
            chunk_corpus = []
            for c in self.chunks:
                text = f"{c.get('heading') or ''} {c.get('text') or ''}".strip()
                chunk_corpus.append(tokenize_code(text if len(text) >= 5 else f"DocChunk {c['id']}"))
            self.bm25_full = BM25Okapi(code_corpus + chunk_corpus)

        row = {nid: i for i, nid in enumerate(vec_ids)}
        fc = [n["id"] for n in self.nodes if n["label"] in FC_LABELS]
        missing = [nid for nid in fc if nid not in row]
        if missing:
            self.warnings.append(f"{len(missing)} Function/Class không có vector "
                                 f"(graph và node_vectors.npy lệch nhau), ví dụ {missing[0]}")
        self.vec_ids = [nid for nid in fc if nid in row]
        self.vec_matrix = (vecs[[row[nid] for nid in self.vec_ids]] if self.vec_ids
                           else np.zeros((0, vecs.shape[1] if vecs.ndim == 2 else 0), dtype=np.float32))
        self.chunk_vec = {c["id"]: vecs[row[c["id"]]] for c in self.chunks if c["id"] in row}

        self.callees: dict[str, set[str]] = defaultdict(set)
        self.callers: dict[str, set[str]] = defaultdict(set)
        for a, b in call_edges:
            if a in self.by_id and b in self.by_id:
                self.callees[a].add(b)
                self.callers[b].add(a)

        # Bảng tra tên cho find_entities
        self._by_name: dict[str, list[str]] = defaultdict(list)
        self._modules: list[dict] = []
        for n in self.nodes:
            if n["label"] in FC_LABELS and n.get("name"):
                self._by_name[n["name"]].append(n["id"])
            elif n["label"] == "Module":
                self._modules.append(n)

    # ── Nạp từ build ─────────────────────────────────────────────────────────
    @classmethod
    def load(cls, index_dir: str | Path, driver=None) -> "RepoIndex":
        """
        Nạp node code và cạnh Calls từ Neo4j, vector và index_state.json từ index_dir.
        Neo4j chỉ giữ graph của một repo, nên trước hết kiểm graph trong Neo4j là graph của index_dir.
        """
        from neo4j import GraphDatabase
        index_dir = Path(index_dir)
        state_path = index_dir / "index_state.json"
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        own = driver is None
        if own:
            driver = GraphDatabase.driver(config.NEO4J_URI,
                                          auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
        try:
            with driver.session() as s:
                counts = {r["l"]: r["c"] for r in s.run(
                    "MATCH (n) RETURN labels(n)[0] AS l, count(*) AS c")}
                check_graph_matches(index_dir, state, counts)
                nodes = [dict(r) for r in s.run(
                    "MATCH (n) WHERE n:Module OR n:Class OR n:Function "
                    "RETURN n.id AS id, labels(n)[0] AS label, n.name AS name, "
                    "coalesce(n.file, n.name) AS file, n.start_line AS start_line, "
                    "n.end_line AS end_line, n.source AS source ORDER BY n.id")]
                calls = [(r["a"], r["b"]) for r in s.run(
                    "MATCH (a)-[:Calls]->(b) RETURN a.id AS a, b.id AS b ORDER BY a, b")]
                chunks = [dict(r) for r in s.run(
                    "MATCH (c:DocChunk) RETURN c.id AS id, c.file AS file, c.heading AS heading, "
                    "c.text AS text ORDER BY c.id")]
                docs = [(r["a"], r["b"]) for r in s.run(
                    "MATCH (a:DocChunk)-[:Documents]->(b) RETURN a.id AS a, b.id AS b ORDER BY a, b")]
        finally:
            if own:
                driver.close()
        vec_ids = json.loads((index_dir / "node_ids.json").read_text(encoding="utf-8"))
        vecs = np.load(index_dir / "node_vectors.npy")
        return cls(nodes, calls, vec_ids, vecs, state, chunks=chunks, doc_edges=docs)

    def _query_vec(self, query: str) -> np.ndarray:
        """Vector của query, nhớ lại cho lần gọi kế tiếp với cùng query (ast_rank rồi doc_pool).
        Đọc và ghi memo qua biến cục bộ, vì nhiều luồng có thể dùng chung một RepoIndex."""
        memo = self._q_memo
        if memo is None or memo[0] != query:
            memo = (query, self._encode(embed_query_text(query)))
            self._q_memo = memo
        return memo[1]

    # ── Xếp hạng AST ─────────────────────────────────────────────────────────
    def ast_rank(self, query: str, depth: int = config.AST_DEPTH) -> list[dict]:
        """
        Xếp hạng AST, mốc chỉ dùng code (mục 4 pipeline_design.md).

        1. BM25 trên mọi node code (kể cả Module), query tách bằng tokenize_code.
        2. Cosine giữa embedding của query (embed_query_text) và Function/Class.
        3. Lấy depth node đầu của mỗi danh sách. Điểm = Σ 1/(RRF_K + r), r bắt đầu từ 0.
           Hòa điểm xếp theo id.
        4. Giữ depth node đầu sau khi gộp, rồi chỉ giữ Function/Class.

        Returns:
            [{"id", "score", "bm25_rank", "bm25_score", "vec_rank", "cos"}], hạng 1-based,
            None khi node không nằm trong depth node đầu của tín hiệu đó.
        """
        if self.bm25 is None:            # repo không có node code
            return []
        bm = self.bm25.get_scores(tokenize_code(query))
        q = self._query_vec(query)
        cos = self.vec_matrix @ q if len(self.vec_ids) else np.zeros(0)

        bm_top = _top_order(bm, min(depth, len(self.nodes)))
        vec_top = _top_order(cos, min(depth, len(self.vec_ids)))
        bm_rank = {self.nodes[i]["id"]: r for r, i in enumerate(bm_top)}
        vec_rank = {self.vec_ids[i]: r for r, i in enumerate(vec_top)}
        bm_score = {n["id"]: float(bm[i]) for i, n in enumerate(self.nodes)}
        cos_of = {nid: float(cos[i]) for i, nid in enumerate(self.vec_ids)}

        k = config.RRF_K
        cand = set(bm_rank) | set(vec_rank)
        fused = sorted(
            ((-(1.0 / (k + bm_rank[x]) if x in bm_rank else 0.0)
              - (1.0 / (k + vec_rank[x]) if x in vec_rank else 0.0), x) for x in cand))
        out = []
        for neg, x in fused[:depth]:
            if self.by_id[x]["label"] not in FC_LABELS:
                continue
            out.append({
                "id": x, "score": -neg,
                "bm25_rank": bm_rank[x] + 1 if x in bm_rank else None,
                "bm25_score": bm_score[x],
                "vec_rank": vec_rank[x] + 1 if x in vec_rank else None,
                "cos": cos_of.get(x),
            })
        return out

    # ── Pool bằng chứng DOC ──────────────────────────────────────────────────
    def doc_pool(self, query: str, n: int = config.EVID_POOL_N) -> dict:
        """
        Xếp chunk bằng RRF của hạng BM25 và hạng cosine, tính bên trong tập chunk được xét
        (hạng bắt đầu từ 0, như search_doc của notebook). Hòa điểm xếp theo id.
        Tập chunk = chunk có cạnh Documents; graph không có cạnh Documents nào → mọi chunk.

        Returns:
            {"pool": "doc_cand" | "doc_cand_all", "items": [{"id", "file", "heading", "text",
             "score", "bm25", "cos", "targets"}]}
        """
        ids = [c["id"] for c in self.chunks if c["id"] in self.doc_targets]
        pool = "doc_cand"
        if not ids:
            ids, pool = [c["id"] for c in self.chunks], "doc_cand_all"
        if not ids or self.bm25_full is None:
            return {"pool": pool, "items": []}
        full = self.bm25_full.get_scores(tokenize_code(query))
        off = len(self.nodes)
        pos = {c["id"]: off + i for i, c in enumerate(self.chunks)}
        q = self._query_vec(query)
        bm = [float(full[pos[c]]) for c in ids]
        vs = [float(self.chunk_vec[c] @ q) if c in self.chunk_vec else 0.0 for c in ids]
        r_bm = {i: r for r, i in enumerate(sorted(range(len(ids)), key=lambda i: -bm[i]))}
        r_vs = {i: r for r, i in enumerate(sorted(range(len(ids)), key=lambda i: -vs[i]))}
        k = config.RRF_K
        scored = sorted(range(len(ids)), key=lambda i: (-(1.0 / (k + r_bm[i]) + 1.0 / (k + r_vs[i])), ids[i]))
        items = []
        for i in scored[:n]:
            c = self.chunk_by_id[ids[i]]
            items.append({"id": c["id"], "file": c.get("file"), "heading": c.get("heading") or "",
                          "text": c.get("text") or "", "score": 1.0 / (k + r_bm[i]) + 1.0 / (k + r_vs[i]),
                          "bm25": bm[i], "cos": vs[i], "targets": list(self.doc_targets.get(c["id"], []))})
        return {"pool": pool, "items": items}

    # ── Thực thể được nhắc trong prompt ──────────────────────────────────────
    def find_entities(self, prompt: str, limit: int = config.ENTITY_LIMIT) -> dict:
        """
        Node trùng tên hoặc đường dẫn mà regex trích từ prompt (extract_identifiers).

        - Tên khớp đúng name của Function/Class → match "name".
        - Đường dẫn (vd src/flask/app.py) hoặc tên file trần (vd app, lấy từ đường dẫn)
          khớp Module có path bằng nó hoặc kết thúc bằng "/<tên>.py" → match "file".
        Thứ tự: Function, rồi Class, rồi Module, rồi id. Giữ limit node.

        Returns:
            {"candidates": [...], "total": số node khớp, "items": [node + matched + match]}
        """
        cands = extract_identifiers(prompt)
        found: dict[str, dict] = {}
        for c in cands:
            for nid in self._by_name.get(c, []):
                found.setdefault(nid, {"matched": c, "match": "name"})
            for m in self._modules:
                path = m["file"] or m["name"] or ""
                if path == c or path.endswith(f"/{c}") or path == f"{c}.py" or path.endswith(f"/{c}.py"):
                    found.setdefault(m["id"], {"matched": c, "match": "file"})
        order = sorted(found, key=lambda nid: (_LABEL_PRIORITY[self.by_id[nid]["label"]], nid))
        items = [{**self.brief(nid), **found[nid]} for nid in order[:limit]]
        return {"candidates": cands, "total": len(found), "items": items}

    # ── Caller và callee ─────────────────────────────────────────────────────
    def neighbors(self, node_id: str, ast_pos: dict[str, int],
                  limit: int = config.NEIGHBOR_LIMIT) -> dict:
        """
        Caller và callee một bước qua cạnh Calls, chỉ tên và vị trí.
        Xếp theo hạng AST (node ngoài danh sách AST đứng sau), rồi theo id.

        Returns:
            {"callers": [...], "callees": [...], "n_callers", "n_callees"} - mỗi phần tử là
            brief(node) kèm ast_rank.
        """
        def _side(ids):
            ordered = sorted(ids, key=lambda x: (ast_pos.get(x, math.inf), x))
            return [{**self.brief(x), "ast_rank": ast_pos.get(x)} for x in ordered[:limit]]
        callers, callees = self.callers.get(node_id, set()), self.callees.get(node_id, set())
        return {"callers": _side(callers), "callees": _side(callees),
                "n_callers": len(callers), "n_callees": len(callees)}

    # ── Tiện ích ─────────────────────────────────────────────────────────────
    def brief(self, node_id: str) -> dict:
        """Định danh và vị trí của node, không kèm source."""
        n = self.by_id[node_id]
        return {"id": node_id, "label": n["label"], "name": n.get("name"),
                "file": n.get("file"), "start_line": n.get("start_line"), "end_line": n.get("end_line")}

    def file_of(self, node_id: str) -> str:
        return self.by_id[node_id].get("file") or ""


def _default_encoder(text: str) -> np.ndarray:
    """Encode query bằng model embedding của build (cùng model, cùng chuẩn hóa)."""
    from pipeline.embeddings import _get_model
    model = _get_model()[0]
    return model.encode([text], normalize_embeddings=True, convert_to_numpy=True)[0].astype(np.float32)
