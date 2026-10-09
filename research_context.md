# Bối cảnh nghiên cứu RepoGraph

File này được cập nhật ngày 2026-10-09. File tóm tắt toàn bộ trạng thái nghiên cứu hiện tại.
Notebook chính là `colab/build_graph_flask_colab.ipynb`. Notebook được chạy trên Kaggle.

---

## 1. Câu hỏi nghiên cứu

Đề tài muốn chứng minh rằng tài liệu của dự án có đóng góp dương cho việc giải quyết issue, khi xét ở mức tổng thể.

- Tài liệu (doc) là các file tài liệu nằm ngoài code, như `.rst`, `.md` và `.txt`. Trong graph, mỗi đoạn tài liệu là một node `DocChunk`. Docstring không được tính là doc.
- Bước được đo là định vị code (code localization). Nghĩa là hệ thống phải tìm ra hàm hoặc lớp cần sửa cho một issue.
- Đề tài chưa đo bước sinh bản sửa (patch).
- Dữ liệu là tập test của SWE-bench bản đầy đủ.

## 2. Khung lập luận đã thống nhất

- Đề tài giả định doc có đủ thông tin để tạo tác động dương.
- Nếu doc gây tác động âm, lỗi nằm ở phương pháp. Khi đó cần tiếp tục điều chỉnh phương pháp.
- Nếu thông tin trong doc trùng với thông tin đã có trong issue và code, doc không tạo tác động. Tác động khi đó bằng 0.
- Mục tiêu là tác động dương. Nếu chưa đạt, mục tiêu tối thiểu là không âm và có một phần dương.
- "Tổng thể" nghĩa là không bắt buộc issue nào cũng có doc mô tả. Doc chỉ cần giúp khi xét chung trên toàn bộ issue.
- Mọi loại doc đều được tính là doc, như specs, requirement hay user guide. Phân tích hiệu quả của từng loại doc sẽ làm sau.
- Đây là phân tích dữ liệu, không phải xây benchmark. Vì vậy đề tài không dùng các bước như chia dev/test cho judge, đăng ký trước giả thuyết, dùng nhiều judge hay gán nhãn thủ công.

## 3. Dữ liệu

- Đề tài dùng 12 repo của SWE-bench bản đầy đủ. Tổng cộng có 2.294 instance.
- 82 instance bị loại, vì graph snapshot không chứa gold nào là Function hoặc Class. Còn lại 2.212 instance.
- Tập dev gồm 288 instance thuộc SWE-bench Lite. Tập dev chỉ dùng để chọn cấu hình kết hợp và ngưỡng của cổng.
- Tập test gồm 1.924 instance còn lại.
- LLM judge chấm toàn bộ 2.212 instance.

| Repo | Tổng | Được dùng | Dev (Lite) | Số graph snapshot |
|---|---|---|---|---|
| django/django | 850 | 820 | 114 | 40 |
| sympy/sympy | 386 | 366 | 77 | 46 |
| scikit-learn/scikit-learn | 229 | 223 | 23 | 17 |
| sphinx-doc/sphinx | 187 | 182 | 16 | 26 |
| matplotlib/matplotlib | 184 | 180 | 23 | 19 |
| pytest-dev/pytest | 119 | 117 | 17 | 30 |
| pydata/xarray | 110 | 107 | 5 | 25 |
| astropy/astropy | 95 | 89 | 6 | 21 |
| pylint-dev/pylint | 57 | 53 | 6 | 14 |
| psf/requests | 44 | 43 | 6 | 26 |
| mwaskom/seaborn | 22 | 22 | 4 | 9 |
| pallets/flask | 11 | 10 | 3 | 6 |
| **Tổng** | **2.294** | **2.212** | **300** (288 được dùng) | **279** |

## 4. Phương pháp

### 4.1 Graph

- Code được phân tích bằng tree-sitter. Graph có các node Module, Class và Function, cùng các cạnh giữa chúng.
- Doc được đọc từ thư mục doc đầu tiên tồn tại trong danh sách ứng viên. Thư mục `_build`, `_static`, `_templates`, `_themes`, `generated` và `auto_examples` bị bỏ qua.
- Mỗi file doc tạo một node `Document`. Mỗi đoạn trong file tạo một node `DocChunk`. Cạnh `HasChunk` nối `Document` với `DocChunk`.
- Cạnh `Documents` nối `DocChunk` với code. Cạnh này **chỉ được tạo từ tên đối tượng Python**. Các nguồn tạo cạnh gồm:
  - các role `:func:`, `:meth:`, `:class:`, `:attr:`, `:exc:` và `:obj:`;
  - các directive `autoclass`, `autofunction` và các directive tương tự;
  - các directive viết tay như `.. class::` hay `.. py:method::`, chẳng hạn trong doc của Django.
