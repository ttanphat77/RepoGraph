# RepoGraph — Tổng hợp thảo luận kiến trúc Graph

> File này tổng hợp toàn bộ thảo luận để tiếp tục trong session khác.
> Ngày tổng hợp: 2026-05-28.

---

## 1. Mục đích thực sự của dự án

**Không chỉ là file localization** — mục tiêu là **automated issue triage**.

Luồng GitLab triage bot (`bot/server.py`, `bot/triage.py`):
1. Nhận webhook khi issue mới được mở
2. Chạy RAG pipeline trên `title + description`
3. LLM phân loại: **Bug / Feature Request / Question / Needs Clarification**
4. Trả về: root cause, proposed fix, danh sách files cần sửa
5. Post comment lên GitLab issue

SWE-bench chỉ là **benchmark để đo chất lượng retrieval**, không phải mục tiêu cuối.

Hệ quả: cần general-purpose code understanding (code + docs + lịch sử), không chỉ predict file path.

---

## 2. Hệ thống hiện tại (baseline)

### Pipeline
```
scripts/build_graph.py   → build graph (offline)
pipeline/retriever.py    → entity resolution + BM25 + BFS
pipeline/generator.py    → Gemini streaming → answer + predicted_files
pipeline/evaluator.py    → orchestrator (đã tách khỏi UI, tái dùng bởi bot)
```

**Đã tách retrieval khỏi graph building** — đây là điểm tốt cần giữ.

### Storage: Neo4j
- Node ID hiện tại: `{base_commit}:{file}:{name}` (commit nằm trong identity)
- BM25 fulltext index cho seed lookup
- Community detection (Leiden) — **đã tính nhưng KHÔNG dùng trong retrieval**

### Metrics hiện tại (`compute_metrics`)
```
tp, precision, recall, f1
```

---

## 3. Metrics nên bổ sung (theo literature)

Tham khảo: SWE-bench (ICLR 2024), bug localization survey 2025, BugLocator/BLIA/Locus.

### Tier 1 — bắt buộc (>80% papers)
| Metric | Ý nghĩa |
|--------|---------|
| `Top@1` | GT file có rank #1 không |
| `Top@5`, `Top@10` | GT file có trong top-k |
| `MRR` | `avg(1/rank_first_correct)` |
| `MAP` | Mean Average Precision |

### Tier 2 — file localization
`Recall@k`, `Precision@k`, `Exact Match`, `Hit Rate`

### Ưu tiên thêm trước
`Top@1`, `Top@3`, `MRR` — phù hợp `_rank_files()` vì output đã là ranked list.

**Lưu ý robust với gt nhiễu:** ưu tiên `Top@1`/`Hit@k` hơn `Recall@full`.

---

## 4. Per-instance graph là BẮT BUỘC

### Lý do cứng
Mỗi SWE-bench instance có `base_commit` khác nhau → source code khác → AST nodes khác → graph phải khác. **Không có shortcut nào tránh được mà vẫn đảm bảo chính xác.**

### Các hướng đã loại bỏ (và lý do)
- **Hướng B (tách commit khỏi node ID, share node)**: ❌ source code bị overwrite → sai chính xác. Không chấp nhận được.
- **Incremental update giữa instances**: ❌ instances là mẫu **thưa** trên timeline dày (Django 30k+ commits, vài chục instances → cách nhau ~600 commits). `git diff A..B` span quá lớn → suy biến thành near-full rebuild.
- **Shared graph + đọc source từ disk**: ❌ structure (Calls/Imports) cũng đổi khi implementation đổi, không chỉ source content.

### Giải pháp đúng (theo literature)
**Pre-build offline toàn bộ instances một lần → cache → evaluation chỉ load.**

Đây là cách RepoGraph và CGM làm. Chi phí trả 1 lần.

---

## 5. Khảo sát các papers (đọc code thực tế, không chỉ paper)

> **Bài học quan trọng:** agent đọc paper mà không đọc code → kết luận SAI ("build per repo"). Thực tế đọc code: tất cả build **per instance**.

