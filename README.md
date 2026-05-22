# GraphRAG POC: File Localization cho SWE-bench

Một Proof of Concept (POC) triển khai công nghệ Knowledge Graph ứng dụng cho bài toán **File Localization** (Dự đoán files cần sửa dựa trên issue text) thông qua bộ dữ liệu `SWE-bench Lite`. Hệ thống trích xuất cấu trúc mã nguồn (AST parsing) từ GitHub, xây dựng đồ thị tại lớp Semantic kết hợp Structural, sau đó dùng GraphRAG pipeline để dự đoán file cần sửa và đánh giá bằng Precision / Recall / F1.

---

## Tính năng

- **Dual Graph Schema:** Hỗ trợ 2 schema đồ thị, chuyển đổi bằng 1 dòng config — không cần sửa code pipeline.
- **Multi-language AST Parsing:** Hỗ trợ **Python** và **Swift** thông qua `LanguageExtractor` pattern — thêm ngôn ngữ mới chỉ cần 1 file extractor mới.
- **Clone từ URL:** Hỗ trợ clone trực tiếp từ GitHub/GitLab URL với tùy chọn branch và access token cho private repo.
- **Idempotency:** Dataset caching, git clone và Neo4j batch-ingestion đều chạy lại được mà không nhân bản dữ liệu.
- **Single Commit Isolation:** Graph đồng bộ tại `base_commit` cố định, dễ đối chiếu với GT Files (Ground-Truth patch files).
- **GraphRAG Pipeline:** Entity resolution → BFS neighborhood extraction → LLM generation (Gemini 2.5 Flash streaming) để dự đoán file cần sửa từ issue text.
- **Evaluation Metrics:** Tính Precision / Recall / F1 tự động so sánh với ground-truth patch files.
- **Trực quan Graph:** Tích hợp File List (highlight GT files với `🎯`) và đồ thị tương tác `pyvis` trên Streamlit.

---

## Graph Schema

Chọn schema bằng cách đặt `ACTIVE_SCHEMA` trong `config.py`:

### `"simple"` (mặc định)

| Loại | Tên |
|------|-----|
| Nodes | `Module`, `Class`, `Function` |
| Edges | `Defines`, `Calls`, `Imports`, `Inherits` |

Phù hợp để phân tích cấu trúc file-level và luồng gọi hàm.

### `"detailed"`

| Loại | Tên |
|------|-----|
| Nodes | `MODULE`, `CLASS`, `METHOD`, `FUNCTION`, `FIELD`, `GLOBAL_VARIABLE` |
| Edges | `CONTAINS`, `INHERITS`, `HAS_METHOD`, `HAS_FIELD`, `USES` |

Phân biệt method (trong class) vs function (module-level), track class attributes và global variables.

### Thêm schema mới

1. Tạo `pipeline/schemas/my_schema.py` implement `SchemaPlugin`
2. Đăng ký 1 entry trong `pipeline/schemas/__init__.py`
3. Đặt `ACTIVE_SCHEMA = "my_schema"` trong `config.py`

---

## Kiến trúc thư mục

```
graphrag-poc/
│
├── config.py                    ← Config tổng (ACTIVE_SCHEMA, Neo4j, parsing limits)
├── .env                         ← Secrets (GEMINI_API_KEY, Neo4j password) — không commit
├── .env.example                 ← Template cho .env
├── docker-compose.yml           ← Spin up Neo4j Community
│
├── scripts/
│   └── build_graph.py           ← CLI entrypoint (swe-lite | local | url)
│
├── pipeline/
│   ├── ast_engine.py            ← Engine: tree-sitter, scope building, cross-file resolution
│   ├── neo4j_ingester.py        ← Batch MERGE/MATCH writes to Neo4j
│   ├── repo_manager.py          ← Git clone, URL clone, file discovery
│   ├── dataset_loader.py        ← SWE-bench dataset loading & caching
│   ├── retriever.py             ← GraphRAG Retriever: entity resolution → BFS → context
│   ├── generator.py             ← LLM Generation: Gemini streaming → predicted files
│   ├── evaluator.py             ← Orchestrator: retriever + generator + metrics
│   ├── languages/
│   │   ├── base.py              ← LanguageExtractor dataclass (interface)
│   │   ├── python.py            ← Python extractor
│   │   └── swift.py             ← Swift extractor
│   └── schemas/
│       ├── __init__.py          ← load_schema("simple" | "detailed")
│       ├── base.py              ← SchemaPlugin ABC + ParseContext
│       ├── simple.py            ← Schema "simple"
│       └── detailed.py          ← Schema "detailed"
│
├── app/                         ← Streamlit UI (inspect & visualize only)
│   ├── main.py
│   ├── neo4j_client.py          ← Read-only graph queries
│   └── components/
│       ├── file_view.py         ← Tab: danh sách file trong graph
│       ├── graph_view.py        ← Tab: đồ thị tương tác pyvis
│       ├── query_view.py        ← Tab: Issue Query UI (gọi pipeline/evaluator.py)
│       └── combined_view.py     ← Tab: Combined view (retriever + generator + metrics)
│
├── cache/                       ← JSON instance state & dataset cache
└── repos/                       ← Cloned repo snapshots
```