- Cạnh `References` nối doc với doc, qua role `:doc:`.
- Graph được ghi bằng orjson thành file `.json` thường, kèm file tóm tắt `.summary.json`. Graph không được nén.

### 4.2 Snapshot và gold

- Mỗi phiên bản SWE-bench được chia thành các khoảng 60 ngày.
- Mỗi khoảng có một graph. Graph được build tại base commit sớm nhất trong khoảng. Cách này tránh việc bản sửa lọt vào graph.
- Trước đây graph được build tại commit trung vị. Khi đó 420 trên 850 instance Django bị lọt bản sửa vào graph.
- Gold được tính tại đúng base commit của từng instance, bằng `git show` và tree-sitter. Sau đó gold được ánh xạ sang id trong graph snapshot.
- Kết quả kiểm tra như sau. 99% gold khớp. BM25 cho kết quả giống hệt ở 113/113 instance. Hit khớp với kết quả trên Lite.

### 4.3 Xếp hạng AST và nguồn doc

- Xếp hạng AST là hệ thống gốc. Hệ thống này tìm kiếm lai bằng BM25 và bge-small, rồi gộp hai kết quả bằng RRF. Ứng viên là các node Function và Class. Mỗi instance lưu top 100.
- Nguồn doc chính là `vote_ast`.
  - Issue được dùng làm truy vấn để lấy các chunk doc.
  - Mỗi chunk bỏ phiếu cho các node code mà nó nối tới qua cạnh `Documents`.
  - Tập doc gồm các node được bỏ phiếu, sắp theo điểm AST.
- Nguồn đối chứng là `random_ast`. Nguồn này dùng cùng quy trình, nhưng các chunk được chọn ngẫu nhiên, với seed theo từng instance.
- Đề tài so sánh ba hệ thống:
  - AST là hệ thống gốc.
  - DOC là AST kết hợp với `vote_ast`.
  - RAND là AST kết hợp với `random_ast`.

### 4.4 Kết hợp (fusion)

- Có hai cách kết hợp.
  - Cách thứ nhất là RRF. Điểm của một node bằng 1/(k + r_AST) + p/(k + r_doc).
  - Cách thứ hai là tổ hợp lồi của các điểm đã chuẩn hóa min-max.
- Tham số `h` giữ nguyên `h` node đầu của AST.
- Bộ lọc `direct` chỉ giữ các node doc nối trực tiếp với chunk.
- Lưới tham số có 64 cấu hình. Cấu hình được chọn trên dev qua hai bước.
  1. Chỉ giữ các cấu hình có ΔHit@k không âm với mọi k ∈ {1, 5, 10, 20}.
  2. Trong các cấu hình đó, chọn cấu hình có ΔHit trung bình lớn nhất.
- Có 18/64 cấu hình không âm. Cấu hình được chọn là `rrf`, `p = 0.1`, `h = 1`, `filter = all`.

### 4.5 Đánh giá theo gold

- Các chỉ số gồm Hit@k ở mức hàm, lớp và file, với k = 1, 5, 10, 20 và 40. Ngoài ra còn có reciprocal rank (RR).
- Hit@k được kiểm định bằng McNemar, tức binomtest trên các cặp có kết quả khác nhau. P-value được hiệu chỉnh bằng Holm.
- RR được kiểm định bằng Wilcoxon.
- Rủi ro theo repo được đo bằng URisk và TRisk (Dinçer và cộng sự, 2014), với α = 1 và α = 5.
  - TRisk < −2 nghĩa là kém hơn AST có ý nghĩa.
  - TRisk > 2 nghĩa là tốt hơn AST có ý nghĩa.

### 4.6 Đánh giá bằng LLM judge

- Đề tài dùng judge vì gold chỉ tính các node bị sửa trong bản vá. Node do doc đưa vào có thể liên quan tới issue nhưng không bị sửa. Khi đó gold vẫn tính node này là sai.
- Model judge là `gemini-3.1-flash-lite`, với thinking level LOW. Đầu ra là JSON theo schema.
- Mỗi instance có một pool. Pool là hợp của top 10 từ AST, DOC và RAND.
  - Thứ tự các node trong pool bị xáo trộn.
  - Judge không biết node đến từ hệ thống nào.
  - Judge không thấy bản sửa.