### RepoGraph (github.com/ozyyshr/RepoGraph)
- Storage: **NetworkX `.pkl`** per instance
- Node: name, category (class/function), kind (def/ref), fname, line, info
- Edge: chỉ 2 loại — Class→Method, Reference→Definition
- Seed: exact name match; Traversal: Python BFS/DFS
- **Pre-build offline 300 graphs → upload HuggingFace/Google Drive**
- `get_project_structure_from_scratch(repo, base_commit, instance_id)` xử lý checkout

### CodexGraph (arXiv 2408.03910)
- Per repo, two-phase indexing, Cypher queries

### Prometheus (github.com/EuniAI/Prometheus)
- **Real-time service** (FastAPI), không phải batch evaluator
- Storage: Neo4j
- Node: **FileNode, ASTNode, TextNode** (TextNode = doc chunk)
- Edge: HAS_FILE, HAS_AST, HAS_TEXT, PARENT_OF, NEXT_CHUNK
- Doc: `.md/.rst/.txt` → LangChain `RecursiveCharacterTextSplitter` → chunks (overlapping)
- `clone_github_repo(url, commit_id)` → checkout per commit → build graph → clear cũ trước

### CodeFuse-CGM (github.com/codefuse-ai/CodeFuse-CGM)
- Storage: **JSON file** per instance + node embeddings (`.pkl`) per instance
- Node (8 loại): REPO, PACKAGE, FILE, **TEXTFILE**, CLASS, ATTRIBUTE, FUNCTION, LAMBDA
- Edge (6 loại): CONTAINS, IMPORTS, EXTENDS, IMPLEMENTS, CALLS, REFERENCES
- Seed: embedding similarity; Traversal: BFS 2 hops bidirectional
- **Pre-build offline per instance**

### Kết luận chung
Cả 3 đều **pre-build per instance offline**. Không paper nào build on-the-fly trong eval loop.

---

## 6. NetworkX vs Neo4j

| | NetworkX | Neo4j |
|--|---------|-------|
| Storage | In-memory `.pkl` | Persistent |
| Multi-instance | Trivial (file riêng, load song song) | Phải clear/overwrite |
| Fulltext/BM25 | ❌ tự implement | ✅ built-in |
| BFS | Native nhanh | Cypher variable-length |
| Dependency | `pip install` | Docker + driver |

- RepoGraph chọn NetworkX vì per-instance isolation tự nhiên (mỗi instance 1 `.pkl`).
- Hệ thống hiện tại dùng Neo4j vì BM25 + Cypher là core của retriever.

---

## 7. KIẾN TRÚC GRAPH — chốt hiện tại

### Nodes
```
Module    {id, file, commit, source, community}
Class     {id, name, file, commit, source, community}
Function  {id, name, file, commit, source, community}
Document  {id, file, commit, type}
DocChunk  {id, text, file, commit, heading, index}
```

> **Issue/PR và Commit nodes: xem mục 9 — quyết định DROP cho POC hiện tại.**

### Edges
```
── Code (AST) ──────────────────────────────────────
Module    --Defines-->       Class / Function
Function  --Calls-->         Function
Module    --Imports-->       Module
Class     --Inherits-->      Class

── Doc → Doc ───────────────────────────────────────
Document  --HasChunk-->      DocChunk
DocChunk  --NextChunk-->     DocChunk
DocChunk  --SubSection-->    DocChunk

── Doc → Code (chỉ explicit, KHÔNG regex) ──────────
Function  --HasDocstring-->  DocChunk     (parse-time)
Class     --HasDocstring-->  DocChunk     (parse-time)
Module    --DocumentedBy-->  Document     (path matching)
DocChunk  --Documents-->     Function/Class (RST directive only)

── Git history (chỉ nếu enrich, xem mục 9) ─────────
Module    --CoChangedWith--> Document     (aggregate weight, không materialize commit)
```

