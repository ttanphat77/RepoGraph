# Thiết kế kỹ thuật của pipeline RepoGraph

Cập nhật ngày 29/10/2026.

File này mô tả từng kỹ thuật trong pipeline, từ dữ liệu đầu vào tới bảng đánh giá. Mỗi bước ghi mục đích, input, cách làm, tham số, output, cơ sở và trạng thái. Nội dung được đối chiếu với code trong notebook `colab/build_graph_flask_colab.ipynb`. Kế hoạch và thứ tự công việc nằm ở `planning.md`. Bối cảnh nghiên cứu nằm ở `research_context.md`. Kết quả của từng lượt chạy nằm ở `experiment_log.md`.

Trạng thái của mỗi bước dùng một trong bốn mức sau.

| Mức | Nghĩa |
|---|---|
| Đã chạy | Đã cài trong notebook thật và đã chạy trên Kaggle. Mã lượt (ví dụ v4-L4) trỏ tới `experiment_log.md` |
| Đã cài | Đã viết trong bản làm việc và đã thử trên máy, nhưng chưa chạy trên Kaggle |
| Đã chốt | Thiết kế đã được xác nhận, nhưng chưa viết code |
| Chưa chốt | Thiết kế còn đang được tìm hiểu |

Cột "Cơ sở" chỉ ghi bài báo đã được đọc và ghi lại trong artifact "Tổng quan tài liệu RepoGraph" hoặc trong `planning.md`. Lựa chọn nào chưa có bài báo làm cơ sở thì được ghi rõ là chưa có.

---

## 0. Tổng quan

**Bài toán.** Input là một issue của SWE-bench và repository ở trạng thái gần thời điểm issue. Output là danh sách hàm/lớp được xếp theo khả năng phải sửa để đóng issue. Đề tài cần chứng minh rằng dùng thêm doc, history và issue cũ giúp xếp hạng tốt hơn so với chỉ dùng code.

**Vai trò của LLM.** LLM chỉ là judge. Không nguồn nào dùng LLM để tạo xếp hạng.

**Luồng xử lý.**

| Bước | Việc | Cell | Output | Trạng thái |
|---|---|---|---|---|
| 1 | Chọn instance và gán snapshot | `scale-data` | `SCALE_INSTANCES` | Đã chạy |
| 2 | Dựng graph code và doc tại snapshot | `build_graph`, `doc-links-v2` | File graph `.json` và `.summary.json` | Đã chạy |
| 3 | Tính gold bằng oracle | `1dc937a9`, `scale-setup` | `gold_ids` | Đã chạy (v4-L1) |
| 4 | Truy hồi AST, tức mốc chỉ dùng code | `load_graph_indices`, `v4-run` | `ast_ids` | Đã chạy (v4-L3) |
| 5 | Nguồn DOC | `doc_votes`, `doc_set`; từ 28/10/2026 danh sách trộn do `graph-proc` tạo | `doc_ids_vote_ast`, `doc_cand`; `doc_ids_doc_kgc` | `vote_ast` đã chạy. `doc_kgc` đã chạy (v4-L8) |
| 6 | Nguồn HIST theo Locus. Từ 29/10/2026 là hệ thống phụ "+HIST (Locus)" | `hist-build`, `hist-proc` | `doc_ids_hist_locus`, `hist_cand` | Đã chạy (v4-L4) |
| 6b | Nguồn HIST theo phần lời của commit, là nguồn HIST chính từ 29/10/2026 | `hist-msg` | `doc_ids_hist_msg`, `hist_msg_cand` | Đã cài (29/10/2026, mục 6b) |
| 7 | Nguồn ISSUE | `issue-fetch`, `issue-index` | `doc_ids_issue`, `issue_cand` | Đã chạy (v4-L2a) |
| 7b | Xếp hạng node sau hop theo KGCompass: nguồn GRAPH và danh sách DOC mới | `graph-proc` | `doc_ids_graph`, `doc_ids_doc_kgc` | Đã chạy (v4-L8, mục 8b) |
| 8 | Trộn các nguồn với AST | `v4-fusion` | `V4_FUSED`, `fusion.json` | RRF gốc đã chạy (v4-L7). Bản có trọng số đã chạy ở v4-L4 đến v4-L6 |
| 9 | Judge, chỉ chấm bằng chứng | `judge-v4` | Nhãn trong `judge_v4/` | Cài đặt mới từ 26/10 (bỏ lý do, thinking MINIMAL, bỏ `#code2`) đã chạy (v4-L6). Judge v5 đã cài (29/10/2026). `#suff` chưa làm |
| 10 | Đánh giá | `verify-v4` | Các bảng ở mục 10 | Bảng 1, 2, kiểm định và phần bằng chứng đã chạy (v4-L7). Phân tích độ phủ doc (mục 10.2) đã chạy (v4-L8). Độ đo bằng chứng mới đã cài (29/10/2026) |
| 11 | Phân tích thành phần Fix | `hist-fix-check`, đã bỏ khỏi notebook ngày 27/10/2026 | Kết quả ở mục 6.6 | Đã chạy (v4-L2a) |
| 12 | Độ đo theo cấu trúc: số node phải đọc và độ sâu tới gold | `depth-v4` | Bảng trong output | Đã chạy (v4-L6, v4-L7) |

Từ ngày 27/10/2026, notebook chỉ còn các cell của pipeline v4. Code của v3 và code chỉ để phân tích đã bị bỏ (mục 11).

---

## 1. Dữ liệu và snapshot

**Mục đích.** Bước này chọn instance và gán mỗi instance cho một graph. Build một graph cho mỗi instance thì quá tốn, nên các instance gần nhau về thời gian dùng chung một graph.

**Input.** Dữ liệu là split `test` của `princeton-nlp/SWE-bench`. Từ ngày 27/10/2026, thực nghiệm gồm cả 12 repo của tập test, với 2.294 instance, theo quyết định 58 của `research_context.md`. `SCALE_REPOS` là `SCALE_REPOS_ALL`. Kết quả của mọi repo nằm ở `v4/`, và nhãn judge nằm ở `judge_v4/`. Các lượt v4-L1 đến v4-L7 chỉ chạy trên Django và SymPy, với 1.236 instance. Biến `V4_PHASE`, có từ ngày 26/10/2026 để tách hai đợt, đã bị bỏ.

**Cách làm.**
1. Trong mỗi cặp (repo, version), instance được sắp theo thời điểm của base commit.
2. Một khoảng mới bắt đầu khi base commit cách đầu khoảng hiện tại hơn 60 ngày.
3. Snapshot của một khoảng là base commit **sớm nhất** trong khoảng. Vì vậy không snapshot nào chứa bản sửa của một instance khác trong cùng khoảng.
4. Instance bị loại khi graph snapshot không có gold nào là Function hoặc Class. Sau bước này còn 1.186 instance.

**Kết quả.** Django có 40 snapshot cho 820 instance. SymPy có 46 snapshot cho 366 instance.

**Không chia dữ liệu.** Theo quyết định ngày 15/10/2026, mọi kết quả đều dùng cả 1.186 instance. Từ ngày 27/10/2026, không tham số nào được chọn trên dữ liệu (quyết định 57), và không có bước xác nhận trên repo giữ lại (quyết định 58). Trường `lite` vẫn được giữ trong dữ liệu, nhưng không còn dùng để chia tập.

**Giới hạn.** Snapshot sớm hơn base commit tới 60 ngày. Vì vậy truy hồi chạy trên code và doc cũ hơn trạng thái thật của issue. Việc 1.3 trong `planning.md` sẽ đo sai lệch này trên 100 instance.

**Cơ sở.** Chưa có bài báo. Đây là phép xấp xỉ để giảm chi phí.

**Trạng thái.** Đã chạy.

---

## 2. Graph

### 2.1 Graph code

**Mục đích.** Graph code cho biết repository có những hàm, lớp, module nào, và chúng liên quan với nhau ra sao.

**Cách làm.**
- Code được parse bằng tree-sitter cho Python.
- File bị bỏ nếu nằm trong thư mục `tests`, `test`, `examples`, `example`, `benchmarks` hoặc `docs`. File `conftest.py` và `setup.py` cũng bị bỏ.
- Node gồm ba loại là Module, Class và Function. Id có dạng `{8 ký tự đầu của snapshot}:{đường dẫn}:{tên lồng nhau}`. Ví dụ `838e432e:django/db/models/query.py:QuerySet:filter`.
- Mỗi node lưu tên, file, dòng đầu, dòng cuối và source. Source bị cắt ở 8.000 ký tự để file JSON không quá lớn.
- Cạnh gồm `Defines` (cha định nghĩa con), `Imports`, `Calls` và `Inherits`. Cạnh `Calls` được phân giải bằng heuristic.

**Embedding.** Model là `BAAI/bge-small-en-v1.5`. Với Function và Class, văn bản được embed là 2.000 ký tự đầu của source. Với DocChunk, văn bản là heading cộng nội dung. Vector được chuẩn hóa và làm tròn tới 5 chữ số. Module không có embedding.

**Lưu trữ.** Graph được ghi bằng orjson thành file `.json`, kèm file `.summary.json` chỉ có id, nhãn, tên, file và dòng của node. Bộ nhớ đệm khi build dùng khóa gồm cả đường dẫn lẫn nội dung file.

**Cơ sở.** Chưa có bài báo. Đây là thiết kế từ v2.

**Trạng thái.** Đã chạy.

### 2.2 Graph doc

**Mục đích.** Graph doc đưa tài liệu của dự án vào graph và nối từng đoạn tài liệu với hàm/lớp mà nó mô tả.

**Cách làm.**
- Thư mục doc là thư mục đầu tiên tồn tại trong danh sách `docs`, `doc`, `documentation`, `Documentation`. Các thư mục `_build`, `_static`, `_templates`, `_themes`, `generated` và `auto_examples` bị bỏ. File được đọc là `.rst`, `.md` và `.txt`.
- Mỗi file là một node `Document`. File được chia thành các đoạn theo heading của RST. Mỗi đoạn là một node `DocChunk`, nối với `Document` bằng cạnh `HasChunk`. Đoạn dài hơn 1.600 ký tự được cắt tiếp theo đoạn văn, và mỗi phần vẫn giữ heading.
- Cạnh `Documents` nối DocChunk với Function hoặc Class. Cạnh được lấy từ role `:func:`, `:meth:`, `:class:`, `:attr:`, `:exc:`, `:obj:` và từ directive `function`, `class`, `method`, `exception`, `attribute`, `decorator` (có thể có tiền tố `py:` hoặc `auto`). Tên dừng ở dấu `(`, nên chữ ký bị bỏ. Directive method không có tên class đi trước được gán cho class gần nhất. Directive `.. module::` và `.. currentmodule::` đặt module ngữ cảnh.
- Cạnh `References` nối doc với doc, lấy từ role `:doc:`.

**Cách nối tên (bản v2, dùng từ v3).** Bảng tên giữ mọi node khớp một tên. Các khóa gồm `module.name`, `pkg.name`, tên trơn, `Class.name` và `pkg.Class.name`. File test không được đưa vào bảng. Tên được thử kèm module ngữ cảnh trước. Nếu nhiều node khớp, chỉ giữ node trong module đó. Nếu vẫn mơ hồ, cạnh không được tạo.

| Snapshot | Số cạnh trước và sau v2 | Tỷ lệ cạnh đúng module trước và sau v2 |
|---|---|---|
| Django `838e432e` | 6.357 và 5.641 | 64,8% và 74,6% |
| SymPy `9bf73cc2` | 1.616 và 1.445 | 70,5% và 81,0% |

**Vấn đề đã biết (đo ngày 23/10/2026, chi tiết ở mục 6.10 của `planning.md`).** Directive đầu mục đã nối đúng method. Cạnh tới class đến chủ yếu từ role trong văn xuôi (Django: 2.437 trên 2.962 cạnh tới class). Phần nối tiếp của một mục dài không nối tới chủ thể của mục (Django: 1.298 trên 6.189 chunk). 117 node (1,3% hàm/lớp Django) nhận 35,3% số cạnh. Ở SymPy, 465 trên 556 chunk có cạnh là khung autodoc không có văn xuôi.

**Thiết kế sửa (đã chốt, chưa cài).** Có ba thay đổi. Thứ nhất, kế thừa chủ thể của mục cho các phần nối tiếp. Thứ hai, trong `doc_votes`, nhân phiếu với idf(n) = log(1 + N / df(n)), với df(n) là số chunk có cạnh tới n. Thứ ba, có điều kiện: loại khung autodoc rỗng khỏi tập của `search_doc`. Graph giữ một loại cạnh `Documents`.

**Cơ sở.** Chưa có bài báo. Số liệu trên là phép đo của đề tài.

**Trạng thái.** Đã chạy. Thiết kế sửa ở mục 6.10 của `planning.md` đã chốt ngày 23/10/2026, chưa cài. Từ ngày 28/10/2026, danh sách DOC khi trộn do `graph-proc` xếp (mục 8b), không dùng `doc_votes` nữa. Vì vậy thay đổi thứ hai (idf trong `doc_votes`) không còn tác dụng lên kết quả. Hai thay đổi còn lại sửa cạnh `Documents` và tập chunk, nên vẫn áp dụng.

---

## 3. Gold và oracle