---

## Cài đặt và chạy

### 1. Chuẩn bị môi trường

Yêu cầu: Python 3.11+, Git, Docker.

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate        # CMD
# hoặc
.venv\Scripts\Activate.ps1    # PowerShell

pip install -r requirements.txt
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Cấu hình secrets

```bash
cp .env.example .env
# Mở .env và điền GEMINI_API_KEY
```

### 3. Khởi động Neo4j

```bash
docker-compose up -d neo4j
```

Giao diện query tại `http://localhost:7474` — credentials mặc định: `neo4j / graphrag123`.

### 4. Build Knowledge Graph

```bash
# Từ SWE-bench Lite (instance đầu tiên)
python scripts/build_graph.py swe-lite 1

# Từ một folder cục bộ (Python)
python scripts/build_graph.py local "duong/dan/thu/muc"

# Từ một folder cục bộ (Swift)
python scripts/build_graph.py local "duong/dan/thu/muc" -l swift

# Clone từ GitHub/GitLab URL
python scripts/build_graph.py url https://github.com/org/repo.git

# Clone branch cụ thể
python scripts/build_graph.py url https://github.com/org/repo.git -b develop

# Clone private repo với access token
python scripts/build_graph.py url https://gitlab.example.com/org/repo.git --token <TOKEN> -l swift
```

Pipeline chạy 4 stage:
1. **Parallel AST Extraction** — parse tất cả source files song song
2. **Cross-File Resolution** — phân giải call/inheritance refs thành edges
3. **Community Detection** — Leiden clustering *(bật mặc định, tắt bằng `ENABLE_COMMUNITY_DETECTION = False`)*
4. **Bulk Ingestion** — MERGE nodes, MATCH endpoints trước khi tạo edges

### 5. Bật Streamlit Dashboard

```bash
streamlit run app/main.py
```

Truy cập `http://localhost:8501`. Dashboard có 4 tab:

- **File View** — danh sách file trong graph, highlight GT files với `🎯`
- **Graph View** — đồ thị tương tác, chọn depth để duyệt dependency levels
- **Issue Query** — nhập issue text → GraphRAG pipeline → dự đoán file cần sửa → Precision / Recall / F1
- **Combined View** — kết hợp retriever context + LLM answer + metrics cùng lúc

---

## Cấu hình chính (`config.py`)

| Tham số | Mặc định | Mô tả |
|---------|----------|-------|
| `ACTIVE_SCHEMA` | `"simple"` | Schema đồ thị: `"simple"` hoặc `"detailed"` |
| `MAX_FILES_PARSED` | `0` | Giới hạn số file parse (0 = không giới hạn) |
| `ENABLE_COMMUNITY_DETECTION` | `True` | Bật/tắt Leiden clustering (chậm trên repo lớn) |
| `NEO4J_BATCH_SIZE` | `500` | Số node/edge mỗi batch write |

Secrets (`GEMINI_API_KEY`, `NEO4J_PASSWORD`, ...) được load từ file `.env` — không hardcode trong `config.py`.

---

## Thêm ngôn ngữ mới

1. Tạo `pipeline/languages/my_lang.py` — khởi tạo `LanguageExtractor` với các field tương ứng
2. Thêm entry vào `LANG_CONFIG` trong `scripts/build_graph.py`
3. Dùng: `python scripts/build_graph.py local <path> -l my_lang`
