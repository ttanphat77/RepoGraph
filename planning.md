# Kế hoạch RepoGraph: từ việc 1.2 đến hết giai đoạn 2

Cập nhật ngày 15/10/2026.

File này gom toàn bộ kế hoạch đang làm vào một chỗ. Nó thay cho file cũ `~/.claude/plans/partitioned-sprouting-stardust.md`. File cũ chỉ có 4 hệ thống và chưa có nguồn ISSUE. Phần mở đầu của file cũ còn ghi sai mục tiêu, vì nó coi quy trình debug là mục tiêu của đề tài.

Phạm vi của đợt này là tới hết giai đoạn 2, theo yêu cầu "hãy implement đến giai đoạn 2". Giai đoạn 3 và 4 chỉ được nêu để thấy toàn cảnh.

---

## 1. Mục tiêu đề tài

Đề tài cần chứng minh rằng dữ liệu đa nguồn giúp định vị lỗi tốt hơn so với chỉ dùng code. Định vị lỗi là bài toán xếp hạng các hàm và lớp trong repository theo khả năng phải sửa để đóng một issue.

Đề tài dùng bốn nguồn dữ liệu.

| Nguồn | Nội dung | Ví dụ |
|---|---|---|
| Code (AST) | Hàm, lớp, module và quan hệ giữa chúng | Hàm `QuerySet.filter` gọi `Query.add_q` |
| DOC | File tài liệu bên ngoài code, chia thành các DocChunk | Một đoạn trong `docs/ref/models/querysets.txt` |
| HIST | Các commit cũ đã sửa code | Một commit "Fixed #31423 -- ..." đã sửa `Query.add_q` |
| ISSUE | Các báo cáo lỗi cũ đã được sửa xong | Ticket Trac #30000 cùng các commit đã sửa nó |

Quy trình debug của developer chỉ là hình mẫu để thiết kế luồng HIST. Nó không phải mục tiêu của đề tài.

### 1.1 Hiện trạng kết luận

- **Kết luận hẹp đã có cơ sở.** Trên 1.006 instance test của Django và SymPy, hệ thống AST+DOC+HIST v3 tăng any-gold Hit@10 từ 57,3% lên 62,4%.
- **Kết luận rộng chưa được chứng minh.** Câu "dữ liệu đa nguồn nói chung tốt hơn chỉ dùng code" còn thiếu năm điều kiện.
  1. Thiết kế v4 được làm sau khi đã xem kết quả test của v3. Vì vậy cần một tập dữ liệu chưa dùng khi thiết kế.
  2. Chỉ có hai repo.
  3. Gold và HIST dùng chung một oracle có lỗi.
  4. Snapshot chỉ là phép xấp xỉ của trạng thái code lúc issue xảy ra.
  5. Nguồn ISSUE chưa được đưa vào.

V4 trên Django và SymPy vẫn là **thực nghiệm khám phá**. Thực nghiệm khám phá dùng để tìm thiết kế tốt, nên không dùng để khẳng định cuối cùng. Phần khẳng định nằm ở giai đoạn 3, trên các repo chưa từng được dùng.

---

## 2. Thuật ngữ

- **Instance.** Một issue trong SWE-bench cùng bản vá thật của nó. Ví dụ `django__django-11099`.
- **Snapshot.** Graph code được build tại một commit đại diện cho một nhóm instance gần nhau về thời gian. Django có 40 snapshot cho 820 instance. SymPy có 46 snapshot cho 366 instance. Commit của snapshot có thể sớm hơn base commit của instance tới 60 ngày. Vì vậy snapshot chỉ là phép xấp xỉ.
- **Gold.** Các hàm và lớp mà bản vá thật đã sửa. Ví dụ bản vá sửa thân hàm `UsernameValidator.__call__`, thì gold là node đó.
- **Oracle.** Hàm `get_oracle` trong notebook. Nó đọc một diff và trả về các hàm/lớp bị sửa. Gold của instance và cạnh Modifies của HIST cùng dùng hàm này.
- **Không tách dev và test.** Ở v2 và v3, 180 instance thuộc SWE-bench Lite là tập dev dùng để chọn tham số, còn 1.006 instance còn lại là tập test. Từ v4, mọi bước chọn tham số và mọi kết quả đều dùng cả 1.186 instance. Vì vậy con số của v4 có thể cao hơn mức thật. Phần khẳng định nằm ở giai đoạn 3.
- **Rò rỉ dữ liệu (leakage).** Hệ thống dùng thông tin mà lúc issue xảy ra chưa thể có. Ví dụ dùng commit đã sửa chính issue đó. Chọn tham số trên tập test cũng là một dạng rò rỉ.
- **RRF (Reciprocal Rank Fusion).** Cách gộp nhiều danh sách xếp hạng. Mỗi node nhận điểm 1/(60 + hạng AST), cộng thêm p/(60 + vị trí của node trong danh sách của nguồn). p là trọng số của nguồn. h là số node đầu của AST được giữ nguyên vị trí. Ví dụ, với h = 3, ba node đầu của AST không bao giờ bị đẩy xuống, nên Hit@1 đến Hit@3 không thể giảm. Hàm thực hiện là `fused_multi` trong cell `scale-fusion`.
- **Hit@10 (any-gold).** Tỷ lệ instance có ít nhất một gold trong 10 node đầu. Ví dụ instance có 3 gold, và chỉ 1 gold ở hạng 7. Instance đó vẫn được tính là trúng.
- **Acc@10.** Tỷ lệ instance có mọi gold trong 10 node đầu. Đây là độ đo của LocAgent và SweRank.
- **MRR.** Trung bình của RR trên mọi instance. RR của một instance bằng 1 chia hạng của gold tốt nhất, và bằng 0 khi mọi gold nằm ngoài hạng 500. Ví dụ gold tốt nhất ở hạng 4 thì RR là 0,25.
- **MAP@500.** Trung bình của precision tại hạng của từng gold, cắt ở hạng 500. Độ đo này tính tới mọi gold, không chỉ gold đầu tiên.
- **nDCG@10 (judge).** Độ đo xếp hạng dùng điểm 0 đến 3 do LLM judge chấm cho 10 node đầu.
- **McNemar.** Kiểm định cho độ đo đúng/sai như Hit@10. Nó chỉ dùng các instance mà hai hệ thống cho kết quả khác nhau. Ví dụ có 71 instance chỉ hệ thống mới trúng, và 19 instance chỉ AST trúng.
- **Bootstrap theo khối snapshot.** Cách tính khoảng tin cậy bằng việc lấy mẫu lại theo snapshot thay vì theo instance. Lý do là các instance cùng snapshot dùng chung graph và history, nên chúng không độc lập với nhau.
- **TRisk.** Độ đo rủi ro của Dinçer, Macdonald và Ounis (SIGIR 2014). Phần giảm so với AST bị phạt (1 + α) lần, rồi chia cho sai số chuẩn. TRisk lớn hơn 2 nghĩa là hệ thống tốt hơn AST một cách đáng tin, dù phần giảm đã bị phạt. TRisk nhỏ hơn −2 nghĩa là hệ thống rủi ro hơn AST.