**Mục đích.** Gold là các hàm/lớp mà bản vá thật đã sửa. Oracle là hàm `get_oracle`, đọc một diff rồi trả về các hàm/lớp bị sửa. Gold của instance, touch set của HIST và việc gán hunk cho hàm ở HIST đều dùng cùng oracle này.

**Cách làm.**
1. Các file `.py` bị sửa được parse tại đúng base commit của instance bằng `_file_nodes_at`. Mỗi node có thêm `deco_start` (dòng của decorator đầu tiên) và `indent` (độ thụt lề của dòng `def` hoặc `class`).
2. Mỗi dòng bị xóa được gán cho hàm/lớp hẹp nhất chứa nó. Khoảng dòng của node tính từ decorator đầu tiên.
3. Các dòng thêm liền nhau tạo thành một khối, gán theo điểm chèn. Khối được gán cho node khi nó nằm giữa thân node. Khối cũng được gán khi nó nối vào cuối thân node và mọi dòng thụt sâu hơn dòng `def`. Gặp một dòng thụt nông hơn nghĩa là bắt đầu code mới, nên phần sau không được gán. Decorator mới ngay trên dòng `def` được gán cho hàm đó.
4. Class chỉ là gold khi có dòng đổi nằm trong class nhưng ngoài mọi method.
5. File đổi tên được đọc theo tên cũ ở base commit. Bảng đổi tên được trả về để đổi id sang tên mới.
6. Gold được đổi sang id của graph snapshot. Gold không có trong snapshot bị bỏ và được đếm.

**Kiểm tra (việc 1.1).** Oracle mới đạt 12 trên 12 ca tự dựng. Trên 1.006 instance từng là tập test của v3, gold đổi ở 44 instance. Có 81 node được thêm và 29 node sai bị bỏ.

**Giới hạn.** Gold, HIST và ISSUE dùng chung oracle. Lỗi chung của oracle có thể làm các nguồn trông tốt hơn thực tế. Điểm này được ghi là mối đe dọa trong luận văn.

**Cơ sở.** Chưa có bài báo.

**Trạng thái.** Đã chạy (v4-L1).

---

## 4. Truy hồi AST, tức mốc chỉ dùng code

**Mục đích.** Đây là hệ thống chỉ dùng code. Mọi nguồn khác được so với hệ thống này.

**Query.** Query là `problem_statement` của instance.

