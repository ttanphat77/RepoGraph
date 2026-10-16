# Thiết kế kỹ thuật của pipeline RepoGraph

Cập nhật ngày 15/10/2026.

File này mô tả từng kỹ thuật trong pipeline, từ dữ liệu đầu vào tới bảng đánh giá. Mỗi bước ghi mục đích, input, cách làm, tham số, output, cơ sở và trạng thái. Nội dung được đối chiếu với code trong bản làm việc `nb_v4_work.ipynb`. Kế hoạch và thứ tự công việc nằm ở `planning.md`. Bối cảnh nghiên cứu nằm ở `research_context.md`.

Trạng thái của mỗi bước dùng một trong bốn mức sau.

| Mức | Nghĩa |
|---|---|
| Đã chạy | Đã cài trong notebook thật và đã chạy trên Kaggle ở v3 |
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
| 3 | Tính gold bằng oracle | `1dc937a9`, `scale-setup` | `gold_ids` | Oracle mới: đã cài |
| 4 | Truy hồi AST, tức mốc chỉ dùng code | `load_graph_indices`, `v4-run` | `ast_ids` | Truy hồi đã chạy. `v4-run` chưa viết |
| 5 | Nguồn DOC | `doc_votes`, `doc_set` | `doc_ids_vote_ast` | Đã chạy |
| 6 | Nguồn HIST theo Locus | `hist-build`, `hist-proc` | `doc_ids_hist_locus` | Đã cài |
| 7 | Nguồn ISSUE | `issue-fetch`, `issue-index` | `doc_ids_issue` | Tạm hoãn |
| 8 | Trộn các nguồn với AST | `v4-fusion` | Danh sách cuối của từng hệ thống | Chưa chốt |
| 9 | Judge | `judge-v4` | Nhãn trong `judge_v4/` | Judge v3 đã chạy. Judge v4 đã chốt |
| 10 | Đánh giá | `verify-v4` | Các bảng ở mục 10 | Đã chốt |

---

## 1. Dữ liệu và snapshot

**Mục đích.** Bước này chọn instance và gán mỗi instance cho một graph. Build một graph cho mỗi instance thì quá tốn, nên các instance gần nhau về thời gian dùng chung một graph.

**Input.** Dữ liệu là split `test` của `princeton-nlp/SWE-bench`. Đề tài dùng hai repo là `django/django` và `sympy/sympy`. Hai repo có 1.236 instance.

**Cách làm.**
1. Trong mỗi cặp (repo, version), instance được sắp theo thời điểm của base commit.
2. Một khoảng mới bắt đầu khi base commit cách đầu khoảng hiện tại hơn 60 ngày.
3. Snapshot của một khoảng là base commit **sớm nhất** trong khoảng. Vì vậy không snapshot nào chứa bản sửa của một instance khác trong cùng khoảng.
4. Instance bị loại khi graph snapshot không có gold nào là Function hoặc Class. Sau bước này còn 1.186 instance.

**Kết quả.** Django có 40 snapshot cho 820 instance. SymPy có 46 snapshot cho 366 instance.

**Không tách dev và test.** Theo quyết định ngày 15/10/2026, mọi bước chọn tham số và mọi kết quả đều dùng cả 1.186 instance. Con số của v4 vì vậy có thể cao hơn mức thật. Phần khẳng định nằm ở giai đoạn 3, với luồng xử lý đã đóng băng. Trường `lite` vẫn được giữ trong dữ liệu, nhưng không còn dùng để chia tập.

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

**Vấn đề đã biết (mục 6.10 của `planning.md`).** Chunk thường chỉ nối tới class, thay vì method được nói tới. Có chunk nhắc tên gold nhưng không có cạnh. Việc sửa chưa có thiết kế.

**Cơ sở.** Chưa có bài báo. Số liệu trên là phép đo của đề tài.

**Trạng thái.** Đã chạy. Việc sửa ở mục 6.10 chưa chốt.

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

**Trạng thái.** Đã cài trong bản làm việc. Chưa áp vào notebook thật.

---

## 4. Truy hồi AST, tức mốc chỉ dùng code

**Mục đích.** Đây là hệ thống chỉ dùng code. Mọi nguồn khác được so với hệ thống này.

**Query.** Query là `problem_statement` của instance.