---

## 3. Lộ trình và trạng thái

| Giai đoạn | Việc | Trạng thái |
|---|---|---|
| 0 | Viết đúng những gì đã chứng minh được trong `research_context.md` | Xong, chưa commit |
| 1.1 | Sửa oracle rồi đếm lại trên 1.006 bản vá và trên cạnh history | Xong trên bản làm việc, chưa áp vào notebook thật |
| 1.2 | Tính lại v3 với oracle đã sửa, xếp hạng tới 500 và quy tắc thống kê thống nhất | Chưa làm |
| 1.3 | Kiểm tra snapshot trên 100 instance | Chưa làm |
| 1.5 | Tìm hiểu bài báo và khả năng lấy dữ liệu cho ISSUE | Xong, đã báo cáo |
| 2 | Hoàn thiện v4 rồi đóng băng | Chưa làm |
| 3 | Xác nhận trên khoảng 8 repo giữ lại từ split train của SWE-bench | Ngoài phạm vi đợt này |
| 4 | Viết luận văn | Ngoài phạm vi đợt này |

---

## 4. Những việc đã xong

### 4.1 Giai đoạn 0

`research_context.md` đã được sửa và chưa commit. Các thay đổi chính như sau.

- Mục 1 ghi ISSUE là nguồn thứ tư, đang còn thiếu.
- Mục 4.2 ghi snapshot là phép xấp xỉ, và liệt kê các lỗi đã biết của oracle.
- Mục 4.4 ghi rõ Hit@10 là any-gold, RR của v3 thực chất là RR@100, và Holm chưa được áp trong `verify-v3`.
- Mục 7.9 đổi tên thành thực nghiệm khám phá. Mục này có kết quả Holm tính lại từ các p đã lưu.
- Mục 8 tách kết luận hẹp và kết luận rộng.
- Mục 9 ghi lộ trình và danh sách hệ thống của v4.
- Mục 11 thêm các quyết định 15 đến 19.

### 4.2 Việc 1.1: sửa oracle

Oracle cũ có ba lỗi. Gold và cạnh history cùng dùng oracle, nên lỗi chung có thể làm HIST trông tốt hơn thực tế.

1. **Đổi tên file.** Diff ghi đường dẫn mới, còn graph của snapshot dùng đường dẫn cũ. Vì vậy oracle cũ không tìm thấy node.
2. **Decorator.** Dòng decorator nằm trước dòng bắt đầu của node, nên thay đổi ở decorator bị bỏ qua. Ví dụ đổi `@property` thành `@cached_property` không được tính là sửa method.
3. **Dòng thêm mới.** Oracle cũ gán khối dòng thêm cho hàm bên cạnh, kể cả khi khối đó là một hàm mới hoàn toàn. Ví dụ chèn hàm `gamma` giữa `alpha` và `beta` bị tính là sửa một hàm có sẵn.

Các thay đổi nằm trong bản làm việc `scratchpad/nb_v4_work.ipynb`. Bản này được tạo bằng `scratchpad/impl/v4_oracle.py <vào> <ra>`. Bản sao lưu của notebook gốc là `scratchpad/nb_backup_before_v4.ipynb`.

- Cell `1dc937a9` có thêm `_src_path` và `_patch_changes`, và có `get_oracle` mới. Hàm mới tính dòng bắt đầu kể cả decorator, xử lý khối dòng thêm theo mức thụt lề, và trả về bảng đổi tên file.
- Hàm `_file_nodes_at` trong `scale-setup` có thêm hai trường `deco_start` và `indent`.
- Cell `hist-build` đổi id trong touch set theo tên file mới. File history đổi tên thành `_history_v2.jsonl`, để Kaggle build lại.

Kết quả kiểm tra như sau.

- `impl/test_oracle_cases.py` có 12 ca tự dựng. Oracle mới đạt cả 12 ca.
- `impl/audit_oracle.py` chạy trên 1.006 instance test. Gold đổi ở 44 instance (Django 30, SymPy 14). Có 81 node được thêm và 29 node sai bị bỏ.
- `impl/audit_hist.py` chạy trên 1.000 commit lấy mẫu mỗi repo. Touch set đổi ở 48 trên 713 commit Django và 67 trên 914 commit SymPy. Bộ lọc "sửa từ 1 đến 50 hàm/lớp" gần như không bị ảnh hưởng.

### 4.3 Việc 1.5: tìm hiểu nguồn ISSUE

Báo cáo đầy đủ đã được gửi trong hội thoại. Tóm tắt các điểm dùng cho thiết kế như sau.

- **BugLocator** (Zhou, Zhang, Lo, ICSE 2012) cho công thức SimiScore(f) = Σ sim(b, b′) / |Fix(b′)|. Tổng chạy qua mọi báo cáo cũ b′ đã được sửa ở f, và không có ngưỡng tương đồng. Trọng số tốt nhất của phần báo cáo cũ là 0,2 đến 0,3. BLUiR+ cộng phần này vào BLUiR và tăng MAP từ 0,01 đến 0,02 trên cả 4 dự án. Tôi chỉ đọc được bài này qua nguồn thứ cấp, vì không lấy được bản PDF gốc.
- **Lingxi** (arXiv 2510.11838) lọc kho issue cũ theo thời gian tạo. Ablation cho thấy cặp (issue, bản vá) thô chỉ thêm khoảng 0,6 điểm Pass@1 cho agent sửa code.
- **ExpeRepair** (arXiv 2506.10484) thấy BM25 tốt hơn hoặc ngang embedding khi tìm ví dụ cũ. Số ví dụ tốt nhất là 3.
- **OM-RAG** (arXiv 2607.21911) cho thấy lịch sử sự cố giúp chẩn đoán hơn tài liệu. Tuy vậy, bài không lọc theo thời gian, nên có thể lấy trúng issue trùng lặp xảy ra sau.

