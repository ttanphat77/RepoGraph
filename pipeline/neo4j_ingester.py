import logging
from collections import defaultdict
from neo4j import GraphDatabase
import config

logger = logging.getLogger(__name__)

class Neo4jIngester:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            config.NEO4J_URI, 
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
        )
        self.node_batch = defaultdict(list) # grouped by primary label
        self.edge_batch = defaultdict(list) # grouped by edge type
        self.batch_size = config.NEO4J_BATCH_SIZE

    def close(self):
        self.flush()
        self.driver.close()

    def add_node(self, node_dict: dict):
        # We assume labels[0] is the primary label (Module, Class, Function)
        primary_label = node_dict["labels"][0]
        # Include id in properties for MERGE
        props = node_dict["properties"].copy()
        props["id"] = node_dict["id"]
        
        self.node_batch[primary_label].append(props)
        if len(self.node_batch[primary_label]) >= self.batch_size:
            self._flush_nodes(primary_label)

    def add_edge(self, edge_dict: dict):
        edge_type = edge_dict["type"]
        entry = {"source": edge_dict["source"], "target": edge_dict["target"]}
        if "line" in edge_dict:
            entry["line"] = edge_dict["line"]
        self.edge_batch[edge_type].append(entry)
        if len(self.edge_batch[edge_type]) >= self.batch_size:
            self._flush_edges(edge_type)

    def flush(self):
        for label in list(self.node_batch.keys()):
            if self.node_batch[label]:
                self._flush_nodes(label)
        for rel_type in list(self.edge_batch.keys()):
            if self.edge_batch[rel_type]:
                self._flush_edges(rel_type)

    def _flush_nodes(self, label: str):
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
            self.node_batch[label] = []

    def _flush_edges(self, edge_type: str):
        batch = self.edge_batch[edge_type]
        query = f"""
        UNWIND $batch AS row
        MATCH (s {{id: row.source}})
        MATCH (t {{id: row.target}})
        MERGE (s)-[r:{edge_type}]->(t)
        FOREACH (_ IN CASE WHEN row.line IS NOT NULL THEN [1] ELSE [] END | SET r.line = row.line)
        """
        try:
            with self.driver.session() as session:
                session.run(query, batch=batch)
            logger.info(f"Ingested {len(batch)} {edge_type} edges.")
        except Exception as e:
            logger.error(f"Failed to ingest edges ({edge_type}): {e}")
        finally:
            self.edge_batch[edge_type] = []
