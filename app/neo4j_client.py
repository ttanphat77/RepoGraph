import sys
import os
import logging
from neo4j import GraphDatabase

# ensure config is loadable
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import config

logger = logging.getLogger(__name__)

class Neo4jClient:
    def __init__(self):
        try:
            self.driver = GraphDatabase.driver(
                config.NEO4J_URI, 
                auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
            )
            # test connection
            self.driver.verify_connectivity()
            self.connected = True
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            self.connected = False
            self.driver = None

    def get_modules(self) -> list[str]:
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

    def get_subgraph(self, seed_file: str, depth: int):
        if not self.connected:
            return {"nodes": [], "edges": []}

        node_query = f"""
        MATCH path = (m:Module {{name: $seed_file}})-[*0..{depth}]-(other)
        UNWIND nodes(path) AS n
        RETURN DISTINCT id(n) AS neo_id, labels(n)[0] AS label, n.id AS identity, n.name AS name, n.community AS community
        """
        nodes_dict = {}
        try:
            with self.driver.session() as session:
                for record in session.run(node_query, seed_file=seed_file):
                    nid = record["neo_id"]
                    if nid not in nodes_dict:
                        nodes_dict[nid] = {
                            "id": nid,
                            "identity": record["identity"],
                            "label": record["label"],
                            "name": record["name"],
                            "community": record["community"],
                        }
        except Exception as e:
            logger.error(f"Error fetching subgraph nodes: {e}")
            return {"nodes": [], "edges": []}

        if not nodes_dict:
            return {"nodes": [], "edges": []}

        node_ids = list(nodes_dict.keys())

        edge_query = """
        MATCH (a)-[r]->(b)
        WHERE id(a) IN $node_ids AND id(b) IN $node_ids
        RETURN DISTINCT id(r) AS rel_id, type(r) AS rel_type,
               id(a) AS start_id, id(b) AS end_id
        """
        edges = []
        try:
            with self.driver.session() as session:
                for record in session.run(edge_query, node_ids=node_ids):
                    edges.append({
                        "id": record["rel_id"],
                        "type": record["rel_type"],
                        "source": record["start_id"],
                        "target": record["end_id"],
                    })
        except Exception as e:
            logger.error(f"Error fetching subgraph edges: {e}")

        return {"nodes": list(nodes_dict.values()), "edges": edges}

    def get_full_graph(self):
        if not self.connected:
            return {"nodes": [], "edges": []}

        nodes_dict = {}
        try:
            with self.driver.session() as session:
                for record in session.run(
                    "MATCH (n) RETURN DISTINCT id(n) AS neo_id, labels(n)[0] AS label, n.id AS identity, n.name AS name, n.community AS community"
                ):
                    nid = record["neo_id"]
                    nodes_dict[nid] = {
                        "id": nid,
                        "identity": record["identity"],
                        "label": record["label"],
                        "name": record["name"],
                        "community": record["community"],
                    }
        except Exception as e:
            logger.error(f"Error fetching all nodes: {e}")
            return {"nodes": [], "edges": []}

        edges = []
        try:
            with self.driver.session() as session:
                for record in session.run(
                    "MATCH (a)-[r]->(b) RETURN DISTINCT id(r) AS rel_id, type(r) AS rel_type, id(a) AS start_id, id(b) AS end_id"
                ):
                    edges.append({
                        "id": record["rel_id"],
                        "type": record["rel_type"],
                        "source": record["start_id"],
                        "target": record["end_id"],
                    })
        except Exception as e:
            logger.error(f"Error fetching all edges: {e}")

        return {"nodes": list(nodes_dict.values()), "edges": edges}

    def get_community_map(self) -> dict:
        """Return {neo4j_internal_id: community_int} for every node that has a community."""
        if not self.connected:
            return {}
        try:
            with self.driver.session() as session:
                result = session.run(
                    "MATCH (n) WHERE n.community IS NOT NULL RETURN id(n) AS nid, n.community AS community"
                )
                return {record["nid"]: record["community"] for record in result}
        except Exception as e:
            logger.error(f"Error fetching community map: {e}")
            return {}

client = Neo4jClient()