Khả năng lấy dữ liệu đã được đo trên máy.

- **Django** không cần token. Trac cho tải CSV hàng loạt, mỗi lần 500 ticket, mất khoảng 1,1 giây. Trong bản clone đầy đủ có 23.678 commit chứa "Fixed #N", nhắc tới 16.826 ticket. Mức trần của ISSUE trên 713 instance test Django là 92,0%. Mức trần ở đây là tỷ lệ instance có ít nhất một commit cũ gắn ticket đã sửa gold. Số này là giới hạn trên, vì phép đo chưa lọc theo quan hệ tổ tiên và chưa loại ticket của chính instance.
- **SymPy** cần GitHub API với token. Liên kết từ PR tới issue chủ yếu nằm trong phần mô tả của PR. Trong mẫu 40 PR, 23 PR (57,5%) có "Fixes/Closes #N".

---

## 5. Việc 1.2 và 1.3

### 5.1 Việc 1.2: tính lại v3 với oracle đã sửa

**Mục đích.** Việc này báo đúng hiệu ứng của v3, sau khi gold được tính bằng oracle đã sửa.

**Cách làm.** Cell `v4-run` chạy lại phần truy hồi với các thay đổi sau.

- Gold và history dùng oracle mới. History được build lại thành `_history_v2.jsonl`.
- `SCALE_TOPK` và `LIST_K` tăng từ 100 lên 500. Nhờ vậy MRR và MAP được tính tới hạng 500.
- Kết quả ghi vào `scale_rows_v4.jsonl` trong `V4_DIR`. File `scale_rows_v3.jsonl` không bị đè.

Cell `verify-v4` trình bày kết quả theo đúng cách ở mục 6.8.

**Điểm dừng.** Nếu kết luận hẹp đổi chiều, thì dừng lại để tìm nguyên nhân. Kết luận hẹp là Top@10 của DOC+HIST v3 cao hơn AST.

**Chi phí.** Việc này chạy trên Kaggle và không gọi LLM. `hist-build` mất khoảng 1,5 giờ. `v4-run` mất vài giờ.

### 5.2 Việc 1.3: kiểm tra snapshot

**Mục đích.** Việc này đo sai lệch do snapshot gây ra. Kết quả quyết định giai đoạn 3 có phải build graph tại đúng base commit hay không.

**Cách làm.** Cell `snapshot-audit` lấy ngẫu nhiên 100 instance trong 1.186 instance, chia theo tỷ lệ của hai repo. Như vậy có 69 instance Django và 31 instance SymPy, với seed cố định. Với mỗi instance, cell build graph và history tại đúng base commit, rồi so với snapshot ở ba điểm.

1. Phần gold bị mất. Đây là các gold có trong graph tại base commit nhưng không có trong snapshot.
2. Khoảng trống history. Đây là các commit nằm giữa snapshot và base commit đã sửa gold.
3. Chênh lệch Hit@10 của AST giữa hai graph.

**Điểm dừng.** Tôi chọn hai ngưỡng. Thứ nhất, Hit@10 của AST chênh từ 3 điểm % trở lên. Ngưỡng này xấp xỉ mức tăng của DOC trong v3, nên sai lệch lớn hơn mức đó có thể che hiệu ứng của một nguồn. Thứ hai, khoảng trống history chứa commit sửa gold ở từ 10% instance trở lên. Nếu vượt một trong hai ngưỡng, giai đoạn 3 phải dùng graph tại đúng base commit.

**Chi phí.** Việc này cần build khoảng 100 graph trên Kaggle. Tôi sẽ đo thời gian build một graph trên máy trước, rồi báo tổng thời gian ước tính.

---

## 6. Giai đoạn 2: thiết kế v4

### 6.1 Các hệ thống so sánh

| Hệ thống | Nguồn dùng | Vai trò |
|---|---|---|
| AST | Code | Mốc so sánh |
| +DOC | Code, DOC | Một nguồn so với AST |
| +HIST | Code, HIST mới | Một nguồn so với AST |
| +ISSUE | Code, ISSUE | Một nguồn so với AST |
| +ALL | Code, DOC, HIST, ISSUE | Mọi nguồn so với AST |
| ALL−DOC | Code, HIST, ISSUE | Bỏ bớt DOC |
| ALL−HIST | Code, DOC, ISSUE | Bỏ bớt HIST |
| ALL−ISSUE | Code, DOC, HIST | Bỏ bớt ISSUE |

Ba hệ thống bỏ bớt một nguồn chỉ tốn bước trộn, và không gọi thêm LLM. Chúng trả lời câu hỏi "mỗi nguồn có còn thêm giá trị khi đã có các nguồn còn lại hay không".

### 6.2 Câu hỏi kiểm chứng

| Câu hỏi | So sánh | Ý nghĩa |
|---|---|---|
| Q1 | +DOC so với AST | DOC có giúp hay không |
| Q2 | +HIST so với AST | HIST có giúp hay không |
| Q3 | +ISSUE so với AST | ISSUE có giúp hay không |
| Q4 | +ALL so với AST | Đa nguồn có tốt hơn chỉ dùng code hay không |
| Q5 | +ALL so với ALL−DOC | DOC còn thêm giá trị khi đã có HIST và ISSUE hay không |
| Q6 | +ALL so với ALL−HIST | HIST còn thêm giá trị khi đã có DOC và ISSUE hay không |
| Q7 | +ALL so với ALL−ISSUE | ISSUE còn thêm giá trị khi đã có DOC và HIST hay không |

Q4 là câu hỏi chính của đề tài.

Độ đo, cách trình bày số liệu và kiểm định nằm ở mục 6.8. Độ đo gồm Top@1, Top@5, Top@10, MRR, MAP và Acc@10, cùng nDCG@10 theo judge. Mỗi câu hỏi có một bảng thay đổi theo từng instance và một kiểm định McNemar cho Top@10. Các bảng của từng nguồn được đặt cạnh nhau.

