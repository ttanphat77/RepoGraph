# Single source of truth — edit here to change experiment parameters

# ── Dataset ──────────────────────────────────────────────────────────────────
DATASET_NAME = "princeton-nlp/SWE-bench_Lite"
DATASET_CACHE = "cache/swebench_lite.json"

# ── Repo storage ──────────────────────────────────────────────────────────────
REPOS_DIR = "repos"

# ── Graph schema ──────────────────────────────────────────────────────────────
# Switch between schemas without touching any other code.
# Available values: "simple" | "detailed"
#   simple   → Module, Class, Function / Defines, Calls, Imports, Inherits
#   detailed → MODULE, CLASS, METHOD, FUNCTION, FIELD, GLOBAL_VARIABLE
#              / CONTAINS, INHERITS, HAS_METHOD, HAS_FIELD, USES
ACTIVE_SCHEMA = "simple"

# ── AST parsing ───────────────────────────────────────────────────────────────
# Stop ingesting after this many files per repo (0 = unlimited)
MAX_FILES_PARSED = 0

# Set False to skip Louvain community detection (slow on large repos)
ENABLE_COMMUNITY_DETECTION = True

# ── Neo4j ─────────────────────────────────────────────────────────────────────
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "graphrag123"

# Batch size for MERGE writes
NEO4J_BATCH_SIZE = 500

# ── Validation ────────────────────────────────────────────────────────────────
# Fail fast if ACTIVE_SCHEMA is misspelled — caught on first import of config.
from pipeline.schemas import load_schema as _load_schema
_load_schema(ACTIVE_SCHEMA)
