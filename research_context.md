# Bối cảnh nghiên cứu RepoGraph

File này được cập nhật ngày 2026-10-12. File tóm tắt toàn bộ trạng thái nghiên cứu hiện tại.
Notebook chính là `colab/build_graph_flask_colab.ipynb`. Notebook được chạy trên Kaggle.

Có hai lượt thực nghiệm:

- **Lượt v2** chạy trên 12 repo của SWE-bench. Kết quả nằm trong `scale_rows_v2.jsonl` và thư mục `judge/`.
- **Lượt v3** chạy trên django và sympy, có thêm lớp git history và judge mới. Lượt này đã được hiện thực và kiểm thử trên máy, nhưng **chưa chạy trên Kaggle**.

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
- **Yêu cầu về judge.** Judge phải chấm **mọi node** của kết quả truy xuất, kể cả node document, và phải nhận nội dung đầy đủ. Lý do là chỉ chấm hàm và lớp thì không đánh giá được bản thân document.

## 3. Dữ liệu

| Repo | Tổng | Được dùng | Dev (Lite) dùng được | Test | Số graph snapshot |
|---|---|---|---|---|---|
| django/django | 850 | 820 | 107 | 713 | 40 |
| sympy/sympy | 386 | 366 | 73 | 293 | 46 |
| scikit-learn/scikit-learn | 229 | 223 | | | 17 |
| sphinx-doc/sphinx | 187 | 182 | | | 26 |
| matplotlib/matplotlib | 184 | 180 | | | 19 |
| pytest-dev/pytest | 119 | 117 | | | 30 |
| pydata/xarray | 110 | 107 | | | 25 |
| astropy/astropy | 95 | 89 | | | 21 |
| pylint-dev/pylint | 57 | 53 | | | 14 |
| psf/requests | 44 | 43 | | | 26 |
| mwaskom/seaborn | 22 | 22 | | | 9 |
| pallets/flask | 11 | 10 | | | 6 |
| **12 repo (lượt v2)** | **2.294** | **2.212** | **288** | **1.924** | **279** |
| **django + sympy (lượt v3)** | **1.236** | **1.186** | **180** | **1.006** | **86** |

- Instance bị loại khi graph snapshot không chứa gold nào là Function hoặc Class.
- Tập dev là các instance thuộc SWE-bench Lite. Tập dev chỉ dùng để chọn cấu hình.

## 4. Phương pháp chung

### 4.1 Graph

- Code được phân tích bằng tree-sitter. Graph có các node Module, Class và Function, cùng các cạnh `Defines`, `Imports`, `Calls` và `Inherits`.
- Doc được đọc từ thư mục doc đầu tiên tồn tại (`docs`, `doc`, ...). Mỗi file doc là một node `Document`. Mỗi đoạn theo heading là một node `DocChunk`, nối với `Document` bằng cạnh `HasChunk`.
- Cạnh `Documents` nối `DocChunk` với Function hoặc Class. Cạnh này chỉ được tạo từ tên đối tượng Python, qua các role `:func:`, `:meth:`, `:class:`, ... và các directive `autoclass`, `.. method::`, ...
- Cạnh `References` nối doc với doc, qua role `:doc:`.
- Graph được ghi bằng orjson thành file `.json`, kèm file tóm tắt `.summary.json`. Graph không được nén.
- Id của node có dạng `{snap8}:{đường dẫn}:{tên lồng nhau}`.

### 4.2 Snapshot và gold

- Mỗi phiên bản SWE-bench được chia thành các khoảng 60 ngày. Mỗi khoảng có một graph, build tại base commit sớm nhất trong khoảng. Cách này tránh việc bản sửa lọt vào graph.
- Gold được tính tại đúng base commit của từng instance, bằng `git show` và tree-sitter (`_file_nodes_at` rồi `get_oracle`). Sau đó gold được ánh xạ sang id của graph snapshot.
- Mỗi dòng bị đổi được gán cho hàm hoặc lớp nhỏ nhất chứa nó. Dòng ở cấp module bị bỏ qua nếu file có đổi hàm. Nếu cả file chỉ đổi ở cấp module, gold là node `Module`, và instance bị loại vì ứng viên chỉ là Function và Class.
- Kết quả kiểm tra như sau. 99% gold khớp. BM25 cho kết quả giống hệt ở 113/113 instance.