### 6.3 Bước 0 cũ: không còn cần

Bước 0 trước đây chọn F = 5, m = 10 và C = 1.500 trên tập test. F là số file đầu lấy từ xếp hạng AST, m là số commit giữ lại cho mỗi file, còn C là số token tối đa của diff cho mỗi commit. Ba tham số này không còn được dùng.

- F và m bị bỏ, vì HIST theo Locus ở mục 6.4 chấm mọi hunk trong lịch sử.
- C bị bỏ cùng thiết kế `hist-llm`. C chỉ dùng để giới hạn input của lần gọi LLM, và LLM chỉ là judge. Judge phải thấy toàn văn, nên diff không bị cắt.

Vì vậy cell `step0-dev` không còn cần.

### 6.4 HIST mới

HIST xếp hạng hàm/lớp theo Locus (Wen, Wu, Cheung, ASE 2016). LLM không tham gia, vì LLM chỉ là judge. Nguồn đã đọc toàn văn gồm mục 3, RQ1 và RQ4 của Locus, cùng mục 3.2 và 3.5 của AmaLgam (Wang, Lo, ICPC 2014). Bài của Sisman và Kak không được dùng, vì chỉ có bản patent và thiếu công thức.

**Vì sao chọn Locus.** Locus là bài duy nhất trong artifact so khớp nội dung history với báo cáo lỗi. Mỗi hunk là một tài liệu, gồm dòng bị đổi, dòng ngữ cảnh và commit message. Đây chính là bước "đọc title, message và diff" của quy trình debug, nhưng không cần LLM. Phần history của AmaLgam không đọc issue. Nó chỉ cho điểm theo các commit sửa lỗi trong cửa sổ 15 ngày, và cửa sổ này là chỗ bị rò rỉ mà bản tái lập ABLoTS đã chỉ ra. Thành phần Boosting của Locus dùng cùng thuật toán của Google nhưng không có cửa sổ. Theo RQ1 của Locus, chấm theo hunk tốt hơn chấm cả file ở cả 6 dự án, ví dụ MAP của SWT tăng từ 0,382 lên 0,630. Theo RQ4, thành phần CE tăng MAP 23,6%, và lịch sử sửa lỗi tăng thêm 5,1%.

**Công thức của Locus, giữ nguyên.**

1. Tài liệu là một hunk h, gồm dòng bị đổi, dòng ngữ cảnh và commit message.
2. NL(b, h) = cos(b_nl, h_nl). Token được tách theo định danh, bỏ stop word tiếng Anh và từ khóa Python, rồi đưa về gốc bằng Porter. Trọng số là w_td = (log f_td + 1) × log(N / n_t). Ở đây f_td là số lần từ t xuất hiện trong tài liệu d, N là số tài liệu, n_t là số tài liệu chứa t.
3. CE(b, h) = cos(b_ce, h_ce). Token CE là tên module, lớp và hàm, giữ nguyên không tách. Chỉ giữ những từ trông giống code và khớp một tên trong graph của snapshot.
4. α = min(1, λ × số tên code trong issue / số token đã tách của issue), với λ = 5.
5. Fix(s) = Σ_i 1 / (1 + e^(−12·t_i + 12)), với t_i là thời điểm của commit sửa lỗi thứ i, chuẩn hóa về [0, 1]. Trọng số là β₁ = 0,1.
6. score(b, s) = max_i {NL(b, h_i) + α·CE(b, h_i)} + β₁·Fix(s).

**Chuyển đổi sang mức hàm/lớp.** Các chỗ dưới đây không có trong bài.

- A1. File s được thay bằng hàm/lớp f. H(f) là các hunk có dòng bị đổi nằm trong f, theo oracle mới, giống cách tính touch set. Điểm là score(b, f) = max_{h∈H(f)} {NL + α·CE} + β₁·Fix(f). Locus đại diện file bằng hunk tốt nhất, và quy tắc đó được áp nguyên cho hàm.
- A2. Commit sửa lỗi cho Fix(f) là đơn vị có message khớp `fix|bug`, theo quy tắc 1 của AmaLgam. Locus chỉ dẫn heuristic mà không ghi cụ thể. Trong file history, 58% đơn vị của Django và 26% đơn vị của SymPy khớp quy tắc này.
- A3. Locus đặt 0 là ngày phát hành của code base, 1 là lúc báo lỗi. Issue của SWE-bench nằm trên nhánh phát triển, nên 0 là đơn vị cũ nhất của file history, còn 1 là `created_at` của instance.
- A4. Tập tài liệu là hunk của các đơn vị là tổ tiên của snapshot. IDF được tính riêng cho từng snapshot. File history bắt đầu từ tháng 8/2012 (Django) và tháng 7/2013 (SymPy), nên commit cũ hơn không có.
- A5. Chỉ lấy file `.py` có trong graph, dùng `git diff -U3 -w`, và bỏ hunk chỉ đổi comment. Bài không ghi cách nhận ra hunk chỉ định dạng lại code, nên bước đó không làm.
- A6. Query là `problem_statement`. SWE-bench tách phần gợi ý (`hints_text`) ra riêng, giống việc Locus không dùng phần thảo luận của developer.
- A7. Locus nhận ra từ trông giống code bằng heuristic của Meng và cộng sự, nhưng không ghi chi tiết. Cell coi một từ là giống code khi nó có dấu `_` hoặc `.`, có chữ hoa sau ký tự đầu, nằm trong dấu backtick, hoặc đứng ngay trước `(`.

**Không có tham số nào phải chọn bằng dữ liệu.** λ = 5 và β₁ = 0,1 lấy từ bài. Locus chấm mọi hunk, nên không cần F và m. Vì vậy cell `step0-dev` ở mục 6.3 không còn cần.

**Cài đặt.** Cell `hist-proc` lấy `git diff -U3 -w` của mọi đơn vị có touch set khác rỗng, tách thành hunk, rồi gán mỗi hunk cho các hàm/lớp mà nó đổi bằng oracle mới. Kết quả ghi vào `history/<repo>_hunks_v2.jsonl`, ước tính 65 nghìn hunk (Django) và 55 nghìn hunk (SymPy). File history và graph không đổi.

