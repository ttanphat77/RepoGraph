# Bối cảnh nghiên cứu RepoGraph

File này được cập nhật ngày 2026-10-28. File tóm tắt toàn bộ trạng thái nghiên cứu hiện tại.
Notebook chính là `colab/build_graph_flask_colab.ipynb`. Notebook được chạy trên Kaggle.
Kết quả chi tiết của từng lượt chạy được ghi ở `experiment_log.md`, để so giữa các lượt.

Có hai lượt thực nghiệm đã chạy xong và một lượt đang chạy:

- **Lượt v2** chạy trên 12 repo của SWE-bench. Kết quả nằm trong `scale_rows_v2.jsonl` và thư mục `judge/`.
- **Lượt v3** chạy trên django và sympy, có thêm lớp git history và judge mới. Lượt này **đã chạy xong trên Kaggle**. Kết quả nằm ở mục 7.9. Các vấn đề phát hiện sau lượt này nằm ở mục 7.10.
- **Lượt v4** đang chạy. Lượt 1 trên Kaggle đã xong ngày 16/10/2026, và kết quả nằm ở mục 9.1. Lượt đầy đủ đầu tiên (v4-L4) xong ngày 22/10/2026, với đủ bốn nguồn, bước trộn và judge bằng chứng. Kết quả nằm ở mục 9.5.
- **Định hướng đề tài** sau buổi thảo luận ngày 18/10/2026 nằm ở mục 12.
- **Bộ độ đo và phương pháp đánh giá** (21/10/2026) nằm ở mục 13.

---

## 1. Câu hỏi nghiên cứu

Đề tài muốn chứng minh rằng **dữ liệu đa nguồn** hiệu quả hơn **chỉ dùng source code** trong việc định vị code cho một issue. Dữ liệu đa nguồn gồm source code, tài liệu của dự án và git history. Mốc chỉ dùng code là xếp hạng AST.

