# Mở rộng Graph Schema để hỗ trợ tài liệu (Document, DocChunk) kết nối trực tiếp với Code AST

Dự án RepoGraph hiện tại chỉ phân tích cú pháp mã nguồn (AST) và nạp cấu trúc code vào Neo4j. Kế hoạch này đề xuất thiết kế tổng quát (Generalized Design) để trích xuất và liên kết tài liệu ngoại vi (External Documentation: `.md`, `.rst`, `.txt`) vào đồ thị.

## Đồ thị Kiến trúc (Graph Schema Diagram)

```mermaid
graph TD
    %% Node Styles
    classDef codeNode fill:#f9f0ff,stroke:#d4b3ff,stroke-width:2px,color:#333
    classDef docNode fill:#e0f7fa,stroke:#4dd0e1,stroke-width:2px,color:#333

    %% Code Nodes
    M((Module)):::codeNode
    C((Class)):::codeNode
    F((Function)):::codeNode

    %% Doc Nodes (External docs like .rst, .md)
    D((Document)):::docNode
    DC1((DocChunk<br><i>[Intro]</i>)):::docNode
    DC2((DocChunk<br><i>[API]</i>)):::docNode

    %% Edges
    M -->|Contains| C
    M -->|Contains| F
    D -->|HasChunk| DC1
    D -->|HasChunk| DC2
    DC1 -->|References| D

    %% Cross-domain Edges (Linking External Doc to Code)
    M -.->|DocumentedBy| D
    DC2 -.->|Documents| C
```

---

## Kế hoạch Triển khai Cụ thể (Step-by-Step Implementation)

### Bước 1: Khai báo Schema (Data Models)
**File**: `pipeline/schemas/simple.py`
- Khai báo 2 class Model mới:
  ```python
  class Document(NodeModel): # attrs: name, file
  class DocChunk(NodeModel): # attrs: name (breadcrumbs), file, source (fulltext), index
  ```
- Khai báo 4 Edge mới kế thừa từ `EdgeModel`: `HasChunk`, `References`, `DocumentedBy`, `Documents`.

### Bước 2: Xây dựng Interface & Các Parser (Strategy Pattern)
**File**: `pipeline/parsers/base_doc.py`
- Tạo abstract class `BaseDocParser` với hàm cốt lõi:
  ```python
  def parse(self, content: str, filepath: str) -> tuple[Document, list[DocChunk], list[tuple]]:
      # Trả về: Node Document, Danh sách DocChunk, Danh sách các Cạnh (References/Documents)
  ```

**File**: `pipeline/parsers/markdown_parser.py` và `pipeline/parsers/rst_parser.py`
- Triển khai **State-aware Chunking**: Duyệt từng dòng văn bản bằng một vòng lặp `for`. Dùng biến trạng thái `in_code_block = True/False` để lờ đi các dấu `#` và `=` nếu đang ở trong code block.
- Quét tìm Explicit Directives (`.. auto*::`) trong `RstParser` và gắn vào danh sách cạnh trả về.

### Bước 3: Xây dựng Path Linker
**File**: `pipeline/linkers/path_linker.py`
- Tạo class `StrictSuffixLinker`.
- Hàm `link(doc_files: list[str], code_files: list[str]) -> list[tuple]`:
  - Split các đường dẫn thành mảng (ví dụ `['docs', 'auth', 'admin.rst']`).
  - Lặp ngược từ cuối lên đầu. Ghép nối cặp Doc-Code có độ dài chuỗi suffix trùng khớp lớn nhất. Trả về mảng cạnh `DocumentedBy`.

### Bước 4: Tích hợp vào Repo Manager
**File**: `pipeline/repo_manager.py`
- Bổ sung hàm `get_doc_files()` dùng `pathlib.Path.rglob` để quét tất cả `.md`, `.rst`, `.txt` (bỏ qua các thư mục `venv`, `.git`, `tests`).

### Bước 5: Viết hàm nạp dữ liệu (Ingestion)
**File**: `pipeline/neo4j_ingester.py`
- Sửa hàm `_ensure_fulltext_index` để thêm nhãn `DocChunk` vào Lucene Index.
- Viết hàm mới `ingest_documents(docs: list[Document], chunks: list[DocChunk], edges: list[dict])`:
  - Dùng `UNWIND` và `MERGE` để batch insert hàng ngàn chunk vào Neo4j với hiệu năng cao nhất.

### Bước 6: Lắp ráp luồng thực thi chính (Orchestration)
**File**: `scripts/build_graph.py`
- Sửa hàm `build_graph_from_repo()` theo đúng pipeline tuyến tính:
  1. `doc_files = repo_manager.get_doc_files()`
  2. Vòng lặp parse từng file bằng Factory (`MarkdownParser` hoặc `RstParser`). Gom toàn bộ `DocChunk` và cạnh nội bộ.
  3. `path_linker.link()` để sinh các cạnh `DocumentedBy`.
  4. `neo4j_ingester.ingest_documents()` để xả toàn bộ vào DB cùng lúc với Code AST.

### Bước 7: Cập nhật RAG Retriever
**File**: `pipeline/retriever.py`
- Không cần sửa nhiều vì BM25 sẽ tự động tìm thấy `DocChunk`.
- Chỉ cần cập nhật hàm `_expand_neighborhood` (BFS) để đi dọc theo cạnh `References` và `DocumentedBy`, cho phép LLM nhìn bao quát hơn.

---

## Verification Plan

1. **Kiểm tra Parser Tổng quát**:
   - Chạy test độc lập cho `MarkdownParser` và `RstParser`.
2. **Build Graph & Ingestion**:
   - `python scripts/build_graph.py swe-lite 1`
   - Xác minh không có dữ liệu trùng lặp.
