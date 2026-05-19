# =============================================================================
# pipeline/neo4j_ingester.py — Ghi nodes và edges vào Neo4j theo batch
#
# Thiết kế:
#   - Dùng MERGE thay INSERT để đảm bảo idempotency (chạy lại không nhân bản)
#   - Batch write: gom node/edge trong memory, flush theo ngưỡng NEO4J_BATCH_SIZE
#   - Tách flush nodes và flush edges: nodes phải tồn tại trước khi tạo edges
#     (MATCH endpoint trong edge query sẽ fail nếu node chưa có)
#   - Group theo label/edge type: mỗi batch dùng cùng một Cypher template
#     → tránh MERGE dynamic label (không được phép trong Neo4j)
#
# Thứ tự ghi bắt buộc trong build_graph.py:
#   1. add_node() tất cả nodes → flush() → (lúc này mọi node đã có trong DB)
#   2. add_edge() tất cả edges → flush()
# =============================================================================

import logging
from collections import defaultdict

from neo4j import GraphDatabase

import config

logger = logging.getLogger(__name__)


class Neo4jIngester:
    """
    Writer batch cho Neo4j. Không thread-safe — dùng một instance per process.

    Workflow:
        ingester = Neo4jIngester()
        for node in nodes: ingester.add_node(node)
        ingester.flush()       # phải flush nodes trước khi add edges
        for edge in edges: ingester.add_edge(edge)
        ingester.flush()
        ingester.close()
    """

    def __init__(self):
        self.driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
        )
        # Gom nodes theo primary label để batch cùng loại với nhau.
        # defaultdict(list): key=label, value=list of property dicts
        self.node_batch: defaultdict[str, list] = defaultdict(list)

        # Gom edges theo relationship type
        self.edge_batch: defaultdict[str, list] = defaultdict(list)

        self.batch_size = config.NEO4J_BATCH_SIZE

    def close(self) -> None:
        """Flush dữ liệu còn lại rồi đóng kết nối driver."""
        self.flush()
        self.driver.close()

    def add_node(self, node_dict: dict) -> None:
        """
        Thêm một node vào batch. Flush tự động nếu batch đầy.

        node_dict format:
            {"labels": ["Class"], "id": "...", "properties": {...}}

        Chỉ lấy labels[0] làm primary label vì Neo4j MERGE cần label cố định
        trong query template. Multi-label có thể thêm bằng SET sau.
        """
        primary_label = node_dict["labels"][0]
        # Đưa "id" vào properties để MERGE dùng làm unique key
        props = node_dict["properties"].copy()
        props["id"] = node_dict["id"]

        self.node_batch[primary_label].append(props)

        # Flush ngay nếu batch đạt ngưỡng — tránh OOM với repo lớn
        if len(self.node_batch[primary_label]) >= self.batch_size:
            self._flush_nodes(primary_label)

    def add_edge(self, edge_dict: dict) -> None:
        """
        Thêm một edge vào batch. Flush tự động nếu batch đầy.

        edge_dict format:
            {"type": "Calls", "source": "...", "target": "...", "line": 42}

        Thuộc tính "line" là optional — chỉ có ở Calls edges.
        """
        edge_type = edge_dict["type"]
        entry = {
            "source": edge_dict["source"],
            "target": edge_dict["target"],
        }
        if "line" in edge_dict:
            entry["line"] = edge_dict["line"]

        self.edge_batch[edge_type].append(entry)

        if len(self.edge_batch[edge_type]) >= self.batch_size:
            self._flush_edges(edge_type)

    def flush(self) -> None:
        """Flush toàn bộ dữ liệu còn trong buffer ra Neo4j."""
        for label in list(self.node_batch.keys()):
            if self.node_batch[label]:
                self._flush_nodes(label)
        for rel_type in list(self.edge_batch.keys()):
            if self.edge_batch[rel_type]:
                self._flush_edges(rel_type)

    def _flush_nodes(self, label: str) -> None:
        """
        Ghi batch nodes có cùng label vào Neo4j dùng MERGE.

        MERGE (n:Label {id: row.id}) đảm bảo idempotency:
          - Nếu node đã tồn tại → update properties (SET n += row)
          - Nếu chưa tồn tại → tạo mới

        Dùng UNWIND để gửi cả batch trong một round-trip thay vì N queries.
        """
        batch = self.node_batch[label]
        query = f"""
        UNWIND $batch AS row
        MERGE (n:{label} {{id: row.id}})
        SET n += row
        """
        try:
            with self.driver.session() as session:
                session.run(query, batch=batch)
            logger.info(f"Ingested {len(batch)} {label} nodes.")
        except Exception as e:
            logger.error(f"Failed to ingest nodes ({label}): {e}")
        finally:
            # Xóa batch dù thành công hay thất bại để tránh retry vô hạn
            self.node_batch[label] = []

    def _flush_edges(self, edge_type: str) -> None:
        """
        Ghi batch edges có cùng type vào Neo4j dùng MATCH + MERGE.

        Dùng MATCH thay MERGE cho endpoints: nodes đã phải tồn tại trước.
        MERGE trên relationship để tránh duplicate edges khi chạy lại pipeline.

        FOREACH trick: gán line chỉ khi row.line không null.
        Không thể dùng SET r.line = row.line vì Neo4j không cho SET null property.
        """
        batch = self.edge_batch[edge_type]
        query = f"""
        UNWIND $batch AS row
        MATCH (s {{id: row.source}})
        MATCH (t {{id: row.target}})
        MERGE (s)-[r:{edge_type}]->(t)
        FOREACH (_ IN CASE WHEN row.line IS NOT NULL THEN [1] ELSE [] END
                 | SET r.line = row.line)
        """
        try:
            with self.driver.session() as session:
                session.run(query, batch=batch)
            logger.info(f"Ingested {len(batch)} {edge_type} edges.")
        except Exception as e:
            logger.error(f"Failed to ingest edges ({edge_type}): {e}")
        finally:
            self.edge_batch[edge_type] = []
