"""
pipeline/retriever.py — GraphRAG Retriever

Triển khai Bước 3 theo hướng dẫn GraphRAG cho Source Code:

  Bước 3a — Entity Resolution:
      Trích identifier (tên class, function, file) từ issue text bằng regex.
      Không dùng LLM ở bước này → nhanh, miễn phí, deterministic.

  Bước 3b — Seed Lookup:
      Tìm node trong Neo4j khớp với identifier vừa trích.
      Ưu tiên Function/Method (signal cao) hơn Class hơn Module.

  Bước 3c — Neighborhood Extraction:
      BFS depth bước quanh seed nodes — lấy cả Callers (ai gọi seed)
      lẫn Callees (seed gọi đến ai). Đây là điểm mấu chốt so với
      vector search thuần túy: nắm được luồng thực thi.

  Bước 3d — Context Building:
      Gộp source code của các node theo thứ tự ưu tiên:
        [SEED] → [CALLER] → [CALLEE] → [node khác]
      Context này sẽ được đưa vào LLM ở bước Generation.
"""

from __future__ import annotations

import logging
import re
from collections import Counter

from neo4j import GraphDatabase

import config

logger = logging.getLogger(__name__)

# ── Regex patterns để trích identifier từ issue text ─────────────────────────

# PascalCase: `QuerySet`, `AuthBackend` — khả năng cao là tên class
_RE_PASCAL = re.compile(r'\b[A-Z][a-zA-Z0-9]{2,}\b')

# snake_case có ít nhất 2 phần: `get_user`, `process_payment` — khả năng cao là tên function
_RE_SNAKE  = re.compile(r'\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b')

# Tên được quote: `foo`, 'bar', "baz" — signal cao nhất (developer cố ý đề cập)
_RE_QUOTED = re.compile(r'[`\'"]([a-zA-Z_][a-zA-Z0-9_]*)[`\'"]')

# File path: `django/db/models.py` — tìm file cụ thể
_RE_FILEPATH = re.compile(r'[\w/]+\.py')

# Tên quá phổ biến hoặc là Python keywords → bỏ qua để tránh flood false positives
_STOPWORDS = frozenset({
    "None", "True", "False", "Error", "Exception", "Type", "List", "Dict",
    "Set", "Tuple", "Optional", "Union", "Any", "Self", "Base", "Mixin",
    "Test", "Tests", "String", "Integer", "Float", "Boolean",
    "The", "This", "That", "For", "With", "From", "Import", "Class",
    "Return", "Raise", "Yield", "Async", "Await",
})

# Giới hạn source code trong context để tránh quá tải LLM context window
_SOURCE_TRUNCATE = 3000  # ký tự tối đa mỗi node

# Cap tổng số node trong subgraph để tránh query quá chậm trên repo lớn
_MAX_NODES = 60