- Thang điểm có bốn mức.
  - Điểm 3 nghĩa là bản sửa phải thay đổi code trong node.
  - Điểm 2 nghĩa là phải đọc hoặc hiểu node thì mới sửa được.
  - Điểm 1 nghĩa là node cùng tính năng, nhưng không cần cho bản sửa.
  - Điểm 0 nghĩa là node không liên quan.
- Các chỉ số gồm:
  - nDCG@10, với gain bằng 2^điểm − 1. Thứ tự lý tưởng được lấy từ các node đã chấm của chính instance đó.
  - Rel@k, bằng 1 khi top k có ít nhất một node đạt điểm ≥ 2.
  - Strict@k, bằng 1 khi top k có ít nhất một node đạt điểm 3.
- Phân tích hoán đổi so sánh điểm của node DOC đưa vào top 10 với điểm của node AST bị đẩy ra. Có ba kịch bản.
  - Kịch bản A là node DOC có điểm cao hơn có ý nghĩa.
  - Kịch bản B là hai bên không khác nhau.
  - Kịch bản C là node DOC có điểm thấp hơn có ý nghĩa.
- Kết quả kiểm tra judge như sau.
  - Có 1.814 gold nằm trong top 10 của ít nhất một hệ thống. Điểm judge trung bình của các gold này là 2,42. Có 82,2% gold được chấm ≥ 2.
  - Strict@10 của judge trùng với Hit@10 của gold ở 67,4% instance với AST, và ở 67,6% instance với DOC.
- Cả 2.212 instance đã có nhãn.

## 5. Kết quả

### 5.1 DOC so với AST theo từng repo

- Các cột gold đo trên tập test, gồm 1.924 instance.
- Các cột judge đo trên toàn bộ 2.212 instance.
- Số trong cột "tốt/kém" là số instance DOC tốt hơn AST và số instance DOC kém hơn AST.

| Repo | Hit@10 gold (tốt/kém) | Hạng gold (tốt/kém) | TRisk RR gold (α=1) | nDCG@10 judge (tốt/kém) | Strict@10 judge (tốt/kém) | TRisk nDCG (α=1) | Hoán đổi |
|---|---|---|---|---|---|---|---|
| django | 18/3 | 99/143 | **−2,33** | **322/256** | 25/4 | 0,33 | A |
| sympy | 3/0 | 28/39 | 0,29 | **108/89** | 9/1 | 1,55 | A |
| scikit-learn | 2/3 | 41/37 | −1,15 | **107/71** | 10/3 | −0,09 | A |
| astropy | 0/0 | 9/13 | −0,44 | 28/29 | 3/0 | −0,67 | A |
| xarray | 1/1 | 15/29 | −1,07 | 40/42 | 3/2 | −1,23 | A |
| pytest | 1/0 | 8/6 | 0,87 | 21/12 | 2/0 | 1,62 | B |
| requests | 2/1 | 10/10 | −0,01 | 17/19 | 3/1 | −0,43 | B |
| flask | 0/0 | 0/3 | −1,67 | 3/5 | 0/1 | −0,78 | B |
| pylint | 0/0 | 1/3 | −0,46 | 6/15 | 0/0 | **−2,19** | B |
| seaborn | 0/1 | 2/9 | −1,21 | 5/17 | 0/1 | **−3,31** | C |
| sphinx | 0/0 | 0/26 | **−2,82** | **21/59** | 1/0 | **−4,39** | B |
| matplotlib | 0/1 | 9/48 | **−2,97** | **36/76** | 2/2 | **−4,91** | B |
| **Tổng** | **27/10** | **222/366** | | **714/690** | **58/15** | | |

Số in đậm ở cột nDCG là các chênh lệch có ý nghĩa theo Wilcoxon sau khi hiệu chỉnh Holm. Số in đậm ở cột TRisk là các giá trị vượt ngưỡng ±2.

### 5.2 Kết quả gộp, chưa có cổng

- Theo gold, DOC có Hit@10 tốt hơn AST ở 27 instance và kém hơn ở 10 instance (p = 0,008).
  - Django chiếm 18 instance tốt hơn và 3 instance kém hơn.
  - Nếu bỏ Django, còn 9 instance tốt hơn và 7 instance kém hơn (p = 0,80).