### Sơ đồ (style cây, AST làm trung tâm)
```
        ┌──────────────[AST Nodes]──────────────┐
        │           Module / Class / Function     │
   Calls   Imports   Defines   Inherits            │
        └────────────────┬─────────────────────────┘
                         │
         ┌───────────────┼────────────────┐
   DocumentedBy     HasDocstring       Documents
         │               │                ▲
         ▼               ▼                │
     Document        DocChunk ────────────┘
         │               ▲
     HasChunk            │
         ▼               │
     DocChunk──NextChunk──DocChunk
         │
     SubSection
         ▼
     DocChunk

   Module ──CoChangedWith──> Document
```

---

## 8. Quyết định thiết kế & lý do

| Quyết định | Lý do |
|-----------|-------|
| AST nodes làm **hub trung tâm** | Mọi retrieval converge ở AST |
| **DocChunk** thay vì Document→AST | Triage cần retrieve đúng section, không phải toàn file (như Prometheus/CGM) |
| `Documents` edge **chỉ từ RST directive** | Regex scan quá noisy → giữ làm BM25 search runtime, không phải static edge |
| **Không** `Mentions` từ regex trong graph | 1:N noisy; explicit (docstring + RST) mới đáng tin |
| `commit` là **property**, không trong node ID | Cho phép nhiều instance coexist; filter `WHERE n.commit = $base_commit` |
| **Không** `HasSnapshot` (Commit→AST) | Redundant — `commit` property đã đủ |
| `CoChangedWith` là **aggregate edge có weight** | Không cần materialize từng commit thành node |
| Community trên AST → dùng trong `_rank_files()` | Boost file cùng community với seed (Microsoft GraphRAG Local Search) |

### Granularity của `Changed` (nếu dùng)
- Map diff line-range → **AST node nhỏ nhất chứa trọn hunk**
- KHÔNG tạo edge tới ancestor (Class/Module) — quan hệ chứa đựng đã có qua `Defines`
- Lan truyền tín hiệu **ngược lên** qua `Defines` với decay tại **retrieval time**:
  ```
  Function changed = 1.0 → Class = 0.5 → Module = 0.25
  ```

---

## 9. Issue/PR/Commit nodes — phân tích & quyết định

### Data leakage (CRITICAL)
KHÔNG được đưa vào graph dùng cho retrieval:
- `Issue --ResolvedBy--> Module` (= gt_files của instance đang xét)
- `Commit/PR --Changes--> Module` (từ patch hiện tại)
- → chỉ dùng cho **training supervision** hoặc **tính metrics**.

Hợp lệ (không leakage): Issue/Commit/PR từ **lịch sử trước `base_commit`** → fault history.

### Commit vs PR
| | Commit | PR |
|--|--------|-----|
| Map SWE-bench | Gián tiếp | **Native** (`instance_id` = PR number) |
| Quan hệ Issue | N commit/fix | **1:1** sạch |
| Diff cho `Changed` | walk N commit | **1 net diff** (= patch) |
→ PR là đơn vị tốt hơn về mặt ngữ nghĩa. **Nhưng** workflow mỗi repo khác nhau (Django dùng Trac, không phải GitHub PR thuần).

### FACT-CHECK quan trọng về SWE-bench patch
- ✅ Một PR **có thể** fix nhiều issue (GitHub closing keywords).
- ❌ SWE-bench patch **KHÔNG** trích riêng theo issue — nó là **toàn bộ PR diff minus tests** (`patch` + `test_patch`).
- → Nếu PR fix nhiều issue: `gt_files` chứa file của cả các issue khác → **nhiễu ground truth đã biết**.
- → Cân nhắc **SWE-bench Verified** (annotate thủ công, sạch hơn).

### Đánh giá chính xác khi gt nhiễu
1. SWE-bench Verified + lọc multi-issue PR
2. **`FAIL_TO_PASS` tests làm oracle chặt hơn patch** — map test → files qua coverage/import (hướng đáng đầu tư nhất)
3. Ưu tiên metric robust: `Top@1`, `Hit@k`
4. Relative comparison vẫn valid (nhiễu là bias cố định)

### Vấn đề density (lý do DROP cho POC)
- Chỉ dùng SWE-bench instances làm Issue/PR nodes → **quá thưa** (~1% history, ~10-20 issue sau temporal filter).
- Fault-history cần **density** để "tìm issue tương tự" (như BugLocator/BLIA dùng full bug repo).
- → **Sparse Issue/PR từ SWE-bench = dead weight.**