class GraphRetriever:
    """
    Retriever kết nối Neo4j để thực hiện graph-based retrieval.

    Mỗi request tạo một session Neo4j riêng. Không thread-safe — dùng
    một instance per Streamlit request.
    """

    def __init__(self):
        self.driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
        )
        self._ensure_fulltext_index()

    def close(self) -> None:
        """Đóng kết nối Neo4j driver. Gọi sau khi xong request."""
        self.driver.close()

    # ── Public API ────────────────────────────────────────────────────────────

    def retrieve(self, issue_text: str, depth: int = 2) -> dict:
        """
        Thực hiện full retrieval pipeline từ issue text.

        Args:
            issue_text: Nội dung issue/bug report
            depth:      Số bước BFS mở rộng subgraph (1-3)

        Returns:
            dict gồm:
              candidates      — list identifier trích từ issue
              seed_nodes      — list node Neo4j khớp với identifier
              subgraph        — {nodes, edges} trong vùng lân cận
              context         — chuỗi source code cho LLM
              candidate_files — danh sách file path xếp hạng theo relevance
        """
        # Step 1a — Entity Resolution (regex)
        candidates = self._extract_identifiers(issue_text)
        logger.info(f"Extracted {len(candidates)} identifier candidates: {candidates[:20]}")

        # Step 1b — BM25 seed lookup (fallback + supplement khi regex thiếu)
        bm25_nodes = self._bm25_seeds(issue_text)
        logger.info(f"BM25 returned {len(bm25_nodes)} seed nodes.")

        # Step 2 — Regex Seed Lookup + merge với BM25
        regex_nodes = self._find_seeds(candidates) if candidates else []
        logger.info(f"Regex found {len(regex_nodes)} seed nodes in graph.")

        # Dedup theo neo_id — regex seeds ưu tiên (exact match), BM25 bổ sung
        seen_ids: set[int] = {n["neo_id"] for n in regex_nodes}
        extra = [n for n in bm25_nodes if n["neo_id"] not in seen_ids]
        seed_nodes = regex_nodes + extra
        logger.info(f"Combined seed nodes: {len(seed_nodes)} (regex={len(regex_nodes)}, bm25_new={len(extra)}).")

        # Step 3 — Neighborhood BFS
        subgraph = (
            self._expand_neighborhood(seed_nodes, depth)
            if seed_nodes
            else {"nodes": [], "edges": []}
        )
        logger.info(f"Subgraph: {len(subgraph['nodes'])} nodes, {len(subgraph['edges'])} edges.")

        # Step 4 — Context + file ranking
        seed_ids = {n["neo_id"] for n in seed_nodes}
        context  = self._build_context(subgraph, seed_ids)
        files    = self._rank_files(subgraph, seed_ids)

        return {
            "candidates":      candidates,
            "seed_nodes":      seed_nodes,
            "subgraph":        subgraph,
            "context":         context,
            "candidate_files": files,
        }

    # ── Index setup ───────────────────────────────────────────────────────────

    def _ensure_fulltext_index(self) -> None:
        """Tạo fulltext index nếu chưa có — idempotent, an toàn gọi nhiều lần."""
        query = f"""
        CREATE FULLTEXT INDEX {config.FULLTEXT_INDEX_NAME} IF NOT EXISTS
        FOR (n:Function|Class|FUNCTION|METHOD|CLASS)
        ON EACH [n.name, n.source]
        OPTIONS {{ indexConfig: {{ `fulltext.analyzer`: 'english' }} }}
        """
        try:
            with self.driver.session() as session:
                session.run(query)
        except Exception as e:
            logger.warning(f"Could not ensure fulltext index: {e}")

    # ── Step 1: Entity Resolution ─────────────────────────────────────────────

    def _extract_identifiers(self, text: str) -> list[str]:
        """
        Trích identifier từ issue text dùng regex — không cần LLM.

        Ưu tiên:
          1. Quoted identifiers — developer cố ý đề cập (`foo`)
          2. File paths — signal rõ ràng nhất (django/db/models.py)
          3. PascalCase — khả năng cao là tên class
          4. snake_case — khả năng cao là tên function

        Lọc qua _STOPWORDS để loại false positives phổ biến.
        """
        found: set[str] = set()

        # PascalCase → likely class names
        found.update(m for m in _RE_PASCAL.findall(text) if m not in _STOPWORDS)

        # snake_case → likely function/method names
        found.update(_RE_SNAKE.findall(text))

        # Quoted identifiers → highest signal (dev mentions explicitly)
        for m in _RE_QUOTED.findall(text):
            if len(m) > 2:
                found.add(m)

        # File paths → trích module name và giữ nguyên path
        for fp in _RE_FILEPATH.findall(text):
            base = fp.split("/")[-1].replace(".py", "")
            if base and base not in _STOPWORDS:
                found.add(base)
            found.add(fp)  # giữ nguyên path để match node.file

        return sorted(found)

    # ── Step 1b: BM25 seed lookup ─────────────────────────────────────────────

    def _bm25_seeds(self, issue_text: str) -> list[dict]:
        """
        Tìm seed nodes bằng BM25 fulltext search trên name + source.

        Bổ sung cho regex seeds: bắt được các hàm liên quan đến issue
        ngay cả khi issue không đề cập tên identifier chính xác.

        Lucene query escaping: các ký tự đặc biệt (+, -, &&, ||, !, (, ),
        {, }, [, ], ^, ", ~, *, ?, :, /) cần escape để tránh parse error.
        Dùng phrase query đơn giản — chỉ giữ lại chữ cái và khoảng trắng.
        """
        # Strip Lucene special chars để tránh query parse error
        safe_query = re.sub(r'[+\-&|!(){}\[\]^"~*?:\\/]', ' ', issue_text)
        safe_query = ' '.join(safe_query.split())  # collapse whitespace

        if not safe_query:
            return []

        cypher = """
        CALL db.index.fulltext.queryNodes($index_name, $search_query)
        YIELD node, score
        RETURN
            id(node)              AS neo_id,
            labels(node)[0]       AS label,
            node.id               AS identity,
            node.name             AS name,
            node.file             AS file,
            node.start_line       AS start_line,
            node.end_line         AS end_line,
            node.source           AS source,
            score
        ORDER BY score DESC
        LIMIT $limit
        """
        try:
            with self.driver.session() as session:
                result = session.run(
                    cypher,
                    index_name=config.FULLTEXT_INDEX_NAME,
                    search_query=safe_query,
                    limit=config.BM25_SEED_LIMIT,
                )
                return [dict(r) for r in result]
        except Exception as e:
            logger.warning(f"BM25 seed lookup failed: {e}")
            return []

    # ── Step 2: Seed Lookup ───────────────────────────────────────────────────

    def _find_seeds(self, candidates: list[str]) -> list[dict]:
        """
        Tìm nodes trong Neo4j khớp với identifier candidates.

        Match theo:
          - n.name = cand       (tên chính xác)
          - n.file = cand       (file path chính xác)
          - n.file ENDS WITH    (basename match)

        ORDER BY label priority: Function/Method trước (signal cao nhất
        khi issue đề cập tên hàm cụ thể), rồi Class, rồi Module.

        LIMIT 30 để tránh quá nhiều seed nodes làm loãng context.
        """
        query = """
        UNWIND $names AS cand
        MATCH (n)
        WHERE n.name = cand OR n.file = cand OR n.file ENDS WITH ('/' + cand + '.py')
        RETURN DISTINCT
            id(n)              AS neo_id,
            labels(n)[0]       AS label,
            n.id               AS identity,
            n.name             AS name,
            n.file             AS file,
            n.start_line       AS start_line,
            n.end_line         AS end_line,
            n.source           AS source
        ORDER BY
            CASE labels(n)[0]
                WHEN 'Function' THEN 0
                WHEN 'METHOD'   THEN 0
                WHEN 'Class'    THEN 1
                WHEN 'CLASS'    THEN 1
                ELSE 2
            END
        LIMIT 30
        """
        try:
            with self.driver.session() as session:
                result = session.run(query, names=candidates)
                return [dict(r) for r in result]
        except Exception as e:
            logger.error(f"Seed lookup error: {e}")
            return []

    # ── Step 3: Neighborhood BFS ──────────────────────────────────────────────

    def _expand_neighborhood(self, seed_nodes: list[dict], depth: int) -> dict:
        """
        Mở rộng đồ thị con quanh seed nodes bằng BFS depth bước.

        Duyệt theo mọi hướng (cả Callers lẫn Callees) để nắm luồng thực thi:
          - Callers: ai đang gọi function này → biết context sử dụng
          - Callees: function này gọi gì → biết nó làm gì

        Đây là ưu điểm cốt lõi của Graph RAG so với vector search:
        vector search tìm "đoạn code tương tự" còn graph search tìm
        "đoạn code có quan hệ thực thi".

        Hai queries riêng biệt vì Neo4j không cho biết node IDs trước
        khi chạy edge query:
          1. Lấy tất cả nodes trong radius depth
          2. Lấy tất cả edges giữa các nodes đó
        """
        seed_ids = [n["neo_id"] for n in seed_nodes]

        # Query 1: BFS nodes — [*0..depth] là Cypher syntax cho variable-length path
        node_query = f"""
        UNWIND $seed_ids AS sid
        MATCH path = (seed)-[*0..{depth}]-(neighbor)
        WHERE id(seed) = sid
        UNWIND nodes(path) AS n
        RETURN DISTINCT
            id(n)        AS neo_id,
            labels(n)[0] AS label,
            n.id         AS identity,
            n.name       AS name,
            n.file       AS file,
            n.start_line AS start_line,
            n.end_line   AS end_line,
            n.source     AS source
        LIMIT {_MAX_NODES}
        """

        nodes = []
        try:
            with self.driver.session() as session:
                for record in session.run(node_query, seed_ids=seed_ids):
                    nodes.append(dict(record))
        except Exception as e:
            logger.error(f"Neighborhood node query error: {e}")
            return {"nodes": [], "edges": []}

        if not nodes:
            return {"nodes": [], "edges": []}

        # Query 2: chỉ lấy edges giữa các nodes đã có trong subgraph
        # Điều này đảm bảo không lấy edges ra ngoài vùng đã fetch
        node_ids = [n["neo_id"] for n in nodes]
        edge_query = """
        MATCH (a)-[r]->(b)
        WHERE id(a) IN $node_ids AND id(b) IN $node_ids
        RETURN DISTINCT
            id(r)    AS rel_id,
            type(r)  AS rel_type,
            id(a)    AS start_id,
            id(b)    AS end_id
        """
        edges = []
        try:
            with self.driver.session() as session:
                for record in session.run(edge_query, node_ids=node_ids):
                    edges.append(dict(record))
        except Exception as e:
            logger.error(f"Neighborhood edge query error: {e}")

        return {"nodes": nodes, "edges": edges}

    # ── Step 4: Context Building ──────────────────────────────────────────────

    def _build_context(self, subgraph: dict, seed_ids: set[int]) -> str:
        """
        Xây dựng chuỗi context source code cho LLM.

        Xếp node theo thứ tự ưu tiên:
          [SEED]    — khớp trực tiếp với issue → quan trọng nhất
          [CALLER]  — ai gọi seed → biết luồng đến từ đâu
          [CALLEE]  — seed gọi đến ai → biết seed làm gì tiếp theo
          [label]   — node còn lại trong subgraph

        Format mỗi node:
          {tag} `{name}` — {file}:{start_line}-{end_line}
          ```python
          {source code}
          ```

        Node không có source code (Module nodes) bị bỏ qua — chỉ có
        Class/Function mới có source để đưa vào context.
        """
        if not subgraph["nodes"]:
            return ""

        # Xác định caller/callee sets từ edge directions
        callee_ids: set[int] = set()  # seed → callee
        caller_ids: set[int] = set()  # caller → seed

        for edge in subgraph["edges"]:
            if edge["start_id"] in seed_ids:
                callee_ids.add(edge["end_id"])
            if edge["end_id"] in seed_ids:
                caller_ids.add(edge["start_id"])

        # Sắp xếp: seed (0) → caller/callee (1) → context (2)
        def _priority(node):
            nid = node["neo_id"]
            if nid in seed_ids:             return 0
            if nid in caller_ids or nid in callee_ids: return 1
            return 2

        ordered = sorted(subgraph["nodes"], key=_priority)

        sections: list[str] = []
        for node in ordered:
            source = (node.get("source") or "").strip()
            if not source:
                continue  # skip nodes không có source (vd: Module)

            nid   = node["neo_id"]
            label = node.get("label", "Node")
            name  = node.get("name", "?")
            file  = node.get("file", "")
            s_ln  = node.get("start_line", "")
            e_ln  = node.get("end_line", "")

            # Tag giúp LLM hiểu vai trò của mỗi đoạn code
            if nid in seed_ids:             tag = "[SEED]"
            elif nid in caller_ids:         tag = "[CALLER]"
            elif nid in callee_ids:         tag = "[CALLEE]"
            else:                           tag = f"[{label}]"

            loc    = f"{file}:{s_ln}-{e_ln}" if s_ln else file
            header = f"{tag} `{name}` — {loc}"
            code   = source[:_SOURCE_TRUNCATE]

            sections.append(f"{header}\n```python\n{code}\n```")

        return "\n\n---\n\n".join(sections)

    # ── File ranking ──────────────────────────────────────────────────────────

    def _rank_files(self, subgraph: dict, seed_ids: set[int]) -> list[str]:
        """
        Xếp hạng file theo độ liên quan với issue.

        Scoring:
          - File chứa seed node: +3 điểm (trực tiếp liên quan)
          - File chứa node khác trong subgraph: +1 điểm

        File có nhiều điểm nhất → khả năng cần sửa cao nhất.
        Dùng Counter.most_common() để sort theo score.
        """
        score: Counter = Counter()
        for node in subgraph["nodes"]:
            f = node.get("file")
            if not f:
                continue
            # Seed nodes có weight cao hơn để ưu tiên file chứa entity được đề cập
            weight = 3 if node["neo_id"] in seed_ids else 1
            score[f] += weight

        return [f for f, _ in score.most_common()]