### 4.3 Xếp hạng và nguồn doc

- **AST** là hệ thống gốc. Hệ thống này tìm kiếm lai BM25 và bge-small trên Function và Class, rồi gộp bằng RRF.
- **Nguồn `vote_ast`.** Issue tìm ra 5 chunk có cạnh `Documents`. Mỗi chunk bỏ phiếu cho các node mà nó nối tới, và lan một bước qua cạnh `Calls` với hệ số 0,5. Tập doc được sắp theo hạng AST.
- **Nguồn `random_ast`** dùng cùng quy trình, nhưng chọn chunk ngẫu nhiên. Đây là nguồn đối chứng.
- **Kết hợp** bằng RRF: điểm của node là 1/(k + r_AST) + p/(k + r_doc), với tham số h giữ nguyên h vị trí đầu của AST. Cấu hình chọn trên dev của lượt v2 là `rrf`, `p = 0.1`, `h = 1`, `filter = all`.

### 4.4 Đánh giá theo gold

- Các chỉ số gồm Hit@k ở mức hàm, lớp và file (k = 1, 5, 10, 20, 40), và reciprocal rank (RR).
- Hit@k dùng McNemar, RR dùng Wilcoxon, và p-value được hiệu chỉnh Holm.
- Rủi ro theo repo dùng URisk và TRisk (Dinçer và cộng sự, 2014). TRisk < −2 nghĩa là kém hơn AST có ý nghĩa.

## 5. Kết quả lượt v2 (12 repo)

### 5.1 Theo gold (còn hiệu lực)

Các kết quả dưới đây đo trên tập test gồm 1.924 instance.

- DOC có Hit@10 tốt hơn AST ở 27 instance và kém hơn ở 10 instance (p = 0,008).
  - Django chiếm 18 instance tốt hơn và 3 instance kém hơn.
  - Nếu bỏ Django, còn 9 instance tốt hơn và 7 instance kém hơn (p = 0,80).
- Hạng của gold tăng ở 222 instance và giảm ở 366 instance.
- DOC có Hit@10 tốt hơn RAND ở 25 instance và kém hơn ở 10 instance (p = 0,017).
- TRisk theo RR (α = 1) âm có ý nghĩa ở django (−2,33), matplotlib (−2,97) và sphinx (−2,82). Không repo nào dương có ý nghĩa.
- Cổng `ndoc <= 86.3` vẫn dùng doc ở 90% instance. Theo gold, cổng có Hit@10 tốt hơn AST ở 25 instance và kém hơn ở 8 instance (p Holm = 0,027).

### 5.2 Theo judge (không còn đáng tin)

Lượt v2 có nDCG@10, Strict@10 và Rel@10 theo judge, phân tích hoán đổi node, bảng Δ nDCG@10 theo B1 và B2, và các cột judge trong Section 7. **Mọi kết quả này không còn đáng tin**, vì judge của lượt v2 đã được hiện thực sai yêu cầu (xem mục 6.1). Vì vậy kết luận "doc chỉ giúp khi tập doc chứa gold" (bảng B1/B2) cũng phải được kiểm tra lại, vì bảng đó dùng nDCG của judge.

### 5.3 Phân tích theo repo (Section 7)

- Theo đặc điểm doc, tỷ lệ chunk API tương quan với lợi ích (ρ = 0,60, p = 0,04). Tuy vậy, giá trị % API của sphinx bị đo sai, vì bộ phân loại dựa trên đường dẫn không nhận ra `doc/extdev/`.
- Sphinx và pylint bị âm vì doc và issue nói bằng tên giao diện người dùng, như config, directive, message hay option. Code đăng ký các tên này bằng chuỗi ký tự, mà cạnh `Documents` chỉ nối được tên đối tượng Python. Hướng sửa cho hai repo này đã được **bỏ** theo quyết định của người dùng.