- Theo gold, hạng của gold tăng ở 222 instance và giảm ở 366 instance. Theo sign test, chênh lệch này có ý nghĩa (p < 0,001).
- Theo judge, Strict@10 tốt hơn ở 58 instance và kém hơn ở 15 instance (p < 0,001).
  - Nếu bỏ Django, còn 33 instance tốt hơn và 11 instance kém hơn (p = 0,001).
- Theo judge, Rel@10 tốt hơn ở 18 instance và không kém ở instance nào.
- Theo judge, nDCG@10 thắng ở 714 instance và thua ở 690 instance. Sign test cho p = 0,54.
  - Wilcoxon gộp cho DOC không cổng chưa được tính.
  - Chênh lệch nDCG@10 trung bình của DOC không cổng là khoảng +0,011.
- DOC thắng RAND, nên lợi ích đến từ nội dung doc, chứ không phải chỉ do xáo trộn danh sách.
  - Theo judge, nDCG@10 của DOC thắng RAND ở 769 instance và thua ở 649 instance (p = 0,002).
  - Theo gold, Hit@10 của DOC tốt hơn RAND ở 25 instance và kém hơn ở 10 instance (p = 0,017).
- Theo phân tích hoán đổi, node DOC đưa vào có điểm cao hơn node AST bị đẩy ra ở 389 instance, và thấp hơn ở 206 instance (p < 0,001).
  - Kịch bản A xảy ra ở 5 repo là django, sympy, scikit-learn, astropy và xarray.
  - Kịch bản C xảy ra ở seaborn.

### 5.3 Doc giúp khi nào (cell `doc-profile`)

Đặc điểm doc được lấy từ graph snapshot có nhiều instance nhất trong mỗi repo. Mức lợi hoặc hại là trung bình của (DOC − AST) trên 2.212 instance.

| Repo | Instance | Chunk | Cạnh Documents / chunk | % API | % hướng dẫn | % changelog | B1 | B2 | Δ nDCG@10 | Δ RR gold |
|---|---|---|---|---|---|---|---|---|---|---|
| scikit-learn | 223 | 1535 | 1,42 | 54 | 28 | 18 | 0,404 | 0,596 | +0,0190 | +0,0030 |
| sympy | 366 | 1465 | 1,10 | 85 | 15 | 0 | 0,224 | 0,262 | +0,0190 | +0,0035 |
| django | 820 | 6643 | 1,03 | 39 | 31 | 29 | 0,218 | 0,315 | +0,0175 | +0,0038 |
| requests | 43 | 106 | 0,42 | 15 | 85 | 0 | 0,116 | 0,395 | +0,0168 | +0,0084 |
| pytest | 117 | 1169 | 0,16 | 8 | 40 | 52 | 0,094 | 0,111 | +0,0141 | +0,0084 |
| astropy | 89 | 2504 | 0,39 | 2 | 91 | 8 | 0,213 | 0,258 | +0,0096 | +0,0013 |
| xarray | 107 | 627 | 1,50 | 7 | 93 | 0 | 0,374 | 0,336 | +0,0087 | +0,0006 |
| pylint | 53 | 291 | 0,02 | 0 | 51 | 49 | 0,094 | 0,075 | −0,0048 | −0,0027 |
| sphinx | 182 | 639 | 0,41 | 0* | 95 | 4 | 0,104 | 0,011 | −0,0085 | −0,0080 |
| flask | 10 | 511 | 0,49 | 6 | 94 | 0 | 0,400 | 0,400 | −0,0087 | −0,0045 |
| matplotlib | 180 | 2549 | 0,16 | 9 | 20 | 71 | 0,194 | 0,239 | −0,0124 | −0,0087 |
| seaborn | 22 | 146 | 2,09 | 13 | 18 | 69 | 0,182 | 0,318 | −0,0358 | −0,0053 |

- B1 là tỷ lệ instance có chunk lấy về nêu tên gold. Chunk được coi là nêu tên gold khi text chứa tên đầy đủ của gold, hoặc khi chunk có cạnh `Documents` tới gold.
- B2 là tỷ lệ instance có tập doc chứa gold.
- Loại doc được xác định bằng regex trên đường dẫn file (`doc_kind`). Dấu * ở sphinx nghĩa là giá trị bị đo sai. Mục 5.5 giải thích lý do.

Tương quan Spearman trên 12 repo cho kết quả như sau.

