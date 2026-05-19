# =============================================================================
# app/neo4j_client.py — Read-only Neo4j client cho Streamlit UI
#
# Tách biệt với Neo4jIngester (write) — client này chỉ đọc dữ liệu
# đã được build_graph.py nạp vào. Kết nối một lần khi app khởi động.
#
# Các query đều dùng DISTINCT để tránh duplicate từ multi-path graph traversal.
# =============================================================================

import sys
import os
import logging

from neo4j import GraphDatabase

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
import config

logger = logging.getLogger(__name__)


class Neo4jClient:
    """
    Client đọc dữ liệu từ Neo4j cho Streamlit components.

    Kết nối được thử ngay khi khởi tạo — nếu fail, self.connected = False
    và mọi method trả về empty result thay vì raise exception.
    Điều này cho phép UI hiển thị thông báo lỗi thân thiện hơn.
    """

    def __init__(self):
        try:
            self.driver = GraphDatabase.driver(
                config.NEO4J_URI,
                auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
            )
            # verify_connectivity() thực sự mở kết nối để kiểm tra
            self.driver.verify_connectivity()
            self.connected = True
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            self.connected = False
            self.driver    = None

    def get_modules(self) -> list[str]:
        """
        Trả về danh sách tất cả Module nodes (= danh sách file đã parse).

        Dùng cho File View tab để hiển thị file list và highlight GT files.
        Sort theo file path để dễ duyệt.
        """
        if not self.connected:
            return []

        query = """
        MATCH (m:Module)
        RETURN m.name AS file_path
        ORDER BY file_path ASC
        """
        try:
            with self.driver.session() as session:
                result = session.run(query)
                return [record["file_path"] for record in result]
        except Exception as e:
            logger.error(f"Error fetching modules: {e}")
            return []

    def get_subgraph(self, seed_file: str, depth: int) -> dict:
        """
        Lấy subgraph xung quanh một module file cụ thể.

        Dùng variable-length path `[*0..depth]` để BFS depth bước.
        UNWIND nodes(path) để lấy tất cả node trong path, không chỉ endpoints.

        Hai queries riêng vì cần biết node IDs trước khi query edges.

        Args:
            seed_file: Tên file (vd: "django/db/models.py")
            depth:     Số bước BFS (1-4)

        Returns:
            {"nodes": [...], "edges": [...]}
        """
        if not self.connected:
            return {"nodes": [], "edges": []}

        # Query 1: lấy tất cả nodes trong radius depth quanh seed module
        node_query = f"""
        MATCH path = (m:Module {{name: $seed_file}})-[*0..{depth}]-(other)
        UNWIND nodes(path) AS n
        RETURN DISTINCT
            id(n)          AS neo_id,
            labels(n)[0]   AS label,
            n.id           AS identity,
            n.name         AS name,
            n.community    AS community
        """
        nodes_dict = {}
        try:
            with self.driver.session() as session:
                for record in session.run(node_query, seed_file=seed_file):
                    nid = record["neo_id"]
                    if nid not in nodes_dict:
                        nodes_dict[nid] = {
                            "id":        nid,
                            "identity":  record["identity"],
                            "label":     record["label"],
                            "name":      record["name"],
                            "community": record["community"],
                        }
        except Exception as e:
            logger.error(f"Error fetching subgraph nodes: {e}")
            return {"nodes": [], "edges": []}

        if not nodes_dict:
            return {"nodes": [], "edges": []}

        # Query 2: chỉ lấy edges giữa các nodes đã có trong subgraph
        node_ids = list(nodes_dict.keys())
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
                    edges.append({
                        "id":     record["rel_id"],
                        "type":   record["rel_type"],
                        "source": record["start_id"],
                        "target": record["end_id"],
                    })
        except Exception as e:
            logger.error(f"Error fetching subgraph edges: {e}")

        return {"nodes": list(nodes_dict.values()), "edges": edges}

    def get_full_graph(self) -> dict:
        """
        Lấy toàn bộ graph (tất cả nodes và edges).

        Dùng cho initial render của Graph View (Cypher LIMIT 2000 trong NeoVis).
        Có thể chậm trên repo lớn — Graph View dùng NeoVis trực tiếp thay vì method này.
        """
        if not self.connected:
            return {"nodes": [], "edges": []}

        nodes_dict = {}
        try:
            with self.driver.session() as session:
                for record in session.run(
                    "MATCH (n) RETURN DISTINCT id(n) AS neo_id, labels(n)[0] AS label, "
                    "n.id AS identity, n.name AS name, n.community AS community"
                ):
                    nid = record["neo_id"]
                    nodes_dict[nid] = {
                        "id":        nid,
                        "identity":  record["identity"],
                        "label":     record["label"],
                        "name":      record["name"],
                        "community": record["community"],
                    }
        except Exception as e:
            logger.error(f"Error fetching all nodes: {e}")
            return {"nodes": [], "edges": []}

        edges = []
        try:
            with self.driver.session() as session:
                for record in session.run(
                    "MATCH (a)-[r]->(b) RETURN DISTINCT id(r) AS rel_id, type(r) AS rel_type, "
                    "id(a) AS start_id, id(b) AS end_id"
                ):
                    edges.append({
                        "id":     record["rel_id"],
                        "type":   record["rel_type"],
                        "source": record["start_id"],
                        "target": record["end_id"],
                    })
        except Exception as e:
            logger.error(f"Error fetching all edges: {e}")

        return {"nodes": list(nodes_dict.values()), "edges": edges}

    def get_community_map(self) -> dict:
        """
        Trả về {neo4j_internal_id → community_int} cho mọi node có community.

        Dùng bởi Graph View để tô màu node theo community khi bật "Hiện Communities".
        Node không có community (vd: khi ENABLE_COMMUNITY_DETECTION=False) bị bỏ qua.
        """
        if not self.connected:
            return {}
        try:
            with self.driver.session() as session:
                result = session.run(
                    "MATCH (n) WHERE n.community IS NOT NULL "
                    "RETURN id(n) AS nid, n.community AS community"
                )
                return {record["nid"]: record["community"] for record in result}
        except Exception as e:
            logger.error(f"Error fetching community map: {e}")
            return {}


# Singleton — tạo một lần khi module được import, dùng chung cho toàn bộ Streamlit session
client = Neo4jClient()