## 6. Các phát hiện sau lượt v2

### 6.1 Judge của lượt v2 sai yêu cầu

| Phần | Yêu cầu | Lượt v2 đã làm |
|---|---|---|
| Node được chấm | Mọi node, kể cả chunk doc | Chỉ node code (hàm và lớp) trong top 10 của AST, DOC và RAND |
| Nội dung judge thấy | Đầy đủ | Lớp chỉ có dòng khai báo và tên method. Hàm bị cắt ở 1.500 ký tự. Issue bị cắt ở 6.000 ký tự. |

Trên snapshot django `838e432e`, judge chỉ thấy trung bình 431 ký tự code cho mỗi node, trong khi code đầy đủ dài 2.156 ký tự. Retrieval của lượt v2 cũng không lưu chunk doc nào, nên không thể chấm chunk doc nếu không chạy lại.

Cơ chế hash nhãn trong `judge-pool` và `judge-run` đã được **gỡ bỏ**, vì được thêm vào khi người dùng không yêu cầu.

### 6.2 Độ chính xác của graph

- **Cạnh `Documents` có thể nối nhầm.** Index tên chỉ giữ một node cho mỗi tên, và bước nối thử tên trơn trước module của đoạn doc. Trên một graph django (6.448 cạnh), 37% cạnh trỏ tới node có tên trùng với node khác, và 12% cạnh chỉ dựa vào tên ngắn.
- **Bộ nhớ đệm AST và doc trong `build_graph` dùng khóa chỉ gồm nội dung file.** Vì vậy, file trùng nội dung ở chỗ khác, hoặc file đổi chỗ giữa các snapshot, nhận đường dẫn của file gặp trước.
  - Với code, lỗi này gần như không ảnh hưởng. Django chỉ bị ở file không có hàm. Sympy bị 13 lần ở `sympy/testing/tmpfiles.py`. Không gold nào bị ảnh hưởng.
  - Với doc, 13 trên 46 snapshot của sympy có file doc đổi chỗ, ví dụ `doc/src/gotchas.rst`. Chunk của các file này mang đường dẫn cũ.
- **Id trùng** chiếm 0,5% ở django và 0,2% ở sympy, chủ yếu là getter và setter của property. Thiết kế giữ nguyên.
- **Cạnh `Calls`** được phân giải bằng heuristic. Cạnh này chỉ ảnh hưởng tới việc lan phiếu của doc, nên được giữ nguyên.

### 6.3 Thay đổi nằm ngoài hàm và lớp

| | django | sympy |
|---|---|---|
| Dòng đổi nằm trong hàm hoặc lớp | 90,6% | 88,6% |
| Import / gán biến cấp module / lệnh khác cấp module | 4,6% / 1,5% / 0,2% | 3,1% / 2,5% / 1,6% |
| Instance chỉ đổi ngoài hàm và lớp (bị loại) | 2,9% | 4,4% |
| Commit chỉ đổi ở cấp module | 6,5% | 7,4% |

Quyết định là giữ nguyên định nghĩa gold, để không ảnh hưởng tới kết quả cũ. Lớp history ghi các dòng cấp module thành cạnh tới `Module`, nhưng cạnh này chỉ được lưu và không bỏ phiếu.

### 6.4 Git history

**Tài liệu tham khảo**

- KGCompass (2025) xây knowledge graph nối issue, PR, file và hàm. Bài báo chỉ giữ artifact có trước `created_at` của instance, và bộ lọc này loại 24% artifact. Riêng graph, top 15 hàm phủ 40,4% gold ở mức hàm trên SWE-bench Lite. Bài báo không có ablation bỏ issue và PR.
- AmaLgam (Wang & Lo, 2014) kết hợp version history, báo cáo lỗi tương tự và cấu trúc code. Mỗi thành phần đều làm tăng độ chính xác ở mức file.
- HAFix (2025) dùng blame commit để sửa lỗi, nhưng cần biết trước dòng lỗi. Vì vậy HAFix không giúp bước định vị.
- Lingxi (2025) dùng các lần sửa issue trước đây làm tri thức quy trình, và đạt 74,6% trên SWE-bench Verified.
- SWE-bench issue #465 báo rằng agent đã chạy `git log --all` và đọc được bản sửa trong tương lai. Vì vậy lịch sử phải được cắt chặt.