**Cách làm.**
1. **BM25** dùng `BM25Okapi` của thư viện `rank_bm25` với tham số mặc định (k1 = 1,5 và b = 0,75). Tập tài liệu gồm mọi node không phải doc, kể cả Module. Văn bản của node là source. Nếu source ngắn hơn 5 ký tự, văn bản là nhãn, tên và file. Token được tách bằng `_tokenize_code`: tách camelCase, đưa về chữ thường, rồi lấy các chuỗi chữ và số. Vì vậy snake_case cũng bị tách.
2. **Embedding.** Query được bỏ các khối code trong dấu ```, rồi cắt ở 2.000 ký tự. Query được so cosine với embedding của Function và Class.
3. **Gộp.** Lấy 500 node đầu của BM25 và 500 node đầu của embedding. Điểm của node là Σ 1/(60 + r), với r là hạng bắt đầu từ 0 trong từng danh sách.
4. Lấy 500 node đầu sau khi gộp (`EXP_DEEP`), rồi chỉ giữ Function và Class. Vì vậy danh sách có tối đa 500 hàm/lớp. Ở v3, chỉ 100 id đầu được lưu. Cell `v4-run` sẽ lưu đủ danh sách này.

**Cơ sở.** Hằng số k = 60 của RRF lấy từ Cormack, Clarke và Büttcher (SIGIR 2009). Các lựa chọn còn lại là thiết kế từ v2 và chưa có bài báo làm cơ sở.

**Trạng thái.** Truy hồi đã chạy. Cell `v4-run` chưa viết.

---

## 5. Nguồn DOC (`vote_ast`)

**Mục đích.** Nguồn này dùng doc để chọn ra các hàm/lớp liên quan tới issue.

**Cách làm.**
1. **Tìm chunk.** Chỉ các DocChunk có ít nhất một cạnh `Documents` được xét. Các chunk được xếp bằng RRF của hạng BM25 và hạng embedding, tính bên trong tập chunk đó. Năm chunk đầu được giữ (`EXP_N_DOC = 5`).
2. **Bỏ phiếu.** Mỗi chunk bỏ phiếu cho mọi Function/Class mà nó có cạnh `Documents` tới. Phiếu bằng điểm RRF của chunk nhân 0,8, là trọng số của cạnh `Documents`. Một node nhận nhiều phiếu thì giữ phiếu cao nhất.
3. **Lan phiếu một bước.** Từ mỗi node được bỏ phiếu, phiếu lan sang các Function/Class nối tới nó bằng cạnh AST chiều xuôi, với hệ số 0,5. Cạnh AST gồm `Calls`, `Inherits`, `Defines` và `Imports`. Node có hơn 20 hàng xóm thì không lan, để tránh hub. Ví dụ, chunk nối tới class `QuerySet` thì các method do `QuerySet` định nghĩa cũng nhận phiếu qua cạnh `Defines`.
4. **Sắp xếp.** Tập node được sắp theo hạng AST. Node ngoài 500 hạng đầu của AST giữ thứ tự phiếu ở cuối. Vì vậy DOC thực chất là các ứng viên AST được bằng chứng doc chọn lọc.
5. **Đối chứng `random_ast`** dùng năm chunk ngẫu nhiên có cạnh `Documents`, với seed theo instance.

**Lưu ý.** Mục 4.3 của `research_context.md` ghi rằng phiếu chỉ lan qua cạnh `Calls`. Code lan theo mọi cạnh AST chiều xuôi, như mô tả ở trên.

**Output.** Mỗi dòng kết quả có `doc_ids_vote_ast`, `doc_score_vote_ast`, `doc_r_vote_ast` (hạng AST, 0 nếu ngoài 500), `doc_gold_vote_ast`, các chunk đã dùng và đích cạnh của từng chunk.

**Cơ sở.** Chưa có bài báo. Đây là thiết kế từ v2.

**Trạng thái.** Đã chạy.

---

## 6. Nguồn HIST theo Locus

**Mục đích.** Nguồn này xếp hạng hàm/lớp bằng cách so khớp issue với nội dung của các thay đổi cũ. Đây là bước "đọc title, message và diff" của quy trình debug, nhưng không dùng LLM.

### 6.1 Lớp history (`hist-build`)

- **Đơn vị** là commit trên nhánh chính (`git log --first-parent`). Với SymPy, phần lớn đơn vị là merge commit của một pull request. Lịch sử được lấy từ snapshot mới nhất lùi tới 5 năm trước snapshot cũ nhất. Django có 18.348 đơn vị (từ tháng 8/2012 tới tháng 7/2023). SymPy có 6.772 đơn vị (từ tháng 7/2013 tới tháng 3/2023).
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

- Mỗi dòng của `scale_rows_v4.jsonl` có `doc_ids_hist_locus`, `doc_score_hist_locus`, `doc_r_hist_locus` và `doc_gold_hist_locus`, theo cùng dạng mà `fused_multi` đọc.
- Danh sách giữ tối đa 500 hàm/lớp có điểm lớn hơn 0, bằng độ sâu của xếp hạng AST. Hàm/lớp không có trong graph của snapshot bị bỏ. Điểm bằng nhau thì xếp theo id.
- `hist_locus_alpha` ghi α của issue.
- `hist_locus_best` ghi hunk tốt nhất của 10 hàm/lớp đầu, dạng [hàm/lớp, sha 8 ký tự, file, thứ tự hunk trong file]. Judge dùng thông tin này để lấy bằng chứng.

### 6.6 Kiểm tra trên máy

Harness dùng 6 instance Django, 6 instance SymPy và khoảng 200 ngày history trước mỗi snapshot.

| Phép kiểm tra | Kết quả |
|---|---|
| Hàm/lớp của các hunk so với touch tính lại bằng oracle mới | 77 đơn vị trùng hẳn. 3 đơn vị có hunk ít hơn touch, do `-w` và bộ lọc comment |
| Rò rỉ | Mọi hunk được dùng đều thuộc đơn vị là tổ tiên của snapshot |
| Tính tay điểm của hàm đứng đầu | Khớp tới 6 chữ số ở cả hai repo |
| Bước trộn | `fused_multi` đọc được nguồn mới |
| Chạy lại | Bỏ qua mọi dòng đã có kết quả |

Máy không có nltk, nên harness thay Porter bằng bản giữ nguyên từ. Phần đưa từ về gốc chưa được thử trên máy.

**Cơ sở.** Locus và AmaLgam, đã đọc toàn văn. Bảy chỗ chuyển đổi không có trong bài.

**Trạng thái.** Đã cài. Cell cần `V4_RESULTS` từ `v4-config` và các dòng do `v4-run` tạo, nhưng hai cell này chưa viết. Phân tích thành phần ở mục 10 cần thêm danh sách của hai cấu hình con (chỉ NL, NL+CE), và cell chưa ghi hai danh sách này.

**Nguồn HIST của v3.** HIST của v3 tìm commit bằng BM25 và embedding trên message, rồi cho commit bỏ phiếu cho hàm đã sửa. Nguồn này chỉ được giữ để chạy lại v3.

---

## 7. Nguồn ISSUE

**Mục đích.** Nguồn này dùng các báo cáo lỗi cũ đã được sửa. Báo cáo cũ giống issue hiện tại thì các hàm mà nó đã sửa được cộng điểm.

**Thiết kế hiện có (mục 6.5 của `planning.md`).**
- Điểm của hàm/lớp f là SimiScore(f) = Σ sim(b, b′) / |Fix(b′)|, theo BugLocator. Tổng chạy qua mọi báo cáo cũ b′ có f thuộc Fix(b′). Ở đây sim là cosine TF-IDF giữa issue và báo cáo cũ, và Fix(b′) là tập hàm/lớp mà các commit sửa b′ đã sửa.
- IDF được tính riêng cho từng snapshot, chỉ trên báo cáo tạo trước thời điểm của snapshot.
- Báo cáo cũ phải được tạo trước `created_at` của instance ít nhất 1 ngày. Commit sửa phải là tổ tiên của snapshot. Báo cáo của chính instance bị loại. Báo cáo có Fix(b′) rỗng không đóng góp.
- Django dùng ticket Trac. SymPy dùng issue GitHub và từ khóa đóng issue trong body của PR.

**Việc còn chờ.** Đề xuất chỉ dùng liên kết "Fixed #N" cho Django, bỏ "Refs #N", chưa được xác nhận. Cơ sở của đề xuất là công thức của BugLocator và quy ước commit của Django.

**Cơ sở.** BugLocator, chỉ đọc qua nguồn thứ cấp. Bộ lọc thời gian theo Lingxi và KGCompass.

**Trạng thái.** Tạm hoãn, vì chưa có dữ liệu issue.

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

**Các hệ thống so sánh (mục 6.1 của `planning.md`).** Có AST, +DOC, +HIST, +ISSUE, +ALL và ba hệ thống bỏ bớt một nguồn (ALL−DOC, ALL−HIST, ALL−ISSUE). Trước mắt, thực nghiệm tập trung vào HIST.

**Cơ sở.** Cormack, Clarke và Büttcher (SIGIR 2009) cho RRF với trọng số bằng nhau, tức p = 1. Lưới p hiện tại {0,05; 0,1; 0,25} và h thuộc {0, 1, 3, 5} được giữ từ v2 và v3, và chưa có bài báo làm cơ sở.

**Trạng thái.** Chưa chốt. Cách trộn thuộc phần đang tìm hiểu về chấm điểm và xếp hạng sau truy hồi. Yêu cầu đã thống nhất là cách được chọn không nên tự đặt trần cho mức một nguồn có thể kéo node lên.

---

## 9. Judge

**Mục đích.** Judge chấm các phần tử được truy hồi. Nhờ vậy đánh giá không chỉ dựa trên gold. Judge chấm mọi phần tử, kể cả DocChunk, và luôn thấy toàn văn.

**Cấu hình chung.**
- Model là `gemini-3.1-flash-lite`, với mức thinking LOW, chạy qua Batch API.
- Mỗi batch gồm mọi request của 150 instance. Lý do là Tier 1 giới hạn 10 triệu token đang xếp hàng.
- Tên và job của từng batch được ghi vào `batch_jobs.txt`, để chạy lại không phải trả tiền hai lần.
- `GOOGLE_API_KEY` là biến thường trong `judge-config`.

**Judge v3 (đã chạy).**
- Request node code chứa hợp top 10 của mọi hệ thống. Judge thấy toàn bộ code của node, lấy từ git tại snapshot theo dòng đầu và dòng cuối. Judge không thấy bản vá.
- Thang điểm là 0 đến 3. Điểm 3 nghĩa là bản sửa phải đổi code trong phần tử. Điểm 2 nghĩa là phải đọc phần tử để sửa. Điểm 1 nghĩa là cùng tính năng nhưng không cần cho bản sửa. Điểm 0 nghĩa là không liên quan.
- Phần tử được xáo trộn và đặt tên C1, D1, H1, nên judge không biết phần tử đến từ nguồn nào.
- nDCG@10 được tính từ nhãn của node code.
- Judge v3 còn có request chunk doc và request commit. Nhãn commit của v3 không dùng được, vì judge chỉ thấy message mà không thấy diff.

**Judge v4 (đã chốt, chưa cài).**
- Request `#code2` dùng lại prompt node code của v3. Nó chỉ chấm node mới vào top 10 của một hệ thống mà chưa có nhãn trong `judge_v3`.
- Request bằng chứng chấm chunk doc (toàn văn, kèm node mà chunk nối tới), bằng chứng HIST và báo cáo cũ của ISSUE. Với HIST, bằng chứng là hunk tốt nhất của 10 hàm/lớp đầu, lấy từ `hist_locus_best`.
- Judge bằng chứng được xem bản vá thật. Mỗi phần tử có hai điểm từ 0 đến 3, một cho mức liên quan và một cho mức hữu ích. Phần tử chỉ cùng file hoặc cùng tính năng được tối đa 1 điểm hữu ích. Judge viết lý do trước điểm. Phần tử được chấm theo danh sách và được xáo thứ tự.
- Khóa của mỗi nhãn chứa hash của input.