- Tỷ lệ chunk API tương quan với Δ nDCG@10 (ρ = 0,60, p = 0,04). Tỷ lệ này cũng tương quan cùng chiều với Δ RR gold (ρ = 0,49, p = 0,10).
- Số chunk tương quan với Δ điểm hoán đổi (ρ = 0,59, p = 0,04).
- Mật độ cạnh `Documents` không tương quan với Δ nDCG@10 (ρ = 0,16, p = 0,62).
- B2 ở mức repo không tương quan với Δ nDCG@10 (ρ = 0,25, p = 0,43).
- Tỷ lệ changelog (ρ = −0,36) và tỷ lệ hướng dẫn (ρ = −0,23) có chiều âm, nhưng không có ý nghĩa.
- Phân tích chỉ có 12 điểm dữ liệu. Ngoài ra, giá trị % API của sphinx bị đo sai. Vì vậy các tương quan này chỉ là bằng chứng gợi ý.

Bảng dưới đây tách Δ nDCG@10 theo B1 và B2, ở mức instance và gộp mọi repo.

| B1 | B2 | Số instance | Δ nDCG@10 trung bình |
|---|---|---|---|
| 0 | 0 | 1482 | −0,0037 |
| 0 | 1 | 237 | +0,0674 |
| 1 | 0 | 94 | −0,0093 |
| 1 | 1 | 399 | +0,0383 |

- Toàn bộ lợi ích đến từ 636 instance có B2 = 1. Các instance này chiếm 29% tổng số.
- Nếu cộng Δ nDCG@10 của từng instance, nhóm B2 = 1 được khoảng +31,3. Nhóm B2 = 0 mất khoảng −6,4.
- Khi tập doc không chứa gold, tác động trung bình gần bằng 0.
- Nhóm có cả B1 và B2 được ít hơn nhóm chỉ có B2. Một giả thuyết giải thích như sau. Khi doc nêu tên gold, issue cũng thường nêu tên gold, nên AST đã tìm được gold. Giả thuyết này chưa được kiểm tra.
- Có 94 instance mà chunk nêu tên gold nhưng tập doc không chứa gold. Đây là lỗi của bước chuyển từ chunk sang node.
- Giả sử có một cổng hoàn hảo, chỉ dùng doc khi B2 = 1. Khi đó Δ nDCG@10 trung bình là khoảng +0,0141. DOC không cổng đã đạt khoảng +0,0113, tức khoảng 80% mức này.

### 5.4 Cổng dựa trên bằng chứng không cần gold (cell `doc-gate`)

- Cổng thử ba tín hiệu không cần gold.
  - `agree` là số node trong tập doc cũng nằm trong top 50 của AST.
  - `vmax` là điểm phiếu cao nhất của tập doc.
  - `ndoc` là cỡ tập doc.
- Ngưỡng được chọn trên dev theo hai điều kiện. Thứ nhất, mọi ΔHit@k phải không âm. Thứ hai, ΔRR phải ≥ 0.
- Có 8/29 ngưỡng đạt điều kiện. Cổng được chọn là `ndoc <= 86.3`.
- Trên tập test, cổng vẫn dùng doc ở 90,1% instance.

Kết quả gộp của cổng so với AST trên tập test như sau.

- Theo gold, Hit@10 tốt hơn ở 25 instance và kém hơn ở 8 instance (p Holm = 0,027).
- Theo gold, hạng tăng ở 196 instance và giảm ở 322 instance. Tuy vậy, RR trung bình vẫn nhỉnh hơn AST (0,347 so với 0,345), và Wilcoxon cho p = 0,106.
- Theo judge, nDCG@10 thắng ở 563 instance và thua ở 516 instance. Wilcoxon cho p Holm = 0,0001.
- Theo judge, Strict@10 tốt hơn ở 48 instance và kém hơn ở 8 instance (p Holm < 0,001).
- Theo judge, Rel@10 tốt hơn ở 16 instance và không kém ở instance nào (p Holm = 0,0002).

Kết quả theo repo trên tập test như sau.