**Cách làm.**
1. **BM25** dùng `BM25Okapi` của thư viện `rank_bm25` với tham số mặc định (k1 = 1,5 và b = 0,75). Tập tài liệu gồm mọi node không phải doc, kể cả Module. Văn bản của node là source. Nếu source ngắn hơn 5 ký tự, văn bản là nhãn, tên và file. Token được tách bằng `_tokenize_code`: tách camelCase, đưa về chữ thường, rồi lấy các chuỗi chữ và số. Vì vậy snake_case cũng bị tách.
2. **Embedding.** Query được bỏ các khối code trong dấu ```, rồi cắt ở 2.000 ký tự. Query được so cosine với embedding của Function và Class.
3. **Gộp.** Lấy 500 node đầu của BM25 và 500 node đầu của embedding. Điểm của node là Σ 1/(60 + r), với r là hạng bắt đầu từ 0 trong từng danh sách. Từ ngày 22/10/2026, các node bằng điểm được xếp theo id. Trước đó, thứ tự của chúng phụ thuộc thứ tự duyệt một `set`, nên lệch nhẹ giữa các lần chạy.
4. Lấy 500 node đầu sau khi gộp (`EXP_DEEP`), rồi chỉ giữ Function và Class. Vì vậy danh sách có tối đa 500 hàm/lớp. Ở v3, chỉ 100 id đầu được lưu. Cell `v4-run` lưu đủ danh sách này.

**Cell `v4-run`.** Mỗi instance có một dòng trong `V4_DIR/scale_rows_v4.jsonl`. Cell chạy tiếp từ instance chưa có. Khi file có dòng thiếu dữ liệu bước A (`doc_cand`), cell đổi tên file đó thành `scale_rows_v4_truoc_buoc_A.jsonl` rồi tính lại mọi instance. Từ ngày 22/10, mỗi dòng ghi `rank_rule`. Khi giá trị này khác `V4_RANK_RULE` hiện tại, cell cũng dựng lại file, và giữ file cũ dưới tên có ngày giờ. Phần này đã cài, chưa chạy trên Kaggle. Từ ngày 28/10/2026, `scale_row` ghi thêm `gold_doc` và `doc_cov` (mục 10.2). Khi file có dòng thiếu `gold_doc`, cell cũng dựng lại file. Trên một `/kaggle/working` mới, điều kiện này không tốn thêm gì.

**Cơ sở.** Hằng số k = 60 của RRF lấy từ Cormack, Clarke và Büttcher (SIGIR 2009). Các lựa chọn còn lại là thiết kế từ v2 và chưa có bài báo làm cơ sở.

**Trạng thái.** Đã chạy (v4-L3). Bản sửa xếp hòa theo id đã chạy ở v4-L5, khi file kết quả được dựng lại.

---

## 5. Nguồn DOC (`vote_ast`)

**Mục đích.** Nguồn này dùng doc để chọn ra các hàm/lớp liên quan tới issue.

**Cách làm.**
1. **Tìm chunk.** Chỉ các DocChunk có ít nhất một cạnh `Documents` được xét. Các chunk được xếp bằng RRF của hạng BM25 và hạng embedding, tính bên trong tập chunk đó. Năm chunk đầu được giữ (`EXP_N_DOC = 5`).
2. **Bỏ phiếu.** Mỗi chunk bỏ phiếu cho mọi Function/Class mà nó có cạnh `Documents` tới. Phiếu bằng điểm RRF của chunk nhân 0,8, là trọng số của cạnh `Documents`. Một node nhận nhiều phiếu thì giữ phiếu cao nhất.
3. **Lan phiếu một bước.** Từ mỗi node được bỏ phiếu, phiếu lan sang các Function/Class nối tới nó bằng cạnh AST chiều xuôi, với hệ số 0,5. Cạnh AST gồm `Calls`, `Inherits`, `Defines` và `Imports`. Node có hơn 20 hàng xóm thì không lan, để tránh hub. Ví dụ, chunk nối tới class `QuerySet` thì các method do `QuerySet` định nghĩa cũng nhận phiếu qua cạnh `Defines`.
4. **Sắp xếp.** Tập node được sắp theo hạng AST. Node ngoài 500 hạng đầu của AST giữ thứ tự phiếu ở cuối. Vì vậy DOC thực chất là các ứng viên AST được bằng chứng doc chọn lọc.
5. **Đối chứng `random_ast`** của v3 dùng năm chunk ngẫu nhiên có cạnh `Documents`. Từ ngày 27/10/2026, nguồn này không còn được tính.

**Lưu ý.** Mục 4.3 của `research_context.md` ghi rằng phiếu chỉ lan qua cạnh `Calls`. Code lan theo mọi cạnh AST chiều xuôi, như mô tả ở trên.

**Output.** Mỗi dòng kết quả có `doc_ids_vote_ast`, `doc_score_vote_ast`, `doc_r_vote_ast` (hạng AST, 0 nếu ngoài 500), `doc_gold_vote_ast`. Từ ngày 27/10/2026, các chunk đã dùng và đích cạnh của từng chunk không còn được ghi, vì chỉ judge của v3 đọc chúng.

**Ứng viên bằng chứng (bước A).** `doc_cand` ghi 10 chunk đầu của `search_doc` (chunk có cạnh `Documents`). 5 phần tử đầu chính là các chunk mà DOC dùng. `doc_cand_all` ghi 10 chunk đầu của `search_doc_all` (mọi chunk). Mỗi phần tử gồm id, `score` (RRF), `bm25`, `cos` (cosine embedding) và đích cạnh `Documents`. Các điểm gốc này dùng để chọn ngưỡng ngoại tuyến ở bước G. `doc_cand` là pool của judge cho loại bằng chứng doc.

**Cơ sở.** Chưa có bài báo. Đây là thiết kế từ v2.

**Trạng thái.** Đã chạy.

**Từ ngày 28/10/2026.** `scale_row` vẫn tính và ghi bốn cột của `vote_ast`, nhưng `v4-fusion` không trộn danh sách này nữa. Danh sách DOC khi trộn là `doc_kgc`. Danh sách này đi từ đích cạnh `Documents` của 10 chunk trong `doc_cand`, rồi xếp theo công thức của KGCompass (mục 8b).

---

## 6. Nguồn HIST theo Locus

**Mục đích.** Nguồn này xếp hạng hàm/lớp bằng cách so khớp issue với nội dung của các thay đổi cũ. Đây là bước "đọc title, message và diff" của quy trình debug, nhưng không dùng LLM.

### 6.1 Lớp history (`hist-build`)

- **Đơn vị** là commit trên nhánh chính (`git log --first-parent`). Với SymPy, phần lớn đơn vị là merge commit của một pull request. Lịch sử được lấy từ snapshot mới nhất lùi tới 5 năm trước snapshot cũ nhất. Trên Kaggle (v4-L1), Django có 22.111 đơn vị, trong đó 10.736 đơn vị sửa ít nhất một hàm/lớp. SymPy có 8.141 đơn vị, trong đó 6.224 đơn vị sửa ít nhất một hàm/lớp.
- Mỗi đơn vị lưu sha, cha thứ nhất, thời điểm, message (cắt ở 2.000 ký tự) và **touch set**. Touch set là các hàm/lớp mà đơn vị đã sửa. Nó được tính bằng oracle mới trên `git diff -U0` giữa đơn vị và cha thứ nhất. Id dùng tên file sau khi đổi tên.
- File là `history/<repo>_history_v2.jsonl`.

### 6.2 Chỉ mục hunk (`hist-proc`, hàm `build_hunks`)

- Chỉ các đơn vị có touch set khác rỗng được duyệt. Đơn vị khác không đổi hàm/lớp nào trong file có ở graph.
- Diff là `git diff -U3 -w` giữa cha thứ nhất và đơn vị, chỉ cho file `.py`. Tùy chọn `-w` bỏ thay đổi chỉ về khoảng trắng.
- File mới tạo và file bị bỏ khỏi graph (test, docs, ví dụ) không được dùng. Hunk chỉ đổi comment bị bỏ.
- Mỗi hunk được gán cho các hàm/lớp mà nó đổi, bằng oracle mới chạy trên riêng hunk đó. Hunk chỉ đổi ở cấp module vẫn được giữ, với danh sách rỗng, vì nó vẫn là tài liệu khi tính IDF.
- File là `history/<repo>_hunks_v2.jsonl`. Ước tính có khoảng 65 nghìn hunk cho Django và 55 nghìn hunk cho SymPy. Chỉ mục được dựng một lần, mất khoảng 45 phút đến 1 giờ trên Kaggle.

### 6.3 Công thức

Các công thức dưới đây giữ nguyên từ Locus (Wen, Wu, Cheung, ASE 2016). Ở đây b là issue, h là hunk, f là hàm/lớp.

1. **Tài liệu** là một hunk, gồm dòng ngữ cảnh, dòng xóa, dòng thêm và commit message. Dòng tiêu đề `@@` và ký tự `+`, `-` ở đầu dòng bị bỏ.
2. **NL(b, h) = cos(b_nl, h_nl).** Token được tách bằng `_tokenize_code`, bỏ stop word tiếng Anh của scikit-learn và từ khóa Python, rồi đưa về gốc bằng Porter của nltk. Trọng số là w_td = (log f_td + 1) × log(N / n_t). Ở đây f_td là số lần từ t xuất hiện trong tài liệu d, N là số tài liệu, n_t là số tài liệu chứa t.
3. **CE(b, h) = cos(b_ce, h_ce).** Token CE là tên giữ nguyên không tách. Chỉ giữ token khớp một tên lớp, tên hàm hoặc tên module dạng chấm trong graph của snapshot, ví dụ `QuerySet` hay `django.db.models.query`.
4. **α = min(1, λ × số tên code trong issue / số token đã tách của issue)**, với λ = 5.
5. **Fix(f) = Σ_i 1 / (1 + e^(−12·t_i + 12))**, với t_i là thời điểm chuẩn hóa của commit sửa lỗi thứ i đã sửa f.
6. **score(b, f) = max_{h ∈ H(f)} {NL(b, h) + α·CE(b, h)} + β₁·Fix(f)**, với β₁ = 0,1.

### 6.4 Chỗ chuyển đổi so với bài gốc

Locus làm ở mức file và mức commit. Đề tài làm ở mức hàm/lớp, nên có bảy chỗ chuyển đổi.

| Mã | Chuyển đổi | Lý do |
|---|---|---|
| A1 | File s thay bằng hàm/lớp f. H(f) là các hunk có dòng đổi nằm trong f, theo oracle mới. | Locus đại diện file bằng hunk tốt nhất. Quy tắc đó được áp nguyên cho hàm. |
| A2 | Commit sửa lỗi là đơn vị có message khớp `fix\|bug` (không phân biệt hoa thường). | Locus chỉ dẫn heuristic mà không ghi cụ thể. AmaLgam ghi rõ quy tắc này. |
| A3 | t = 0 ở đơn vị cũ nhất của file history. t = 1 ở `created_at` của instance. | Locus đặt 0 là ngày phát hành. Issue của SWE-bench nằm trên nhánh phát triển nên không có ngày phát hành. |
| A4 | Tài liệu là hunk của các đơn vị là tổ tiên của snapshot. IDF tính riêng cho từng snapshot. | Locus dùng mọi thay đổi trước lúc báo lỗi. Điều kiện tổ tiên chặt hơn và chống rò rỉ. |
| A5 | Chỉ file `.py` có trong graph, `git diff -w`, bỏ hunk chỉ đổi comment. | Locus bỏ hunk ngoài file nguồn và hunk chỉ đổi khoảng trắng hoặc comment. Bài không ghi cách nhận ra hunk chỉ định dạng lại, nên bước đó không làm. |
| A6 | Query là `problem_statement`. | SWE-bench tách `hints_text` ra riêng, giống việc Locus không dùng phần thảo luận của developer. |
| A7 | Từ giống code là từ có dấu `_` hoặc `.`, có chữ hoa sau ký tự đầu, nằm trong backtick, hoặc đứng ngay trước `(`. Từ có dấu chấm được tách thêm thành từng phần. | Locus dùng heuristic của Meng và cộng sự nhưng không ghi chi tiết. |

**Giới hạn của A7.** Quy tắc này bỏ sót tên lớp chỉ viết hoa chữ đầu. Ví dụ, issue `django-10880` nhắc tới `Count` và `Case`, nhưng α = 0 vì hai từ này không được coi là giống code.

### 6.5 Output

- Mỗi dòng của `scale_rows_v4.jsonl` có `doc_ids_hist_locus`, `doc_score_hist_locus`, `doc_r_hist_locus` và `doc_gold_hist_locus`, cùng dạng với nguồn DOC.
- Danh sách giữ tối đa 500 hàm/lớp có điểm lớn hơn 0, bằng độ sâu của xếp hạng AST. Hàm/lớp không có trong graph của snapshot bị bỏ. Điểm bằng nhau thì xếp theo id.
- `hist_locus_alpha` ghi α của issue.
- Hai cấu hình con cho phân tích thành phần được ghi với hậu tố `_nl` (chỉ NL) và `_nlce` (NL + α·CE).
- `hist_locus_best` ghi hunk tốt nhất của 10 hàm/lớp đầu, làm bằng chứng cho judge cũ. Từ ngày 27/10/2026, cột này không còn được ghi, vì `hist_cand` đã thay nó.
- **Ứng viên bằng chứng (bước A).** `hist_cand` ghi 10 hunk có s = NL + α·CE cao nhất trong snapshot. Mỗi phần tử gồm sha 8 ký tự, file, thứ tự hunk, NL, CE (chưa nhân α) và các hàm/lớp mà hunk sửa. Từ v4-L4, hunk của commit sửa hơn 50 hàm/lớp (`HIST_MAX_TOUCH`) bị bỏ, và chỗ trống được bù bằng hunk kế tiếp. Lý do là các commit này chỉ chiếm 1,0% (Django) và 2,4% (SymPy) số commit, nhưng chứa 25% và 39% số hunk, và mỗi hunk kéo theo danh sách hàm/lớp rất dài khi đưa cho judge. ROSE cũng bỏ transaction chạm hơn 30 thực thể. Dòng có `hist_cand_max_touch` khác ngưỡng hiện tại được tính lại. `hist_cand` là pool của judge cho loại bằng chứng HIST.

### 6.6 Kiểm tra trên máy

Harness dùng 6 instance Django, 6 instance SymPy và khoảng 200 ngày history trước mỗi snapshot.

| Phép kiểm tra | Kết quả |
|---|---|
| Hàm/lớp của các hunk so với touch tính lại bằng oracle mới | 77 đơn vị trùng hẳn. 3 đơn vị có hunk ít hơn touch, do `-w` và bộ lọc comment |
| Rò rỉ | Mọi hunk được dùng đều thuộc đơn vị là tổ tiên của snapshot |
| Tính tay điểm của hàm đứng đầu | Khớp tới 6 chữ số ở cả hai repo |
| Bước trộn | `fused_multi` đọc được nguồn mới |
| Chạy lại | Bỏ qua mọi dòng đã có kết quả |

Bảng trên là lượt thử ngày 15/10, khi máy chưa có nltk. Từ ngày 21/10, máy đã có nltk, và các lượt thử dùng Porter thật. Kết quả các lượt thử từ ngày 21/10 nằm ở mục 12 của `experiment_log.md`.

**Kết quả của bước D (`hist-fix-check`).** Ở Django, 68,9% đơn vị có touch khớp `fix|bug`. Fix kéo hàm bị sửa nhiều lần lên đầu danh sách: trung vị số lần bị sửa của 10 hàm/lớp đầu tăng từ 6,5 lên 37,5. Khi đứng riêng, Top@10 của Django giảm từ 57,7% (NL+CE) xuống 43,1%. Đổi A3 (t = 0 ở đơn vị cũ nhất trong 5 năm trước snapshot) chỉ nâng lên 51,6%. Sau khi trộn với AST, Fix không thêm gì: Top@10 là 62,1 với Fix và 62,3 không có Fix. A2 và A3 chưa đổi. Cell `hist-fix-check` là phân tích một lần. Cell này đã bị bỏ khỏi notebook ngày 27/10/2026, còn kết quả được giữ ở đây.

**Cơ sở.** Locus và AmaLgam, đã đọc toàn văn. Bảy chỗ chuyển đổi không có trong bài.

**Trạng thái.** Đã chạy (v4-L1, v4-L4).

**Nguồn HIST của v3.** HIST của v3 tìm commit bằng BM25 và embedding trên message, rồi cho commit bỏ phiếu cho hàm đã sửa. Ngày 27/10/2026, nguồn này bị bỏ khỏi notebook, cùng hàm `hist_index` và phần tính embedding cho message của `hist-build`.

---

## 6b. Nguồn HIST theo phần lời của commit (`hist-msg`)

> Thêm ngày 29/10/2026, theo mục 6.18.3 của `planning.md`. Từ ngày này, đây là nguồn HIST của các hệ thống chính (+HIST, +ALL, ALL−DOC, ALL−ISSUE, +ALL+GRAPH). HIST theo Locus (mục 6) được giữ thành hệ thống phụ "+HIST (Locus)", để so với các lượt trước.

**Mục đích.** HIST cung cấp phần lời của lịch sử. Phần này cho biết trước đây cái gì hỏng, vì sao code được sửa, quyết định thiết kế nào đã được đưa ra, và lỗi tương tự đã được xử lý ra sao. Việc tìm code là của AST. HIST theo Locus so issue với diff của hunk và khớp tên code (CE), tức là làm lại việc của AST.

**Văn bản của một commit.** text(c) gồm message đầy đủ của commit c, cộng tiêu đề và mô tả của mọi ticket, issue hoặc PR liên kết với c.
- Message được lấy bằng một lệnh `git log` cho mỗi repo. File history chỉ giữ 2.000 ký tự đầu của message, nên không dùng được ở đây.
- Với Django, liên kết là ticket có "Fixed #N" trong message. Loại "Refs #N" không được dùng.
- Với repo GitHub, liên kết là issue mà commit đóng, và PR của commit. PR được nhận ra bằng "Merge pull request #N" hoặc "(#N)" ở cuối dòng đầu, theo đúng hai biểu thức của `issue-index`.
- Liên kết tới ticket và issue được lấy bằng hàm `issue_links` của `issue-index`. Đây là hàm ghi ra `<repo>_links.jsonl`, nên các cặp trùng với file đó. Cell gọi hàm thay vì đọc file, để vẫn chạy được khi file không còn. File liên kết không có PR, nên số PR được tìm lại trong message. Nội dung PR lấy từ các dòng `pr = true` của `<repo>_reports.jsonl`.

**Commit được xét.** Commit trên nhánh chính phải là tổ tiên của snapshot, sửa ít nhất một hàm/lớp có trong graph snapshot, và sửa không quá 50 hàm/lớp (`HIST_MAX_TOUCH`, như `hist_cand`).

**Rò rỉ.** Một liên kết chỉ được đưa vào text(c) khi báo cáo được tạo trước mốc cắt của instance ít nhất 1 ngày, và không phải báo cáo của chính instance. Mốc cắt và cách nhận ra báo cáo của chính instance lấy từ `issue_cutoff` và `issue_own` của nguồn ISSUE (mục 7). Với repo GitHub, PR của chính instance cũng bị bỏ. Khi liên kết bị bỏ, commit vẫn được xét với message.

**TF-IDF.** Cách tách token, bỏ stop word, đưa về gốc bằng Porter và công thức trọng số giống NL của Locus (mục 6.3). IDF được tính riêng cho từng snapshot, trên text(c) của các commit được xét. Ở bước tính IDF, text(c) chỉ gồm các liên kết tạo trước thời điểm của snapshot ít nhất 1 ngày. Với từng instance, commit nào có liên kết mà bộ lọc của instance cho kết quả khác thì được tính lại vectơ, còn IDF giữ nguyên. `issue-index` cũng làm theo kiểu này: IDF theo snapshot, còn bộ lọc theo instance.

**Điểm của commit.** Hai danh sách xếp hạng commit được gộp bằng RRF gốc với k = 60 (`HIST_MSG_K`).
1. Danh sách lời gồm các commit có cosine giữa issue và text(c) lớn hơn 0, xếp theo cosine giảm dần.
2. Danh sách nối AST gồm các commit sửa ít nhất một hàm/lớp trong 500 node đầu của AST. Danh sách này xếp theo hạng AST tốt nhất trong các hàm/lớp mà commit sửa.

s(c) = 1/(60 + hạng trong danh sách lời) + 1/(60 + hạng trong danh sách nối AST). Commit không có mặt trong một danh sách thì không nhận số hạng của danh sách đó. Như vậy commit nối tới node AST được ưu tiên, nhưng không bắt buộc. Hòa trong từng danh sách và hòa ở s(c) đều được xếp theo commit mới hơn trước, rồi theo sha.

**Output.**
- `doc_ids_hist_msg`, `doc_score_hist_msg`, `doc_r_hist_msg` và `doc_gold_hist_msg` có cùng dạng với nguồn DOC. score(f) = max s(c) trên các commit c đã sửa f, theo quy tắc A1 của mục 6.4. Danh sách dài tối đa 500. Không có Fix và CE.
- `hist_msg_cand` là pool của judge cho HIST, gồm 10 commit có s(c) cao nhất. Mỗi phần tử ghi sha, thời điểm commit, s, cosine, hạng AST tốt nhất, các hàm/lớp mà commit sửa, và số của các báo cáo liên kết đã qua bộ lọc. Danh sách hàm/lớp chỉ dùng cho phân tích, không đưa vào prompt.
- `hist_msg_cfg` ghi cấu hình. Dòng có cấu hình khác `HIST_MSG_CFG` được tính lại.
- Cell in tỷ lệ commit của pool có liên kết, tỷ lệ commit nối AST, và tỷ lệ instance có báo cáo nằm ở cả pool HIST lẫn pool ISSUE.

**Cơ sở.** Locus (Wen, Wu, Cheung, ASE 2016) cho thấy message chia sẻ từ với báo cáo lỗi nhiều hơn code, và cho công thức NL. HAFixAgent và HAFix (Shi và cộng sự) chọn commit theo chỗ code bị nghi, và thấy việc đưa diff thô cho LLM thường làm kết quả kém hơn. RRF gốc theo Cormack, Clarke và Büttcher (SIGIR 2009). Việc ghép phần lời của commit với ticket hoặc PR, việc dùng hạng AST làm danh sách thứ hai, và cách xếp hòa theo commit mới hơn là đề xuất của đề tài.

**Giới hạn đã biết.** Message của Django có trung vị 72 ký tự, và 32,7% message có phần thân ngoài dòng đầu. Ở SymPy, 92% commit trên nhánh chính là merge của PR, với phần thân trung vị 42 ký tự. Phần lời chủ yếu đến từ ticket hoặc PR liên kết, nên pool HIST mới trùng một phần với pool ISSUE. Ở tầng xếp hạng, CE đang đóng góp phần lớn mức tăng của Q2, nên HIST mới có thể kém Locus. Kết quả sẽ được báo đúng như vậy.

**Kiểm tra trên máy (29/10/2026).** Harness chạy mọi cell của notebook trên 12 instance, gồm 6 instance Django ở snapshot `838e432e` và 6 instance SymPy ở snapshot `9bf73cc2`, với khoảng 200 ngày history trước mỗi snapshot.

| Phép kiểm tra | Kết quả |
|---|---|
| Tính lại độc lập bằng vòng lặp Python trên chuỗi thô (liên kết, bộ lọc, TF-IDF, hai danh sách, RRF, score(f)) | 12 trên 12 instance khớp: pool 10 commit, s và cosine tới 6 chữ số, danh sách 500 hàm/lớp, và liên kết đã qua bộ lọc |
| Rò rỉ | Không liên kết nào trong pool được tạo sau mốc cắt trừ 1 ngày, hay là báo cáo của chính instance |
| Bộ lọc theo instance | Cùng snapshot Django, số commit có liên kết qua bộ lọc khác nhau giữa các instance, ví dụ 2.449 và 2.513 trên 4.287 commit |
| Mô tả pool | 85,0% commit của pool có liên kết qua bộ lọc. Mọi commit của pool sửa ít nhất một node trong 500 node đầu của AST. 75,0% instance có báo cáo nằm ở cả pool HIST lẫn pool ISSUE |
| Các hệ thống khác | Danh sách trộn của AST, +DOC, +ISSUE, +GRAPH, ALL−HIST, hai cấu hình thành phần của Locus và +ISSUE (Refs) trùng lượt thử ngày 28/10/2026. "+HIST (Locus)" trùng "+HIST" của lượt đó |
| Độ dài request HIST | Trung bình khoảng 5.600 token, lớn nhất khoảng 14.600 token (ước lượng bằng số ký tự chia 4) |

Việc chạy lại cell trên file đã tính (không còn dòng nào phải tính) chưa được thử riêng. Cơ chế này giống `graph-proc`.

**Trạng thái.** Đã cài (29/10/2026), đã chạy thử trên 12 instance mẫu. Chưa chạy trên Kaggle.

---

## 7. Nguồn ISSUE

**Mục đích.** Nguồn này dùng các báo cáo lỗi cũ đã được sửa. Báo cáo cũ giống issue hiện tại thì các hàm mà nó đã sửa được cộng điểm.

**Tải dữ liệu (`issue-fetch`).**
- Django dùng ticket Trac có resolution là fixed, tải bằng CSV từ `code.djangoproject.com/query`, mỗi trang 500 ticket. Lần tải ngày 21/10/2026 được 19.388 ticket, trong 39 trang.
- SymPy dùng issue và PR đã đóng, tải qua `/repos/sympy/sympy/issues?state=closed` của GitHub, mỗi trang 100 mục. GitHub chỉ nhận tham số `page` cho 1.000 mục đầu, nên cell đi theo link "next" có con trỏ `after` trong header `Link`. Lần tải ngày 21/10 được 24.139 mục, gồm 9.607 issue và 14.532 PR, trong 8,3 phút với token. Từ ngày 26/10/2026, URL lấy theo tên repo, nên cell chạy được cho mọi repo GitHub.
- `GITHUB_TOKEN` là biến thường trong `v4-config`. Không có token thì GitHub chỉ cho 60 lượt gọi mỗi giờ. Tải dở thì cell đi tiếp từ link đã ghi ở file `.next`.
- Kết quả ghi ở `V4_DIR/issues/<repo>_reports.jsonl`. File đã có thì không tải lại.

**Liên kết báo cáo với commit (`issue-index`).**
- Django: commit có "Fixed #N" (loại fixed) hoặc "Refs #N" (loại refs) trong message, kể cả dạng danh sách. Cặp có cả hai loại được coi là fixed.
- Repo GitHub: PR có từ khóa đóng issue trong body nối tới đơn vị của PR đó. Đơn vị của PR là merge commit "Merge pull request #PR", hoặc commit squash có "(#PR)" ở cuối dòng đầu. Đơn vị có từ khóa đóng issue ngay trong message cũng được dùng. Từ khóa chỉ nhận số issue của chính repo, gồm "#N", "<repo>#N" và URL issue của repo.
- Quy tắc commit squash được thêm ngày 26/10/2026. Lý do là nhiều repo trong 10 repo còn lại của tập test merge PR theo kiểu squash. Trong 5 năm trước snapshot đo ở `coverage_report.md`, commit squash chiếm 2.101 trên 4.060 commit nhánh chính của scikit-learn, 1.473 trên 1.651 của xarray, 966 trên 3.102 của pylint và 269 trên 458 của seaborn. SymPy không có commit squash nào, và mẫu từ khóa của SymPy giữ nguyên, nên liên kết của SymPy không đổi.
- Cặp liên kết được ghi ở `V4_DIR/issues/<repo>_links.jsonl`.

**Điểm.** Điểm của hàm/lớp f là SimiScore(f) = Σ sim(b, b′) / |Fix(b′)|, theo BugLocator. Tổng chạy qua mọi báo cáo cũ b′ có f thuộc Fix(b′). Ở đây sim là cosine TF-IDF giữa issue và báo cáo cũ. Fix(b′) là hợp các touch set của những commit đã nối với b′ và là tổ tiên của snapshot. Token được tách bằng `_tokenize_code`, bỏ stop word tiếng Anh và đưa về gốc bằng Porter. TF-IDF là `TfidfTransformer(sublinear_tf=True)` của scikit-learn. IDF được tính riêng cho từng snapshot, chỉ trên báo cáo tạo trước thời điểm của snapshot.

**Lọc rò rỉ.**
1. Báo cáo cũ phải được tạo trước mốc cắt ít nhất 1 ngày. Mốc cắt mặc định (`ISSUE_CUTOFF = "instance"`) là thời điểm tạo báo cáo của chính instance. Khi nhận ra nhiều báo cáo, mốc là báo cáo mới nhất tạo trước `created_at`. Khi không nhận ra báo cáo nào, hoặc khi `ISSUE_CUTOFF = "pr"`, mốc là `created_at` của SWE-bench.
2. Commit sửa phải là tổ tiên của snapshot.
3. Báo cáo của chính instance bị loại. Báo cáo này được nhận ra khi title trùng dòng đầu của problem statement. Với repo GitHub, các issue mà PR của instance đóng cũng bị loại.
4. Báo cáo có Fix(b′) rỗng không đóng góp.

**Output.** Hai biến thể được ghi: chỉ từ liên kết fixed (`doc_*_issue`, `issue_cand`) và từ fixed cộng refs (`doc_*_issue_refs`, `issue_cand_refs`). Danh sách hàm/lớp dài tối đa 500. `issue_cand` ghi 10 báo cáo cũ có sim cao nhất và Fix(b′) khác rỗng, kèm cosine, Fix(b′) và loại liên kết. Mỗi dòng ghi `issue_sig`, dấu của cách tính gồm `ISSUE_CUTOFF`, `V4_EVID_N`, `LOCUS_TOPN` và cây cú pháp của cell. Dòng có dấu khác dấu hiện tại được tính lại.

**Kết quả (v4-L2a).** Mức trần là 83,2% (Django) và 63,4% (SymPy). Top@10 của ISSUE đứng riêng là 21,1% và 18,6%. Thêm "Refs #N" nâng mức trần của Django lên 88,1%, nhưng không giúp khi trộn với AST. Vì vậy hệ thống chính chỉ dùng "Fixed #N".

**Cơ sở.** BugLocator, chỉ đọc qua nguồn thứ cấp. Bộ lọc thời gian theo Lingxi và KGCompass.

**Trạng thái.** Đã chạy (v4-L2a). Bản cho mọi repo GitHub đã chạy ở v4-L6 và v4-L7 trên Django và SymPy, và cột ISSUE của hai lượt trùng nhau. Dấu cách tính lấy mã của cell từ biến `In` của IPython. Ở v4-L6, `In` rỗng, nên dấu chỉ dựa trên cấu hình (`bf41ef497580`). Ở v4-L7, dấu dựa trên mã của cell (`4172b591e4be`). Khi `In` rỗng, cell không báo lỗi, và một thay đổi trong mã sẽ không làm cột ISSUE được tính lại.

---

## 8. Trộn các nguồn với AST

**Mục đích.** Bước này gộp danh sách AST với danh sách của một hoặc nhiều nguồn thành danh sách cuối của mỗi hệ thống.

**Hàm hiện có (`fused_multi`).**
- Điểm của node x là 1/(60 + hạng AST của x) + Σ_s p_s / (60 + vị trí của x trong danh sách của nguồn s). Ở đây p_s là trọng số của nguồn s, và hạng bắt đầu từ 1.
- Node ngoài danh sách AST đã lưu vẫn nhận 1/(60 + hạng AST sâu) một lần, nếu hạng đó được biết.
- h node đầu của AST được giữ nguyên vị trí.

**Giới hạn đã biết.** Node ở hạng 10 của AST có điểm khoảng 0,0143. Bảng dưới đây cho biết hạng AST tệ nhất mà một node đứng đầu danh sách của nguồn vẫn vào được top 10.

| p | Hạng AST tệ nhất vẫn vào top 10 |
|---|---|
| 0,05 | 14 |
| 0,1 | 19 |
| 0,25 | 38 |
| 0,5 | 104 |
| 1 | Không giới hạn |

**Các hệ thống so sánh (mục 6.1 của `planning.md`).** Có AST, +DOC, +HIST, +ISSUE, +ALL và ba hệ thống bỏ bớt một nguồn (ALL−DOC, ALL−HIST, ALL−ISSUE).

`fused_multi` và cell `v3-recheck` đã bị bỏ khỏi notebook ngày 27/10/2026. Các hệ thống của v4 dùng cell `v4-fusion` mô tả dưới đây.

**Cách trộn của v4 (`v4-fusion`, từ ngày 27/10/2026).**
- Công thức là RRF gốc của Cormack, Clarke và Büttcher (SIGIR 2009), với trọng số bằng nhau: score(d) = 1/(60 + hạng AST của d) + Σ_s 1/(60 + hạng của d trong nguồn s). Hạng bắt đầu từ 1. Node không có trong một danh sách không nhận điểm từ danh sách đó. Mọi danh sách, kể cả AST, có trọng số 1. Không giữ cố định đầu danh sách AST.
- Mỗi nguồn xếp theo bằng chứng của chính nó. DOC xếp theo điểm `doc_votes` (từ 28/10/2026 là điểm S của `doc_kgc`, mục 8b), HIST theo điểm Locus, ISSUE theo SimiScore, GRAPH theo điểm S của `graph`. Hòa điểm xếp theo hạng AST rồi theo id, để kết quả lặp lại được. Danh sách trộn dài tới 500.
- Không tham số nào được chọn trên dữ liệu của đề tài. Hằng số k = 60 lấy từ bài.
- Có 11 hệ thống. Đó là 8 hệ thống của mục 6.1 trong `planning.md`, cộng ba hệ thống phụ là +HIST (chỉ NL), +HIST (NL+CE) và +ISSUE (thêm Refs). Từ ngày 28/10/2026 có thêm +GRAPH và +ALL+GRAPH, nên có 13 hệ thống.
- Output là `V4_FUSED` (tên hệ thống → hàm trả danh sách id) và `V4_DIR/fusion.json`. File này ghi phương pháp, k, độ dài danh sách, nguồn và hệ thống.

**Lịch sử.** Lượt v4-L2b (21/10/2026) dùng RRF gốc. Từ ngày 22/10/2026, cell chuyển sang RRF có trọng số theo nguồn. Trọng số được chọn trên lưới 0,05 đến 3 bằng kiểm định chéo 5 phần theo MAP, và RRF gốc được giữ làm 7 hệ thống đối chứng có đuôi " (RRF)". Ngày 27/10/2026, việc chọn trọng số bị bỏ theo quyết định của người dùng, vì nó chọn tham số trên chính dữ liệu của đề tài. Cell quay về RRF gốc. Các lượt v4-L3 đến v4-L6 dùng cách trộn có trọng số. Số liệu RRF gốc của các lượt đó nằm ở các hàng có đuôi "(RRF)" trong `experiment_log.md`.

**Cơ sở.** Cormack, Clarke và Büttcher (SIGIR 2009) cho công thức và hằng số k = 60. Bài này đã được đọc toàn văn.

**Giới hạn.** Bài của Cormack không thử trộn một danh sách mạnh với các danh sách yếu hơn nhiều. Ở lượt v4-L2b, cách này cho DOC và ISSUE một lá phiếu ngang AST, nên Top@10 của +DOC giảm từ 55,5% xuống 43,7%.

**Trạng thái.** Đã cài ngày 27/10/2026 và đã chạy thử trên 12 instance mẫu. Danh sách của mọi hệ thống trùng từng id với RRF trọng số bằng nhau của bản cũ. Đã chạy ở v4-L7. Kết quả ở mục 9 của `experiment_log.md`.

**Từ ngày 28/10/2026.** Có thêm nguồn GRAPH, và nguồn DOC đọc danh sách `doc_kgc`. Cả hai danh sách do cell `graph-proc` tạo (mục 8b). Có 13 hệ thống, tức 11 hệ thống cũ cộng +GRAPH và +ALL+GRAPH.

---

## 8b. Xếp hạng node sau hop theo KGCompass (`graph-proc`)

**Mục đích.** Bước này cho biết cách xếp hạng các node mà graph đưa vào kết quả, tức các node đi tới được từ node xuất phát qua cạnh của graph. Trước bước này, chỉ DOC đi trên graph. DOC lan phiếu một bước với hệ số 0,5, và hệ số này chưa có bài báo làm cơ sở. Bước này áp một công thức có cơ sở trong miền code cho mọi node sau hop.

**Công thức.** Điểm của một Function hoặc Class f là S(f) = β^l(f) × (α × cos_norm(e_issue, e_f) + (1 − α) × lev(t_issue, t_f)). Đây là phương trình 1 ở mục 3.1 của bài KGCompass.
- l(f) là tổng trọng số trên đường ngắn nhất từ issue tới f, tìm bằng Dijkstra. Cạnh được đi theo cả hai chiều.
- cos_norm = (cos + 1) / 2, như bài. Cosine tính giữa embedding của query và embedding của node. Model và cách lấy query giống AST (mục 4).
- lev = 1 − d / max(|a|, |b|), với d là khoảng cách Levenshtein theo ký tự. Đây là hàm `apoc.text.levenshteinSimilarity` mà code KGCompass gọi. Thư viện `rapidfuzz` cho cùng giá trị. a là dòng đầu của issue, cộng một dấu cách, cộng phần còn lại, như KGCompass. b là source của node, cắt ở 20.000 ký tự. Graph chỉ lưu tối đa 8.000 ký tự, nên b thực tế không quá 8.000 ký tự.
- β = 0,6 và α = 0,3, lấy từ mục 4.3 của bài. Tác giả KGCompass chọn hai giá trị này bằng cách thử trên SWE-bench. Đề tài dùng nguyên giá trị, không chọn lại trên dữ liệu của đề tài.

**Cạnh và trọng số.** Bài KGCompass không nêu trọng số cạnh, nên trọng số lấy từ code công khai của KGCompass. Code này có ba mức là 0,25, 0,5 và 1,0.

| Cạnh | Trọng số | Cơ sở |
|---|---|---|
| Issue tới node xuất phát | 0,25 | KGCompass cho mức này khi nối issue gốc với issue có tiêu đề giống nhất, tức một liên kết chọn bằng độ giống |
| `Defines` (module tới hàm/lớp, lớp tới method) | 0,25 | KGCompass cho 0,25 khi file chứa method và khi lớp chứa method |
| Module tới method của lớp | 0,25 | KGCompass nối mọi method với file chứa nó, kể cả method của lớp. Graph của đề tài chỉ có `Defines` từ lớp tới method, nên `graph-proc` thêm cạnh chứa này (28/10/2026). Hàm lồng trong hàm khác không có cạnh này |
| `Documents` (chunk tới hàm/lớp) | 0,5 | Cạnh được giải từ tên trong role và directive RST. KGCompass cho 0,5 khi tham chiếu được giải bằng khớp tên |
| `Calls` | 1,0 | KGCompass cho cạnh gọi hàm trọng số 1 |
| `Inherits` | 1,0 | KGCompass không có cạnh này. LocAgent xếp quan hệ kế thừa chung nhóm với quan hệ gọi, nên cạnh này nhận cùng trọng số với `Calls` |
| `Imports` | Không dùng | KGCompass không có cạnh này. Bỏ cạnh này thì graph hop trùng graph của `depth-v4` (mục 10.1) |

Cạnh `Calls` và `Inherits` chỉ được đi khi đích của cạnh nằm trong 500 node đầu của AST. KGCompass chỉ tạo cạnh gọi tới 500 method giống issue nhất. Đề tài thay tập đó bằng danh sách AST 500 node đã có. Module chỉ là node trung gian, không là ứng viên.

**Ngân sách.** Ứng viên phải có l ≤ 4. Giá trị này lấy từ code KGCompass (`max_hops=4`), vì bài không nêu ngưỡng. Bảng sau cho ví dụ.

| Node | l | 0,6^l |
|---|---|---|
| Node xuất phát của GRAPH | 0,25 | 0,880 |
| Hàm cấp module hoặc method của lớp, cùng file với node xuất phát, kể cả method của lớp khác. Áp dụng khi node xuất phát là hàm cấp module, lớp hoặc method của lớp | 0,75 | 0,682 |
| Hàm cấp module hoặc method của lớp, cùng file, khi node xuất phát là hàm lồng một cấp trong hàm khác. Hàm lồng chỉ nối với hàm bao nó | 1,0 | 0,600 |
| Node được DOC nối tới trực tiếp | 0,75 | 0,682 |
| Hàm gọi tới hoặc được gọi bởi node xuất phát | 1,25 | 0,528 |
| Qua hai cạnh gọi | 2,25 | 0,317 |

**Hai danh sách.** Mỗi danh sách dùng một loại node xuất phát.
1. **GRAPH** (`graph`). Node xuất phát là 10 node đầu của AST, với l = 0,25. Chưa có bài code Graph RAG nào cố định số node xuất phát. Số 10 bằng k lớn nhất của độ đo số node phải đọc, theo cách đọc của Renieris và Reiss (mục 10.1). Số này cũng là mức cắt của Top@10 và Acc@10, và là kích thước pool bằng chứng.
2. **DOC** (`doc_kgc`). Node xuất phát là đích cạnh `Documents` của các chunk trong `doc_cand`, tức 10 chunk mà judge chấm, với l = 0,25 + 0,5. Danh sách này thay danh sách `vote_ast` khi trộn. Cách bỏ phiếu cũ (nhân 0,8, lan một bước nhân 0,5, 5 chunk) bị thay vì chưa có cơ sở. Theo HippoRAG, lan sang hàng xóm mà không suy giảm theo khoảng cách làm kết quả kém hơn.

**Ứng viên và thứ tự.** Ứng viên là mọi Function và Class có embedding và có l ≤ 4. KGCompass bỏ node không có embedding. Bộ lọc lớp chứa method và bộ lọc tên test của KGCompass không được dùng. Lý do là gold của đề tài có cả lớp, và danh sách AST không lọc tên test. Danh sách xếp theo S giảm dần. Khi bằng điểm, node có l nhỏ hơn đứng trước, như KGCompass, rồi tới id. Danh sách dài tối đa 500.

**Output.** Mỗi dòng của `scale_rows_v4.jsonl` có thêm các cột sau, với `<src>` là `graph` hoặc `doc_kgc`.
- `doc_ids_<src>` và `doc_score_<src>` là danh sách và điểm S.
- `doc_l_<src>` là l của từng node trong danh sách.
- `doc_r_<src>` là hạng AST của từng node, 0 nếu ngoài 500.
- `doc_gold_<src>` là vị trí của từng gold trong danh sách.
- `<src>_gold_l` là l của từng gold, None khi gold ngoài ngân sách.
- `<src>_ncand` là số ứng viên.
- `kgc_cfg` ghi cấu hình. Dòng có cấu hình khác được tính lại.

**Trộn và câu hỏi.** GRAPH là một danh sách như các nguồn khác, và được trộn với AST bằng RRF gốc (mục 8). Có hai hệ thống mới là +GRAPH và +ALL+GRAPH. Có hai câu hỏi mới là G1 (+GRAPH so với AST) và G2 (+ALL+GRAPH so với +ALL). Holm được tính riêng cho họ G1, G2, tách khỏi họ Q1 đến Q7. Q1 đến Q7 giữ nguyên, và Q1 dùng danh sách DOC mới.

**Tiêu chí đặt trước khi chạy.** GRAPH có giá trị xếp hạng khi +GRAPH tốt hơn AST có ý nghĩa ở ít nhất một độ đo của Bảng 1 mức hàm/lớp, và không kém hơn có ý nghĩa ở độ đo nào. DOC mới dùng cùng tiêu chí ở Q1. Kết quả được báo dù tốt hay xấu. β, α, trọng số và ngân sách không đổi sau khi xem kết quả.

**Chỗ lệch so với KGCompass.**
- Embedding là bge-small của graph (2.000 ký tự đầu của source), không phải jina-embeddings-v2-base-code. Lý do là AST và GRAPH dùng cùng một embedding.
- Tập 500 node của giới hạn cạnh gọi là danh sách AST, không phải 500 method có S cao nhất.
- Đề tài không có các tham chiếu tường minh từ issue của KGCompass, gồm đường dẫn file, stack trace, và issue hay PR được nhắc tới. Vì vậy GRAPH chỉ kiểm tra phần "suy giảm theo đường đi nhân độ giống" trên cạnh code.
- Bài ghi cos_norm = (cos + 1) / 2, còn code KGCompass dùng cosine thô. Đề tài theo bài.

**Cơ sở.**
- KGCompass (arXiv 2503.21710) cho công thức, β, α và cách dùng Dijkstra. Bài đã được đọc ở phần công thức và tham số. Code công khai (GLEAM-Lab/KGCompass, bản ngày 22/7/2025 và bản hiện tại) cho trọng số cạnh, ngân sách 4, giới hạn cạnh gọi và thứ tự khi hòa. Hai bản có cùng công thức.
- KGCompass dẫn Zhu và Iglesias (IEEE TKDE 29(1), 2017) cho phần suy giảm theo đường đi. Bài này định nghĩa wpath = 1 / (1 + length × k^IC), tức dạng nghịch đảo, và bỏ qua hướng cạnh. Dạng mũ β^l gần với phương pháp của Li và cộng sự, theo mô tả trong bài Zhu và Iglesias, với e^(−0,2 × length). Bài đã được đọc toàn văn phần phương pháp và thực nghiệm.
- KGCompass dẫn Ballatore, Bertolotto và Wilson (ISPRS IJGI 4(2), 2015) cho cách cộng tuyến tính hai độ giống có hệ số α. Bài đó cộng độ giống cấu trúc mạng với độ giống văn bản, và thấy α tốt nhất khoảng 0,5. Giá trị 0,3 của KGCompass không đến từ bài này. Bài đã được đọc toàn văn.
- LocAgent cho việc xếp kế thừa chung nhóm với lời gọi. HippoRAG cho lý do bỏ cách lan không suy giảm.

**Giới hạn.**
- Phần Levenshtein chiếm 70% điểm. Vì d ≥ ||a| − |b||, nên lev ≤ min(|a|, |b|) / max(|a|, |b|). Như vậy phần này bị chặn trên bởi tỷ lệ độ dài giữa issue và source của node.
- β và α được tác giả KGCompass chọn trên SWE-bench, nên không phải giá trị trung lập với dữ liệu.
- RRF gốc cho mọi danh sách một lá phiếu ngang nhau (mục 8). Giới hạn này áp dụng cho GRAPH như các nguồn khác.
- GRAPH và DOC mới đi trên chính graph của `depth-v4`, nên có lợi sẵn ở độ sâu nhỏ.

**Trạng thái.** Đã cài ngày 28/10/2026 và đã chạy thử trên 12 instance mẫu. l và S khớp với phép tính độc lập, và các hệ thống không có DOC giữ nguyên danh sách. Số ứng viên có trung vị 5.980 (GRAPH) và 5.458 (DOC), lớn nhất 11.246. Chi tiết kiểm thử ở mục 12 của `experiment_log.md`. Đã chạy ở v4-L8. Kết quả ở mục 10 của `experiment_log.md`.

---

## 9. Judge

**Mục đích.** Judge chấm các phần tử bằng chứng được truy hồi, gồm chunk doc, hunk và báo cáo cũ. Nhờ vậy đánh giá không chỉ dựa trên gold. Judge luôn thấy toàn văn. Từ ngày 26/10/2026, judge không chấm node code nữa. Node code được đánh giá bằng gold (mục 10) và bằng độ đo theo cấu trúc (mục 10.1).

**Cấu hình chung.**
- Model là `gemini-3.1-flash-lite`, chạy qua Batch API. Từ ngày 26/10/2026, mức thinking là MINIMAL. Các lượt trước dùng mức LOW.
- Từ ngày 26/10/2026, mỗi batch gồm mọi request của 100 instance. Trước đó là 150 instance. Lý do là Tier 1 giới hạn 10 triệu token đang xếp hàng. Khi chỉ còn request bằng chứng, mỗi instance có khoảng 20 nghìn token, nên một batch có khoảng 2 triệu token.
- Tên và job của từng batch được ghi vào `batch_jobs.txt`, để chạy lại không phải trả tiền hai lần.
- Từ ngày 27/10/2026, `judge-v4` đọc file nhãn một lần cho mỗi phần batch, và một lần trước khi chấm lại từng request. Trước đó, file được đọc lại một lần cho mỗi request. Với file nhãn 26 MB và khoảng 3.900 request, cách cũ tốn thêm khoảng 25 đến 40 phút CPU.
- `GOOGLE_API_KEY` là biến thường trong `judge-config`.

**Judge v3 (đã chạy, code đã bỏ khỏi notebook ngày 27/10/2026).**
- Request node code chứa hợp top 10 của mọi hệ thống. Judge thấy toàn bộ code của node, lấy từ git tại snapshot theo dòng đầu và dòng cuối. Judge không thấy bản vá.
- Thang điểm là 0 đến 3. Điểm 3 nghĩa là bản sửa phải đổi code trong phần tử. Điểm 2 nghĩa là phải đọc phần tử để sửa. Điểm 1 nghĩa là cùng tính năng nhưng không cần cho bản sửa. Điểm 0 nghĩa là không liên quan.
- Phần tử được xáo trộn và đặt tên C1, D1, H1, nên judge không biết phần tử đến từ nguồn nào.
- nDCG@10 được tính từ nhãn của node code.
- Judge v3 còn có request chunk doc và request commit. Nhãn commit của v3 không dùng được, vì judge chỉ thấy message mà không thấy diff.

**Judge v4, phần bằng chứng (đã chạy ở v4-L4 và v4-L5).**
- Mỗi instance có ba request: `#ev-doc` (10 chunk của `doc_cand`), `#ev-hist` (10 hunk của `hist_cand`) và `#ev-issue` (tối đa 10 báo cáo của `issue_cand`).
- Chunk doc có toàn văn và các node mà chunk nối tới. Hunk có message đầy đủ của commit (lấy từ git), mọi hàm/lớp mà commit đã sửa, và diff của hunk. Báo cáo cũ có title, body và Fix(b′).
- Một prompt chung cho mọi loại. Judge được xem bản vá thật. Với mỗi phần tử, judge cho điểm liên quan (0 đến 3), điểm hữu ích (0 đến 3) và danh sách loại thông tin. Từ ngày 26/10/2026, judge không viết lý do. Ở các lượt trước, judge viết lý do trước điểm. Phần tử chỉ cùng file hoặc cùng tính năng được tối đa 1 điểm hữu ích. Danh sách loại thông tin có bảy loại theo Ko và cộng sự cùng hai nhãn loại trừ (mục 13.3 của `research_context.md`). Nhãn loại trừ phải đứng một mình.
- Phần tử được xáo thứ tự theo seed của instance, và được đặt tên D1, H1, I1. Kết quả không đủ alias, điểm ngoài 0 đến 3, hoặc nhãn loại trừ đi cùng nhãn khác bị loại, rồi được chấm lại.
- Khóa của request là `<instance>#<loại>#<12 ký tự đầu của sha1 của request>`. Nội dung đổi thì khóa đổi, nên nhãn cũ không bị dùng nhầm.
- Request gửi qua Batch API, mỗi batch gồm request của 150 instance. Tên batch có hash của tập request, nên chạy lại thì chờ đúng batch đã gửi.
- Khi `GOOGLE_API_KEY` trống, cell chỉ dựng request và in số token.
- Ở v4-L4, mỗi request có trung bình khoảng 5.000 token (ev-doc), 6.000 token (ev-hist) và 5.600 token (ev-issue). 3.561 trên 3.561 request có nhãn.

**Judge v4, phần còn lại.**
- `#code2` chấm node code mới vào top 10 của 8 hệ thống bằng prompt node code của v3. Phần này đã chạy ở v4-L5 và cho nDCG@10 theo judge. Ngày 26/10/2026, `#code2` bị bỏ khỏi notebook vì hai lý do. Thứ nhất, judge chấm node code mà không thấy bản vá, nên nhãn chỉ là phỏng đoán về mức liên quan. Thứ hai, khi phải chấm lại mọi node để mọi nhãn cùng một cài đặt, phần này chiếm khoảng 56 đến 64% token đầu vào. Node code được đánh giá bằng độ đo theo cấu trúc ở mục 10.1.
- Chấm lặp một mẫu 100 instance, với thứ tự phần tử khác, để đo độ ổn định của judge. Phần này đã chạy ở v4-L5, với κ từ 0,6 đến 0,8.
- `#suff` chấm "đủ thông tin" cho cả tập K(p), chỉ cho Q4. Chờ bước G.

**Cơ sở.** eRAG (Salemi, Zamani, SIGIR 2024) cho thấy nhãn "liên quan" do LLM chấm gần như không tương quan với kết quả cuối. Utility judgments (Zhang và cộng sự, SIGIR 2024) cho thấy prompt hỏi "hữu ích" tốt hơn prompt hỏi "liên quan", chấm theo danh sách tốt hơn, và LLM nhạy với vị trí. Hai bài này đã được đọc toàn văn. Thomas và cộng sự (SIGIR 2024) mới được đọc ở mức tóm tắt.

Việc bỏ lý do và hạ mức thinking là quyết định của người dùng ngày 26/10/2026. Không phần phân tích nào đọc lý do, và lý do chiếm khoảng một nửa số ký tự output. Chiang và Lee (Findings of EMNLP 2023) cho thấy việc bắt LLM giải thích điểm giúp nhãn khớp với người chấm hơn, nhưng bài này thử trên model không có thinking. Ảnh hưởng của cài đặt mới lên nhãn chưa được đo. Bảng độ ổn định sẽ được đo lại ở lượt chạy tới.

**Judge v5 (cài ngày 29/10/2026, mục 6.18 của `planning.md`).**
- **Lý do.** Prompt v4 định nghĩa "hữu ích" theo việc phần tử chỉ tới code của bản sửa. Prompt này cũng đưa vào phần tử danh sách hàm/lớp do pipeline suy ra. Vì vậy nhãn v4 gần với câu hỏi "phần tử có dẫn tới code của bản sửa không", thay vì đo giá trị nội dung của doc, history và issue cũ.
- **Prompt v5.** Prompt nói rõ bằng chứng dùng để cho thông tin mà code không cho, và việc tìm code là của thành phần khác. Bản sửa chỉ dùng để kiểm tra thông tin có đúng và có cần cho issue hay không. Phần tử không cần nhắc tới code bị sửa mới được coi là hữu ích. Judge làm ba bước theo thứ tự: loại thông tin, điểm hữu ích, rồi điểm liên quan. Toàn văn prompt nằm ở mục 6.18.1 của `planning.md`.
- **Schema.** Schema giữ ba trường của v4, theo thứ tự `info_types`, `usefulness`, `relevance`. Quy tắc nhận nhãn và chấm lại giữ nguyên.
- **Phần tử.** Phần tử chỉ chứa nội dung vốn có của artifact. Chunk doc gồm file, heading và văn bản, không còn danh sách node mà chunk nối tới. Phần tử HIST là một commit của `hist_msg_cand` (mục 6b), gồm sha 8 ký tự, ngày commit, message đầy đủ, và mỗi ticket hoặc PR liên kết một khối theo số tăng dần. Phần tử HIST không còn diff và danh sách hàm/lớp. Báo cáo cũ gồm số, ngày tạo, tiêu đề và nội dung, không còn Fix(b′). Ngày được giữ để judge xét mức 0 "outdated".
- **Lượt thử.** Notebook không có chế độ chạy thử. Lượt Kaggle luôn là lượt đầy đủ. Lượt thử của judge v5 được chạy ở máy bằng script ngoài notebook, với `GOOGLE_API_KEY` của `judge-config` (mục 6.18.5 của `planning.md`). Ngày 29/10/2026, cơ chế `JUDGE_PILOT_N` từng được cài để chạy thử 150 instance trên Kaggle, rồi bị bỏ cùng ngày theo yêu cầu của người dùng.
- **Nhãn v4.** Khóa của request v5 khác khóa của request v4, nên nhãn v4 vẫn nằm trong file nhãn và không bị dùng nhầm.

**Trạng thái.** Judge v3 đã chạy. Phần bằng chứng, `#code2` và phần chấm lặp của judge v4 đã chạy (v4-L5). Judge v5 đã cài (29/10/2026), chưa chạy trên Kaggle. Lượt thử ở máy trên 48 instance của Django và SymPy đã chạy cùng ngày, với Gemini thật. Kết quả nằm ở mục 6.18.5 của `planning.md`. Khi chạy với client Gemini giả trên 12 instance, prompt không còn danh sách node của chunk hay danh sách hàm/lớp, và Bảng 3 tính lại bằng tay từ pool và nhãn khớp với hàm của `verify-v4`. Cài đặt mới từ ngày 26/10/2026 đã chạy ở v4-L6 và chấm lại toàn bộ bằng chứng (3.861 request). So với cài đặt cũ, judge mới cho ít điểm 0 hơn và nhiều điểm 1 hơn, và tỷ lệ instance có phần tử hữu ích giảm nhẹ. κ của nhãn hữu ích khi gộp ba nguồn là 0,627, so với 0,629 ở cài đặt cũ. Chi tiết ở mục 8 của `experiment_log.md`.

---

## 10. Đánh giá (`verify-v4`)

> Cập nhật 21/10/2026: bộ độ đo đã chốt (hai mức hàm/lớp và file, độ đo cho bằng chứng theo pool, loại thông tin, đủ thông tin cho cả tập, kiểm định hoán vị và Holm) nằm ở mục 13 của `research_context.md` và mục 6.12 của `planning.md`. Phần dưới đây là thiết kế trước đó.
>
> Cập nhật 22/10/2026: cell `verify-v4` đã chạy ở v4-L4. Cell tính Bảng 1 ở hai mức (hàm/lớp và file, với file được xếp theo điểm cao nhất của hàm/lớp trong file), Bảng 2 theo độ khó của AST, và phân tích theo việc issue có nêu tên gold. Kiểm định gồm McNemar chính xác cho độ đo đúng/sai, kiểm định hoán vị ghép cặp 10.000 lần (seed 20261021) cho MRR và MAP, và Holm trong từng độ đo trên Q1 đến Q7. Hệ thống lấy từ `V4_FUSED`. Phần bằng chứng (Bảng 3, Bảng 4, độ ổn định của judge, nDCG@10) đã được cài ngày 22/10, chưa chạy trên Kaggle.

**Mục đích.** Bước này trình bày số liệu cho các câu hỏi ở mục 6.2 của `planning.md`. Phần phụ trợ được giữ đơn giản, nên không có khoảng tin cậy, TRisk hay hiệu chỉnh cho nhiều kiểm định.

**Bảng 1. Độ đo chính.** Mỗi hệ thống có một hàng. Bảng có ba phần: gộp hai repo, riêng Django và riêng SymPy.

| Độ đo | Cách tính | Cơ sở |
|---|---|---|
| Top@1, Top@5, Top@10 | Tỷ lệ instance có ít nhất một gold trong N vị trí đầu | Locus và AmaLgam, đã đọc toàn văn |
| MRR | Trung bình của 1 chia hạng của gold đầu tiên | Locus, đã đọc toàn văn |
| MAP | Trung bình của độ chính xác tại hạng của từng gold | Locus, đã đọc toàn văn |
| Acc@10 | Tỷ lệ instance có mọi gold trong top 10 | LocAgent và SweRank, mới đọc tóm tắt |

Hạng được tính tới 500. Gold ngoài hạng 500 đóng góp 0 vào MRR và MAP.

**Bảng 2. Thay đổi theo từng instance.** Với mỗi câu hỏi, bảng so hai hệ thống trên từng instance theo hạng của gold tốt nhất. Bảng ghi số và tỷ lệ instance tốt hơn, kém hơn và không đổi. Bảng được tách theo độ khó của AST: gold đã ở top 10, gold ở hạng 11 đến 100, và gold ngoài hạng 100.

**Phân tích bổ sung.**
1. **Đóng góp của từng thành phần trong HIST**, theo RQ4 của Locus. +HIST được chạy với ba cấu hình: chỉ NL, NL+CE và NL+CE+Fix.
2. **Tách theo việc issue có nêu sẵn tên gold hay không**, theo Kochhar, Tian và Lo (ASE 2014) và bản làm lại của Widyasari và cộng sự. Hai bài này mới được đọc ở mức tóm tắt.
3. **Một kiểm định McNemar cho Top@10 ở mỗi câu hỏi.** Kiểm định chỉ dùng hai con số: số instance chỉ hệ thống thứ nhất có gold trong top 10, và số instance chỉ hệ thống thứ hai có gold trong top 10.

**Nhóm repo có doc (26/10/2026, bỏ ngày 28/10/2026).** Bảng 1 và kiểm định từng được tính thêm cho các repo trong `V4_DOC_REPOS`, tức 7 repo có độ phủ doc từ 5% trở lên theo `coverage_report.md`. Nhãn "gộp hai repo" của các bảng được đổi thành "gộp mọi repo". Từ ngày 28/10/2026, nhóm này bị bỏ, và độ phủ doc được phân tích như một biến (mục 10.2, quyết định 60 của `research_context.md`).

**Các bảng giữ nguyên từ kế hoạch trước.** Có mức hữu ích của bằng chứng theo nguồn và độ phủ liên kết của ISSUE. nDCG@10 theo judge đã chạy ở v4-L5. Từ ngày 26/10/2026, phần này được thay bằng độ đo ở mục 10.1. Ngày 27/10/2026, khối tính nDCG@10 bị bỏ khỏi `verify-v4`, cùng nhánh dự phòng dùng 4 hệ thống của v3 khi chưa có `V4_FUSED`.

**Họ kiểm định (28/10/2026).** Holm được tính riêng trong từng họ của `V4_FAMILIES`. Họ thứ nhất là Q1 đến Q7. Họ thứ hai là G1 (+GRAPH so với AST) và G2 (+ALL+GRAPH so với +ALL), mục 8b. Cặp phụ không thuộc họ nào.

**Độ đo bằng chứng mới (29/10/2026, mục 6.18.4 của `planning.md`).** Bảng 3 cũ tính Precision trên mọi instance có output, nhưng tính Recall và F1 chỉ trên instance có phần tử hữu ích. Vì vậy F1 bỏ qua đúng những instance mà trả rỗng là đúng. Từ ngày 29/10/2026, Bảng 3 dùng các độ đo sau, trên mọi instance có pool.
- Precision, recall trong pool và F1 dạng micro, tính từ tổng TP, FP, FN trên mọi instance (Bacchelli, Lanza, Robbes, ICSE 2010, mục 3.4). TP là phần tử được giữ và hữu ích. FP là phần tử được giữ mà không hữu ích. FN là phần tử hữu ích mà không được giữ. Recall chỉ tính trên phần tử hữu ích có trong pool, nên được gọi là recall trong pool.
- Utility tuyến tính T11U = 2·TP − FP cho từng instance, lấy trung bình (Robertson và Soboroff, TREC 2002 Filtering, mục 2.3). Hệ số 2:1 lấy từ bài.
- Bảng 2×2 đếm số instance theo hai câu hỏi: output có rỗng không, và pool có phần tử hữu ích không. Bảng này thay hai cột "Trả rỗng đúng" và "Trả rỗng sai" cũ.
- Mọi cách cắt giữ tối đa 10 phần tử.
- Bảng 4 có thêm số phần tử có từng loại thông tin trên mỗi instance, tính trên mọi phần tử trừ hai nhãn loại trừ.
- So sánh giữa các nguồn ở Bảng 3 chỉ là mô tả. So sánh có ý nghĩa chỉ nằm trong cùng một nguồn, tức giữa các cách cắt, hoặc giữa judge v4 và v5.
- Pool HIST của Bảng 3 là `hist_msg_cand` (mục 6b).

**Trạng thái.** Bảng 1, Bảng 2, kiểm định và phần bằng chứng đã chạy (v4-L5).

### 10.1 Độ đo theo cấu trúc (`depth-v4`)

**Mục đích.** Bước này đo mức độ gần chỗ sửa của cả danh sách hàm/lớp mà hệ thống trả về, mà không cần LLM. Độ đo này thay cho nDCG@10 theo judge từ ngày 26/10/2026.

**Graph.** Node là Function và Class của graph snapshot. Cạnh là `Calls`, `Inherits` và `Defines`, đi theo cả hai chiều. Cạnh `Imports` không được dùng, vì nó nối các module với nhau.

**Số node phải đọc.** Độ đo được tính với k = 1, 5 và 10.
1. Một người đọc lý tưởng đọc lần lượt k node đầu theo hạng. Nếu gặp gold ở hạng r, số node phải đọc là r.
2. Nếu chưa gặp gold, người đó đọc mọi hàm/lớp kề với các node đã đọc (lớp 1), rồi lớp 2, cho đến lớp có gold.
3. Số node phải đọc bằng số node của các lớp trước, cộng vị trí kỳ vọng của gold đầu tiên trong lớp cuối. Nếu lớp cuối có n node và g gold, vị trí kỳ vọng là (n + 1) / (g + 1).
4. Nếu không tới được gold, số node phải đọc bằng số hàm/lớp của snapshot.

Ví dụ, top 10 không có gold, còn lớp 1 có 40 node và 1 gold. Khi đó số node phải đọc là 10 + 41/2 = 30,5.

Mỗi node sai trong top k cũng là một điểm xuất phát, nên danh sách có nhiều node nằm rải rác bị phạt. Vì vậy giá trị ở k = 10 có thể lớn hơn ở k = 5. Đi qua một hub tốn nhiều node phải đọc, nên độ đo không cần ngưỡng hub riêng.

**Độ sâu.** Độ sâu của một node là số bước ngắn nhất tới gold gần nhất, tối đa 3 bước. Bảng độ sâu ghi tỷ lệ node trong top 10 ở độ sâu 0, 1, 2, 3 và xa hơn 3, lấy trung bình theo instance.

**Output.** Cell in ba bảng. Bảng thứ nhất có trung vị và trung bình của số node phải đọc theo hệ thống và theo k, cùng tỷ lệ instance không tới được gold. Bảng thứ hai là kiểm định hoán vị ghép cặp (10.000 hoán vị, hàm `_perm_test` của `verify-v4`) với Holm trong từng họ (Q1 đến Q7; G1 và G2). Bảng thứ ba là bảng độ sâu. Instance không có gold nào trong graph bị bỏ, và số instance bị bỏ được in ra.

**Cơ sở.** Renieris và Reiss (ASE 2003) chấm kết quả định vị lỗi theo phần chương trình mà một người dùng lý tưởng không phải xem, khi người đó đi dần từ chỗ được báo sang chỗ lân cận trên graph phụ thuộc. Cleve và Zeller (ICSE 2005) dùng lại cách chấm này. Parnin và Orso (ISSTA 2011) cho thấy số tuyệt đối có ý nghĩa với developer hơn phần trăm của chương trình, nên độ đo báo số node, không báo tỷ lệ. Ba bài này chưa được đọc toàn văn.

**Giới hạn.**
- Độ đo tính từ gold. Vì vậy node cần đọc nhưng ở xa gold trên graph không được tính.
- Graph gọi hàm tĩnh của Python thiếu cạnh, ví dụ lời gọi qua dispatch động. Vì vậy số node phải đọc có thể cao hơn thực tế.
- Cách đọc theo từng lớp là một giả định. Parnin và Orso cũng cho thấy developer thật không đọc tuần tự. Độ đo nên được trình bày là ước lượng công sức tương đối giữa các hệ thống.
- DOC lan phiếu qua chính các cạnh `Defines` và `Calls`, nên có lợi sẵn ở độ sâu 1. Từ ngày 28/10/2026, GRAPH và DOC mới đi trên chính graph này (mục 8b), nên cũng có lợi sẵn ở độ sâu nhỏ.

**Trạng thái.** Đã chạy ở v4-L6 và v4-L7. Kết quả ở mục 8 và 9 của `experiment_log.md`.

### 10.2 Ảnh hưởng của độ phủ doc

**Mục đích.** Bước này đo độ phủ doc ảnh hưởng thế nào tới mức đóng góp của DOC. Đây là mục đích của bảng độ phủ trong `coverage_report.md` (quyết định 60 của `research_context.md`). Vì vậy repo có độ phủ thấp được giữ, vì chúng là phần đầu thấp của khoảng độ phủ.

**Biến.** `scale_row` ghi hai cột cho mỗi instance.
- `doc_cov` là tỷ lệ Function/Class của graph snapshot có ít nhất một cạnh `Documents`. Định nghĩa giống mục 1 của `coverage_report.md`. Giá trị được nhớ theo snapshot. Độ phủ của một repo là trung bình `doc_cov` trên các instance của repo.
- `gold_doc` là số gold có cạnh `Documents` trong graph snapshot.

**Kết quả và đối chứng.** Kết quả chính là Δ của +DOC so với AST theo từng instance, ở mức hàm/lớp, cho mọi độ đo của Bảng 1. Kết quả phụ là +ALL so với ALL−DOC. +HIST và +GRAPH so với AST là đối chứng âm, vì hai nguồn này không đọc doc. Nếu Δ của chúng cũng đi theo độ phủ, quan hệ của DOC có thể do đặc điểm của repo (Lipsitch, Tchetgen Tchetgen, Cohen, Epidemiology 2010).

**Bảng và kiểm định.** Khối "Ảnh hưởng của độ phủ doc" của `verify-v4` in các bảng sau.
1. **Bảng C-A, mức repo.** Mỗi cặp so sánh có một bảng. Mỗi repo một hàng, gồm số instance, độ phủ, tỷ lệ instance có `gold_doc` ≥ 1 và Δ trung bình. Bảng xếp theo độ phủ.
2. **C1.** ρ của Spearman giữa độ phủ của repo và Δ trung bình của repo. Hạng hòa nhận hạng trung bình. p hai phía tính bằng 10.000 lần hoán vị nhãn repo (`V4_PERM_B`, `V4_PERM_SEED`). C1 cần ít nhất 3 repo. Với ít hơn 3 repo, cell in thông báo và để trống ρ.
3. **Bảng C-B, mức instance.** Với nhóm `gold_doc` ≥ 1 và nhóm `gold_doc` = 0, cell in Bảng 1 của AST và +DOC, và kiểm định ghép cặp như Bảng 1. `_v4_tests` nhận thêm tham số `pairs` cho việc này.
4. **C2.** Hiệu Δ trung bình giữa hai nhóm. p hai phía tính bằng 10.000 lần hoán vị nhãn nhóm trong từng repo. Hoán vị trong từng repo để phép so không trộn khác biệt giữa các repo, vì gold có doc tập trung ở repo có nhiều doc.
5. **Bảng C-B phụ.** Δ của +DOC so với AST theo hai biến: gold có doc hay không, và issue có nêu tên gold hay không. Bảng chỉ để mô tả.
6. **Bảng C-C, mô tả cơ chế.** Trong nhóm `gold_doc` ≥ 1, cell in ba tỷ lệ theo repo: tỷ lệ instance có gold trong top 10 của danh sách DOC, tỷ lệ có gold ở bất kỳ vị trí nào trong danh sách DOC, và tỷ lệ có chunk của `doc_cand` nối tới gold.
7. **Họ C.** Họ C gồm C1 và C2 của +DOC so với AST, với Holm trong từng độ đo. Kết quả phụ và đối chứng chỉ có p thô.

**Tiêu chí ghi trước khi chạy.** "Độ phủ doc ảnh hưởng tới hiệu quả" khi thỏa cả hai điều kiện. Thứ nhất, C1 có ρ dương, hoặc C2 cho Δ lớn hơn ở nhóm `gold_doc` ≥ 1, có ý nghĩa sau Holm ở ít nhất một độ đo. Thứ hai, không đối chứng âm nào có ρ có ý nghĩa. Khi đối chứng âm cũng có ý nghĩa, kết quả được ghi là chưa tách được khỏi đặc điểm của repo. Kết quả được báo dù tốt hay xấu.

**Cơ sở.**
- Cronen-Townsend, Zhou và Croft (SIGIR 2002) dùng kiểm định tương quan hạng Spearman để đo quan hệ giữa một đặc tính và độ chính xác truy hồi, vì không biết phân bố của điểm. Đã đọc đoạn này trong toàn văn.
- Kochhar, Tian và Lo (ASE 2014) tách báo cáo lỗi theo một đặc tính rồi so hiệu quả. Mới đọc ở mức tóm tắt.
- Gelman và Stern (The American Statistician 2006) cho thấy một nhóm có ý nghĩa và một nhóm không có ý nghĩa không chứng tỏ hai nhóm khác nhau. Wang và cộng sự (NEJM 2007) yêu cầu ghi trước các nhóm con. Hai bài này mới được đọc ở mức tóm tắt.
- Lipsitch, Tchetgen Tchetgen và Cohen (Epidemiology 2010) cho cách dùng đối chứng âm. Đã đọc phần định nghĩa.
- Altman và Royston (BMJ 2006) cho lý do không cắt độ phủ thành hai nhóm. Mới đọc ở mức tóm tắt.
- Hoán vị trong từng repo là kiểm định hoán vị của Smucker và cộng sự, giới hạn trong từng repo. Chưa đọc bài nào làm cơ sở riêng cho cách giới hạn này.

**Giới hạn.**
- 12 repo trải từ 0,2% tới 24,0%. Trên 12,7% chỉ có flask với 11 instance, nên đầu cao rất mỏng.
- C1 chỉ có 12 điểm, nên chỉ phát hiện được quan hệ mạnh.
- Độ phủ đo ở mức repo đi kèm nhiều đặc điểm khác của repo. Đối chứng âm chỉ phát hiện được nhiễu, không loại được nhiễu.
- Chưa có bài nào đã đọc đo trực tiếp quan hệ giữa độ phủ doc do người viết và hiệu quả định vị lỗi không dùng LLM.

**Trạng thái.** Đã cài ngày 28/10/2026 và đã chạy thử trên 12 instance mẫu. Đã chạy ở v4-L8. Chi tiết kiểm thử ở mục 12, và kết quả ở mục 10 của `experiment_log.md`.

---

## 11. Chạy trên Kaggle và manifest

**Môi trường.** `WORK_DIR` là `/kaggle/working`. Repo được clone vào `/tmp/repos`. Kaggle giới hạn 12 giờ mỗi lần chạy. File trong `/kaggle/working` vẫn còn khi mở phiên mới (`experiment_log.md`, các lượt ngày 27/10 và 28/10). Vì vậy các cell dùng lại graph, history, báo cáo issue, dòng kết quả và nhãn judge đã có.

**Các file của v4.**

| File | Nội dung |
|---|---|
| `history/<repo>_history_v2.jsonl` | Đơn vị history, với touch set theo oracle mới |
| `history/<repo>_hunks_v2.jsonl` | Chỉ mục hunk của HIST |
| `V4_DIR/scale_rows_v4.jsonl` | Một dòng cho mỗi instance, gồm xếp hạng AST, danh sách của các nguồn và ứng viên bằng chứng |
| `V4_DIR/scale_rows_v4_truoc_buoc_A.jsonl` | File kết quả cũ, được `v4-run` đổi tên khi dựng lại |
| `V4_DIR/issues/<repo>_reports.jsonl` | Báo cáo cũ của ISSUE |
| `V4_DIR/issues/<repo>_links.jsonl` | Cặp báo cáo và commit, kèm loại liên kết |
| `V4_DIR/fusion.json` | Cấu hình trộn |
| `judge_v4/` | Request, pool, nhãn và `batch_jobs.txt` của judge v4 |
| `V4_DIR/manifest.json` | Repo, số instance, model và mức thinking của judge, hash của prompt và schema bằng chứng, cách trộn, các tham số chính, sha1 của các file dữ liệu, và sha1 của mã từng cell đã chạy trong phiên. Giá trị của `GOOGLE_API_KEY` và `GITHUB_TOKEN` được xóa trước khi băm. Từ ngày 27/10/2026, khóa của mỗi cell là số thứ tự trong `In` cộng dòng đầu của cell. Lý do là cell Doc Extractor và cell index tìm kiếm cùng bắt đầu bằng `import re`, nên khóa theo dòng đầu làm hash của cell này đè cell kia. Run All trong kernel mới cho cùng số thứ tự ở mọi lần chạy. Đã chạy ở v4-L6, nhưng ghi 0 cell vì `In` rỗng. Ở v4-L7, manifest ghi đủ 31 cell. Manifest không báo lỗi khi `In` rỗng. Từ ngày 28/10/2026, phần tham số ghi thêm cấu hình của `graph-proc` (`KGC`) |

**Dọn notebook (27/10/2026).** Theo quyết định của người dùng, notebook chỉ còn code của pipeline v4, và còn 45 cell. Phân tích chỉ dùng một lần được chạy ngoài notebook, rồi kết quả được ghi vào tài liệu.
- Code của v3 bị bỏ. Đó là 11 cell có dòng đầu `%%v3`, cờ `RUN_V3`, magic `%%v3`, `SCALE_RESULTS`, các prompt và schema của judge v3, `JUDGE_DIR` và `POOL_DEPTH`.
- Ba cell chỉ để phân tích bị bỏ. Đó là `v3-recheck`, `gpu_cuda_check` và `hist-fix-check`. Dòng `LIST_K = V4_TOPK` được chuyển từ `v3-recheck` sang `v4-config`.
- `scale_row` chỉ còn ghi các cột mà pipeline đọc. Đó là `ast_ids`, `gold_ids`, `issue_names_gold`, bốn cột của `vote_ast`, `doc_cand` và `doc_cand_all`. Các cột chỉ phục vụ phân tích của v3 bị bỏ, gồm cột Hit của thiết kế m suất, B0, B1, B2, nhóm doc, nguồn `random_ast`, nguồn HIST của v3 và `node_meta`. Vì vậy `funnel_setup`, `candidates`, `unit_of` và các nguồn `random`, `chunkvec`, `randvec` của `doc_set` cũng bị bỏ.
- `hist-build` không còn tính embedding cho message commit, nên file `<repo>_history_v2.emb.npy` không còn được dùng. Hàm `hist_index` bị bỏ.
- Các bảng chỉ để xem nhanh ở cuối `scale-data`, `hist-proc` và `issue-index` bị bỏ. Thống kê từng instance của `issue-index` và cột `hist_locus_best` cũng bị bỏ.
- Các dòng `import` được giữ nguyên, vì `v4-fusion` và `judge-v4` dùng `random` do các cell phía trước import.
- Bản cũ và bản mới được chạy trên máy với cùng 12 instance (graph 838e432e và 9bf73cc2). Mọi cột mà bản mới ghi trùng bản cũ. Trọng số trộn và các bảng của `verify-v4` và `depth-v4` trùng nhau. `fusion.json` chỉ khác ở mục 10 node đầu. 72 request của `judge-v4` trùng cả khóa lẫn nội dung, nên nhãn judge đã có vẫn dùng được.
- File `scale_rows_v4.jsonl` hiện có vẫn dùng được, nên không cần chạy lại `v4-run`. Dòng cũ còn các cột thừa, nhưng không cell nào đọc chúng.
- Sau khi dọn, không cell nào còn đọc các cột `doc_r_*` và `doc_gold_*`. Các cột này vẫn được giữ.
- Số mục của notebook nhảy từ 2 sang 4 và từ 6 sang 8, vì mục 3 (GPU check) và mục 7 (phân tích doc của v3) đã bị bỏ.
- Cell `cell-files` bị mất trong bản notebook quay về từ v4-L6, rồi được khôi phục từ bản sao lưu vào đúng vị trí cũ, trước `cell-schema-header` (27/10/2026). Cell này định nghĩa `_SKIP_DIRS`, `_SKIP_FILES` và `get_python_files`. Thiếu cell này thì `v4-run` dừng với lỗi `NameError` khi phải tính instance mới. v4-L6 không gặp lỗi, vì không phải tính lại instance nào và mọi graph đều lấy từ cache.

**Dữ liệu cũ.** Nhiều cell bỏ qua phần việc đã làm khi thấy file có sẵn. `v4-run`, `hist-proc`, `issue-index` và `graph-proc` có kiểm tra để không giữ dữ liệu cũ sau khi code hoặc cấu hình đổi. Nhãn judge có hash của request trong khóa. File graph và file history chỉ được kiểm tra theo tên schema và tên file.

**Manifest.** Manifest ghi code và cấu hình của từng lượt, để biết kết quả do code nào tạo ra. Notebook không được commit vì còn API key, nên hash của từng cell thay cho commit hash.

---

## 12. Bảng tham số

| Tham số | Giá trị | Nơi dùng | Cơ sở |
|---|---|---|---|
| Độ dài một khoảng snapshot | 60 ngày | Mục 1 | Chưa có bài báo |
| Độ dài tối đa của chunk doc | 1.600 ký tự | Mục 2.2 | Chưa có bài báo |
| Source lưu trong node | 8.000 ký tự | Mục 2.1, BM25 | Chưa có bài báo |
| Văn bản embedding của hàm/lớp | 2.000 ký tự đầu của source | Mục 2.1 | Chưa có bài báo |
| Query cho embedding | Bỏ khối code, giữ 2.000 ký tự | Mục 4 | Chưa có bài báo |
| BM25 | k1 = 1,5 và b = 0,75 | Mục 4 và 5 | Mặc định của `rank_bm25` |
| Hằng số RRF | k = 60 | Mục 4, 5 và 8 | Cormack và cộng sự (2009) |
| Độ sâu xếp hạng AST | 500 | Mục 4 và 6 | Chưa có bài báo |
| Số chunk của DOC | 5 (danh sách `vote_ast`, không trộn từ 28/10/2026) | Mục 5 | Chưa có bài báo |
| Trọng số cạnh `Documents`, hệ số lan, số hàng xóm tối đa | 0,8; 0,5; 20 (danh sách `vote_ast`, không trộn từ 28/10/2026) | Mục 5 | Chưa có bài báo |
| β, hệ số suy giảm theo đường đi (`KGC_BETA`) | 0,6 | Mục 8b | KGCompass, mục 4.3 |
| α, trọng số cosine so với Levenshtein (`KGC_ALPHA`) | 0,3 | Mục 8b | KGCompass, mục 4.3 |
| Ngân sách đường đi (`KGC_BUDGET`) | 4 | Mục 8b | Code KGCompass (`max_hops=4`) |
| Trọng số cạnh (`KGC_W`) | Issue tới node xuất phát 0,25; `Defines` 0,25; `Documents` 0,5; `Calls` 1,0; `Inherits` 1,0 | Mục 8b | Code KGCompass. `Inherits` theo cách LocAgent xếp kế thừa chung nhóm với lời gọi |
| Giới hạn cạnh gọi | Đích cạnh `Calls` hoặc `Inherits` phải nằm trong 500 node đầu của AST | Mục 8b | Code KGCompass (500 method giống issue nhất) |
| Số node xuất phát của GRAPH (`KGC_SEEDS`) | 10 | Mục 8b | Bằng k lớn nhất của độ đo số node phải đọc (Renieris và Reiss). Chưa có bài code Graph RAG cố định số này |
| Source tối đa cho Levenshtein (`KGC_SRC_MAX`) | 20.000 ký tự | Mục 8b | Code KGCompass |
| λ của Locus | 5 | Mục 6 | Locus |
| β₁ của Locus | 0,1 | Mục 6 | Locus |
| Quy tắc commit sửa lỗi | `fix\|bug` | Mục 6 | AmaLgam |
| Số hàm/lớp lưu cho HIST | 500 | Mục 6 và 6b | Bằng độ sâu AST |
| k của RRF trong điểm commit của `hist-msg` (`HIST_MSG_K`) | 60 | Mục 6b | Cormack, Clarke và Büttcher (2009) |
| Liên kết của commit trong `hist-msg` | Django: "Fixed #N". GitHub: issue được đóng và PR của commit | Mục 6b | Giống liên kết của ISSUE (mục 7). Ghép phần lời với ticket hoặc PR là đề xuất của đề tài |
| Số phần tử mỗi loại bằng chứng (`V4_EVID_N`) | 10 | Mục 5, 6, 7 và 9 | Bằng kích thước pool của judge (mục 13.2 của `research_context.md`) |
| Ngưỡng commit lớn cho bằng chứng HIST (`HIST_MAX_TOUCH`) | 50 hàm/lớp | Mục 6.5 | ROSE bỏ transaction chạm hơn 30 thực thể. Giá trị 50 có sẵn ở `hist-build` |
| Mốc cắt của ISSUE (`ISSUE_CUTOFF`) | `"instance"`, đệm 1 ngày | Mục 7 | Lingxi, KGCompass |
| Cách trộn | RRF gốc, mọi danh sách có trọng số 1, k = 60 | Mục 8 | Cormack, Clarke và Büttcher (2009) |
| Seed của kiểm định hoán vị | 20261021 | Mục 10 | Giá trị chọn của đề tài |
| Số hoán vị | 10.000 | Mục 10 | Giá trị chọn của đề tài |
| Model judge | `gemini-3.1-flash-lite`, thinking MINIMAL, không viết lý do (từ 26/10/2026) | Mục 9 | Chọn theo chi phí. Bỏ lý do theo quyết định của người dùng |
| Số node đầu của độ đo theo cấu trúc | 1, 5, 10 | Mục 10.1 | Bằng các mức cắt của Top@k |
| Cạnh của độ đo theo cấu trúc | `Calls`, `Inherits`, `Defines`, hai chiều | Mục 10.1 | Chưa có bài báo |
| Độ sâu tối đa trong bảng độ sâu | 3 | Mục 10.1 | Chưa có bài báo |
| Số instance mỗi batch judge | 100 (từ 26/10/2026) | Mục 9 | Giới hạn 10 triệu token của Tier 1 |
| Số instance chấm lặp | 130, một mẫu trên mọi instance của 12 repo (từ 27/10/2026). Trước đó là 100 trên Django và SymPy | Mục 9 | Bằng tổng 100 và 30 đã định cho hai đợt cũ. Chưa có bài báo |
| Nhóm repo có doc (`V4_DOC_REPOS`) | Bỏ từ 28/10/2026. Trước đó là 7 repo có độ phủ doc từ 5% | Mục 10 | Ngưỡng chưa có bài báo. Thay bằng phân tích độ phủ như một biến (mục 10.2) |
| Biến độ phủ doc | `doc_cov` (tỷ lệ Function/Class của snapshot có cạnh `Documents`), `gold_doc` (số gold có cạnh `Documents`) | Mục 10.2 | Định nghĩa của `coverage_report.md`, mục 1 |
| Số repo tối thiểu cho C1 | 3 | Mục 10.2 | Ít nhất 3 điểm để hệ số tương quan hạng có nghĩa |

---

## 13. Việc còn mở

> Cập nhật 27/10/2026, sau lượt v4-L7. Danh sách ưu tiên đầy đủ nằm ở mục 14.15 của `planning.md`.

1. Lượt Kaggle trên cả 12 repo của tập test. Notebook đã gộp 12 repo thành một thực nghiệm ngày 27/10/2026, nhưng 10 repo còn lại chưa chạy. Cần `GITHUB_TOKEN`. Cần kiểm tra trước xem `/kaggle/working` còn graph cũ của 10 repo này từ lượt v2 hay không, vì bộ nhớ đệm chỉ kiểm tra tên schema.
2. Mẫu chấm lặp đổi thành 130 instance trên mọi repo, nên độ ổn định của judge sẽ được đo lại ở lượt tới.
3. Cách chọn ngưỡng (bước G) chưa chốt.
4. Sửa cách nối doc với code (mục 2.2): thiết kế đã chốt ngày 23/10/2026 ở mục 6.10 của `planning.md`, chưa cài. Tiêu chí của thiết kế được viết cho cách trộn có trọng số, nên cần chốt lại cho RRF gốc.
5. Quy tắc A7 bỏ sót tên lớp chỉ viết hoa chữ đầu (mục 6.4).
6. Thành phần Fix của HIST: kết quả của bước D đã có (mục 6.6), nhưng chưa quyết định có đổi A2, A3 hay không. Ở v4-L7, Fix vẫn không thêm gì.
7. Việc 1.3 (kiểm tra snapshot) chưa làm.
8. `manifest` và dấu cách tính của `issue-index` phụ thuộc vào `In` của IPython, và không báo lỗi khi `In` rỗng.
9. Một số chỗ trong `planning.md` chưa khớp với các quyết định mới. Mục 5.1 và 6.2 vẫn có quy tắc thống kê và độ đo chính cũ. Mục 6.3, 6.7, bảng ở mục 7 và mục 9 vẫn nhắc tới F, m và bước 3 cũ. Mục 4.3 của `research_context.md` cũng chưa khớp.
10. Sau khi dọn notebook, các cột `doc_r_*` và `doc_gold_*` không còn cell nào đọc. Cần quyết định bỏ hay giữ chúng.
11. `graph-proc` (mục 8b) đã cài ngày 28/10/2026 và đã chạy ở v4-L8. Kết quả của G1, G2 và của Q1 với danh sách DOC mới nằm ở mục 10 của `experiment_log.md`. Phân tích ngoài notebook sẽ báo l của gold đầu tiên trong GRAPH, và tỷ lệ instance có gold là ứng viên của GRAPH nhưng nằm ngoài 500 node đầu của AST.
12. Thiết kế sửa cạnh doc ở mục 2.2 có bước idf trong `doc_votes`. Từ ngày 28/10/2026, `doc_votes` không còn được trộn, nên bước này không còn tác dụng.
13. Phân tích độ phủ doc (mục 10.2) đã cài ngày 28/10/2026 và đã chạy ở v4-L8. Đầu cao của khoảng độ phủ rất mỏng. Thêm repo phần train có độ phủ cao, như cryptography (37,6%), sẽ nối dài khoảng này, nhưng việc đó đổi tập dữ liệu.