**Output.** Mỗi dòng của `scale_rows_v4.jsonl` có thêm `doc_ids_hist_locus`, `doc_score_hist_locus`, `doc_r_hist_locus` và `doc_gold_hist_locus`, theo cùng dạng mà `fused_multi` đọc. Danh sách giữ 500 hàm/lớp đầu, bằng độ sâu của xếp hạng AST. Hàm/lớp không có trong graph của snapshot bị bỏ. Mỗi dòng cũng ghi hunk tốt nhất của 10 hàm/lớp đầu, để judge chấm.

Thiết kế `hist-llm` cũ đã bị bỏ. Trong thiết kế đó, LLM viết ý đồ của từng commit, nêu giả thuyết nguyên nhân lỗi, rồi liệt kê hàm/lớp để trộn với AST. Thiết kế này trái với vai trò của LLM, vì LLM chỉ là judge.

### 6.5 ISSUE

Cell `issue-fetch` tải dữ liệu. Cell `issue-index` dựng chỉ mục và tính danh sách xếp hạng cho từng instance.

**Tài liệu.** Mỗi tài liệu là một báo cáo lỗi cũ đã được sửa.

- Với Django, tài liệu là summary và description của ticket Trac có resolution là fixed. Dữ liệu được tải bằng CSV hàng loạt từ `code.djangoproject.com/query`, mỗi trang 500 ticket.
- Với SymPy, tài liệu là title và body của issue GitHub đã đóng. Dữ liệu được tải qua endpoint `/repos/sympy/sympy/issues?state=closed`. Endpoint này trả về cả issue lẫn PR, kèm body. Cell cần biến thường `GITHUB_TOKEN = "..."` trong `v4-config`. Không có token thì GitHub chỉ cho 60 lượt gọi mỗi giờ, và việc tải mất gần 5 giờ.

**Liên kết từ báo cáo tới hàm/lớp.**

- Với Django, ticket N nối tới các commit có "Fixed #N" hoặc "Refs #N" trong message. Biểu thức chính quy bắt cả dạng danh sách như "Fixed #123, #456".
- Với SymPy, issue N nối tới PR có từ khóa đóng issue của GitHub trong body. Các từ khóa là close, closes, closed, fix, fixes, fixed, resolve, resolves và resolved. PR nối tới đơn vị history "Merge pull request #PR". Các commit lẻ có "fixes #N" trong message cũng được dùng.
- Fix(b′) là hợp các touch set hàm/lớp của các commit đã nối. Các touch set này do `hist-build` tính bằng oracle đã sửa.

BugLocator cũng lấy liên kết từ số lỗi trong commit message.

**Điểm số.** Điểm của một hàm/lớp f là SimiScore(f) = Σ sim(b, b′) / |Fix(b′)|. Tổng chạy qua mọi báo cáo cũ b′ có f thuộc Fix(b′). Trong đó sim là cosine TF-IDF giữa issue hiện tại và báo cáo cũ. Không có ngưỡng tương đồng. Đây đúng là công thức của BugLocator, chỉ đổi mức file thành mức hàm/lớp. Nhờ vậy kết quả so được với BugLocator, AmaLgam và BLUiR+.

Ví dụ, issue mới giống báo cáo A với sim = 0,3, và A đã sửa hai hàm X và Y. Issue mới cũng giống báo cáo B với sim = 0,2, và B chỉ sửa X. Khi đó SimiScore(X) = 0,3/2 + 0,2/1 = 0,35, còn SimiScore(Y) = 0,15.

Cách tách từ như sau.

- Văn bản được tách bằng `_tokenize_code` có sẵn trong notebook. Hàm này tách camelCase và giữ chữ số.
- Stop word tiếng Anh bị bỏ, và từ được đưa về gốc bằng Porter stemmer. BugLocator cũng tiền xử lý theo cách này.
- TF dùng dạng log (`sublinear_tf=True`), giống rVSM của BugLocator.
- IDF được tính riêng cho từng snapshot, chỉ trên các báo cáo tạo trước thời điểm của snapshot. Nhờ vậy thống kê từ vựng không chứa báo cáo tương lai.

Tôi chọn TF-IDF cosine thay cho BM25. ExpeRepair thấy BM25 tốt hơn, nhưng đó là khi tìm ví dụ cho bước sửa code, không phải cho bước định vị. Bước này không dùng tóm tắt bằng LLM, vì LLM chỉ là judge.

**Lọc rò rỉ.** Bộ lọc có bốn điều kiện.

1. Báo cáo cũ phải được tạo trước `created_at` của instance ít nhất 1 ngày. Cột Created của Trac không ghi rõ múi giờ, nên khoảng đệm 1 ngày tránh lỗi múi giờ.
2. Commit sửa báo cáo phải là tổ tiên của snapshot. Điều kiện này có sẵn, vì liên kết đi qua đơn vị history của snapshot.
3. Báo cáo của chính instance bị loại. Cell nhận ra nó bằng cách so title đã chuẩn hóa với dòng đầu của problem statement. Commit sửa chính instance không phải tổ tiên của snapshot, nên điều kiện 2 cũng chặn trường hợp này.
4. Báo cáo có Fix(b′) rỗng không đóng góp điểm. Nhờ vậy ticket đóng vì trùng lặp hoặc không sửa cũng không được tính.

OM-RAG chỉ loại bản ghi của chính issue và không lọc theo thời gian. Lingxi và KGCompass lọc theo thời gian tạo. Vì vậy bộ lọc của chúng ta theo Lingxi và KGCompass, và chặt hơn nhờ điều kiện tổ tiên.

**Output.** Mỗi dòng có danh sách hàm/lớp xếp theo SimiScore, ở dạng mà `fused_multi` đọc được. Mỗi dòng cũng có 5 báo cáo cũ có sim cao nhất và Fix không rỗng, để judge chấm. Số 5 bằng số chunk mà DOC dùng. Ngoài ra, cell ghi mức trần ISSUE sau khi lọc, trên cả 1.186 instance.

### 6.6 Trộn

Cell `v4-fusion` trộn các nguồn với AST. Cách trộn chưa chốt. Nó thuộc phần đang tìm hiểu về chấm điểm và xếp hạng sau truy hồi, và sẽ được chọn từ bài báo.