**Phép đo tiềm năng trên django và sympy** (ánh xạ chính xác, mỗi đơn vị là một commit trên nhánh chính, chỉ dùng tổ tiên của snapshot, chỉ giữ commit sửa từ 1 đến 50 hàm hoặc lớp, 10 commit giống issue nhất theo BM25)

| Cửa sổ | django | sympy |
|---|---|---|
| 3 năm | 29,6% (27 hàm) | 25,7% (36 hàm) |
| 5 năm | 35,2% (27 hàm) | 24,9% (36 hàm) |
| Toàn bộ lịch sử đã build | 37,0% (29 hàm) | 24,9% (37 hàm) |
| 10 commit ngẫu nhiên | 2,1% | 3,6% |
| So sánh: B2 của doc | 31,5% | 26,2% |

- Lợi ích đến từ nội dung message, không đến từ việc code mới bị sửa.
- Build history mất 42 phút cho 18.348 đơn vị của django, và 33 phút cho 6.772 đơn vị (PR) của sympy, khi chạy song song trên máy. 80% lượt sửa ánh xạ được sang graph snapshot.

**Mức trùng với AST và với doc** (cửa sổ 5 năm, 10 commit)

| Chỉ số | django | sympy |
|---|---|---|
| Top 10 của AST có gold | 56,5% | 52,5% |
| Tập chứa gold mà top 10 của AST chưa có: chỉ doc / chỉ history / cả hai | 11,2% / 10,4% / 5,6% | 11,7% / 9,3% / 4,9% |
| Trong các instance mà AST trượt top 10: doc chứa gold / history chứa gold / ít nhất một nguồn | 23,0% / 23,2% / 39,5% | 19,0% / 15,5% / 29,3% |
| Hàm của history nằm trong tập doc / trong top 100 của AST | 5,0% / 20,0% | 3,2% / 8,9% |

History mang thông tin mới so với AST, và gần như không trùng với doc. Doc vẫn có phần đóng góp riêng ở khoảng 11% instance mà history không phủ.

## 7. Thực nghiệm v3 (django và sympy)

### 7.1 Câu hỏi

| Câu hỏi | So sánh |
|---|---|
| RQ1 | DOC mới (cạnh đã sửa) so với DOC cũ và so với AST |
| RQ2 | HIST so với AST |
| RQ3 | HIST so với RAND_HIST, để biết lợi ích đến từ nội dung message hay từ việc code mới bị sửa |
| **RQ4** | **DOC+HIST so với HIST, tức đóng góp riêng của doc khi đã có history** |
| RQ5 | DOC+HIST so với DOC |

### 7.2 Kiến trúc graph mới

| Node | Id | Thuộc tính chính |
|---|---|---|
| Module, Class, Function | Như cũ | Như cũ |
| Document, DocChunk | Như cũ | Như cũ |
| **Commit (mới)** | sha | Cha thứ nhất, thời điểm, message (tối đa 2.000 ký tự), có phải merge không, hàm và lớp bị sửa, file có dòng đổi cấp module, embedding của message |

| Cạnh | Thay đổi |
|---|---|
| Defines, Imports, Calls, Inherits, HasChunk, References | Không đổi |
| **Documents** | Mỗi tên được index với mọi node khớp. Bước nối thử tên kèm module của đoạn doc trước. Nếu nhiều node khớp, chỉ giữ node trong module đó. Nếu vẫn mơ hồ, không nối. Trên django `838e432e`, số cạnh giảm từ 6.357 xuống 5.641, và tỷ lệ cạnh đúng module tăng từ 64,8% lên 74,6%. Trên sympy `9bf73cc2`, số cạnh giảm từ 1.616 xuống 1.445, và tỷ lệ đúng module tăng từ 70,5% lên 81,0%. Số gold có cạnh gần như không đổi. |
| **Modifies → Function/Class (mới)** | Tính bằng đúng hàm tính gold, trên diff giữa commit và cha thứ nhất. Đây là cạnh dùng để bỏ phiếu. |
| **Modifies → Module (mới)** | Cho dòng nằm ngoài mọi hàm và lớp. Chỉ được lưu, không bỏ phiếu. |