| Repo | Dùng doc (%) | Δ nDCG DOC | Δ nDCG cổng | TRisk nDCG DOC | TRisk nDCG cổng | TRisk RR DOC (gold) | TRisk RR cổng (gold) |
|---|---|---|---|---|---|---|---|
| sympy | 85,3 | 0,0206 | 0,0200 | 1,84 | **2,19** | 0,29 | 1,11 |
| scikit-learn | 63,0 | 0,0197 | 0,0151 | −0,09 | 0,53 | −1,15 | −0,56 |
| requests | 94,6 | 0,0177 | 0,0138 | −0,33 | −0,49 | −0,01 | −0,01 |
| django | 97,3 | 0,0166 | 0,0158 | 0,06 | −0,05 | **−2,33** | **−2,32** |
| pytest | 100,0 | 0,0138 | 0,0138 | 1,31 | 1,31 | 0,87 | 0,87 |
| astropy | 94,0 | 0,0130 | 0,0109 | −0,21 | −0,36 | −0,44 | −0,77 |
| xarray | 97,1 | 0,0091 | 0,0142 | −1,16 | −0,34 | −1,07 | −1,02 |
| pylint | 100,0 | −0,0032 | −0,0032 | −1,82 | −1,82 | −0,46 | −0,46 |
| sphinx | 99,4 | −0,0083 | −0,0083 | **−4,19** | **−4,18** | **−2,82** | **−2,82** |
| matplotlib | 73,9 | −0,0135 | −0,0095 | **−4,79** | **−3,87** | **−2,97** | **−2,70** |
| seaborn | 88,9 | −0,0281 | −0,0231 | **−2,70** | **−2,31** | −1,21 | −0,52 |
| flask | 100,0 | −0,0345 | −0,0345 | −1,11 | −1,11 | −1,67 | −1,67 |

- Cổng giúp một phần. Sympy trở thành dương có ý nghĩa. Scikit-learn, xarray, matplotlib và seaborn bớt âm.
- Cổng không đạt mục tiêu "không âm". Theo judge, sphinx, matplotlib và seaborn vẫn có TRisk dưới −2. Theo gold, django, sphinx và matplotlib vẫn có TRisk RR dưới −2.
- Cổng thất bại vì các tín hiệu chỉ đo độ mạnh của bước lấy doc trong từng issue. Các tín hiệu này không nhận ra loại doc. Ví dụ, cổng vẫn dùng doc ở 99,4% instance của sphinx.

### 5.5 Nguyên nhân ở sphinx và pylint

Phần này kiểm tra doc tại đúng commit snapshot. Commit của sphinx là `07983a5a` (2020-12-27). Commit của pylint là `789a3818` (2022-03-30).

Ở sphinx, kết quả kiểm tra như sau.

- Giá trị 0% API là do bộ phân loại `doc_kind` sai.
  - Bộ phân loại chỉ nhận ra thư mục hoặc file tên `api`, `ref`, `reference`, `modules` hoặc `generated`.
  - API reference của sphinx nằm ở `doc/extdev/`, với các file như `appapi.rst` và `builderapi.rst`. Riêng `appapi.rst` có 59 tham chiếu tới đối tượng Python.
  - Khoảng 1/6 số file doc của sphinx thực ra là API reference.
- Doc của sphinx chủ yếu mô tả giao diện người dùng.
  - 83 file doc có 523 chỗ khai báo hoặc nhắc tới config (`confval`).
  - Doc có 341 chỗ cho directive và role RST, và 102 chỗ cho option.
  - Số tham chiếu tới đối tượng Python chỉ là 511.
  - Một phần tham chiếu Python chỉ là ví dụ cú pháp. Ví dụ, `domains.rst` có 52 tham chiếu dạng này. Các tên đó không trỏ tới code của sphinx.
- Khoảng 63% issue của sphinx nhắc tới tên config, như `autodoc_typehints`, hoặc tên directive, như `autoclass`. Con số này được đếm bằng regex thô.
- Tên config và tên directive nối với code qua chuỗi ký tự. Ví dụ, code đăng ký chúng bằng `app.add_config_value("autodoc_typehints", ...)` và `app.add_directive("autoclass", ...)`.
- Bộ trích doc không tạo cạnh `Documents` cho các tên này. Vì vậy tập doc của sphinx chỉ chứa gold ở 1,1% instance.

Ở pylint, kết quả kiểm tra như sau.

- Giá trị 0% API là đúng. 59 file doc chỉ có 22 tham chiếu tới đối tượng Python. Mỗi chunk chỉ có trung bình 0,02 cạnh `Documents`.
- Doc chủ yếu nói về message và option. Doc có 527 chỗ nhắc tới mã message hoặc tên message, như `W0611` hay `unused-import`.
- Khoảng 81% issue của pylint nhắc tới mã message, tên message hoặc option dòng lệnh. Con số này cũng được đếm bằng regex thô.
- Message và option nối với code qua chuỗi ký tự. Ví dụ, checker khai báo message trong dict `msgs`, như `"W0611": ("Unused %s", "unused-import", ...)`.
- Pylint vẫn bị âm. Giả thuyết hiện tại như sau. Doc có rất ít cạnh, và phần lớn cạnh đến từ vài chunk chung chung như `how_tos/custom_checkers.rst`. Các node chung chung đó có thể bị chèn vào nhiều issue không liên quan. Giả thuyết này chưa được kiểm tra.