Code hiện có là hàm `fused_multi` của v3. Điểm của node là 1/(60 + hạng AST) + Σ p_s/(60 + vị trí của node trong danh sách của nguồn s), và h node đầu của AST được giữ nguyên vị trí. Lưới của v3 gồm p thuộc {0,05; 0,1; 0,25} và h thuộc {0, 1, 3, 5}. Quy tắc chọn của v3 là `_choose`. Hàm này chỉ xét các cấu hình không làm giảm Top@k ở mọi k thuộc {1, 5, 10, 20}, rồi chọn cấu hình có mức tăng trung bình lớn nhất. Lưới và quy tắc này chưa có bài báo làm cơ sở.

Lưới hiện tại đặt trần cho hiệu ứng của mọi nguồn. Với p = 0,25, một node đứng đầu danh sách của nguồn chỉ vào được top 10 khi hạng AST của nó nhỏ hơn khoảng 38. Yêu cầu đã thống nhất là cách được chọn không tự đặt trần như vậy. RRF gốc của Cormack và cộng sự (SIGIR 2009) dùng trọng số bằng nhau, tức p = 1.

Nếu cách được chọn có tham số phải chọn bằng dữ liệu, thì tham số đó được chọn trên cả 1.186 instance, vì đề tài không tách dev và test.

DOC dùng cạnh Documents hiện tại. Việc sửa cách nối doc với code nằm ở mục 6.10.

### 6.7 Judge v4

Judge v4 có hai loại request. Nhãn được ghi vào thư mục `judge_v4`.

**Node code (`#code2`).** Judge dùng prompt cũ của v3 để so được với v3. Judge chỉ chấm các node mới vào top 10 của một trong 8 hệ thống mà chưa có nhãn ở `judge_v3`. Judge thấy toàn bộ code của node.

**Bằng chứng.** Một prompt chung chấm mọi loại bằng chứng.

- Chunk doc mà DOC dùng, có toàn văn và danh sách node mà chunk nối tới.
- Bằng chứng của HIST là hunk tốt nhất của 10 hàm/lớp đầu trong danh sách HIST, lấy từ `hist_locus_best`. Mỗi bằng chứng có title và message đầy đủ của commit, danh sách hàm/lớp mà commit đã sửa, và diff của hunk đó.
- Báo cáo cũ mà ISSUE dùng, có toàn văn và Fix(b′).

Judge được xem bản vá thật. Mỗi phần tử có hai điểm từ 0 đến 3. Điểm thứ nhất là mức liên quan, điểm thứ hai là mức hữu ích cho việc sửa. Phần tử chỉ cùng file hoặc cùng tính năng thì tối đa được 1 điểm hữu ích. Judge viết lý do trước điểm. Các phần tử được chấm theo danh sách và được xáo thứ tự.

Các lựa chọn này có cơ sở như sau.

- Theo eRAG, nhãn "liên quan" do LLM chấm gần như không tương quan với kết quả cuối. Kendall τ chỉ từ −0,04 đến 0,19.
- Theo Utility judgments, prompt hỏi "hữu ích" tốt hơn prompt hỏi "liên quan", với F1 tăng 30,98% trên NQ. Chấm theo danh sách cũng tốt hơn. LLM nhạy với vị trí, nên cần xáo thứ tự.

Judge thấy toàn văn của mọi phần tử, kể cả DocChunk. Nếu có phần tử dài bất thường, tôi đo phân bố độ dài trong lúc kiểm thử trên máy, rồi báo bạn trước khi đặt bất kỳ giới hạn nào.

Khóa của mỗi nhãn có hash của input. Nhờ vậy nhãn cũ không bị dùng nhầm khi nội dung đã đổi.

### 6.8 Phân tích (`verify-v4`)

Cell `verify-v4` trình bày số liệu cho các câu hỏi ở mục 6.2. Phần phụ trợ được giữ đơn giản, nên cell không tính khoảng tin cậy, TRisk hay hiệu chỉnh cho nhiều kiểm định.

**Bảng 1. Độ đo chính.** Mỗi hệ thống có một hàng. Bảng có ba phần: gộp hai repo, riêng Django và riêng SymPy.

| Độ đo | Ý nghĩa | Cơ sở |
|---|---|---|
| Top@1, Top@5, Top@10 | Tỷ lệ instance có ít nhất một gold trong N vị trí đầu. Trước đây độ đo này được gọi là Hit@k. | Locus và AmaLgam, đã đọc toàn văn |
| MRR | Trung bình của 1 chia hạng của gold đầu tiên. Độ đo này cho biết khả năng tìm phần tử đúng đầu tiên. | Locus, đã đọc toàn văn |
| MAP | Trung bình của độ chính xác tại hạng của từng gold. Độ đo này cho biết khả năng tìm mọi gold. | Locus, đã đọc toàn văn |
| Acc@10 | Tỷ lệ instance có mọi gold nằm trong top 10 | LocAgent và SweRank, mới đọc ở mức tóm tắt |

MAP quan trọng vì 45% instance Django và 54% instance SymPy có hơn một gold. Hạng được tính tới 500, bằng độ sâu của xếp hạng AST. Gold nằm ngoài hạng 500 đóng góp 0 vào MRR và MAP.

**Bảng 2. Thay đổi theo từng instance.** Với mỗi câu hỏi, bảng so hai hệ thống của câu hỏi đó trên từng instance, theo hạng của gold tốt nhất. Bảng ghi số và tỷ lệ instance tốt hơn, kém hơn và không đổi. Bảng được tách theo độ khó của AST, gồm ba nhóm: gold đã ở top 10, gold ở hạng 11 đến 100, và gold ngoài hạng 100. Bảng của các nguồn được đặt cạnh nhau.

**Phân tích bổ sung.**