- **Đơn vị commit** là mỗi commit trên nhánh chính (`git log --first-parent`). Với sympy, mỗi đơn vị là một PR, và message chứa tiêu đề PR.
- **Commit được dùng cho một snapshot** khi là tổ tiên của snapshot (`git rev-list`), nằm trong 5 năm trước snapshot, và sửa từ 1 đến 50 hàm hoặc lớp có trong graph.
- **Cách lưu.** Cạnh `Documents` mới được thay trực tiếp trong file graph, và graph được đánh dấu `doc_links: v2`. Lớp history nằm trong `history/<repo>_history.jsonl` và `history/<repo>_history.emb.npy`, và được nạp khi dựng index. `build_graph` dùng khóa bộ nhớ đệm gồm cả đường dẫn và nội dung file.

### 7.3 Retrieval và các hệ thống

- Mỗi instance lưu thêm các chunk doc mà DOC và RAND đã dùng, 10 chunk đầu khi tìm trên toàn bộ doc (`search_doc_all`, kể cả chunk không có cạnh), đích cạnh `Documents` của từng chunk, và các commit mà HIST và RAND_HIST đã dùng.
- Nguồn history được lưu với k = 5, 10 và 20 commit. Issue tìm commit bằng BM25 kết hợp embedding của message (RRF). Mỗi commit bỏ phiếu cho các hàm mà nó đã sửa, và không lan phiếu.
- Có sáu hệ thống: AST, DOC, RAND, HIST, RAND_HIST và DOC+HIST.
  - DOC giữ cấu hình cũ (`DOC_FIXED = ("rrf", 0.1, 1, "all")`), để so được với kết quả cũ.
  - HIST chọn k, p và h trên dev, so với AST.
  - DOC+HIST giữ nguyên phần DOC, thêm phần HIST, rồi chọn trọng số của HIST và h trên dev, so với AST.
  - RAND và RAND_HIST dùng cùng cấu hình với DOC và HIST.

### 7.4 Judge mới

- Mỗi instance có ba request.
  - **Node code**: hợp top 10 của sáu hệ thống. Judge thấy toàn bộ code của node, kể cả thân lớp, lấy từ git tại snapshot.
  - **Chunk doc**: chunk của DOC, chunk ngẫu nhiên của RAND, và 10 chunk tìm trên toàn bộ doc. Judge thấy toàn văn chunk.
  - **Commit**: các commit của HIST và cùng số commit ngẫu nhiên của RAND_HIST. Judge thấy message và danh sách hàm đã sửa.
- Mỗi loại có thang điểm 0 đến 3 riêng. Judge không thấy patch hay gold, và không biết phần tử đến từ nguồn nào.
- Model là `gemini-3.1-flash-lite`, thinking LOW, dùng Batch API. Nhãn ghi vào `judge_v3/`, và nhãn cũ vẫn ở `judge/`.
- **Chi phí ước tính.** Mỗi request node code dài trung bình khoảng 23.000 token khi chỉ có 3 nguồn (tối đa 41.000). Lớp dài nhất của django là `Query`, khoảng 22.700 token. Tổng cộng khoảng trên 40 triệu token đầu vào, tức gấp khoảng 5 lần lượt v2.

### 7.5 Đánh giá theo sáu tầng (cell `eval-v3`, trên tập test)

