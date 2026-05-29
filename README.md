# RepoGraph — GraphRAG for File Localization

A POC using Knowledge Graphs for **file localization** (predicting which files to edit given an issue) on `SWE-bench Lite`. Parses source code via AST, builds a semantic+structural graph in Neo4j, then uses a GraphRAG pipeline (Gemini 2.5 Flash) to predict files and evaluate with Precision / Recall / F1.

---

## Features

- **Dual Graph Schema** — switch between `simple` and `detailed` via one config line
- **Multi-language AST** — Python, Swift, JavaScript via pluggable `LanguageExtractor`
- **URL Clone** — clone directly from GitHub/GitLab with optional branch and token
- **Idempotent** — dataset caching, git clone, and Neo4j ingestion are all safe to re-run
- **Single Commit Isolation** — graph synced at `base_commit` for ground-truth comparison
- **GraphRAG Pipeline** — entity resolution → BFS neighborhood → LLM generation → predicted files
- **Auto Evaluation** — Precision / Recall / F1 against ground-truth patch files
- **Streamlit UI** — file list (GT files highlighted with `🎯`) + interactive pyvis graph

---

## Graph Schemas

Set `ACTIVE_SCHEMA` in `config.py`:

| Schema | Nodes | Edges |
|--------|-------|-------|
| `"simple"` (default) | `Module`, `Class`, `Function` | `Defines`, `Calls`, `Imports`, `Inherits` |
| `"detailed"` | `MODULE`, `CLASS`, `METHOD`, `FUNCTION`, `FIELD`, `GLOBAL_VARIABLE` | `CONTAINS`, `INHERITS`, `HAS_METHOD`, `HAS_FIELD`, `USES` |

**Add a new schema:** implement `SchemaPlugin` in `pipeline/schemas/my_schema.py`, register it in `pipeline/schemas/__init__.py`, then set `ACTIVE_SCHEMA = "my_schema"`.

---

## Project Structure

```
graphrag-poc/
├── config.py                  ← Global config (schema, Neo4j, limits)
├── .env                       ← Secrets (GEMINI_API_KEY, Neo4j password) — not committed
├── .env.example
├── docker-compose.yml         ← Neo4j Community
├── scripts/
│   └── build_graph.py         ← CLI entrypoint (swe-lite | local | url)
├── pipeline/
│   ├── ast_engine.py          ← tree-sitter parsing, scope building, cross-file resolution
│   ├── neo4j_ingester.py      ← Batch MERGE/MATCH writes
│   ├── repo_manager.py        ← Git clone, URL clone, file discovery
│   ├── dataset_loader.py      ← SWE-bench dataset loading & caching
│   ├── retriever.py           ← Entity resolution → BFS → context
│   ├── generator.py           ← Gemini streaming → predicted files
│   ├── evaluator.py           ← Orchestrator: retriever + generator + metrics
│   ├── languages/
│   │   ├── base.py            ← LanguageExtractor interface
│   │   ├── python.py
│   │   ├── swift.py
│   │   └── javascript.py
│   └── schemas/
│       ├── __init__.py        ← load_schema("simple" | "detailed")
│       ├── base.py            ← SchemaPlugin ABC + ParseContext
│       ├── simple.py
│       └── detailed.py
└── app/                       ← Streamlit UI (read-only)
    ├── main.py
    ├── neo4j_client.py
    └── components/
        ├── file_view.py       ← File list tab
        ├── graph_view.py      ← Interactive graph tab
        ├── query_view.py      ← Issue Query tab
        └── combined_view.py   ← Combined view tab
```

---

## Setup

**Requirements:** Python 3.11+, Git, Docker

```bash
# 1. Create and activate venv
python -m venv .venv
.venv\Scripts\activate          # Windows CMD
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt

# 2. Configure secrets
cp .env.example .env
# Edit .env — add GEMINI_API_KEY

# 3. Start Neo4j
docker-compose up -d neo4j
# UI at http://localhost:7474  (default: neo4j / graphrag123)
```

---

## Build the Graph

```bash
# From SWE-bench Lite (first instance)
python scripts/build_graph.py swe-lite 1

# From a local folder
python scripts/build_graph.py local path/to/repo
python scripts/build_graph.py local path/to/repo -l swift
python scripts/build_graph.py local path/to/repo -l javascript

# From a GitHub/GitLab URL
python scripts/build_graph.py url https://github.com/org/repo.git
python scripts/build_graph.py url https://github.com/org/repo.git -b develop
python scripts/build_graph.py url https://gitlab.example.com/org/repo.git --token <TOKEN>
```

Pipeline stages:
1. **Parallel AST Extraction** — parse all source files concurrently
2. **Cross-File Resolution** — resolve call/inheritance refs into edges
3. **Community Detection** — Leiden clustering (disable via `ENABLE_COMMUNITY_DETECTION = False`)
4. **Bulk Ingestion** — MERGE nodes, then MATCH endpoints before creating edges

---

## Run the Dashboard

```bash
streamlit run app/main.py
# → http://localhost:8501
```

Tabs: **File View** · **Graph View** · **Issue Query** · **Combined View**

---

## Configuration (`config.py`)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ACTIVE_SCHEMA` | `"simple"` | Graph schema: `"simple"` or `"detailed"` |
| `MAX_FILES_PARSED` | `0` | File parse limit (0 = unlimited) |
| `ENABLE_COMMUNITY_DETECTION` | `True` | Leiden clustering (slow on large repos) |
| `NEO4J_BATCH_SIZE` | `500` | Nodes/edges per batch write |

---

## Supported Languages

| Language | Flag | Extensions |
|----------|------|------------|
| Python | *(default)* | `.py` |
| Swift | `-l swift` | `.swift` |
| JavaScript | `-l javascript` | `.js`, `.mjs`, `.cjs` |

**Add a language:** install `tree-sitter-<lang>`, create `pipeline/languages/my_lang.py` with a `LanguageExtractor`, add an entry to `LANG_CONFIG` in `scripts/build_graph.py`. Refer to `src/node-types.json` in the grammar repo for node type names.