Nguyên nhân chung của hai repo như sau. Doc và issue đều nói bằng tên giao diện người dùng, như config, directive, message hay option. Code đăng ký các tên này bằng chuỗi ký tự. Trong khi đó, phương pháp hiện tại chỉ nối doc với code qua tên đối tượng Python. Như vậy doc có thông tin, nhưng phương pháp không khai thác được. Trường hợp này khớp với khung lập luận ở mục 2.

## 6. Kết luận hiện tại

### 6.1 Những điều đã đủ bằng chứng

- Doc có tác động dương ở mức tổng thể, khi mỗi instance được tính một phiếu như cách tính chuẩn của SWE-bench. Bằng chứng gồm nDCG@10, Strict@10 và Rel@10 của judge, cùng Hit@10 của gold.
- Lợi ích đến từ nội dung doc. Bằng chứng là DOC thắng RAND.
- Cơ chế đã rõ. Doc giúp khi liên kết từ doc dẫn tới code cần sửa (B2 = 1). Khi liên kết không dẫn tới gold, tác động gần bằng 0.

### 6.2 Những điều chưa đạt

- Điều kiện "không âm ở mọi repo" chưa đạt. Sphinx và matplotlib bị âm rõ. Seaborn cũng bị âm, nhưng chỉ có 22 instance.
- Nếu mỗi repo được tính một phiếu, kết quả gần bằng 0, vì 7 repo dương và 5 repo âm. Phần dương khi gộp đến chủ yếu từ django, sympy và scikit-learn.
- Theo gold, số instance bị tụt hạng vẫn nhiều hơn số instance lên hạng. Lý do là mỗi node doc chèn vào top 10 đều đẩy một node AST xuống.
- Cổng dựa trên độ mạnh tín hiệu không sửa được các repo âm.
- Tương quan giữa tỷ lệ API và lợi ích yếu hơn đã báo cáo, vì sphinx bị đo sai.

## 7. Vấn đề còn mở

- Wilcoxon gộp cho DOC không cổng trên tập test chưa được tính. Trước đây có nhận định rằng nDCG@10 của DOC không cổng "không có ý nghĩa". Nhận định đó chỉ dựa trên số lần thắng và thua.
- Bộ phân loại `doc_kind` dựa trên đường dẫn. Bộ phân loại xếp sai `doc/extdev/` của sphinx. Bộ phân loại có thể cũng xếp sai `technical_reference/` của pylint.
- Cơ chế gây hại ở matplotlib chưa rõ. Tập doc chứa gold ở 24% instance, nhưng node DOC đưa vào chỉ ngang bằng node bị đẩy ra (điểm judge 0,56 so với 0,55). Doc của matplotlib có 71% changelog.
- Giả thuyết về các node chung chung ở pylint chưa được kiểm tra.
- Giả thuyết "B1 = 1 thì thông tin trùng với issue" chưa được kiểm tra. Có thể kiểm tra bằng cột `issue_names_gold`.
- Có 94 instance bị mất gold ở bước chuyển từ chunk sang node. Nguyên nhân có thể là chunk chỉ nhắc tên gold trong text mà không có cạnh `Documents`. Nguyên nhân cũng có thể là tập doc bị cắt bớt.
- Một số gold không có trong snapshot và bị bỏ. Xarray bị bỏ 65 gold, django 21 gold, matplotlib 12 gold. Lý do chưa được kiểm tra.
- Flask có 10 instance và seaborn có 22 instance. Số liệu của hai repo này không ổn định.

## 8. Hướng tiếp theo

Chưa hướng nào được triển khai.

1. **Kết luận với kết quả hiện tại.**
   - Kết luận chính là doc dương ở mức tổng thể, và cơ chế là liên kết từ doc tới code cần sửa.
   - Sphinx và matplotlib được ghi là giới hạn của phương pháp.
   - Phát hiện về loại doc trở thành đầu vào cho phần phân tích theo loại doc.
2. **Thêm cạnh `Documents` cho các tên được đăng ký bằng chuỗi.**
   - `confval X` nối tới code đăng ký hoặc đọc config `X`.
   - Directive nối tới class được đăng ký cho directive đó.
   - Message và option của pylint nối tới checker khai báo chúng.
   - Hướng này sát nguyên nhân ở mục 5.5 nhất. Hướng này cần cập nhật cạnh trong graph, rồi chạy lại `scale-run` và judge.