1. **Chất lượng bằng chứng.** Success@k, Precision@k, nDCG@k và recall theo pool của chunk và commit, so với RAND và RAND_HIST.
2. **Chất lượng liên kết.** Trong các chunk hoặc commit liên quan, tỷ lệ có cạnh tới code (độ phủ) và tỷ lệ có cạnh tới gold (độ chính xác).
3. **Mức tận dụng khi kết hợp.** Tỷ lệ tận dụng là tỷ lệ instance mà xếp hạng kết hợp đưa gold vào top k, khi tập của nguồn chứa gold nhưng AST chưa có. Tỷ lệ gây hại do chèn là tỷ lệ gold rơi khỏi top k.
4. **Đóng góp của từng nguồn.** Giá trị Shapley: φ_DOC = ½[(M_DOC − M_AST) + (M_DOC+HIST − M_HIST)], kèm khoảng tin cậy bootstrap 95%. Bảng lợi ích riêng gồm chỉ DOC, chỉ HIST và cả hai.
5. **Thông tin mới so với issue.** Mức chênh trong ba nhóm: bằng chứng chỉ tới gold mà issue không nêu tên gold, cả hai cùng nêu, và bằng chứng không chỉ tới gold.
6. **Tổng hợp.** Mức chênh của sáu cặp hệ thống, kèm khoảng tin cậy 95%, tính theo instance và theo repo.

Cell `judge-analysis` có thêm bảng nhóm nguyên nhân theo chunk doc: (1) DOC lấy được chunk liên quan và tập doc chứa gold; (2) DOC lấy được chunk liên quan nhưng cạnh không dẫn tới gold; (3a) chunk liên quan có cạnh nhưng DOC xếp ngoài top 5; (3b) chunk liên quan không có cạnh; (4) không tìm được chunk liên quan.

### 7.6 Các cell của lượt v3

| Cell | Vai trò |
|---|---|
| `DAAopL5Eo6Rz` | `SCALE_REPOS` gồm django và sympy, `SCALE_RESULTS = scale_rows_v3.jsonl`, danh sách 12 repo giữ trong `SCALE_REPOS_ALL` |
| `PqDgRg_1mNuK`, `9df72df0`, `ec3fc119` | Cách nối cạnh mới, khóa bộ nhớ đệm có đường dẫn, `search_doc_all` |
| `v3-md`, **`doc-links-v2`** | Thay cạnh `Documents` của 86 graph. Graph có chunk mang sai đường dẫn được build lại với `force=True`. |
| `scale-setup`, **`hist-build`**, `scale-run` | Lưu chunk, commit và nguồn history; build và nạp history; dựng `hist_index` cho từng snapshot |
| `scale-fusion` | Chọn cấu hình HIST và DOC+HIST, so sáu cặp hệ thống, TRisk, bảng bổ sung lẫn nhau |
| `judge-md`, `judge-config`, `judge-pool`, `judge-run`, `judge-analysis` | Judge mới |
| `eval-md`, **`eval-v3`** | Đánh giá sáu tầng |

### 7.7 Kiểm chứng đã làm trên máy

- Toàn bộ luồng chạy trên 12 instance của django và sympy, với embedding giả và client Gemini giả, nên không gọi API thật. Không có lỗi.
- `doc-links-v2` cho số cạnh trùng với bản kiểm chứng riêng. Nhánh build lại đã được thử bằng một graph có chunk mang đường dẫn sai.
- Chạy lại `scale-run` thì bỏ qua đúng các instance đã có kết quả.
- Định dạng khóa của gold, của đích cạnh chunk và của hàm mà commit sửa đều khớp nhau.
- Không có id commit 8 ký tự nào bị trùng trong history của hai repo.

### 7.8 Chạy trên Kaggle