- Các nguồn của dữ liệu đa nguồn: source code (AST), tài liệu (DOC), git history (HIST) và **issue cũ đã đóng (ISSUE)**. ISSUE được hoãn sau history vì history nhanh và tiện hơn; ISSUE được đưa vào v4.
- Mọi kết quả đều được so với AST. Mỗi nguồn được đo bằng tác động của nó khi thêm vào AST. Mục tiêu chính không phải tìm nguồn nào mạnh nhất. Tuy vậy, các nguồn vẫn được so với nhau, để thống kê và để điều chỉnh phương pháp.
- Các câu hỏi kiểm chứng như sau. Doc + history có hiệu quả hơn chỉ dùng doc không? Doc + history có hiệu quả hơn AST thuần không? Bao nhiêu phần trăm instance được history tác động dương, so với doc?
- **Hình mẫu để thiết kế luồng history (không phải mục tiêu của đề tài).** Luồng history được thiết kế theo cách một developer debug. Developer tìm file liên quan, rồi tìm các commit cũ đã sửa file đó. Sau đó developer đọc title, message và cách file được sửa, suy ra ý đồ của từng commit, rồi suy ra nguyên nhân lỗi. Hình mẫu này chỉ dùng để xác định input, cách xử lý và output của luồng. Mục tiêu của đề tài vẫn là so dữ liệu đa nguồn với AST.
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
- Đây là phân tích dữ liệu, không phải xây benchmark. Vì vậy đề tài không chia dev và test, không dùng nhiều judge và không gán nhãn thủ công. Kế hoạch phân tích của v4 được viết trước khi xem kết quả, và phương pháp đã chốt không đổi chỉ vì kết quả xấu (mục 6.9 của `planning.md`). Đề tài cũng không chia dữ liệu thành tập dùng để chọn và tập dùng để xác nhận (quyết định 58).
- **Yêu cầu về judge.** Judge phải chấm **mọi node** của kết quả truy xuất, kể cả node document, và phải nhận nội dung đầy đủ. Lý do là chỉ chấm hàm và lớp thì không đánh giá được bản thân document. Từ ngày 26/10/2026, yêu cầu này được thu hẹp: judge chỉ chấm bằng chứng, gồm chunk doc, hunk và báo cáo cũ. Node code được đánh giá bằng gold và độ đo theo cấu trúc (quyết định 52 và 53).
- **LLM chỉ là judge.** Không nguồn nào dùng LLM để tạo xếp hạng. LLM chỉ chấm kết quả truy hồi.
- **Commit phải được đọc cùng diff.** Chỉ đưa message mà không có diff thì không đánh giá được gì. Message có giá trị khi đi kèm diff.
- **Phạm vi so sánh.** V4 so 8 hệ thống, gồm AST, +DOC, +HIST, +ISSUE, +ALL và ba hệ thống bỏ bớt một nguồn (mục 6.1 của `planning.md`). Ba hệ thống bỏ bớt một nguồn chỉ tốn bước trộn. Trước mắt, thực nghiệm tập trung vào HIST.
- **Quyết định kỹ thuật phải có bài báo làm cơ sở.** Mỗi quyết định về graph, hop, lọc node, prompt, cách trộn, judge và độ đo phải dẫn được bài báo tương tự. Số đo của đề tài chỉ dùng để bổ sung, ví dụ để chọn một giá trị trong khoảng mà các bài đã dùng. Báo cáo đọc bài báo nằm ở artifact "Tổng quan tài liệu RepoGraph" (https://claude.ai/artifact/DSWQi3W5KrFzSFPLKynKcL).

## 3. Dữ liệu

| Repo | Tổng | Được dùng | Thuộc Lite | Không thuộc Lite | Số graph snapshot |
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
- Ở v2 và v3, các instance thuộc SWE-bench Lite là tập dev, chỉ dùng để chọn cấu hình. Phần còn lại là tập test. Từ v4, đề tài không chia dev và test, và mọi kết quả dùng cả 1.186 instance.

## 4. Phương pháp chung

### 4.1 Graph

- Code được phân tích bằng tree-sitter. Graph có các node Module, Class và Function, cùng các cạnh `Defines`, `Imports`, `Calls` và `Inherits`.
- Doc được đọc từ thư mục doc đầu tiên tồn tại (`docs`, `doc`, ...). Mỗi file doc là một node `Document`. Mỗi đoạn theo heading là một node `DocChunk`, nối với `Document` bằng cạnh `HasChunk`.
- Cạnh `Documents` nối `DocChunk` với Function hoặc Class. Cạnh này chỉ được tạo từ tên đối tượng Python, qua các role `:func:`, `:meth:`, `:class:`, ... và các directive `autoclass`, `.. method::`, ...
- Cạnh `References` nối doc với doc, qua role `:doc:`.
- Graph được ghi bằng orjson thành file `.json`, kèm file tóm tắt `.summary.json`. Graph không được nén.
- Id của node có dạng `{snap8}:{đường dẫn}:{tên lồng nhau}`.

### 4.2 Snapshot và gold

- Mỗi phiên bản SWE-bench được chia thành các khoảng 60 ngày. Mỗi khoảng có một graph, build tại base commit sớm nhất trong khoảng.
  - **Snapshot là phép xấp xỉ để giảm chi phí.** Build graph tại đúng base commit của từng instance cũng không làm bản sửa lọt vào graph. Việc chọn base commit **sớm nhất** trong khoảng mới là điều đảm bảo không instance nào trong khoảng thấy bản sửa của instance khác.
  - **Hệ quả.** Truy hồi chạy trên code và doc cũ hơn trạng thái của issue tới 60 ngày. Trên tập test, 16 instance mất một phần gold (27 gold node, vì hàm được tạo hoặc đổi tên sau snapshot). History của HIST chỉ gồm commit là tổ tiên của **snapshot**, nên mất tới 60 ngày history gần nhất trước base commit. Có 1.045 instance test ban đầu, chỉ 1.006 được đánh giá.
- Gold được tính tại đúng base commit của từng instance, bằng `git show` và tree-sitter (`_file_nodes_at` rồi `get_oracle`). Sau đó gold được ánh xạ sang id của graph snapshot.
- Mỗi dòng bị đổi được gán cho hàm hoặc lớp nhỏ nhất chứa nó. Dòng ở cấp module bị bỏ qua nếu file có đổi hàm. Nếu cả file chỉ đổi ở cấp module, gold là node `Module`, và instance bị loại vì ứng viên chỉ là Function và Class.
- Kết quả kiểm tra như sau. 99% gold khớp. BM25 cho kết quả giống hệt ở 113/113 instance.
- **Lỗi đã biết của oracle (đang sửa ở việc 1.1).** (1) Dòng thêm mới được gán cho dòng cũ đứng ngay trước, nên hàm mới chèn giữa hai hàm có thể bị gán cho hàm phía trước. (2) Khi file bị đổi tên, `unidiff` trả đường dẫn **sau** khi đổi, nhưng file được đọc tại base commit, nơi chỉ có đường dẫn cũ. (3) Decorator không thuộc khoảng dòng của hàm, nên thay đổi chỉ ở decorator bị gán cho lớp hoặc Module. Cùng hàm `get_oracle` được dùng để tính cạnh "commit đã sửa hàm nào" của history, nên lỗi ảnh hưởng cả nhãn lẫn đặc trưng của HIST.

### 4.3 Xếp hạng và nguồn doc

- **AST** là hệ thống gốc. Mô tả chính xác: BM25 lập chỉ mục **mọi node không phải doc, kể cả Module**. Embedding dùng bge-small. Hai xếp hạng được gộp bằng RRF, rồi mới lọc lấy Function và Class. Source của node bị cắt ở 8.000 ký tự cho BM25 và 2.000 ký tự cho embedding. Xếp hạng AST được tính tới hạng 500 (`EXP_DEEP`), nhưng chỉ 100 id đầu được lưu (`SCALE_TOPK`).
- **Nguồn `vote_ast`.** Issue tìm ra 5 chunk có cạnh `Documents`. Mỗi chunk bỏ phiếu cho các node mà nó nối tới. Phiếu lan một bước theo mọi cạnh AST chiều xuôi (`Calls`, `Inherits`, `Defines`, `Imports`) với hệ số 0,5, trừ node có hơn 20 hàng xóm. Vì vậy chunk nối tới một class cũng cho phiếu tới các method của class đó, qua cạnh `Defines`. Tập doc được sắp theo hạng AST. Vì vậy DOC (và HIST của v3) thực chất là **ứng viên AST được bằng chứng chọn lọc**: bằng chứng quyết định node nào được đẩy lên, còn thứ tự bên trong tập vẫn theo AST.
- **Nguồn `random_ast`** dùng cùng quy trình, nhưng chọn chunk ngẫu nhiên. Đây là nguồn đối chứng.
- **Kết hợp** bằng RRF: điểm của node là 1/(k + r_AST) + p/(k + r_doc), với tham số h giữ nguyên h vị trí đầu của AST. Cấu hình chọn trên dev của lượt v2 là `rrf`, `p = 0.1`, `h = 1`, `filter = all`.

### 4.4 Đánh giá theo gold

- Các chỉ số gồm Hit@k ở mức hàm, lớp và file (k = 1, 5, 10, 20, 40), và reciprocal rank (RR).
- **Hit@k là any-gold:** bằng 1 khi **ít nhất một** gold nằm trong top k. RR dùng gold có hạng tốt nhất.
- **RR của v3 thực chất là RR@100:** danh sách sau khi trộn bị cắt ở 100 (`LIST_K`), gold ngoài 100 có RR = 0. Giới hạn sai số so với RR đầy đủ là khoảng 164/(1.006 × 101) ≈ 0,0016.
- **Kiểm định.** Ở v2 (`compare_ranks`), cột hiển thị MRR nhưng Wilcoxon chạy trên log(hạng), với gold không tìm thấy gán hạng 1.000. Holm được áp trong từng repo ở các bảng của `scale-analysis` và `scale-fusion`. Ở `verify-v3`, Holm **không** được áp. Hit@10 kết luận theo p < 0,05 thô, còn nDCG và RR kết luận theo khoảng tin cậy bootstrap.
- Các kiểm định coi từng instance là độc lập, trong khi nhiều instance dùng chung repo, snapshot, doc và history. Vì vậy khoảng tin cậy có thể hẹp hơn thực tế, và hai repo không đủ để khái quát cho repository nói chung.
- Rủi ro theo repo dùng URisk và TRisk (Dinçer và cộng sự, 2014). TRisk < −2 nghĩa là kém hơn AST có ý nghĩa.

## 5. Kết quả lượt v2 (12 repo)

### 5.1 Theo gold (còn hiệu lực)

Các kết quả dưới đây đo trên tập test gồm 1.924 instance.

- DOC có Hit@10 tốt hơn AST ở 27 instance và kém hơn ở 10 instance (p = 0,008).
  - Django chiếm 18 instance tốt hơn và 3 instance kém hơn.
  - Nếu bỏ Django, còn 9 instance tốt hơn và 7 instance kém hơn (p = 0,80).
- Hạng của gold tăng ở 222 instance và giảm ở 366 instance. Phép so sánh này dùng log(hạng), không phải RR.
- Kết quả gold của v2 hợp lệ cho hệ thống v2 đã chạy (linker và cache cũ). Hiệu quả của hệ thống sau khi sửa linker và cache chưa được kiểm chứng trên 12 repo.
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

**Đối chiếu với các câu hỏi đã báo cáo ở mục 7.9 (Q1 đến Q5)**

| Thiết kế | Báo cáo | Ghi chú |
|---|---|---|
| RQ1 | Q1 (DOC so với AST) | Phần "DOC mới so với DOC cũ" **chưa được làm** |
| RQ2 | Q2 (HIST so với AST) | Khớp |
| RQ3 | Không có trong Q1–Q5 | HIST so với RAND_HIST có output trong `scale-fusion` và `judge-analysis`, nhưng không đưa vào phần chính |
| (mới) | Q3 (DOC+HIST so với AST) | Thêm khi chuyển trọng tâm sang "đa nguồn so với AST" |
| RQ4 | Q5 (DOC+HIST so với HIST) | Đổi số thứ tự |
| RQ5 | Q4 (DOC+HIST so với DOC) | Đổi số thứ tự |

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
| **`hist-all`** | Tìm 10 commit trên toàn bộ history, không qua bộ lọc, rồi ghi lý do commit bị loại. Judge chấm thêm các commit này qua request `#histall`. |
| `verify-md`, **`verify-v3`** | Trả lời các câu hỏi kiểm chứng Q1 đến Q5 so với AST. Gồm tỷ lệ tác động, độ khó, độ nhạy theo cấu hình, tách theo issue có nêu tên gold, ví dụ, và độ phủ của cạnh tới gold. |

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
- **Batch theo số instance.** Tier 1 giới hạn 10 triệu token đang xếp hàng. Lượt đầu bị lỗi 429 vì một batch khoảng 28 triệu token. `judge-run` giờ chia request thành nhiều phần, mỗi phần gồm mọi request của 150 instance (`JUDGE_BATCH_INSTANCES`). Các phần được gửi lần lượt.
- **Chạy lại không trả tiền hai lần.** Tên và job của mỗi phần được ghi vào `judge_v3/batch_jobs.txt`. Khi chạy lại, cell chờ và lấy kết quả của batch đã gửi. Request đã có nhãn trong `labels_<model>.jsonl` không bị gửi lại. Hai file này nằm trong `/kaggle/working`. Thư mục này vẫn còn khi mở phiên Kaggle mới (`experiment_log.md`, các lượt ngày 27/10 và 28/10), nên lần chạy ở phiên sau cũng không gửi lại.
- **Dung lượng.** 86 graph của hai repo chiếm khoảng 9 GB. File mới của lượt v3 ước tính dưới 1 GB. Graph của 10 repo còn lại vẫn nằm trên đĩa.

### 7.9 Kết quả v3 (tập test, 1.006 instance, gộp hai repo; thực nghiệm khám phá)

Bốn hệ thống được so sánh:
- AST chỉ dùng code.
- DOC là code + doc.
- HIST là code + history.
- DOC+HIST là cả ba nguồn.

Có ba độ đo chính:
- nDCG@10 theo judge, chấm node code từ 0 đến 3.
- Hit@10 theo gold (any-gold), là tỷ lệ instance có **ít nhất một** hàm bị sửa nằm trong top 10.
- RR@100 theo gold, bằng 1 chia hạng của gold tốt nhất, và bằng 0 khi gold nằm ngoài hạng 100.
- nDCG@10 theo judge đo mức **liên quan**, không đo mức hữu ích cho việc sửa.

**Câu hỏi kiểm chứng**

| Câu hỏi | Δ nDCG@10 (judge) | Δ Hit@10 (gold), số instance tốt hơn / kém hơn | Δ RR@100 (gold) |
|---|---|---|---|
| Q1. DOC so với AST | +0,019 | +2,0 điểm %, 23 / 3 | +0,004, chưa có ý nghĩa |
| Q2. HIST so với AST | +0,022 | +4,0 điểm %, 59 / 19 | +0,009 |
| Q3. DOC+HIST so với AST | +0,036 | +5,2 điểm %, 71 / 19 | +0,010 |
| Q4. DOC+HIST so với DOC | +0,017 | +3,2 điểm %, 52 / 20 | +0,007 |
| Q5. DOC+HIST so với HIST | +0,014 | +1,2 điểm %, 15 / 3 | +0,002 |

- **Mức ý nghĩa sau hiệu chỉnh Holm.** Holm được tính lại từ các p đã lưu trong output, trên 5 câu hỏi, riêng cho từng độ đo và từng phạm vi. Cell `verify-v3` chưa áp Holm; việc này sửa ở việc 1.2.
  - **Gộp hai repo:** Hit@10 có ý nghĩa ở cả Q1 đến Q5. RR@100 có ý nghĩa ở Q2, Q3 và Q4, không có ở Q1 và Q5 (Q5: p = 0,0263, sau Holm 0,0526). ΔnDCG@10 có khoảng tin cậy bootstrap dương ở cả 5 câu (Wilcoxon p ≤ 0,0001).
  - **Django:** Hit@10 có ý nghĩa ở Q1 đến Q4. RR@100 có ý nghĩa ở Q2, Q3 và Q4. Q5 không có ý nghĩa ở cả hai độ đo.
  - **SymPy:** Không câu nào có Hit@10 hay RR@100 có ý nghĩa sau Holm (Q3: Hit@10 p = 0,0118, sau Holm 0,059; RR@100 p = 0,0221, sau Holm 0,1105). ΔnDCG@10 có khoảng tin cậy dương ở cả 5 câu, nhưng Wilcoxon của Q4 có p = 0,13.
- **Kết luận hẹp đứng vững:** Hit@10 any-gold tăng từ 57,3% (AST) lên 62,4% (DOC+HIST). Kết luận này chỉ nói về việc ít nhất một gold nằm trong top 10, không nói về việc định vị đủ mọi gold.

**Tỷ lệ instance được tác động**

| | DOC | HIST | DOC+HIST |
|---|---|---|---|
| Judge chấm tốt hơn / kém hơn AST | 38,4% / 27,1% | 43,1% / 35,1% | 53,2% / 32,2% |
| Đưa gold vào top 10 khi AST trượt (430 instance) | 5,3% (23) | 13,7% (59) | 16,5% (71) |
| Làm gold rơi khỏi top 10 khi AST đã có (576 instance) | 0,5% | 3,3% | 3,3% |

- Hai nguồn bổ sung cho nhau. Trong các instance mà AST trượt, 2,8% chỉ được doc cứu, 11,2% chỉ được history cứu, và 2,6% được cả hai cứu. Tổng là 16,6%, gần bằng 16,5% của DOC+HIST.
- **Theo độ khó.** Với gold ở hạng 11 đến 100 của AST (266 instance), DOC, HIST và DOC+HIST đưa gold vào top 10 ở 8,7%, 22,2% và 26,7% số instance. Với gold ngoài hạng 100 (164 instance), không hệ thống nào đưa được. Nguyên nhân nằm ở công thức RRF. Ở trường hợp tốt nhất, DOC với p = 0,1 chỉ kéo được node có hạng AST tới 19. HIST với p = 0,25 kéo được tới hạng 38, và DOC+HIST tới hạng 56.
- **Theo loại issue** (Δ nDCG@10). Khi issue không nêu tên gold, DOC tăng +0,016, HIST +0,031 và DOC+HIST +0,043. Khi issue nêu tên gold, DOC tăng +0,022, HIST +0,013 và DOC+HIST +0,028. History mạnh khi issue không nêu tên code, còn doc mạnh khi issue có nêu.
- **Độ bền và rủi ro.** Mọi cấu hình kết hợp đều tăng Hit@10 trên test. TRisk theo gold (tập test, α = 1, tính trên RR@100): DOC+HIST đạt 3,12 ở django và 1,94 ở sympy; DOC ở django có −2,03. TRisk theo judge của DOC+HIST là 3,07 (django) và 3,64 (sympy), nhưng **hai số này tính trên mọi instance có nhãn (dev và test)**, không phải riêng tập test; sẽ tính lại ở việc 1.2. Với α = 5, mọi hệ thống đều âm, vì có nhiều thay đổi xấu nhỏ.
- **So sánh doc và history (chỉ mang tính mô tả, không dùng để kết luận nguồn nào tốt hơn).** Hai luồng có cấu hình và độ phủ khác nhau: DOC dùng p = 0,1, h = 1 giữ từ v2, còn HIST dùng p = 0,25, h = 3 chọn trên dev. Ở cùng cấu hình, Δ Hit@10 của DOC là 3,0 điểm %, của HIST là 4,0 điểm %. Gold bị một commit dùng được sửa ở 87% (django) và 85% (sympy) instance, còn gold có cạnh Documents chỉ ở 28% và 43%. Mục tiêu của đề tài là đo tác động khi thêm từng nguồn vào AST, nên các số này chỉ mô tả hai luồng xử lý cụ thể.
- **Bộ lọc của history (`hist-all`).** `hist-all` tìm trong **phạm vi history đã build** (từ snapshot sớm nhất lùi 5 năm), không phải toàn bộ lịch sử repo. Chỉ 32% (django) và 48% (sympy) commit tìm được qua bộ lọc. Phần đánh giá mức liên quan của các commit này dựa trên nhãn judge không có diff, nên không dùng được.
- **Lưu ý.** Các số dựa trên nhãn commit của judge không dùng được, vì judge chỉ thấy message (mục 7.10). Các số đó gồm tỷ lệ commit liên quan, nhóm nguyên nhân của history và bảng `hist-all`.

### 7.10 Các vấn đề phát hiện sau v3

- **Judge chấm mức liên quan, không chấm mức hữu ích.** Chỉ 33% (django) và 29% (sympy) commit được chấm liên quan thật sự sửa gold. Với chunk doc, tỷ lệ này là 15% và 24%. Ví dụ ở django-9703, ba commit cùng khu vực management command được chấm 2, nhưng không commit nào sửa gold, và gold còn tụt khỏi top 10.
- **Judge chỉ thấy message của commit.** `build_history` có tính diff, nhưng chỉ dùng diff để tìm hàm bị sửa, rồi bỏ diff đi. Vì vậy nhãn commit của v3 không dùng được.
- **Input không cân bằng.** Commit kèm tên hàm đã sửa, nhưng chunk doc không kèm node mà nó nối tới. Thang điểm của doc và của commit cũng đo hai thứ khác nhau.
- **JSON schema đặt điểm trước lý do**, nên lý do được viết sau để biện minh cho điểm.
- **Nhiều gold.** Có 45% (django) và 54% (sympy) instance test có hơn một hàm gold, trung bình 2,4 và 3,9 hàm. Hit@10 của AST là 58,2% và 54,9%, nhưng Acc@10 (mọi gold nằm trong top 10, độ đo của LocAgent và SweRank) chỉ là 34,5% và 25,6%.
- **Hai cell `doc-profile` và `doc-gate`** viết cho 12 repo, nên output không có ý nghĩa với 2 repo.

**Phát hiện từ bản đánh giá độc lập (14/10/2026), đã kiểm chứng trên code**

- `verify-v3` không áp Holm (đã ghi ở 7.9). RR là RR@100. Hit@10 là any-gold.
- Snapshot là phép xấp xỉ: mất một phần gold và tới 60 ngày history gần nhất (mục 4.2).
- Oracle có ba lỗi (dòng thêm mới, đổi tên file, decorator), dùng chung cho gold và cạnh history (mục 4.2). Lỗi dùng chung có thể làm HIST trông tốt hơn thực tế.
- TRisk theo judge tính trên dev và test. `hist-all` chỉ trong phạm vi history đã build.
- Baseline AST khác với mô tả cũ (mục 4.3). DOC và HIST của v3 là ứng viên AST được bằng chứng chọn lọc.
- DOC và HIST được tinh chỉnh không cân bằng. Câu hỏi nghiên cứu ở thiết kế và ở kết quả không khớp (mục 7.1).
- Kiểm định của v2 chạy trên log(hạng) (mục 4.4).
- Kiểm định coi từng instance là độc lập. Hai repo không đủ để khái quát.
- Không chứng minh được artifact (graph, history, nhãn judge) được tạo bởi đúng code hiện tại: cache chỉ kiểm tra tên schema, sự tồn tại của file hoặc số dòng; khóa nhãn judge không có hash của input.
- Bước 0 của v4 đã chọn F, m, C trên tập test (rò rỉ); phải chọn lại trên dev. Kiến trúc v4 được thiết kế sau khi xem kết quả test của v3, nên v4 trên cùng 1.006 instance là **thực nghiệm khám phá**.

## 8. Kết luận hiện tại

- **Kết luận về xếp hạng (lượt v4-L8, 28/10/2026).** Lượt này chạy trên cả 12 repo của tập test SWE-bench, và đánh giá 2.214 instance có gold. Cách trộn là RRF gốc với trọng số bằng nhau và k = 60, nên không tham số nào được chọn trên dữ liệu (quyết định 57). "Có ý nghĩa" ở đây là có ý nghĩa sau hiệu chỉnh Holm. Chi tiết ở mục 10 của `experiment_log.md`.
  - Thêm HIST giúp định vị tốt hơn chỉ dùng code ở mọi độ đo. So với AST, +HIST tăng Top@1 từ 22,4% lên 26,4%, Top@10 từ 54,2% lên 59,3%, MRR từ 0,331 lên 0,375 và MAP từ 0,247 lên 0,283. Mọi mức tăng đều có ý nghĩa. ΔMRR của +HIST dương ở cả 12 repo. Thêm HIST vào DOC và ISSUE cũng tốt hơn có ý nghĩa ở mọi độ đo. +HIST là hệ thống tốt nhất ở Top@1, Top@5 và MRR.
  - Đủ bốn nguồn (+ALL) không tốt hơn AST. Top@10 chỉ tăng từ 54,2% lên 55,6%, và mức tăng này không có ý nghĩa. Top@1 giảm còn 18,5%, MRR giảm còn 0,306 và MAP giảm còn 0,228, đều có ý nghĩa. Ở mức file, +ALL kém AST có ý nghĩa ở Top@1, Acc@1, Acc@3, MRR và MAP.
  - Ở lượt v4-L7 trên Django và SymPy, +ALL tốt hơn AST có ý nghĩa ở Top@10 (55,5% lên 59,6%). Kết luận này không còn đúng khi chạy đủ 12 repo.
  - DOC và ISSUE đứng riêng làm kết quả kém hơn AST có ý nghĩa ở mọi độ đo. Top@10 của +DOC là 39,5%, và của +ISSUE là 44,4%. Khi đã có HIST và ISSUE, thêm DOC làm Top@1 giảm 1,6 điểm, có ý nghĩa. Khi đã có DOC và HIST, thêm ISSUE làm Top@10 giảm 1,9 điểm và Acc@10 giảm 3,1 điểm, có ý nghĩa.
  - Nguyên nhân là danh sách của DOC và ISSUE yếu hơn danh sách của AST nhiều, nhưng RRF gốc cho mọi danh sách lá phiếu ngang nhau. Bài của Cormack không thử trường hợp này. Phân tích chi tiết của judge cho thấy cơ chế. Danh sách của một nguồn chỉ giúp khi bằng chứng của nguồn đó dẫn tới gold. Khi bằng chứng không dẫn tới gold, danh sách đẩy các hàm/lớp khác gold lên trên.
  - +ALL giúp ở ca khó và gây hại ở ca dễ. Khi gold đã ở top 10 của AST, +ALL làm 50,9% instance kém hơn. Khi gold ở hạng 11 đến 100, +ALL làm 67,7% instance tốt hơn.
  - Trong HIST, CE (khớp tên code) đóng góp nhiều nhất, và Fix không thêm gì. CE chỉ giúp khi issue nêu tên gold.
  - Số node phải đọc của +ALL và của +HIST không khác AST có ý nghĩa. Thêm HIST vào DOC và ISSUE giảm số node phải đọc có ý nghĩa ở mọi k.
  - Kết luận này gắn với cách trộn đã chốt, trên 12 repo của tập test.
- **Vai trò của graph trong kết quả hiện tại.** Từ lượt v4-L8, DOC và GRAPH đi trên cạnh của graph theo công thức của KGCompass (quyết định 59). DOC (`doc_kgc`) đi từ đích cạnh `Documents` của 10 chunk trong `doc_cand`. GRAPH đi từ 10 node đầu của AST theo cạnh code. HIST và ISSUE là tìm kiếm văn bản rồi nối kết quả với hàm/lớp theo id, nên không đi trên graph. Commit và issue cũ vẫn nằm ở file riêng, chưa thành node của graph (mục 9.3 và 9.4).
  - GRAPH đứng riêng không đạt tiêu chí đặt trước (G1). +GRAPH kém AST có ý nghĩa ở Top@1, Top@5, Acc@5, MRR và MAP.
  - Thêm GRAPH vào +ALL tốt hơn có ý nghĩa ở mọi độ đo (G2). +ALL+GRAPH có Top@10 cao nhất (60,0%), nhưng vẫn kém +HIST ở Top@1, MRR và MAP. Có một giả thuyết chưa được kiểm tra. GRAPH đi từ 10 node đầu của AST, nên thêm GRAPH có thể chỉ trả lại phần lá phiếu của AST mà DOC và ISSUE đã làm loãng.
  - DOC theo KGCompass vẫn kém AST có ý nghĩa ở mọi độ đo (Q1). Với cách trộn có trọng số trước đây, trọng số của DOC luôn ở mức nhỏ nhất của lưới.
  - Độ đo độ sâu vốn có lợi cho DOC ở độ sâu 1. Dù vậy, DOC không đưa top 10 lại gần gold hơn AST (8,8% so với 10,3% node ở độ sâu 1).
  - Ảnh hưởng của độ phủ doc được đo ở mức repo và mức instance (quyết định 60, mục 13.6). Độ phủ doc của repo không liên quan tới hiệu quả của +DOC (C1). Ở mức instance, việc gold có cạnh `Documents` quyết định hiệu quả của DOC (C2, Holm 0,0002). Khi gold có doc, MRR của +DOC giảm 0,039 so với AST. Khi gold không có doc, MRR giảm 0,162. Đối chứng âm +HIST không khác giữa hai nhóm. Chỉ 27,6% instance có gold có doc.
  - Như vậy việc cạnh `Documents` có tới gold hay không là một nguyên nhân chính làm DOC kém. Trung bình theo instance, cạnh này chỉ phủ 10,7% hàm/lớp của snapshot.
  - Phần tăng chắc chắn của đa nguồn vẫn đến từ tìm kiếm trên history.
- **Bằng chứng theo judge (lượt v4-L8).** Judge xem bản vá thật và chấm từng phần tử bằng chứng. Chi tiết ở mục 10 của `experiment_log.md`, gồm cả phần phân tích chi tiết của judge.
  - Tỷ lệ instance có ít nhất một phần tử hữu ích trong 10 phần tử đầu là 37,8% với DOC, 68,7% với HIST và 73,7% với ISSUE. Ở lượt v4-L6 trên hai repo, các tỷ lệ này là 46,2%, 74,1% và 77,7%.
  - Mỗi nguồn cho một loại thông tin riêng. DOC chủ yếu cho hành vi mong đợi và cách dùng API. HIST cho vị trí code và thay đổi trước đây. ISSUE cho vị trí code, lỗi tương tự và nguyên nhân lỗi.
  - Phần tử hữu ích tập trung ở đầu danh sách. Ở cả ba nguồn, tỷ lệ hữu ích giảm dần theo vị trí trong pool.
  - Khi chấm lại cùng phần tử với thứ tự xáo khác, κ của nhãn hữu ích là 0,610 với DOC, 0,656 với HIST, 0,634 với ISSUE và 0,646 khi gộp. Mẫu chấm lặp gồm 130 instance của mọi repo.
  - Nhãn hữu ích nhất quán với việc phần tử nối tới gold, vì tỷ lệ phần tử nối gold tăng theo điểm hữu ích. Tuy vậy, phần lớn phần tử hữu ích không nối tới gold. Tỷ lệ không nối là 77,1% với DOC, 62,3% với HIST và 67,1% với ISSUE.
  - Trộn chỉ giúp khi bằng chứng hữu ích nối tới gold. Ở nhóm instance này, ΔMRR so với AST là +0,167 với HIST, +0,092 với ISSUE và +0,002 với DOC. Khi bằng chứng hữu ích không nối tới gold, nguồn không tốt hơn so với khi không có phần tử hữu ích nào.
  - 91,4% instance có phần tử hữu ích từ ít nhất một nguồn. Khi AST không có gold trong top 10, tỷ lệ này là 87,2%.
  - Như vậy DOC và ISSUE không giúp xếp hạng, nhưng vẫn cung cấp loại thông tin mà HIST hiếm khi có. Phần lớn thông tin đó không phải vị trí code, nên RRF không dùng được.
- **Kết quả cũ, với cách trộn có tham số chọn trên dữ liệu.** Các kết quả này không còn là kết luận hiện tại.
  - Lượt v3 chọn p và h trên tập dev. Trên 1.006 instance test, AST+DOC+HIST v3 tăng any-gold Hit@10 từ 57,3% lên 62,4%.
  - Lượt 1 của v4 (16/10/2026) giữ cấu hình trộn của v3 và dùng oracle mới. Top@10 của DOC+HIST v3 tăng từ 55,5% lên 61,2% (mục 9.1).
  - Các lượt v4-L4 đến v4-L6 (22/10 đến 27/10/2026) chọn trọng số bằng kiểm định chéo. Khi đó +ALL tốt hơn AST ở mọi độ đo chính, ví dụ Top@10 tăng từ 55,5% lên 62,2% (mục 9.5). Với RRF gốc, kết luận về +ALL đổi chiều ở Top@1 và MAP.
- **Kết luận rộng (chưa chứng minh).** Câu "dữ liệu đa nguồn nói chung tốt hơn chỉ dùng code" chưa được chứng minh. Với cách trộn đã chốt, trên 12 repo, đủ nguồn không tốt hơn AST có ý nghĩa ở độ đo nào, và kém hơn ở Top@1, MRR và MAP. Sai lệch của snapshot chưa được đo.
- **Mức tăng còn vừa phải.** +HIST, hệ thống tốt nhất, vẫn làm 26,6% instance kém hơn AST. Với +HIST, Acc@10 chỉ đạt 34,2%, tức phần lớn instance chưa có đủ mọi gold trong top 10.
- **Kết luận theo gold của lượt v2 vẫn giữ** cho hệ thống v2 đã chạy. Kết luận theo judge của lượt v2 đã được thay bằng kết quả v3.
- **Phân tích dựa trên nhãn commit của v3 không dùng được**, vì judge chỉ thấy message.

## 9. Thiết kế lượt v4 (thực nghiệm trên Django và SymPy)

**Lộ trình đã thống nhất (14/10/2026).** Giai đoạn 0: sửa tài liệu. Giai đoạn 1: sửa oracle và kiểm tra lại (1.1), tính lại với quy tắc thống kê thống nhất và xếp hạng tới 500 (1.2), kiểm tra snapshot trên 100 instance (1.3). Giai đoạn 1.5: tìm hiểu bài báo và dữ liệu cho ISSUE. Giai đoạn 2: hoàn thiện v4 (HIST theo Locus, thêm +ISSUE, đóng băng luồng xử lý và manifest). Giai đoạn 3: xác nhận trên repo giữ lại lấy từ split train của SWE-bench (37 repo không trùng với tập test). Giai đoạn 4: viết luận văn. Từ ngày 27/10/2026, đề tài không còn giai đoạn xác nhận trên repo giữ lại, và không đóng băng luồng xử lý để xác nhận (quyết định 58).

**Hệ thống so sánh của v4:** AST, +DOC, +HIST, +ISSUE, +DOC+HIST+ISSUE, và ba hệ thống bỏ bớt một nguồn.

**Bước 0 cũ.** Các số liệu ở phần "Kết quả bước 0" bên dưới thuộc thiết kế cũ. Trong thiết kế đó, HIST lấy F file đầu của AST và m commit mỗi file, rồi cắt diff ở C token. Thiết kế này đã được thay bằng Locus, nên F, m và C không còn được dùng.

Kế hoạch đầy đủ nằm ở `planning.md`. Thiết kế kỹ thuật của từng bước nằm ở `pipeline_design.md`.

**HIST mới, theo Locus (Wen, Wu, Cheung, ASE 2016)**

1. **Tài liệu.** Mỗi hunk của các đơn vị history là tổ tiên của snapshot là một tài liệu. Hunk gồm dòng ngữ cảnh, dòng xóa, dòng thêm và commit message. Diff là `git diff -U3 -w`, chỉ cho file `.py` có trong graph. Hunk chỉ đổi comment bị bỏ.
2. **Điểm.** score(b, f) = max_{h ∈ H(f)} {NL(b, h) + α·CE(b, h)} + β₁·Fix(f). NL và CE là cosine trong mô hình vector với trọng số (log f + 1)·log(N / n_t). α tăng theo tỷ lệ tên code trong issue, với λ = 5. Fix(f) cộng điểm cho hàm/lớp từng bị sửa lỗi, nhiều hơn khi lần sửa gần đây, với β₁ = 0,1.
3. **Chuyển sang mức hàm/lớp.** H(f) là các hunk có dòng đổi nằm trong f, theo oracle mới. Bảy chỗ chuyển đổi so với bài gốc được ghi ở mục 6.4 của `planning.md`.
4. **Không có LLM và không có tham số chọn bằng dữ liệu.** LLM chỉ là judge. λ và β₁ lấy từ bài. Thiết kế `hist-llm` cũ, trong đó LLM viết ý đồ commit, nêu giả thuyết rồi liệt kê hàm/lớp, đã bị bỏ.
5. **Trộn.** Danh sách hàm/lớp được trộn với AST. Từ ngày 27/10/2026, cách trộn là RRF gốc với trọng số bằng nhau (quyết định 57).

**Các phần khác**

- **Hệ thống so sánh.** Có AST, +DOC, +HIST, +ISSUE, +ALL và ba hệ thống bỏ bớt một nguồn. Trước mắt, thực nghiệm tập trung vào HIST. ISSUE tạm hoãn vì chưa có dữ liệu.
- **Judge.** Node code giữ prompt cũ và chỉ chấm node mới. Bằng chứng gồm chunk doc kèm node mà nó nối tới, và hunk tốt nhất của 10 hàm/lớp đầu trong danh sách HIST, kèm title và message của commit. Bằng chứng được chấm bằng một prompt chung, có xem bản vá thật, cho hai điểm là liên quan và hữu ích. Lý do được viết trước điểm.
- **Độ đo.** Độ đo và cách trình bày theo mục 6.8 của `planning.md`. Độ đo gồm Top@1, Top@5, Top@10, MRR, MAP, Acc@10 và nDCG@10 theo judge. Mỗi câu hỏi có bảng thay đổi theo từng instance và một kiểm định McNemar cho Top@10. Có thêm ba phân tích bổ sung. Câu hỏi là Q1 đến Q7.

**Các bước thực hiện**

1. Viết cell `hist-proc` theo Locus. Việc này đã xong trong bản làm việc và đã thử trên máy.
2. Viết `v4-config` và `v4-run`.
3. Chạy trên Kaggle `hist-build`, `v4-run` và `hist-proc`.
4. Trộn, khi cách trộn đã chốt.
5. Chạy judge v4.
6. Chạy `verify-v4`.

**Kết quả bước 0 cũ (thiết kế đã bỏ; hạt giống ở mức file, tập test, dữ liệu trên máy, không gọi LLM)**

- File gold nằm trong 3 file đầu của AST ở 71% (django) và 68% (sympy) instance. Với 5 file đầu, các tỷ lệ là 79% và 74%.
- Xét các instance AST trượt top 10, tỷ lệ còn giữ được commit đã sửa gold là:
  - mức trần (mọi commit của 5 file): 75% và 59%, nhưng khi đó có trung vị 281 và 127 commit mỗi instance;
  - F = 5, m = 10: 55% và 45%, trung vị 45 và 38 commit;
  - F = 3, m = 10: 46% và 39%;
  - F = 5, m = 5: 44% và 36%.
- Với F = 5, m = 10 và C = 1.500, phần message cộng diff có trung vị 13,9 nghìn token (django) và 16,0 nghìn token (sympy) mỗi instance. p90 là 17,7 nghìn và 20,4 nghìn. Danh sách tên hàm/lớp trong 5 file có trung vị 177 và 386 tên, tức khoảng 2,1 nghìn và 4,6 nghìn token.
- Với thiết kế `hist-llm` cũ (đã bỏ), tổng mỗi lần gọi có trung vị khoảng 17 nghìn và 21 nghìn token. Tổng cộng khoảng 22 đến 23 triệu token cho 1.186 instance.
- Diff của một file thường nhỏ, nên trần C hầu như không ảnh hưởng ở django. Ở sympy, mỗi commit là một merge commit chứa cả pull request, nên trần có ảnh hưởng.
- File history thử trên máy không ghi các commit chỉ sửa code cấp module, nên số thật trên Kaggle có thể cao hơn một chút.

**Cơ sở tài liệu cho bước lọc node** (chi tiết ở artifact "Tổng quan tài liệu RepoGraph")

- **Không dùng cửa sổ thời gian cứng.** Locus, ROSE, Sisman và Kak, KGCompass, HAFix và HAFixAgent đều dùng toàn bộ lịch sử trước thời điểm báo lỗi. Chỉ AmaLgam dùng cửa sổ 15 ngày, và bản tái lập ABLoTS năm 2026 cho thấy code của AmaLgam rò rỉ ở mốc thời gian. Khi sửa mốc, MAP của ABLoTS giảm từ 0,488 xuống 0,055.
- **Độ gần đây là tín hiệu xếp hạng, không phải bộ lọc.** Sisman và Kak dùng trọng số giảm theo hàm mũ (MAP tăng tới 80%, so với 30% khi không giảm). Locus dùng trọng số 0,1 đến 0,2, đóng góp khoảng 4 đến 5% MAP.
- **Bỏ commit hoặc nội dung nhiễu.** ROSE bỏ transaction chạm hơn 30 thực thể. Locus bỏ hunk ngoài file nguồn, hunk chỉ đổi khoảng trắng hoặc comment, và hunk chỉ định dạng lại code.
- **Chọn ngưỡng bằng độ phủ.** KGCompass giữ top 15 hàm vì phủ 97,3% gold mà graph tìm được. Bước 0 cũ của đề tài làm theo cách này.
- **Nội dung đưa cho LLM.** Theo HAFix (model 7B đến 16B), tên các hàm sửa cùng giúp ổn định nhất, còn diff thô thường làm kém hơn và tốn token nhất. Theo HAFixAgent (model lớn hơn), diff là loại đơn lẻ tốt nhất ở 2 trên 3 model, và gộp nhiều loại là tốt nhất.
- **Lan điểm qua graph.** Theo HippoRAG, mở rộng hàng xóm đơn thuần làm kém hơn chỉ dùng node gốc (R@2 42,2 so với 50,7). PPR với restart 0,5 và trọng số specificity (1 chia số đoạn văn chứa node) đạt 57,4. Theo ROSE, co-change ở mức hàm chỉ có precision khoảng 26%.
- **Judge.** Theo eRAG, nhãn "liên quan" do LLM chấm gần như không tương quan với kết quả cuối (Kendall τ từ −0,04 đến 0,19). Theo Utility judgments, prompt hỏi "hữu ích" tốt hơn prompt hỏi "liên quan" (F1 +30,98% trên NQ), chấm cả danh sách tốt hơn, và LLM nhạy với vị trí.

**Đề xuất rút ra từ tài liệu khi HIST còn dùng LLM**

Các đề xuất này được đưa ra trước khi HIST chuyển sang Locus.

- Chọn commit bằng `git blame` trên dòng code của các node top AST trong file (HAFix, HAFixAgent). Đề xuất này chưa được dùng.
- Khi bỏ phiếu, giảm trọng số cho commit hoặc hàm quá phổ biến, theo kiểu node specificity (HippoRAG). Đề xuất này chưa được dùng.
- Judge chấm theo danh sách và xáo thứ tự phần tử (Utility judgments). Đề xuất này đã được đưa vào judge v4. Việc chấm vài lần với thứ tự khác nhau (k-sampling) chưa được đưa vào.

**Đã đo trên máy trước đó (hạt giống ở mức hàm)**

- Khi xếp hạng commit, tiêu chí "commit sửa ít hàm" và "tỷ lệ hạt giống trong commit" bỏ đúng những commit dẫn sang hàm mới. Chia commit theo từng hạt giống tốt hơn xếp chung. RRF của message và độ gần đây ổn định ở cả hai repo. Bỏ cửa sổ 5 năm giữ thêm được commit hữu ích.
- Nếu chỉ cắt diff trong hàm hạt giống, phần thay đổi của gold bị mất ở 50 đến 67% commit sửa gold nằm ngoài hạt giống. Lấy diff theo file, đặt file chứa hạt giống lên trước và dùng trần 1.500 token, thì giữ được 60 đến 88%.
- Hop từ code sang doc qua cạnh Documents ít tác dụng. Chỉ 18% (django) và 8% (sympy) hàm/lớp có chunk nối tới.

**Để sau**

- Sửa cách nối chunk doc với code. Hiện chunk thường chỉ nối tới lớp thay vì method, và có chunk nhắc tên gold nhưng không có cạnh.
- Cổng chọn nguồn cho từng instance.
- Đo lượng code phải đọc, và đo bằng tác vụ định vị của LLM.

### 9.1 Kết quả lượt 1 trên Kaggle (16/10/2026)

**Chạy.** Lượt 1 chạy Run All với `RUN_V3 = False`. Cả 11 cell v3 đều được bỏ qua. Cả 86 graph cũ được dùng lại mà không phải build lại. `hist-build` dựng 22.111 đơn vị cho Django và 8.141 đơn vị cho SymPy. `v4-run` chạy 1.236 instance trong 3.288 giây. Số instance có gold dùng được là 1.187, gồm 821 của Django và 366 của SymPy. Con số này nhiều hơn trước 1 instance, vì oracle mới tìm được gold dạng Function/Class cho một instance trước đây bị loại.

**Tính lại v3 với oracle mới (cell `v3-recheck`, việc 1.2).** Cấu hình trộn giữ đúng như v3. DOC dùng p = 0,1 và h = 1. HIST dùng 10 commit, p = 0,25 và h = 3. DOC+HIST dùng cả hai nguồn với h = 3. Bảng dưới đây gộp hai repo.

| Hệ thống | Top@1 | Top@5 | Top@10 | MRR | MAP | Acc@10 |
|---|---|---|---|---|---|---|
| AST | 23,9 | 45,6 | 55,5 | 0,345 | 0,266 | 33,6 |
| DOC | 23,9 | 46,7 | 57,4 | 0,349 | 0,268 | 35,8 |
| HIST (v3) | 23,9 | 50,7 | 59,7 | 0,354 | 0,274 | 36,9 |
| DOC+HIST (v3) | 23,9 | 51,2 | 61,2 | 0,356 | 0,276 | 38,4 |

- Top@1 giống nhau ở mọi hệ thống, vì cách trộn luôn giữ nguyên node đầu của AST.
- Top@10 của Django tăng từ 56,6% lên 62,6%. Top@10 của SymPy tăng từ 53,0% lên 58,2%.
- McNemar cho Top@10, với cặp số là số instance chỉ hệ thống thứ nhất trúng và số instance chỉ hệ thống thứ hai trúng. DOC so với AST là 26 và 4 (p = 0,0001). HIST so với AST là 71 và 21 (p < 0,0001). DOC+HIST so với AST là 87 và 19 (p < 0,0001). DOC+HIST so với DOC là 67 và 21 (p < 0,0001). DOC+HIST so với HIST là 21 và 3 (p = 0,0003).
- Nếu so theo hạng của gold tốt nhất, DOC+HIST làm 268 instance tốt hơn và 297 instance kém hơn so với AST. Ở nhóm gold vốn đã trong top 10, số tốt hơn và kém hơn bằng nhau (77 và 77). Ở nhóm gold ở hạng 11 đến 100, có 148 instance tốt hơn và 135 instance kém hơn. Ở nhóm gold ngoài hạng 100, có 43 instance tốt hơn và 85 instance kém hơn.
- Theo việc issue có nêu tên gold, Top@10 ở nhóm có nêu (572 instance) lần lượt là 72,4% (AST), 74,7% (DOC), 74,7% (HIST) và 76,7% (DOC+HIST). Ở nhóm không nêu (615 instance), các con số là 39,8%, 41,3%, 45,9% và 46,8%. History giúp nhiều nhất khi issue không nêu tên code.

**HIST theo Locus, danh sách đứng riêng, chưa trộn với AST.**

| Repo | Top@10 của AST | Chỉ NL | NL+CE | Đủ, có thêm Fix |
|---|---|---|---|---|
| Django | 56,6% | 53,2% | 57,7% | 43,1% |
| SymPy | 53,0% | 44,5% | 50,3% | 48,9% |

Thành phần Fix làm Django giảm mạnh. Nguyên nhân chưa được kiểm chứng. Nghi vấn nằm ở hai chỗ chuyển đổi. Ở A2, gần như mọi commit Django đều có chữ "Fixed", nên Fix gần như chỉ đếm số lần hàm bị sửa. Ở A3, mốc thời gian khác bài gốc.

### 9.2 Dữ liệu ISSUE đã cào (16/10/2026)

Dữ liệu được cào bằng script trong scratchpad của session ngày 16/10/2026, và chưa nằm trong repo. Django được cào từ CSV của Trac và không cần token. SymPy được cào bằng `gh api` với tài khoản GitHub đã đăng nhập. Các phép đo liên kết dùng file history thử trên máy và gold tính bằng oracle cũ, nên chỉ là ước lượng.

| Thông tin | Django | SymPy |
|---|---|---|
| Số báo cáo cũ | 19.382 ticket Trac có resolution là fixed | 9.596 issue và 14.467 PR đã đóng trên GitHub |
| Tỷ lệ báo cáo nối được tới commit hoặc PR | 83,5% ("Fixed #N" trên nhánh `main`) | 33,3% (từ khóa đóng issue trong PR đã merge) |
| Tỷ lệ nối được ở giai đoạn gần đây | 95,9% với ticket từ 2018 | khoảng 50% với issue từ 2015 |
| Báo cáo có Fix(b′) khác rỗng | 69,6% | 91,4% |
| Số hàm/lớp trong Fix(b′), trung vị | 1 | 2 |
| Nhận ra báo cáo của chính instance | 98,7% bằng so title | 100% khi gộp từ khóa đóng issue và so title |
| Khoảng cách từ báo cáo tới PR, trung vị và p90 | 2 ngày và 1.313 ngày | 6 ngày và 1.024 ngày |
| Báo cáo cũ dùng được mỗi instance, trung vị | 4.694 | 1.157 |
| Mức trần sau khi lọc | 83,7% | 66,9% |

Bản clone Django trên máy đang dừng ở snapshot `838e432e`. Vì vậy mọi phép đo trên lịch sử phải đọc từ nhánh `main` hoặc từ snapshot mới nhất, không đọc từ HEAD.

### 9.3 Kiến trúc graph (16/10/2026)

Graph có ba nhóm. Nhóm Code (AST) gồm Module, Class, Function và các cạnh code. Nhóm Doc gồm Document, DocChunk và các cạnh HasChunk, Documents, References. Nhóm History gom commit và issue cũ, theo quyết định của người dùng.

- Node Commit giữ như v3. Với SymPy, mỗi commit là merge commit của một PR.
- Node **Issue** là issue cũ đã được sửa. Node có id `issue:<repo>:<số>`, số issue, title, toàn văn nội dung, thời điểm tạo, và loại ticket với Django. Phần thảo luận không được đưa vào, giống Locus.
- Cạnh Modifies đi từ Commit tới hàm/lớp và mang diff của hunk đã sửa. Cạnh Fixes đi từ Commit tới Issue.
- Issue đang cần định vị chỉ là query, không phải node. Khi viết, nó được gọi là "issue của instance".
- Nhóm History được lưu một lần cho mỗi repo, rồi đổi id hàm/lớp sang id của từng snapshot khi chạy.

Cơ sở là graph của Abedu và cộng sự (TOSEM), với các cạnh Fixed và Changed, và KGCompass, với cách nối issue tới hàm và lọc theo thời gian.

### 9.4 Đề xuất đang chờ xác nhận

1. **Trộn theo RRF gốc của Cormack và cộng sự (SIGIR 2009).** Công thức là RRFscore(d) = Σ 1/(60 + r(d)), với trọng số bằng nhau. Mỗi nguồn dùng thứ tự theo bằng chứng của chính nó, không xếp lại theo hạng AST, và bỏ p, h. Thử trên máy cần file `scale_rows_v4.jsonl` của lượt 1.
2. **Cạnh Impacted đi thẳng từ Issue tới hàm/lớp,** theo cạnh Impacted của Abedu và cộng sự. Cạnh mang danh sách commit đã sửa issue, để lọc điều kiện tổ tiên của snapshot.
3. **Bốn hệ thống AST, +DOC, +HIST, +DOC+HIST,** trong đó HIST gồm cả danh sách commit lẫn danh sách issue cũ, trộn phẳng. Commit riêng và issue riêng được báo như phân tích thành phần.
4. **Chỉ dùng liên kết "Fixed #N" cho Django,** bỏ "Refs #N".
5. **Mốc thời gian của ISSUE** cắt theo thời điểm tạo báo cáo của chính instance, thay cho thời điểm tạo PR.
6. **Tìm nguyên nhân Fix làm giảm danh sách HIST ở Django.**

> Tình trạng ngày 22/10/2026. Ý 1 đã thử ở lượt v4-L2b và được thay bằng RRF có trọng số theo nguồn (mục 9.5). Ý 2 và 3 chưa làm: commit và issue cũ vẫn nằm ở file riêng, chưa thành cạnh của graph. Ý 4 và 5 được giữ làm mặc định (quyết định 44 và 50). Ý 6 đã làm ở bước D (mục 9.5).

### 9.5 Kết quả lượt đầy đủ của v4 (22/10/2026)

> Tình trạng ngày 29/10/2026. Mục này ghi kết quả của lượt v4-L4 và được giữ làm lịch sử. Cách trộn có trọng số của lượt này đã bị bỏ ngày 27/10/2026 (quyết định 57). Nhãn judge đã được phân tích ở các lượt sau. Kết quả hiện tại là lượt v4-L8 trên 12 repo, nằm ở mục 8 của file này và mục 10 của `experiment_log.md`.

Lượt v4-L4 chạy trên 1.187 instance, với đủ bốn nguồn. Bảng đầy đủ, thời gian và sự cố của các lượt v4 nằm ở `experiment_log.md`.

**Cách trộn.** RRF có trọng số theo nguồn: score(d) = 1/(60 + hạng AST) + Σ_s w_s/(60 + hạng trong nguồn s). Trọng số được chọn bằng kiểm định chéo 5 phần theo MAP. Trọng số đã chọn rất ổn định giữa các phần. DOC luôn ở 0,05, là giá trị nhỏ nhất của lưới. HIST ở 0,75 đến 1,5, tức ngang AST. ISSUE ở 0,05 đến 0,2. Từ ngày 27/10/2026, cách trộn này bị bỏ, và v4 dùng RRF gốc với trọng số bằng nhau (quyết định 57).

**Mức hàm/lớp, gộp hai repo.**

| Hệ thống | Top@1 | Top@10 | MRR | MAP |
|---|---|---|---|---|
| AST | 23,8 | 55,5 | 0,344 | 0,265 |
| +DOC | 22,4 | 56,4 | 0,340 | 0,259 |
| +HIST | 27,5 | 62,1 | 0,390 | 0,306 |
| +ISSUE | 24,3 | 56,7 | 0,355 | 0,272 |
| +ALL | 27,7 | 62,2 | 0,392 | 0,308 |
| ALL−DOC | 28,7 | 62,3 | 0,398 | 0,312 |

**Trả lời các câu hỏi.**
- Q4: +ALL tốt hơn AST ở Top@1, Top@5, Top@10, MRR và MAP, có ý nghĩa sau Holm. 584 instance tốt hơn và 303 instance kém hơn.
- Q2 và Q6: HIST giúp khi đứng riêng, và vẫn thêm giá trị khi đã có DOC và ISSUE.
- Q1 và Q3: DOC và ISSUE chỉ tăng Top@10 (0,8 và 1,2 điểm, có ý nghĩa). MRR và MAP không đổi có ý nghĩa.
- Q5 và Q7: DOC và ISSUE không thêm gì khi đã có HIST.
- Ở mức file, +HIST và +ALL tăng Top@1 (5,6 và 4,3 điểm), MRR và MAP, có ý nghĩa. Top@10 mức file không đổi có ý nghĩa, vì AST đã đạt 85,6%.

**Phân tích phụ.**
- Phần tăng đến từ ca khó. Với gold ở hạng 11 đến 100 của AST, +ALL làm 76,3% instance tốt hơn. Với gold ngoài hạng 100, tỷ lệ này là 54,1%, so với 17,3% kém hơn.
- Trong HIST, CE (khớp tên code) đóng góp nhiều nhất: Top@10 là 59,2 khi chỉ dùng NL và 62,3 khi dùng NL+CE. Fix không thêm gì sau khi trộn (62,1).
- Bước D cho thấy Fix kéo hàm bị sửa nhiều lần lên đầu danh sách ở Django. Trung vị số lần bị sửa của 10 hàm/lớp đầu tăng từ 6,5 lên 37,5 khi có Fix. Đổi A3 giảm được một phần thiệt hại nhưng không xóa hết.
- Liên kết "Refs" của Django không giúp. Mức trần của ISSUE là 83,2% (Django) và 63,4% (SymPy).
- RRF trọng số bằng nhau (lượt v4-L2b) làm +DOC và +ISSUE kém hơn AST rõ rệt. Ví dụ, Top@10 của +DOC giảm còn 43,7%. Trộn có trọng số sửa được thiệt hại này. Cách trộn có trọng số đã bị bỏ ngày 27/10/2026 (quyết định 57).

**Judge.** 3.561 trên 3.561 request bằng chứng có nhãn. Nhãn chưa được phân tích. Bảng bằng chứng (bước I) đã được cài ngày 22/10, và sẽ có số liệu ở lượt Kaggle tiếp theo.

**Độ lặp lại.** Hai lần dựng lại toàn bộ trên Kaggle chỉ lệch khoảng 1 instance trên 1.187, do thứ tự node bằng điểm trong `_rrf`. Từ ngày 22/10, `_rrf` xếp node bằng điểm theo id.

## 10. Notebook và môi trường

- Từ ngày 27/10/2026, notebook có 45 cell và chỉ chứa code của pipeline v4. Phần v4 nằm ở cuối, gồm `v4-md`, `v4-config`, `v4-run`, `hist-proc`, `issue-fetch`, `issue-index`, `v4-fusion`, `judge-v4`, một cell trống, `verify-v4`, `depth-v4` và `manifest`. Cell `verify-v4` được tạo lại trên Kaggle, nên mang id mới `744cae31-2884-4a39-b41f-eb642ad52ce5`.
- Ngày 27/10/2026, code của v3 bị bỏ khỏi notebook. Đó là 11 cell `%%v3`, cờ `RUN_V3` và các prompt của judge v3. Ba cell chỉ để phân tích cũng bị bỏ, gồm `v3-recheck`, `gpu_cuda_check` và `hist-fix-check` (quyết định 56).
- Notebook trong repo đang chứa output của lượt v4-L7 trên Kaggle (27/10/2026), và đang chứa `GOOGLE_API_KEY` thật. Không commit khi key còn trong file.
- Ngày 27/10/2026, cell `cell-files` bị mất trong bản notebook quay về từ lượt v4-L6, rồi được khôi phục từ bản sao lưu. Cell này định nghĩa `_SKIP_DIRS`, `_SKIP_FILES` và `get_python_files`. Thiếu cell này thì `v4-run` dừng với lỗi `NameError` khi phải tính instance mới.
- `manifest` và dấu cách tính của `issue-index` lấy mã của cell từ biến `In` của IPython. Ở lượt v4-L6, `In` rỗng, nên manifest ghi 0 cell và dấu cách tính chỉ dựa trên cấu hình. Ở lượt v4-L7, `In` có đủ mã cell, và manifest ghi 31 cell. Cả hai lượt đều chạy bằng Run All trong editor của Kaggle, và nguyên nhân chưa rõ. Cả hai cell không báo lỗi khi `In` rỗng.
- `GITHUB_TOKEN` ở `v4-config` là biến thường, để trống. Không có token thì `issue-fetch` tải SymPy mất khoảng 5 giờ. File báo cáo đã tải nằm ở `/kaggle/working/v4/issues/`, nên các lượt sau bỏ qua việc tải.

- `WORK_DIR` là `/kaggle/working`, được lưu khi Save Version. `REPO_DIR` là `/tmp/repos`, không được lưu.
- `judge-config` chứa API key dạng biến thường `GOOGLE_API_KEY`. Trong repo, biến này để trống. Cần dán key trước khi chạy judge, và xóa key trước khi commit.
- Gemini API trên project có billing cần prepaid credit. Batch API rẻ hơn 50%.
- File kết quả: `scale_rows_v2.jsonl` và `judge/` (lượt v2); `scale_rows_v3.jsonl`, `history/` và `judge_v3/` (lượt v3); `v4/scale_rows_v4.jsonl`, `history/<repo>_history_v2.jsonl` và `history/<repo>_hunks_v2.jsonl` (lượt 1 của v4).
- File thêm từ ngày 21/10: `v4/issues/<repo>_reports.jsonl` (báo cáo cũ), `v4/issues/<repo>_links.jsonl` (cặp báo cáo và commit kèm loại liên kết), `v4/fusion.json` (cấu hình trộn), `judge_v4/` (request, pool, nhãn và `batch_jobs.txt`). File kết quả cũ được đổi tên thành `v4/scale_rows_v4_truoc_buoc_A.jsonl` khi `v4-run` dựng lại.

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
10. Lượt v3 chạy xong trên Kaggle. Judge được gửi theo từng phần 150 instance, vì giới hạn 10 triệu token đang xếp hàng của Tier 1.
11. Mục tiêu được nêu lại: chứng minh dữ liệu đa nguồn tốt hơn chỉ dùng code, và mọi kết quả được so với AST.
12. Judge được xác định là đo mức liên quan, không đo mức hữu ích, và commit chỉ được chấm theo message. Nhãn commit của v3 bị bỏ.
13. History được thiết kế lại theo quy trình debug của developer: file, rồi commit, rồi ý đồ, rồi nguyên nhân lỗi. Diff được lấy từ git theo file, không chia theo cạnh.
14. Lượt v4 chỉ so 4 hệ thống (AST, +DOC, +HIST, +DOC+HIST), không làm ablation.
15. Quy trình debug của developer được xác định là hình mẫu để thiết kế luồng history, không phải mục tiêu của đề tài.
16. Bước 0 chọn F = 5 file, m = 10 commit mỗi file và trần C = 1.500 token mỗi commit, bằng phép đo độ phủ.
17. Mọi quyết định kỹ thuật phải có bài báo tương tự làm cơ sở. Đã đọc 18 bài và tổng hợp trong artifact "Tổng quan tài liệu RepoGraph". Lần đọc toàn văn đã đính chính hai điểm. Thứ nhất, ROSE đạt 64% ở mức hàm chứ không phải hơn 70%. Thứ hai, trong HAFix, diff thô thường làm kết quả kém hơn.
18. Bản đánh giá độc lập (17 điểm) được chấp nhận sau khi kiểm chứng trên code. Phạm vi khẳng định thu hẹp về kết luận hẹp ở mục 8. V3 và v4 trên 1.006 instance được ghi là thực nghiệm khám phá. Phần "thực nghiệm khám phá" được thay bằng quyết định 58.
19. Nguồn ISSUE được đưa vào v4. Muốn có kết luận rộng thì phải xác nhận trên repo giữ lại với luồng xử lý đã đóng băng. Phần xác nhận trên repo giữ lại được thay bằng quyết định 58.
20. LLM chỉ là judge, như đã nêu từ đầu. Thiết kế `hist-llm` bị bỏ. Cách xếp hạng của HIST được chọn lại từ bài báo và không dùng LLM. Tham số C bị bỏ theo.
21. Không tách dev và test. Mọi bước chọn tham số và mọi kết quả dùng cả 1.187 instance.
22. Phần phụ trợ được giữ đơn giản. Kết quả được trình bày theo mục 6.8 của `planning.md`, kèm một kiểm định McNemar cho Top@10.
23. HIST xếp hạng theo Locus ở mức hàm/lớp, với 7 chỗ chuyển đổi ghi ở mục 6.4 của `planning.md`. F và m bị bỏ.
24. Các cell chỉ phục vụ v3 được chặn bằng cờ `RUN_V3` và magic `%%v3`. Quyết định này được thay bằng quyết định 56.
25. Lượt 1 của v4 xác nhận kết luận hẹp với oracle mới.
26. Mục tiêu chính không phải tìm nguồn mạnh nhất, nhưng các nguồn vẫn được so với nhau để thống kê và điều chỉnh.
27. Trong graph, commit và issue cũ được gom vào nhóm History. Node của issue cũ tên là Issue.
28. Chủ đề được hiểu là truy xuất ngữ cảnh. Agent sẽ được dùng để kiểm chứng hiệu quả, nhưng thực nghiệm hiện tại chưa dùng agent. LLM judge đánh giá các node output sẽ được dùng cho agent sau này.
29. Giá trị chính của doc, issue cũ và history là ngữ nghĩa, thông tin và ngữ cảnh mà node cung cấp. Judge chấm nội dung này, không dùng để so với gold.
30. Node doc, issue cũ và hunk là output, không chỉ là phiếu bầu cho AST. Output được ghép theo loại.
31. Graph liên kết các node: đưa vào kết quả node mà search không với tới, và ưu tiên node bằng chứng có liên kết với AST node đã truy hồi. AST node cũng hop ra node khác.
32. Dùng ngưỡng thay cho số lượng cố định, ở ba chỗ: trước khi hop, trước khi vote và trước khi output. Cách chọn ngưỡng sẽ được tìm hiểu từ bài báo.
33. Giữ toàn bộ khung so sánh với AST, gồm các mức hop và các cách kết hợp nguồn. Giữ Q1 đến Q7.
34. Judge bằng chứng ghi thêm loại thông tin mà phần tử cung cấp.
35. Định hướng của các quyết định 28 đến 34 nằm ở mục 12.
36. Input của hệ thống là một prompt bất kỳ trên repository (issue, câu hỏi, yêu cầu tìm code hay doc). Phân tích issue chỉ là một use case.
37. Thực nghiệm hiện tại chỉ tập trung vào kiến trúc retrieval. Use case được đánh giá là issue trên SWE-bench.
38. Đánh giá phần AST ở hai mức: hàm/lớp là mức chính, file là mức phụ. Xếp hạng file suy từ điểm cao nhất của hàm/lớp trong file, theo SweRank.
39. Phần bằng chứng được đánh giá bằng một pool 10 phần tử đầu mỗi loại, chấm một lần, với Precision, Recall, F1, bảng trả rỗng và số token. Mốc so sánh là hạn ngạch cố định.
40. Loại thông tin của judge: một danh sách chung, nhiều nhãn, bảy loại theo Ko và cộng sự (ICSE 2007) cộng hai nhãn loại trừ.
41. Thêm request "đủ thông tin cho cả tập" theo Sufficient Context, chỉ cho Q4, sau khi đo chi phí trên 50 instance.
42. Kiểm định: McNemar cho độ đo đúng/sai, hoán vị ghép cặp cho độ đo liên tục, Holm trong từng độ đo. Thay cho quyết định 22.
43. Chi tiết của các quyết định 38 đến 42 nằm ở mục 13.
44. Mốc cắt của ISSUE là thời điểm tạo báo cáo của chính instance (`ISSUE_CUTOFF = "instance"`). Khi nhận ra nhiều báo cáo, mốc là báo cáo mới nhất tạo trước `created_at`. Khi không nhận ra báo cáo nào, mốc là `created_at` (21/10/2026).
45. `issue-fetch` tải issue của SymPy bằng phân trang con trỏ, vì GitHub chỉ nhận tham số `page` cho 1.000 mục đầu (21/10/2026).
46. Cách trộn là RRF có trọng số theo nguồn, chọn bằng kiểm định chéo 5 phần theo MAP. RRF trọng số bằng nhau được giữ làm hệ thống đối chứng. Lý do là ở lượt v4-L2b, RRF trọng số bằng nhau làm nguồn yếu kéo kết quả xuống (22/10/2026). Quyết định này được thay bằng quyết định 57.
47. Bằng chứng HIST đưa cho judge giữ đủ danh sách hàm/lớp mà commit đã sửa. Hunk của commit sửa hơn 50 hàm/lớp bị bỏ khỏi bằng chứng, theo ROSE và `HIST_MAX_TOUCH`. Xếp hạng HIST không đổi (22/10/2026).
48. Không chạy thử judge riêng trên vài chục instance. Prompt judge bằng chứng giữ như bản đã cài (21/10/2026).
49. Để kết quả lặp lại được, `_rrf` xếp node bằng điểm theo id, `issue-index` tự tính lại khi cấu hình hoặc cách tính đổi, và `v4-run` tự dựng lại file kết quả khi dữ liệu cũ không còn khớp (22/10/2026).
50. Liên kết Django chỉ dùng "Fixed #N". Lượt v4-L4 cho thấy thêm "Refs #N" không giúp (22/10/2026).
51. Kết quả của mọi lượt chạy được ghi ở `experiment_log.md`, theo một mẫu chung, để theo dõi giữa các lượt (22/10/2026).
52. Judge không viết lý do và dùng mức thinking MINIMAL. Lý do là không phần phân tích nào đọc lý do, và lý do chiếm khoảng một nửa số ký tự output (26/10/2026).
53. Judge không chấm node code nữa. nDCG@10 theo judge được thay bằng độ đo theo cấu trúc: số node phải đọc trước khi gặp gold và độ sâu tới gold trên graph code, theo Renieris và Reiss (ASE 2003). Lý do là judge chấm node code mà không thấy bản vá, và phần này chiếm phần lớn token (26/10/2026).
54. Lượt chạy tới chấm lại toàn bộ bằng chứng với cài đặt judge mới, để mọi nhãn bằng chứng có cùng một cài đặt (26/10/2026).
55. Đợt xác nhận chạy trên 10 repo còn lại của tập test SWE-bench, gồm 1.058 instance. Pipeline được khóa, và trọng số trộn được chọn trên Django và SymPy. Câu hỏi về DOC được báo riêng trên 7 repo có độ phủ doc từ 5%. Chi tiết ở mục 6.14 của `planning.md` (26/10/2026). Phần trọng số được thay bằng quyết định 57. Phần đợt xác nhận và khóa pipeline được thay bằng quyết định 58. Phần báo riêng câu hỏi về DOC trên nhóm 5% được thay bằng quyết định 60.
56. Notebook chỉ chứa code của pipeline. Phân tích chỉ dùng một lần chạy ngoài notebook, và kết quả được ghi vào tài liệu. Code của v3 và các cell chỉ để phân tích bị bỏ khỏi notebook. Lý do là mỗi lượt Run All trên Kaggle chạy lại các cell này, tốn thời gian, và có thể dừng khi gặp lỗi. Chi tiết ở mục 6.15 của `planning.md` (27/10/2026).
57. Cách trộn là RRF gốc của Cormack và cộng sự (SIGIR 2009), với mọi danh sách có trọng số 1 và k = 60. Không tham số nào được chọn trên dữ liệu của đề tài, kể cả bằng kiểm định chéo. Lý do là đề tài không huấn luyện model, nên không khớp tham số theo dữ liệu. Giới hạn là bài của Cormack không thử trộn một danh sách mạnh với các danh sách yếu hơn nhiều. Ở lượt v4-L2b, cách này làm DOC và ISSUE kéo kết quả xuống. Kết luận về xếp hạng sẽ được viết lại theo số của lượt Kaggle đầu tiên dùng RRF gốc. Chi tiết ở mục 8 của `pipeline_design.md` (27/10/2026).
58. Không chia dữ liệu thành dev và test, train và test, hay đợt chính và đợt xác nhận. Lý do là đề tài không huấn luyện model. Tham số lấy từ bài báo, và không tham số nào được chọn trên dữ liệu của đề tài (quyết định 57). Vì vậy kết quả trên Django và SymPy không bị gọi là thực nghiệm khám phá chỉ vì thiếu tập giữ lại. 10 repo còn lại của tập test là thêm dữ liệu cho cùng một thực nghiệm, không phải tập để xác nhận. Quyết định này thay cho phần giữ lại và đóng băng của các quyết định 18, 19 và 55. Quy tắc không đổi phương pháp đã chốt chỉ vì kết quả xấu vẫn giữ nguyên. Cùng ngày, notebook bỏ `V4_PHASE` và chạy 12 repo của tập test như một thực nghiệm. Kết quả của mọi repo ghi chung vào `v4/`, và nhãn judge ghi chung vào `judge_v4/` (27/10/2026).
59. Node sau hop được xếp theo công thức của KGCompass (arXiv 2503.21710): S(f) = 0,6^l(f) × (0,3 × cos_norm + 0,7 × lev). l(f) là tổng trọng số trên đường ngắn nhất từ issue tới f, với trọng số cạnh lấy từ code công khai của KGCompass (0,25 cho quan hệ chứa và cho issue tới node xuất phát, 0,5 cho `Documents`, 1,0 cho `Calls` và `Inherits`) và ngân sách 4. Có hai danh sách. GRAPH đi từ 10 node đầu của AST. DOC đi từ đích cạnh `Documents` của 10 chunk trong `doc_cand`, và thay cách bỏ phiếu cũ (nhân 0,8, lan một bước nhân 0,5). Lý do là cách bỏ phiếu cũ chưa có cơ sở, còn KGCompass là cách chấm điểm sau hop trong miền code không dùng LLM và không cần huấn luyện. Hai bài KGCompass dẫn, Zhu và Iglesias và Ballatore và cộng sự, chỉ cho ý tưởng suy giảm theo đường đi và cộng tuyến tính hai độ giống, không cho dạng hàm hay giá trị tham số. β và α do tác giả KGCompass chọn trên SWE-bench, và đề tài dùng nguyên giá trị. Có hai câu hỏi mới là G1 (+GRAPH so với AST) và G2 (+ALL+GRAPH so với +ALL), với Holm riêng cho họ này. Tiêu chí được đặt trước khi chạy: GRAPH có giá trị xếp hạng khi +GRAPH tốt hơn AST có ý nghĩa ở ít nhất một độ đo của Bảng 1 mức hàm/lớp và không kém hơn có ý nghĩa ở độ đo nào. Chi tiết ở mục 8b của `pipeline_design.md` (28/10/2026).
60. Bảng độ phủ doc của `coverage_report.md` được lập để đo độ phủ doc ảnh hưởng thế nào tới hiệu quả. Vì vậy repo có độ phủ thấp được giữ trong thực nghiệm, và độ phủ được phân tích như một biến. Có hai mức. Ở mức repo, C1 là ρ của Spearman giữa độ phủ và mức đóng góp của DOC. Ở mức instance, C2 so mức đóng góp của DOC giữa instance có gold được document và instance không có. +HIST và +GRAPH là đối chứng âm. Nhóm repo có độ phủ từ 5% (`V4_DOC_REPOS`) bị bỏ, vì ngưỡng 5% chưa có bài báo làm cơ sở, việc cắt một biến liên tục thành hai nhóm làm mất thông tin và lực kiểm định (Altman và Royston, BMJ 2006), và nhóm này bỏ đúng phần độ phủ thấp mà câu hỏi cần. Quyết định này thay phần báo riêng câu hỏi về DOC của quyết định 55. Chi tiết ở mục 13.6 (28/10/2026).

## 12. Định hướng đề tài (thảo luận ngày 18/10/2026)

- **Chủ đề và vai trò của agent.** Chủ đề là truy xuất ngữ cảnh. Mục tiêu là hỗ trợ AI agent, nên agent sẽ được dùng để kiểm chứng hiệu quả. Thực nghiệm hiện tại chưa dùng agent. LLM judge đánh giá các node output, tức các node sau này sẽ được đưa cho agent.
- **Giá trị của các nguồn.** Giá trị chính của doc, issue cũ và history là ngữ nghĩa, thông tin và ngữ cảnh mà node cung cấp. Judge chấm nội dung đó. Judge không được dùng để so với gold.
- **Output.** Ở các lượt đầu, output là AST node, và kết quả được so với gold function/module. Từ khi có judge, node doc, issue cũ và hunk cũng là output. Chúng cung cấp thêm thông tin cho judge, và sau này cho agent. Output được ghép theo loại, mỗi loại là một phần riêng.
- **Vai trò của graph.** Graph liên kết các node. Khi kết quả search không với tới node cần thiết, quan hệ giữa các node đưa node đó vào kết quả truy hồi. Ví dụ, search được một AST node và nhiều hist node, thì hist node có liên kết với AST node đó được ưu tiên hơn. AST node cũng hop ra các node khác.
- **Ngưỡng.** Ngưỡng thay cho số lượng cố định, và có thể dùng ở ba chỗ: trước khi hop, trước khi vote và trước khi output. Lý do là một instance có thể có 5 đến 10 issue cũ liên quan, hoặc không có issue nào. Khi đó đưa đủ 5 issue không liên quan làm loãng context. Theo ước lượng ở mục 9.2, mức trần của ISSUE sau khi lọc là 83,7% (Django) và 66,9% (SymPy), nên một phần đáng kể instance không có issue cũ nào nối tới gold. Điểm embedding và điểm TF-IDF là cosine, có thang cố định, nên đặt được ngưỡng tuyệt đối. BM25 và RRF không có thang cố định. Cách chọn ngưỡng sẽ được tìm hiểu từ bài báo hoặc kỹ thuật liên quan.
- **Khung so sánh.** Giữ toàn bộ khung so sánh với AST, gồm các mức hop và các cách kết hợp nguồn. Câu hỏi giữ nguyên Q1 đến Q7 (mục 6.2 của `planning.md`).
- **Judge bằng chứng.** Ngoài điểm liên quan và điểm hữu ích, judge ghi thêm loại thông tin mà phần tử cung cấp. Danh sách loại chưa chốt.
- **Phát biểu bài toán (20/10/2026).** Input là một prompt trên repository: issue, câu hỏi, hoặc yêu cầu tìm code hay doc. Hệ thống truy xuất tập ngữ cảnh đa nguồn K(p) gồm code, doc, history và issue cũ, ghép theo loại và lọc bằng ngưỡng. Đánh giá là K(p) có cung cấp đúng thông tin cần cho prompt hay không. Với issue là có tìm được file và hàm cần sửa không. Với hỏi đáp là có tìm đúng thông tin cần không. Phân tích issue chỉ là một use case.
- **Phạm vi thực nghiệm (21/10/2026).** Thực nghiệm hiện tại chỉ tập trung vào kiến trúc retrieval. Use case được đánh giá là issue trên SWE-bench. Agent, sinh patch và các use case khác nằm ngoài thực nghiệm hiện tại. Tài liệu và phân tích được thu thập cũng chỉ giới hạn ở quy trình retrieval.
- **Giới hạn khi viết.** Kết quả chỉ khẳng định cho use case issue. HIST theo Locus và ISSUE theo BugLocator có cơ sở bài báo cho báo cáo lỗi, chưa có cho loại prompt khác. Thành phần Fix, việc judge đối chiếu với bản vá, và mốc thời gian chống rò rỉ đang gắn với use case issue. Mức đánh giá cho use case issue (file, hàm/lớp, hay cả hai) chưa chốt.

## 13. Bộ độ đo và phương pháp đánh giá (21/10/2026)

Mục này chốt cách đánh giá output của retrieval cho use case issue. Bài báo làm cơ sở nằm ở mục "Độ đo và kiểm định" của artifact "Tổng quan tài liệu RepoGraph". Cách cài nằm ở mục 6.12 của `planning.md`.

### 13.1 Phần AST: đo bằng gold ở hai mức

- **Mức hàm/lớp là mức chính**, vì output là AST node. **Mức file là mức phụ**, để so được với Locus, AmaLgam, BugLocator, LocAgent và SweRank.
- Xếp hạng file được suy từ xếp hạng hàm/lớp: điểm của file bằng điểm cao nhất của hàm/lớp nằm trong file, theo SweRank. Gold mức file là các file chứa gold hàm/lớp. Hai mức dùng cùng tập 1.187 instance.
- Độ đo ở cả hai mức: Top@1, Top@5, Top@10 (any-gold), MRR, MAP (hạng tới 500), và Acc@k (mọi gold nằm trong top k). Acc@k dùng k = 5 và 10 ở mức hàm/lớp, k = 1, 3 và 5 ở mức file, như LocAgent và SweRank.
- nDCG@10 theo judge cho node code được thay bằng độ đo theo cấu trúc từ ngày 26/10/2026 (quyết định 53). Độ đo mới gồm số node phải đọc trước khi gặp gold, với k = 1, 5 và 10, và độ sâu tới gold của các node trong top 10. Định nghĩa nằm ở mục 10.1 của `pipeline_design.md`.

### 13.2 Phần bằng chứng: chấm một pool, đánh giá mọi ngưỡng ngoại tuyến

- Với mỗi instance và mỗi loại bằng chứng (DOC, HIST, ISSUE), pool là hợp của 10 phần tử đầu mà các hệ thống trả về cho loại đó. Số 10 bằng trần trên của output. Judge chấm mọi phần tử trong pool một lần. Mọi ngưỡng chỉ giữ một phần của pool, nên nhãn đủ để đánh giá mọi ngưỡng mà không gọi judge lại.
- Một phần tử **hữu ích** khi điểm hữu ích từ 2 trở lên, tức phải đọc hoặc phải sửa theo thang của judge.
- Độ đo cho mỗi loại, tính theo từng instance rồi lấy trung bình:
  - Precision: tỷ lệ phần tử được giữ là hữu ích. Chỉ tính trên instance có output khác rỗng.
  - Recall: tỷ lệ phần tử hữu ích trong pool được giữ. Chỉ tính trên instance có pool chứa phần tử hữu ích.
  - F1 của hai số trên, trên cùng tập instance với Recall. F1 là độ đo chuẩn của bài toán cắt danh sách (Arampatzis và cộng sự 2009, Choppy, Surprise, Meng và cộng sự 2024).
  - Trường hợp rỗng: bảng 2×2 giữa "output rỗng hay không" và "pool có phần tử hữu ích hay không". Báo tỷ lệ trả rỗng đúng và tỷ lệ trả rỗng sai.
  - Chi phí: số token của output mỗi loại, như Adaptive-k và GraphRAG báo.
- Mốc so sánh là hạn ngạch cố định hiện tại (5 chunk, 5 issue cũ, 10 hunk), vì Meng và cộng sự (2024) cho thấy fixed-k là mốc khó vượt.

### 13.3 Judge

**Loại thông tin.** Một danh sách chung cho mọi loại bằng chứng, gán nhiều nhãn. Bảy loại lấy từ nhu cầu thông tin của developer (Ko, DeLine, Venolia, ICSE 2007) và các thành phần của báo cáo lỗi (Bettenburg và cộng sự). Hai nhãn cuối là nhãn loại trừ, không đi cùng nhãn nào khác.

| Loại | Cơ sở |
|---|---|
| Hành vi mong đợi, mục đích của code | Ko: "What is the program supposed to do?", "What is the purpose of this code?"; Bettenburg: expected behavior |
| Cách dùng API | Ko: "How do I use this data structure or function?" |
| Triệu chứng và điều kiện lỗi tương tự | Ko: "What does the failure look like?", "In what situations does this failure occur?"; Bettenburg: observed behavior, stack trace, steps to reproduce |
| Nguyên nhân lỗi | Ko: "What code caused this program state?" |
| Vị trí code liên quan | Ko: "What code could have caused this behavior?", "What's statically related to this code?" |
| Lý do thiết kế | Ko: "Why was this code implemented this way?" |
| Thay đổi trước đây, cách sửa | Ko: "How have resources I depend on changed?"; Locus, HAFix |
| Không có thông tin mới (loại trừ) | Khung lập luận: thông tin trùng thì tác động bằng 0 |
| Không liên quan (loại trừ) | |

**Đủ thông tin cho cả tập.** Theo Sufficient Context (Joren và cộng sự, ICLR 2025), judge gán nhãn nhị phân "đủ" hay "không đủ" cho cả tập K(p). Khác với bài gốc, judge được xem bản vá thật, vì use case issue có đáp án. Request này chỉ chạy cho câu hỏi chính Q4 (AST so với +ALL), tức 2 request mỗi instance. Chi phí phải được đo trên 50 instance trước khi chạy hết, vì mỗi request chứa toàn bộ K(p).

**Cài đặt từ ngày 26/10/2026.** Judge chỉ chấm bằng chứng, không viết lý do, và dùng mức thinking MINIMAL (quyết định 52 và 53).

### 13.4 Kiểm định

- McNemar cho độ đo đúng/sai: Top@k, Acc@k, trả rỗng đúng.
- Kiểm định hoán vị ghép cặp (paired permutation, hay randomization) cho MRR, MAP, số node phải đọc, Precision, Recall và F1. nDCG@10 theo judge cũng dùng kiểm định này cho tới khi bị thay ngày 26/10/2026. Smucker, Allan, Carterette (CIKM 2007) khuyên dùng kiểm định này. Urbano, Lima, Hanjalic (SIGIR 2019) cho thấy t-test và permutation giữ đúng sai số loại I, còn Wilcoxon và sign test thì không. V2 từng dùng Wilcoxon trên log(hạng); v4 bỏ cách đó.
- Hiệu chỉnh Holm trong từng độ đo, trên 7 câu hỏi.
- Giới hạn: kiểm định vẫn coi từng instance là độc lập, dù nhiều instance dùng chung snapshot, doc và history.

### 13.5 Thay đổi so với kế hoạch trước

- Quyết định 22 (chỉ một McNemar cho Top@10, không hiệu chỉnh) được thay bằng mục 13.4.
- Mục 6.8 của `planning.md` được bổ sung mức file, độ đo cho bằng chứng và request đủ thông tin.
- nDCG@10 theo judge được thay bằng độ đo theo cấu trúc, và judge chỉ chấm bằng chứng (26/10/2026).

### 13.6 Ảnh hưởng của độ phủ doc (28/10/2026)

Mục này đo độ phủ doc ảnh hưởng thế nào tới mức đóng góp của DOC (quyết định 60). Độ phủ doc là tỷ lệ hàm/lớp có cạnh `Documents`, như mục 1 của `coverage_report.md`. Cách cài nằm ở mục 10.2 của `pipeline_design.md`.
- **Biến.** `doc_cov` là độ phủ của graph snapshot. Độ phủ của một repo là trung bình `doc_cov` trên các instance của repo. `gold_doc` là số gold có cạnh `Documents`.
- **Kết quả.** Kết quả chính là Δ của +DOC so với AST theo từng instance, ở mức hàm/lớp. Kết quả phụ là +ALL so với ALL−DOC. +HIST và +GRAPH so với AST là đối chứng âm, vì hai nguồn này không đọc doc (Lipsitch, Tchetgen Tchetgen, Cohen, Epidemiology 2010).
- **C1, mức repo.** ρ của Spearman giữa độ phủ của repo và Δ trung bình của repo, với p tính bằng hoán vị nhãn repo. Cronen-Townsend, Zhou và Croft (SIGIR 2002) dùng kiểm định tương quan hạng Spearman để đo quan hệ giữa một đặc tính và độ chính xác truy hồi, vì không biết phân bố của điểm.
- **C2, mức instance.** Hiệu Δ trung bình giữa nhóm `gold_doc` ≥ 1 và nhóm `gold_doc` = 0, với p tính bằng hoán vị nhãn nhóm trong từng repo. Cách tách theo một đặc tính của instance theo Kochhar, Tian và Lo (ASE 2014). Hiệu giữa hai nhóm được kiểm định trực tiếp, theo Gelman và Stern (The American Statistician 2006) và Wang và cộng sự (NEJM 2007).
- **Họ C.** C1 và C2 của +DOC so với AST là một họ, với Holm trong từng độ đo. Kết quả phụ và đối chứng chỉ có p thô.
- **Tiêu chí ghi trước khi chạy.** "Độ phủ doc ảnh hưởng tới hiệu quả" khi C1 có ρ dương, hoặc C2 cho Δ lớn hơn ở nhóm `gold_doc` ≥ 1, có ý nghĩa sau Holm ở ít nhất một độ đo, và không đối chứng âm nào có ρ có ý nghĩa. Khi đối chứng âm cũng có ý nghĩa, kết quả được ghi là chưa tách được khỏi đặc điểm của repo.
- **Giới hạn.** 12 repo trải từ 0,2% tới 24,0%, và trên 12,7% chỉ có flask với 11 instance. C1 chỉ có 12 điểm, nên chỉ phát hiện được quan hệ mạnh. Chưa có bài nào đã đọc đo trực tiếp quan hệ giữa độ phủ doc do người viết và hiệu quả định vị lỗi không dùng LLM. RepoRepair (arXiv 2603.01048) cho thấy bỏ doc do LLM sinh làm số hàm định vị đúng trên SWE-bench Lite giảm từ 205/300 xuống 159/300, nhưng bài đó định vị bằng LLM.