**Cơ sở.** eRAG (Salemi, Zamani, SIGIR 2024) cho thấy nhãn "liên quan" do LLM chấm gần như không tương quan với kết quả cuối. Utility judgments (Zhang và cộng sự, SIGIR 2024) cho thấy prompt hỏi "hữu ích" tốt hơn prompt hỏi "liên quan", chấm theo danh sách tốt hơn, và LLM nhạy với vị trí. Hai bài này đã được đọc toàn văn. Thomas và cộng sự (SIGIR 2024) mới được đọc ở mức tóm tắt.

**Trạng thái.** Judge v3 đã chạy. Judge v4 đã chốt. Mục 6.7 của `planning.md` vẫn mô tả bằng chứng HIST theo thiết kế cũ.

---

## 10. Đánh giá (`verify-v4`)

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

**Các bảng giữ nguyên từ kế hoạch trước.** Có nDCG@10 theo judge, mức hữu ích của bằng chứng theo nguồn, và độ phủ liên kết của ISSUE.

**Trạng thái.** Đã chốt, chưa cài.

---

## 11. Chạy trên Kaggle và manifest

**Môi trường.** `WORK_DIR` là `/kaggle/working`. Repo được clone vào `/tmp/repos`. Kaggle giới hạn 12 giờ mỗi lần chạy, và xóa `/kaggle/working` khi mở phiên mới. Vì vậy nhãn judge cũ phải được nạp lại từ một dataset.