### Quyết định
- **POC hiện tại: DROP Issue/PR/Commit nodes.** Tập trung graph **code + doc**.
- Thêm fault-history sau như **enrichment riêng** nếu kết quả cho thấy cần.

---

## 10. Crawl issue history (nếu làm fault-history)

### Django — RẤT khả thi (OpenData chính thức)
- **CSV data dump** (tốt nhất): tar+bzip ~35MB, toàn bộ tickets.
  - Bảng: `ticket` (id, summary, description, status), `ticket_change` (history)
  - Không rate limit, offline 1 lần → giải quyết density
- XML-RPC/JSON-RPC: `trac.ticket.query(...)` (cần login, cho query lẻ)
- Link: commit message `"Fixed #NNNNN"` = **Trac ticket** (không phải GitHub) → join với git log

```
CSV dump → Issue nodes (dày)
git log "Fixed #N" → FixedBy edges
Issue (Trac #N) --FixedBy--> Commit --Changed--> File
```

### Caveat: KHÔNG generalize
Mỗi repo SWE-bench có tracker khác:
- Django → Trac (code.djangoproject.com)
- astropy, sympy... → GitHub Issues
→ Cần **adapter cho từng loại tracker** nếu muốn cả 11 repos.
- Temporal filter bắt buộc: chỉ ticket/commit < `base_commit`.

---

## 11. Nguồn dữ liệu & leakage (tổng hợp)

| Node / Edge | Nguồn | Leakage? |
|-------------|-------|----------|
| Module/Class/Function | AST tại `base_commit` | ❌ |
| Document/DocChunk | Doc files tại `base_commit` | ❌ |
| `HasDocstring` | AST (có sẵn) | ❌ |
| `Documents` | RST directive | ❌ |
| `CoChangedWith` | `git log --name-only` trước base_commit | ❌ |
| Issue/PR history | Trac dump / GitHub API trước base_commit | ❌ (cần temporal filter) |
| gt_files / patch | SWE-bench ground truth | ✅ CHỈ dùng metrics |

---

## 12. Việc cần làm tiếp (next steps)

### Hướng 1 — Hoàn thiện đánh giá (nhanh nhất)
- [ ] Thêm `Top@k`, `MRR`, `MAP` vào `compute_metrics()`
- [ ] Pre-build nhiều instances để có kết quả thực nghiệm
- [ ] (Nâng cao) Map `FAIL_TO_PASS` → files làm oracle sạch

### Hướng 2 — Mở rộng graph schema (code + doc)
- [ ] Thêm `Document`, `DocChunk` nodes
- [ ] `repo_manager.py`: discover `.md/.rst/.txt`
- [ ] Doc extractor: chunk theo heading (hoặc fixed-size overlap như Prometheus)
- [ ] Edges: `HasDocstring`, `DocumentedBy`, `Documents` (RST), `HasChunk`, `NextChunk`, `SubSection`
- [ ] Cập nhật `schemas/simple.py`, `neo4j_ingester.py`

### Hướng 3 — Cải thiện retrieval (không rebuild graph)
- [ ] Dùng community trong `_rank_files()` (boost file cùng community seed)
- [ ] Đưa DocChunk vào BFS context

### Hướng 4 — Fault-history (chỉ nếu cần, sau POC)
- [ ] Crawl Trac CSV dump (Django) / GitHub API (repos khác)
- [ ] Adapter per tracker
- [ ] `Issue --FixedBy--> Commit/PR --Changed--> File` với temporal filter

---

## 13. Câu hỏi mở cần quyết định

1. **Schema**: giữ `simple` hay nâng `detailed`?
2. **DocChunk**: chunk theo heading hay fixed-size overlap?
3. **SWE-bench**: chuyển sang **Verified** (gt sạch hơn) không?
4. **Output pipeline**: file path hay section cụ thể? (ảnh hưởng Document-level vs DocChunk-level)
5. **Fault-history**: làm riêng Django trước, hay cần adapter cả 11 repos?
6. **Community trong retrieval**: bật ngay hay để sau?