- Cần bật GPU và Internet. Tài khoản Gemini cần có prepaid credit cho Batch API.
- Code **không tự xóa** graph hay file nào. Graph cũ được dùng lại qua cache, và đó là điều mong muốn. Cạnh mới được áp bằng cách sửa tại chỗ trong `doc-links-v2`. Lớp history, index và kết quả mới không phụ thuộc vào cache của graph.
- Thời gian ước tính: `doc-links-v2` khoảng 1 giờ, `hist-build` khoảng 1,5 giờ, `scale-run` vài giờ, và batch judge thường vài giờ, tối đa 24 giờ. Kaggle giới hạn 12 giờ mỗi lần chạy.
- Đề xuất chạy hai lượt. Lượt 1 chạy từ đầu tới `judge-pool`, rồi Save Version. Lượt 2 chạy `judge-run`, `judge-analysis`, `eval-v3` và Section 7.
- **Rủi ro trả tiền judge hai lần.** `judge-run` chờ batch ngay trong cell. Nếu session dừng giữa chừng, chạy lại `judge-run` sẽ gửi batch mới. Khi đó cần dùng `collect_batch(JUDGE_MODEL, "<tên job>")`, với tên job lấy từ `judge_v3/batch_jobs.txt`.
- **Dung lượng.** 86 graph của hai repo chiếm khoảng 9 GB. File mới của lượt v3 ước tính dưới 1 GB. Graph của 10 repo còn lại vẫn nằm trên đĩa.

## 8. Kết luận hiện tại

- **Đã đủ bằng chứng theo gold.** Trên 12 repo, doc có Hit@10 tốt hơn AST ở mức tổng thể, và tốt hơn chunk ngẫu nhiên. Tuy vậy, phần dương tập trung ở Django, và hạng của gold tụt ở nhiều instance hơn số instance lên hạng.
- **Chưa còn bằng chứng theo judge.** Mọi kết luận theo judge của lượt v2 phải chờ lượt v3 chấm lại với judge đúng yêu cầu.
- **Git history** có tín hiệu định vị ngang doc, và gần như không trùng với doc. Đây mới là phép đo tiềm năng theo gold. Tác động thật lên xếp hạng phải chờ lượt v3.

## 9. Việc đang chờ quyết định

1. Có build sẵn hai file history trên máy để tải lên Kaggle hay không. Nếu có, đặt `HIST_INPUT` trỏ tới thư mục của dataset.
2. Có sửa `judge-run` để khi chạy lại thì tự lấy kết quả của batch đang chờ, thay vì gửi batch mới, hay không.
3. Có thêm cell dọn graph của 10 repo không dùng hay không, nếu thiếu dung lượng.
4. Có xóa 86 graph để build lại từ đầu hay không. Việc này mất khoảng 1 đến 1,5 giờ, và không bắt buộc.

## 10. Notebook và môi trường

- `WORK_DIR` là `/kaggle/working`, được lưu khi Save Version. `REPO_DIR` là `/tmp/repos`, không được lưu.
- `judge-config` chứa API key dạng biến thường `GOOGLE_API_KEY`. Không commit hay push notebook khi biến này còn key.
- Gemini API trên project có billing cần prepaid credit. Batch API rẻ hơn 50%.
- File kết quả: `scale_rows_v2.jsonl` và `judge/` (lượt v2); `scale_rows_v3.jsonl`, `history/` và `judge_v3/` (lượt v3).

## 11. Lịch sử các quyết định chính

1. Thí nghiệm đầu tiên chạy trên SWE-bench Lite. Số instance quá nhỏ để kết luận.
2. Thí nghiệm được mở rộng lên 12 repo của SWE-bench đầy đủ, với graph snapshot build tại commit sớm nhất trong mỗi khoảng 60 ngày.
3. LLM judge được thêm vào, vì gold phạt các node liên quan nhưng không bị sửa.
4. Section 7 phân tích khi nào doc giúp, và thử cổng. Cổng không sửa được các repo âm.
5. Hướng nối tên đăng ký bằng chuỗi cho sphinx và pylint bị bỏ.
6. Git history được chọn làm nguồn mới, trước issue, vì nhanh và tiện hơn. Thực nghiệm giới hạn ở django và sympy.
7. Judge của lượt v2 được xác định là sai yêu cầu. Judge mới chấm cả chunk doc và commit, với nội dung đầy đủ. Cơ chế hash nhãn bị gỡ bỏ.
8. Thay đổi ngoài hàm và lớp được giữ như gold. Lớp history chỉ lưu cạnh tới `Module`, không dùng để bỏ phiếu.
9. Đánh giá sáu tầng được thêm vào, để đo từng bước trong chuỗi của mỗi nguồn.