3. **Sửa bộ phân loại loại doc.** Bộ phân loại mới sẽ dựa trên nội dung chunk. Ví dụ, chunk có directive `auto*` hoặc `py:*` được xếp vào loại API. Sau đó chỉ cần chạy lại `doc-profile`, nên chi phí thấp.
4. **Các kiểm tra không cần chạy lại retrieval.**
   - Tính Wilcoxon gộp cho DOC không cổng.
   - Tách B1 theo `issue_names_gold`.
   - Tách Δ nDCG@10 theo B2 trong từng repo.

Đề xuất "chỉ dùng chunk loại API" đã bị loại. Lý do thứ nhất là cách này chỉ tắt doc chứ không khai thác doc. Lý do thứ hai là ở sphinx, cách này còn bỏ mất phần API thật, vì bộ phân loại sai.

## 9. Notebook và môi trường chạy

### 9.1 Thứ tự cell

1. Cài đặt và cấu hình (`DAAopL5Eo6Rz`).
2. Section 1 gồm build graph (`9df72df0`), oracle và xóa cache index.
3. Section 2 gồm clone repo (`cell-clone`).
4. Kiểm tra GPU.
5. Section 4 gồm `exp-setup` và `exp-docgroup-setup`. Hai cell này chỉ chứa hàm dùng chung.
6. Section 5 gồm `scale-data`, `scale-setup`, `scale-run`, `scale-analysis` và `scale-fusion`.
7. Section 6 gồm `judge-config`, `judge-pool`, `judge-run` và `judge-analysis`.
8. Section 7 gồm `doc-profile` và `doc-gate`.

Khi session khởi động lại, cần chạy lại các cell theo thứ tự trên. `scale-run` không chạy lại instance nào, vì kết quả đã có trong file. `judge-run` không gọi API, vì mọi request đã có nhãn.

### 9.2 Đường dẫn trên Kaggle

- `WORK_DIR` là `/kaggle/working`. Thư mục này được lưu khi bấm Save Version. Giới hạn dung lượng khoảng 20 GB.
- `WORK_DIR` chứa graph (`{repo}_graph_{sha8}.json` và `.summary.json`), file kết quả `scale_rows_v2.jsonl` và thư mục `judge/`.
- `REPO_DIR` là `/tmp/repos`. Thư mục này chứa các repo đã clone và không được lưu. Mỗi session mới phải clone lại.
- Lệnh checkout dùng `force=True`. Lý do là trước đây repo nằm trong `/kaggle/working` và bị mất quyền thực thi của file.

### 9.3 API và chi phí

- `judge-config` chứa API key dạng biến thường `GOOGLE_API_KEY`. Không commit hay push notebook khi biến này còn key.
- Gemini API trên project có billing cần mua prepaid credit, tối thiểu 5 USD. Tín dụng Cloud của gói AI Pro chỉ dùng được sau khi đã mua prepaid credit. Project có billing không dùng được gói miễn phí.
- `judge-run` có hai chế độ là `sync` và `batch`. Batch API rẻ hơn 50%.

### 9.4 Việc đang chờ quyết định

- `judge-pool` và `judge-run` có cơ chế hash. Nhãn cũ chỉ được dùng lại khi hash của request khớp. Cơ chế này được thêm khi chưa có yêu cầu. Chưa có quyết định giữ hay bỏ.

## 10. Lịch sử các quyết định chính

1. Thí nghiệm đầu tiên chạy trên SWE-bench Lite. Số instance quá nhỏ để kết luận.
2. Thí nghiệm được mở rộng lên SWE-bench bản đầy đủ, với 12 repo và graph snapshot.
3. Snapshot được chuyển từ commit trung vị sang commit sớm nhất trong khoảng 60 ngày, để tránh lọt bản sửa vào graph.
4. LLM judge được thêm vào, vì gold phạt các node liên quan nhưng không bị sửa.
5. Mọi phần liên quan tới Cursor và Google Drive đã bị bỏ. Các phân tích cũ không còn dùng đã được dọn.
6. Thư mục clone repo được chuyển sang `/tmp/repos` để giảm dung lượng. Graph vẫn được lưu trong `/kaggle/working`.
7. Section 7 được thêm vào để phân tích khi nào doc giúp, và để thử cổng.
8. Phân tích nguyên nhân ở sphinx và pylint cho thấy phương pháp chưa nối được các tên đăng ký bằng chuỗi.