1. **Đóng góp của từng thành phần trong HIST.** Phân tích này làm theo RQ4 của Locus. Hệ thống +HIST được chạy với ba cấu hình: chỉ NL, NL+CE, và NL+CE+Fix. Bảng 1 được tính cho từng cấu hình. Kết quả cho biết mức tăng đến từ chữ trong message và diff, từ tên code, hay từ lịch sử sửa lỗi.
2. **Tách theo việc issue có nêu sẵn tên gold hay không.** Kochhar, Tian và Lo (ASE 2014) cho thấy báo cáo lỗi nêu sẵn vị trí lỗi làm kết quả định vị cao lên đáng kể. Bản làm lại của Widyasari và cộng sự trên 2.913 báo cáo lỗi Python cho kết quả tương tự. Hai bài này mới được đọc ở mức tóm tắt. Bảng 1 và Bảng 2 được tính riêng cho hai nhóm issue.
3. **Một kiểm định McNemar cho Top@10 ở mỗi câu hỏi.** Kiểm định dùng hai con số đã có ở Bảng 2. Con số thứ nhất là số instance chỉ hệ thống thứ nhất có gold trong top 10. Con số thứ hai là số instance chỉ hệ thống thứ hai có gold trong top 10. Locus dùng kiểm định Mann-Whitney U, nhưng kiểm định đó dành cho hai mẫu độc lập. Ở đây hai hệ thống được so trên cùng các instance, nên McNemar là phép phù hợp cho dữ liệu ghép cặp.

**Các bảng giữ nguyên từ kế hoạch trước.**

- nDCG@10 theo judge của từng hệ thống, và mức hữu ích của bằng chứng theo nguồn, lấy từ judge bằng chứng.
- Mức trần và độ phủ liên kết của ISSUE ở từng repo.

### 6.9 Đóng băng và manifest

Trước khi xem kết quả của v4, tôi viết sẵn bản kế hoạch phân tích. Bản này gồm 8 hệ thống, 7 câu hỏi, các độ đo, các kiểm định và các quy tắc chọn tham số.

Cell `manifest` ghi các thông tin sau vào `V4_DIR/manifest.json`.

- Hash của mã nguồn từng cell v4. Notebook không được commit vì còn API key, nên hash cell thay cho commit hash.
- Hash của từng prompt, tên model và cấu hình thinking.
- Hash của input cho từng request judge.
- Hash của file history, file issue và `scale_rows_v4.jsonl`.
- Các giá trị p và h đã chọn.

Giai đoạn 3 chỉ được chạy với đúng luồng xử lý đã ghi trong manifest.

### 6.10 Sửa cách nối doc với code

Lộ trình yêu cầu việc này phải xong **trước** khi đóng băng. Nếu sửa sau khi đã xem kết quả trên repo mới, thì đó là rò rỉ.

Hiện có hai vấn đề đã đo được.

- Chunk thường chỉ nối tới lớp, thay vì method được nói tới. Ví dụ `.. method:: filter(*args, **kwargs)` trong `querysets.txt` thuộc về `.. class:: QuerySet` đã khai báo trước đó.
- Có chunk nhắc tên gold nhưng không có cạnh.

Việc này chưa có thiết kế chi tiết. Tôi sẽ viết thiết kế riêng, có cơ sở từ bài báo, sau khi xong các cell HIST và ISSUE. Thiết kế đó được gửi để bạn xác nhận trước khi làm.

---

## 7. Cách tổ chức notebook

Mọi cell mới nằm trong một phần v4 riêng ở cuối notebook. Nhờ vậy v3 vẫn chạy lại được.

- Phần v4 dùng đường dẫn riêng, gồm `V4_DIR`, `scale_rows_v4.jsonl` và `judge_v4`.
- `SCALE_RESULTS` của v3 không bị đổi.
- Dòng gọi judge trong `judge-run` được chặn bằng `RUN_V3_JUDGE = False`, để không chạy lại judge v3.
- Dòng `GOOGLE_API_KEY` giữ nguyên. `GITHUB_TOKEN` là biến thường trong `v4-config`.

| Cell | Việc | Ghi vào |
|---|---|---|
| `v4-md` | Mô tả phần v4 | |
| `v4-config` | Đường dẫn, tham số, `GITHUB_TOKEN`, cờ chạy | |
| `v4-run` | Truy hồi lại với oracle mới, xếp hạng tới 500 | `scale_rows_v4.jsonl` |
| `snapshot-audit` | Kiểm tra snapshot trên 100 instance | `V4_DIR/snapshot_audit.json` |
| `issue-fetch` | Tải ticket Trac và issue/PR GitHub | `V4_DIR/issues/` |
| `issue-index` | Liên kết, lọc, TF-IDF, SimiScore | Thêm cột ISSUE vào `scale_rows_v4.jsonl` |
| `hist-proc` | Dựng chỉ mục hunk, rồi xếp hạng hàm/lớp theo Locus (mục 6.4) | `history/<repo>_hunks_v2.jsonl`, thêm cột HIST vào `scale_rows_v4.jsonl` |
| `v4-fusion` | Trộn các nguồn với AST cho 8 hệ thống. Cách trộn chưa chốt (mục 6.6) | `V4_DIR/fusion.json` |
| `judge-v4` | Tạo request `#code2` và bằng chứng, gửi batch, đọc nhãn | `judge_v4/` |
| `verify-v4` | Q1 đến Q7 và các bảng phân tích | Output của cell |
| `manifest` | Ghi hash và tham số | `V4_DIR/manifest.json` |

Các thành phần có sẵn được dùng lại gồm `HIST[repo]["units"]`, `_git`, `_tokenize_code`, `get_oracle`, `_file_nodes_at`, `fused_multi`, `_choose`, `run_batch`, `parse_judgment`, `_request` và `_items`.

---

## 8. Kiểm thử trên máy

Mọi cell được thử trên máy trước khi áp vào notebook thật. Harness được dựng theo mẫu `scratchpad/test_v3.py`.

- Client Gemini và embedding đều là bản giả, nên không gọi API thật.
- Dữ liệu gồm graph `838e432e` (Django) và `9bf73cc2` (SymPy), bản clone `django_full` và `sympy_full`, và `swe_full_test.parquet`.
- Môi trường là venv `D:\tmp\rgvenv`.

Các điểm cần kiểm tra như sau.

- Hàm/lớp của từng hunk khớp với touch set tính bằng oracle mới, và mọi hunk được dùng đều thuộc đơn vị là tổ tiên của snapshot.
- Tên hàm/lớp trong danh sách xếp hạng của HIST khớp với graph.
- Liên kết ISSUE không chứa báo cáo tạo sau instance, và không chứa báo cáo của chính instance.
- `fused_multi` với một nguồn cho kết quả trùng `fused_list`.
- Request judge có đủ toàn văn của từng phần tử, và khóa có hash của input.
- `verify-v4` chạy hết trên dữ liệu giả mà không lỗi.
- `test_oracle_cases.py` vẫn đạt 12 trên 12 ca.