**Các file của v4.**

| File | Nội dung |
|---|---|
| `history/<repo>_history_v2.jsonl` | Đơn vị history, với touch set theo oracle mới |
| `history/<repo>_hunks_v2.jsonl` | Chỉ mục hunk của HIST |
| `V4_DIR/scale_rows_v4.jsonl` | Một dòng cho mỗi instance, gồm xếp hạng AST và danh sách của các nguồn |
| `judge_v4/` | Nhãn của judge v4 |
| `V4_DIR/manifest.json` | Hash của từng cell v4, prompt, model, input của judge, các file dữ liệu và tham số |

**Đóng băng.** Giai đoạn 3 chỉ được chạy với đúng luồng xử lý đã ghi trong manifest. Notebook không được commit vì còn API key, nên hash của từng cell thay cho commit hash.

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
| Số chunk của DOC | 5 | Mục 5 | Chưa có bài báo |
| Trọng số cạnh `Documents`, hệ số lan, số hàng xóm tối đa | 0,8; 0,5; 20 | Mục 5 | Chưa có bài báo |
| λ của Locus | 5 | Mục 6 | Locus |
| β₁ của Locus | 0,1 | Mục 6 | Locus |
| Quy tắc commit sửa lỗi | `fix\|bug` | Mục 6 | AmaLgam |
| Số hàm/lớp lưu cho HIST | 500 | Mục 6 | Bằng độ sâu AST |
| Số hàm/lớp được ghi bằng chứng cho judge | 10 | Mục 6 và 9 | Bằng số node judge chấm cho mỗi hệ thống |
| p và h của bước trộn | Chưa chốt | Mục 8 | Đang tìm hiểu |
| Model judge | `gemini-3.1-flash-lite`, thinking LOW | Mục 9 | Chọn theo chi phí |
| Số node đầu mỗi hệ thống được judge chấm | 10 | Mục 9 | Bằng mức cắt của nDCG@10 |
| Số instance mỗi batch judge | 150 | Mục 9 | Giới hạn 10 triệu token của Tier 1 |

---

## 13. Việc còn mở

1. Cách trộn các nguồn với AST (mục 8) chưa chốt.
2. Việc sửa cách nối doc với code (mục 2.2) chưa có thiết kế.
3. Quy tắc A7 bỏ sót tên lớp chỉ viết hoa chữ đầu (mục 6.4).
4. Cell `hist-proc` chưa ghi danh sách của hai cấu hình con cho phân tích thành phần (mục 10).
5. Các cell `v4-config`, `v4-run`, `v4-fusion`, `judge-v4`, `verify-v4` và `manifest` chưa viết.
6. Nguồn ISSUE tạm hoãn. Đề xuất chỉ dùng "Fixed #N" chưa được xác nhận.
7. Việc 1.2 (tính lại v3 với oracle mới) và việc 1.3 (kiểm tra snapshot) chưa làm.
8. Một số chỗ trong `planning.md` chưa khớp với các quyết định mới. Mục 5.1 và 6.2 vẫn có quy tắc thống kê và độ đo chính cũ. Mục 6.3, 6.7, bảng ở mục 7 và mục 9 vẫn nhắc tới F, m và bước 3 cũ. Mục 4.3 và mục 9 của `research_context.md` cũng chưa khớp.