Sau khi harness chạy đạt, tôi áp các cell vào `colab/build_graph_flask_colab.ipynb`. Notebook được ghi lại ở dạng JSON gọn, với `ensure_ascii=False` và `separators=(',',':')`, và không có dòng trống ở cuối.

---

## 9. Chạy trên Kaggle

Bạn là người chạy trên Kaggle. Kaggle giới hạn 12 giờ mỗi lần chạy, và xóa `/kaggle/working` khi mở phiên mới. Vì vậy tôi đề xuất ba lượt.

| Lượt | Cell | Điểm dừng |
|---|---|---|
| 1 | `v4-config`, `hist-build`, `v4-run`, `hist-proc`. Thêm `issue-fetch` và `issue-index` khi nguồn ISSUE được làm tiếp | Kết luận hẹp của việc 1.2 không đổi chiều |
| 2 | `snapshot-audit` | Kết quả quyết định cách làm của giai đoạn 3 |
| 3 | `v4-fusion`, `judge-v4`, `verify-v4`, `manifest` | Bạn xem kết quả Q1 đến Q7 |

Cell `hist-proc` dựng chỉ mục hunk một lần, mất khoảng 45 phút đến 1 giờ. Chỉ mục được ghi vào `history/`, nên lượt sau dùng lại được nếu file được lưu.

Nhãn của `judge_v3` cần được nạp lại từ một dataset Kaggle trước lượt 3. Nếu không, mọi node code đều bị chấm lại và tốn thêm token.

---

## 10. Chi phí

Các con số dưới đây là ước tính. Chúng sẽ được đo lại khi chạy `hist-proc` và `judge-v4`.

| Phần | Ước tính |
|---|---|
| Judge bằng chứng | Bằng chứng HIST là 10 hunk, mỗi hunk kèm message của commit. Ngoài ra còn bản vá, chunk doc và báo cáo cũ. Số token chưa được đo |
| `hist-proc` | Dựng chỉ mục hunk khoảng 45 phút đến 1 giờ trên Kaggle, chỉ một lần. Không gọi LLM |
| Judge `#code2` | Ít, vì chỉ chấm node mới |
| `issue-fetch` | Django khoảng 1 phút. SymPy vài phút khi có token |

Batch API rẻ hơn gọi thường 50%. Tier 1 giới hạn 10 triệu token đang xếp hàng, nên mỗi batch chỉ gồm request của 150 instance, như `JUDGE_BATCH_INSTANCES` của v3.

---

## 11. Rủi ro và cách xử lý

| Rủi ro | Cách xử lý |
|---|---|
| SymPy chỉ có khoảng 57,5% PR ghi số issue, nên ISSUE yếu hơn ở SymPy | Báo độ phủ liên kết riêng cho từng repo trong `verify-v4` |
| ISSUE và HIST dùng chung commit, nên hai nguồn có thể trùng thông tin | Q6 và Q7 đo phần đóng góp riêng của từng nguồn |
| Oracle vẫn dùng chung cho gold, HIST và ISSUE | Đã kiểm tra ở việc 1.1, và vẫn ghi là mối đe dọa trong luận văn |
| Kaggle xóa file nhãn khi mở phiên mới | Nạp nhãn từ dataset, và mỗi batch được ghi vào `batch_jobs.txt` để không gửi lại |
| Thiết kế v4 dựa trên kết quả test của v3 | Ghi v4 là thực nghiệm khám phá. Phần khẳng định nằm ở giai đoạn 3 |

---

## 12. Quy tắc khi làm

- Chỉ sửa đúng phần được yêu cầu. Mọi bản sửa thêm chỉ được nêu ra để bạn quyết định.
- Trước mỗi việc chạy lâu, tôi báo việc gì, vì sao và mất bao lâu. Trong lúc chạy, tôi báo tiến độ.
- Mỗi quyết định kỹ thuật phải có bài báo làm cơ sở. Số đo của mình chỉ bổ sung.
- Dòng `GOOGLE_API_KEY` giữ nguyên dạng biến thường. Không dùng biến môi trường, secret hay getpass. `GITHUB_TOKEN` cũng là biến thường.
- Không commit hay push notebook khi nó còn API key. Không push `colab/notebook5f48a387d*.ipynb`. Không dùng Google Drive.
- "Document" chỉ có nghĩa là DocChunk.
- Judge phải chấm mọi phần tử được truy hồi với toàn văn, kể cả DocChunk.
- LLM chỉ là judge. Không nguồn nào dùng LLM để tạo xếp hạng.
- Commit luôn được xem cùng diff. Message không kèm diff thì không đủ để đánh giá.

---

## 13. Tài liệu tham khảo

- [BugLocator, bản ghi ở SMU](https://ink.library.smu.edu.sg/sis_research/1531)
- [Slide về BugLocator, Virginia Tech CS6704](https://courses.cs.vt.edu/cs6704/spring17/slides_by_students/CS6704Presentation_ShresthaC.pdf)
- [Lingxi, arXiv 2510.11838](https://arxiv.org/abs/2510.11838)
- [ExpeRepair, arXiv 2506.10484](https://arxiv.org/abs/2506.10484)
- [Leveraging Resolved Incident History (OM-RAG), arXiv 2607.21911](https://arxiv.org/abs/2607.21911)
- [GloBug, arXiv 2101.05862](https://arxiv.org/abs/2101.05862)
- [IncBL, arXiv 2106.07413](https://arxiv.org/abs/2106.07413)
- [AmaLgam: Version History, Similar Report, and Structure](https://www.researchgate.net/publication/261635117_Version_History_Similar_Report_and_Structure_Putting_Them_Together_for_Improved_Bug_Localization)
- Các bài về history, fusion và judge (Locus, ROSE, Sisman và Kak, KGCompass, HAFix, HAFixAgent, HippoRAG, eRAG, Utility judgments) có chi tiết trong artifact [Tổng quan tài liệu RepoGraph](https://claude.ai/artifact/DSWQi3W5KrFzSFPLKynKcL).
