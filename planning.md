# Kế hoạch RepoGraph: từ việc 1.2 đến hết giai đoạn 2

Cập nhật ngày 29/10/2026 (mục 6.18 và 14.18). Trạng thái mới nhất của mục 14 nằm ở mục 14.18. Kết quả của từng lượt chạy nằm ở `experiment_log.md`.

File này gom toàn bộ kế hoạch đang làm vào một chỗ. Nó thay cho file cũ `~/.claude/plans/partitioned-sprouting-stardust.md`. File cũ chỉ có 4 hệ thống và chưa có nguồn ISSUE. Phần mở đầu của file cũ còn ghi sai mục tiêu, vì nó coi quy trình debug là mục tiêu của đề tài.

Phạm vi của đợt này là tới hết giai đoạn 2, theo yêu cầu "hãy implement đến giai đoạn 2". Giai đoạn 3 và 4 chỉ được nêu để thấy toàn cảnh. Từ ngày 27/10/2026, giai đoạn 3 không còn là bước xác nhận trên repo giữ lại (quyết định 58 của `research_context.md`).

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

> Cập nhật 27/10/2026. Kết luận dưới đây theo lượt v4-L7, với RRF gốc và không tham số nào chọn trên dữ liệu. Chi tiết ở mục 8 của `research_context.md` và mục 9 của `experiment_log.md`.

- **Thêm HIST giúp ở mọi độ đo.** Trên 1.187 instance của Django và SymPy, +HIST tăng Top@1 từ 23,8% lên 27,9%, Top@10 từ 55,5% lên 62,4% và MAP từ 0,265 lên 0,309, có ý nghĩa sau Holm.
- **Đủ bốn nguồn cho kết quả hai chiều.** +ALL tăng Top@10 lên 59,6%, nhưng giảm Top@1 còn 19,1% và MAP còn 0,241, đều có ý nghĩa. DOC và ISSUE đứng riêng làm kết quả kém hơn AST ở mọi độ đo.
- **Kết luận rộng chưa được chứng minh.** Câu "dữ liệu đa nguồn nói chung tốt hơn chỉ dùng code" chưa đúng ngay trên hai repo, vì +ALL kém AST ở Top@1 và MAP. Kết quả còn ba giới hạn.
  1. Chỉ có hai repo.
  2. Gold và HIST dùng chung một oracle.
  3. Snapshot chỉ là phép xấp xỉ của trạng thái code lúc issue xảy ra.

Đề tài không chia dữ liệu thành tập dùng để chọn và tập dùng để xác nhận, vì không huấn luyện model (quyết định 58 của `research_context.md`). 10 repo còn lại của tập test là thêm dữ liệu cho cùng một thực nghiệm.

---

## 2. Thuật ngữ

- **Instance.** Một issue trong SWE-bench cùng bản vá thật của nó. Ví dụ `django__django-11099`.
- **Snapshot.** Graph code được build tại một commit đại diện cho một nhóm instance gần nhau về thời gian. Django có 40 snapshot cho 820 instance. SymPy có 46 snapshot cho 366 instance. Commit của snapshot có thể sớm hơn base commit của instance tới 60 ngày. Vì vậy snapshot chỉ là phép xấp xỉ.
- **Gold.** Các hàm và lớp mà bản vá thật đã sửa. Ví dụ bản vá sửa thân hàm `UsernameValidator.__call__`, thì gold là node đó.
- **Oracle.** Hàm `get_oracle` trong notebook. Nó đọc một diff và trả về các hàm/lớp bị sửa. Gold của instance và cạnh Modifies của HIST cùng dùng hàm này.
- **Không tách dev và test.** Ở v2 và v3, 180 instance thuộc SWE-bench Lite là tập dev dùng để chọn tham số, còn 1.006 instance còn lại là tập test. Từ v4, mọi kết quả đều dùng cả 1.186 instance. Từ ngày 27/10/2026, không tham số nào được chọn trên dữ liệu (quyết định 57), và đề tài không chia dữ liệu (quyết định 58).
- **Rò rỉ dữ liệu (leakage).** Hệ thống dùng thông tin mà lúc issue xảy ra chưa thể có. Ví dụ dùng commit đã sửa chính issue đó. Đề tài chống rò rỉ bằng mốc cắt thời gian và điều kiện tổ tiên của snapshot.
- **RRF (Reciprocal Rank Fusion).** Cách gộp nhiều danh sách xếp hạng. Mỗi node nhận điểm 1/(60 + hạng AST), cộng thêm p/(60 + vị trí của node trong danh sách của nguồn). p là trọng số của nguồn. h là số node đầu của AST được giữ nguyên vị trí. Ví dụ, với h = 3, ba node đầu của AST không bao giờ bị đẩy xuống, nên Hit@1 đến Hit@3 không thể giảm. Ở v3, hàm thực hiện là `fused_multi` trong cell `scale-fusion`. Cả hai đã bị bỏ khỏi notebook ngày 27/10/2026. Từ ngày 27/10/2026, cell `v4-fusion` của v4 dùng RRF gốc của Cormack và cộng sự (SIGIR 2009). Trong RRF gốc, mọi danh sách có trọng số 1, và không node nào được giữ cố định.
- **Hit@10 (any-gold).** Tỷ lệ instance có ít nhất một gold trong 10 node đầu. Ví dụ instance có 3 gold, và chỉ 1 gold ở hạng 7. Instance đó vẫn được tính là trúng.
- **Acc@10.** Tỷ lệ instance có mọi gold trong 10 node đầu. Đây là độ đo của LocAgent và SweRank.
- **MRR.** Trung bình của RR trên mọi instance. RR của một instance bằng 1 chia hạng của gold tốt nhất, và bằng 0 khi mọi gold nằm ngoài hạng 500. Ví dụ gold tốt nhất ở hạng 4 thì RR là 0,25.
- **MAP@500.** Trung bình của precision tại hạng của từng gold, cắt ở hạng 500. Độ đo này tính tới mọi gold, không chỉ gold đầu tiên.
- **nDCG@10 (judge).** Độ đo xếp hạng dùng điểm 0 đến 3 do LLM judge chấm cho 10 node đầu. Từ ngày 26/10/2026, độ đo này được thay bằng số node phải đọc (mục 6.13).
- **Số node phải đọc.** Số hàm/lớp mà một người đọc lý tưởng phải đọc trước khi gặp gold. Người đó bắt đầu từ k node đầu của hệ thống, rồi mở rộng dần sang các node kề trên graph code. Ví dụ, top 10 không có gold, còn lớp kề đầu tiên có 40 node và 1 gold. Khi đó số node phải đọc là 10 + 41/2 = 30,5.
- **McNemar.** Kiểm định cho độ đo đúng/sai như Hit@10. Nó chỉ dùng các instance mà hai hệ thống cho kết quả khác nhau. Ví dụ có 71 instance chỉ hệ thống mới trúng, và 19 instance chỉ AST trúng.
- **Bootstrap theo khối snapshot.** Cách tính khoảng tin cậy bằng việc lấy mẫu lại theo snapshot thay vì theo instance. Lý do là các instance cùng snapshot dùng chung graph và history, nên chúng không độc lập với nhau.
- **TRisk.** Độ đo rủi ro của Dinçer, Macdonald và Ounis (SIGIR 2014). Phần giảm so với AST bị phạt (1 + α) lần, rồi chia cho sai số chuẩn. TRisk lớn hơn 2 nghĩa là hệ thống tốt hơn AST một cách đáng tin, dù phần giảm đã bị phạt. TRisk nhỏ hơn −2 nghĩa là hệ thống rủi ro hơn AST.

---

## 3. Lộ trình và trạng thái

| Giai đoạn | Việc | Trạng thái |
|---|---|---|
| 0 | Viết đúng những gì đã chứng minh được trong `research_context.md` | Xong, đã commit ở `1f81c55` |
| 1.1 | Sửa oracle rồi đếm lại trên 1.006 bản vá và trên cạnh history | Xong, đã áp vào notebook ở `1f81c55` và chạy ở lượt 1 trên Kaggle (16/10/2026) |
| 1.2 | Tính lại v3 với oracle đã sửa, xếp hạng tới 500 và quy tắc thống kê thống nhất | Xong ở lượt 1 (cell `v3-recheck`, đã bỏ khỏi notebook ngày 27/10/2026). Kết luận hẹp giữ nguyên: Top@10 tăng từ 55,5% (AST) lên 61,2% (DOC+HIST). Chi tiết ở mục 9.1 của `research_context.md` |
| 1.3 | Kiểm tra snapshot trên 100 instance | Chưa làm |
| 1.5 | Tìm hiểu bài báo và khả năng lấy dữ liệu cho ISSUE | Xong, đã báo cáo |
| 2 | Hoàn thiện v4 | Đang làm. Lượt v4-L7 (27/10/2026) đã chạy với RRF gốc. Xếp hạng node sau hop theo KGCompass (`graph-proc`, mục 6.16) đã cài ngày 28/10/2026 và đã chạy ở v4-L8. Còn việc sửa cách nối doc và chọn ngưỡng |
| 3 | Chạy thêm 10 repo còn lại của tập test, như thêm dữ liệu cho cùng thực nghiệm (quyết định 58) | Code đã cài, chưa chạy |
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

**Mục đích.** Việc này đo sai lệch do snapshot gây ra. Kết quả quyết định các lượt chạy sau có phải build graph tại đúng base commit hay không.

**Cách làm.** Cell `snapshot-audit` lấy ngẫu nhiên 100 instance trong 1.186 instance, chia theo tỷ lệ của hai repo. Như vậy có 69 instance Django và 31 instance SymPy, với seed cố định. Với mỗi instance, cell build graph và history tại đúng base commit, rồi so với snapshot ở ba điểm.

1. Phần gold bị mất. Đây là các gold có trong graph tại base commit nhưng không có trong snapshot.
2. Khoảng trống history. Đây là các commit nằm giữa snapshot và base commit đã sửa gold.
3. Chênh lệch Hit@10 của AST giữa hai graph.

**Điểm dừng.** Tôi chọn hai ngưỡng. Thứ nhất, Hit@10 của AST chênh từ 3 điểm % trở lên. Ngưỡng này xấp xỉ mức tăng của DOC trong v3, nên sai lệch lớn hơn mức đó có thể che hiệu ứng của một nguồn. Thứ hai, khoảng trống history chứa commit sửa gold ở từ 10% instance trở lên. Nếu vượt một trong hai ngưỡng, các lượt chạy sau phải dùng graph tại đúng base commit.

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

**Output.** Mỗi dòng của `scale_rows_v4.jsonl` có thêm `doc_ids_hist_locus`, `doc_score_hist_locus`, `doc_r_hist_locus` và `doc_gold_hist_locus`, theo cùng dạng mà `fused_multi` đọc. Danh sách giữ 500 hàm/lớp đầu, bằng độ sâu của xếp hạng AST. Hàm/lớp không có trong graph của snapshot bị bỏ. Mỗi dòng cũng ghi hunk tốt nhất của 10 hàm/lớp đầu, để judge chấm. Số lượng cố định này sẽ được thay bằng ngưỡng (mục 6.11).

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

**Output.** Mỗi dòng có danh sách hàm/lớp xếp theo SimiScore, ở dạng mà `fused_multi` đọc được. Mỗi dòng cũng có 5 báo cáo cũ có sim cao nhất và Fix không rỗng, để judge chấm. Số 5 bằng số chunk mà DOC dùng. Số lượng cố định này sẽ được thay bằng ngưỡng (mục 6.11). Ngoài ra, cell ghi mức trần ISSUE sau khi lọc, trên cả 1.186 instance.

### 6.6 Trộn

> Cập nhật 22/10/2026: cách trộn đã chốt là RRF có trọng số theo nguồn, chọn bằng kiểm định chéo 5 phần theo MAP. RRF trọng số bằng nhau được giữ làm đối chứng. Lý do và kết quả nằm ở mục 14.12 và ở `experiment_log.md`.
>
> Cập nhật 27/10/2026. Việc chọn trọng số bằng kiểm định chéo bị bỏ, vì nó chọn tham số trên chính dữ liệu của đề tài. Cell `v4-fusion` dùng RRF gốc của Cormack và cộng sự (SIGIR 2009), với trọng số bằng nhau và k = 60. Chi tiết ở mục 8 của `pipeline_design.md`.

Cell `v4-fusion` trộn các nguồn với AST. Cách trộn đã chốt ngày 27/10/2026 là RRF gốc, theo ghi chú ở trên. Các đoạn dưới đây mô tả thiết kế trước ngày đó.

Code hiện có là hàm `fused_multi` của v3. Điểm của node là 1/(60 + hạng AST) + Σ p_s/(60 + vị trí của node trong danh sách của nguồn s), và h node đầu của AST được giữ nguyên vị trí. Lưới của v3 gồm p thuộc {0,05; 0,1; 0,25} và h thuộc {0, 1, 3, 5}. Quy tắc chọn của v3 là `_choose`. Hàm này chỉ xét các cấu hình không làm giảm Top@k ở mọi k thuộc {1, 5, 10, 20}, rồi chọn cấu hình có mức tăng trung bình lớn nhất. Lưới và quy tắc này chưa có bài báo làm cơ sở.

Lưới hiện tại đặt trần cho hiệu ứng của mọi nguồn. Với p = 0,25, một node đứng đầu danh sách của nguồn chỉ vào được top 10 khi hạng AST của nó nhỏ hơn khoảng 38. Yêu cầu đã thống nhất là cách được chọn không tự đặt trần như vậy. RRF gốc của Cormack và cộng sự (SIGIR 2009) dùng trọng số bằng nhau, tức p = 1.

Cách trộn đã chốt không có tham số nào phải chọn bằng dữ liệu (quyết định 57).

DOC dùng cạnh Documents hiện tại. Việc sửa cách nối doc với code nằm ở mục 6.10.

### 6.7 Judge v4

> Cập nhật 21/10/2026: số bằng chứng được chấm, trường loại thông tin và request đủ thông tin được chốt lại ở mục 6.12.
>
> Cập nhật 22/10/2026: phần bằng chứng đã cài và đã chạy (lượt v4-L4). Bằng chứng HIST lấy từ `hist_cand`, tức 10 hunk có NL + α·CE cao nhất, thay cho `hist_locus_best`. Hunk của commit sửa hơn 50 hàm/lớp bị bỏ khỏi `hist_cand`.
>
> Cập nhật 26/10/2026: judge chỉ chấm bằng chứng. `#code2` bị bỏ, judge không viết lý do, và mức thinking là MINIMAL. Chi tiết ở mục 6.13.

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

**Loại thông tin (thêm ngày 18/10/2026).** Mỗi phần tử bằng chứng có thêm một trường ghi loại thông tin mà nó cung cấp. Danh sách loại chưa chốt (mục 6.11).

### 6.8 Phân tích (`verify-v4`)

> Cập nhật 21/10/2026: độ đo và kiểm định được chốt lại ở mục 6.12, thay cho phần tương ứng ở đây.

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

- Mức hữu ích của bằng chứng theo nguồn, lấy từ judge bằng chứng. nDCG@10 theo judge được thay bằng số node phải đọc và độ sâu tới gold từ ngày 26/10/2026 (mục 6.13).
- Mức trần và độ phủ liên kết của ISSUE ở từng repo.

### 6.9 Đóng băng và manifest

Trước khi xem kết quả của v4, tôi viết sẵn bản kế hoạch phân tích. Bản này gồm 8 hệ thống, 7 câu hỏi, các độ đo, các kiểm định và các quy tắc chọn tham số.

Cell `manifest` ghi các thông tin sau vào `V4_DIR/manifest.json`.

- Hash của mã nguồn từng cell v4. Notebook không được commit vì còn API key, nên hash cell thay cho commit hash.
- Hash của từng prompt, tên model và cấu hình thinking.
- Hash của input cho từng request judge.
- Hash của file history, file issue và `scale_rows_v4.jsonl`.
- Cách trộn và hằng số k. Từ ngày 27/10/2026, cách trộn là RRF gốc, nên không còn trọng số nào được chọn.
- Từ ngày 27/10/2026, khóa của mỗi cell trong manifest là số thứ tự trong `In` cộng dòng đầu của cell, để hai cell cùng dòng đầu không đè nhau.

Manifest ghi code và cấu hình của từng lượt, để biết kết quả do code nào tạo ra. Phương pháp đã chốt không đổi chỉ vì kết quả xấu.

Hash của cell lấy từ biến `In` của IPython. Ở lượt v4-L6, `In` rỗng, nên manifest ghi 0 cell. Ở lượt v4-L7, manifest ghi đủ 31 cell. Nguyên nhân của lượt v4-L6 chưa rõ, và manifest không báo lỗi khi `In` rỗng.

### 6.10 Sửa cách nối doc với code

Theo quyết định 58, việc này không phải là điều kiện để chạy thêm repo. Khi cách nối doc đổi, mọi repo được chạy lại với cách nối mới.

> Cập nhật 27/10/2026. Tiêu chí bên dưới được viết cho cách trộn có trọng số, nên câu "trọng số DOC vẫn ở đáy lưới" không còn áp dụng được. Với RRF gốc (lượt v4-L7), +DOC kém AST có ý nghĩa ở mọi độ đo. Tiêu chí cho RRF gốc cần được chốt trước khi sửa cách nối.

**Lý do (lượt v4-L5).** Thêm DOC khi đã có HIST và ISSUE làm Top@1 giảm 2,0 điểm, MRR và MAP giảm có ý nghĩa (Q5), dù trọng số của DOC đã ở mức nhỏ nhất của lưới (0,05). Theo khung lập luận, tác động âm là lỗi phương pháp.

**Hiện trạng đo được (23/10/2026).** Đo trên snapshot Django `838e432e` và SymPy `9bf73cc2` bằng đúng code của cell `PqDgRg_1mNuK`. Phép đo tái tạo đúng 5.641 và 1.445 cạnh.

| Chỉ số | Django | SymPy |
|---|---|---|
| Hàm/lớp có ít nhất một cạnh `Documents` | 17,6% | 8,2% |
| Method có ít nhất một cạnh | 12,4% | 0,2% |
| Cạnh từ role trong văn xuôi / từ directive | 76% / 24% | 11% / 89% |
| Cạnh tới class đến từ role | 2.437 trên 2.962 | 13 trên 483 |
| Tham chiếu bị bỏ vì mơ hồ | 834 (9,0%) | 180 (9,9%) |
| Chunk là phần nối tiếp của một mục dài | 1.298 trên 6.189 | 249 trên 1.465 |
| Node nhận cạnh từ ít nhất 10 chunk | 117 node (1,3%), chiếm 35,3% số cạnh | Không có |
| Chunk có cạnh nhưng là khung autodoc không có văn xuôi | Không đáng kể | 465 trên 556 |

- Mô tả cũ "chunk thường chỉ nối tới lớp" không đúng hẳn. Directive đầu mục đã nối đúng method, ví dụ `querysets.txt:7` nối tới `QuerySet.filter`. Cạnh tới class đến chủ yếu từ role `:class:` trong văn xuôi, và từ các phần nối tiếp của một mục dài, vốn không có directive nên không nối tới chủ thể của mục.
- `doc_votes` giữ phiếu cao nhất của mỗi node, không cộng dồn. Mọi đích của cùng một chunk bằng điểm nhau, nên hạng AST quyết định thứ tự giữa chúng. Trên 820 instance Django của `scale_rows_v2.jsonl` (cạnh kiểu cũ, sắp theo điểm phiếu như `v4-fusion`), hạng 1 của danh sách DOC là node hub ở 30,2% instance, hub có mặt trong danh sách DOC ở 94,5% instance, nhưng gold là hub chỉ ở 5,4% instance.

**Các hướng đã đo và bỏ.** Số đo trên hai snapshot trên. Cột gold dùng 51 instance của `scale_rows_v2.jsonl` thuộc đúng hai snapshot này.

| Hướng | Cạnh mới (Django / SymPy) | Node mới có cạnh (Django) | Gold mới có cạnh | Quyết định |
|---|---|---|---|---|
| Phân giải tên ngắn theo class khai báo trong ngữ cảnh (RecoDoc, ARCLIN) | 110 / 8 | 31 | 0 | Bỏ. Lợi ích nhỏ, code tăng gấp đôi |
| Nối literal giống code trong văn xuôi, ví dụ ``values()`` | 1.864 (+33%) / 135 | 289 | 3, cùng 1 instance | Hoãn. 34% cạnh mới đi vào hub (`QuerySet` thêm 109 cạnh) và precision có dấu hiệu thấp. Xem lại sau khi biết thay đổi 2 có hiệu quả |
| Nhận `.. automodule::` làm module ngữ cảnh | Không đáng kể | | | Bỏ |

Graph giữ một loại cạnh `Documents` duy nhất (quyết định ngày 23/10/2026).

**Thay đổi 1. Kế thừa chủ thể của mục.** Mỗi chunk cắt ra từ một mục dài được nối thêm tới chủ thể của mục, tức hàm/lớp mà directive gần nhất đứng trước chunk trong cùng mục định nghĩa (`.. method::`, `.. class::`, `.. function::`). Mục không có directive thì không thêm gì. Cạnh vốn có giữ nguyên.
- Quy mô: Django thêm 251 cạnh (+4,4%), và 142 chunk trước đây không có cạnh nay vào được tập của `search_doc`. SymPy thêm 3 cạnh. Không gold nào mới có cạnh trong mẫu 51 instance, nên lợi ích chủ yếu ở pool bằng chứng.
- Nơi sửa: `DocExtractor.extract` trong cell `PqDgRg_1mNuK`.
- Cơ sở: RecoDoc (Dagenais và Robillard, ICSE 2012, mục II) lấy cả mục làm ngữ cảnh cục bộ của một tên. Quy tắc "directive gần nhất đứng trước" khi một mục có nhiều directive là đề xuất của đề tài.

**Thay đổi 2. Giảm phiếu cho node được nối từ quá nhiều chunk.** Trong `doc_votes`, phiếu của mỗi đích nhân thêm idf(n) = log(1 + N / df(n)). Ở đây df(n) là số chunk có cạnh tới n, và N là số chunk có cạnh trong snapshot. Hệ số tính riêng cho từng snapshot, chỉ từ graph doc, không dùng gold. Các tham số khác của `doc_votes` giữ nguyên (5 chunk, 0,8 cho đích trực tiếp, 0,5 khi lan phiếu).
- Nơi sửa: `doc_votes` trong cell `ec3fc119`. df được tính một lần khi nạp index.
- Cơ sở: node specificity s_i = 1/|P_i| của HippoRAG (Gutiérrez và cộng sự, NeurIPS 2024). Dạng log là đề xuất của đề tài, để giảm nhẹ hơn. Dạng 1/df được chạy kèm làm đối chứng. Macdonald và Ounis (CIKM 2006) cho thấy chia tổng phiếu cho số liên kết (CombANZ) làm kết quả sụp, nên không dùng cách chia đều.

**Thay đổi 3. Loại khung autodoc rỗng khỏi tập của `search_doc` (có điều kiện).** Chunk không có văn xuôi ngoài dòng directive bị loại khỏi tập DOC tìm kiếm, nên cũng không vào pool của judge. Cạnh vẫn giữ trong graph.
- Điều kiện làm, đặt trước khi đo: trên các instance SymPy của `scale_rows_v4.jsonl`, khung rỗng chiếm ít nhất 30% số chunk trong 10 chunk đầu của `doc_cand`, **và** tỷ lệ hữu ích theo judge của khung rỗng thấp hơn rõ so với chunk có văn xuôi. Nếu không, bỏ thay đổi này. Ngưỡng 30% chờ xác nhận.
- Cơ sở: Maalej và Robillard (TSE 2013, Bảng 8) thấy 43% đến 51% tài liệu tham chiếu của từng member không chứa thông tin.
- Hệ quả: SymPy sẽ còn rất ít chunk DOC. Đây là đặc điểm của tài liệu SymPy và được báo cáo đúng như vậy. Quyết định "docstring không tính là doc" giữ nguyên.

**Đo trước khi sửa (không cần Kaggle, cần `v4/scale_rows_v4.jsonl` và `judge_v4/`).**
1. Tỷ lệ hub ở hạng 1 của danh sách DOC với cạnh hiện tại.
2. Điều kiện của thay đổi 3.
3. Dựng lại danh sách DOC có hệ số idf từ `doc_cand` (đã lưu đích của 10 chunk), rồi chạy lại `v4-fusion`. Phần lan phiếu không dựng lại được, vì file không lưu cạnh AST.

**Tiêu chí, đặt trước khi chạy.**
- Tỷ lệ hub ở hạng 1 của danh sách DOC phải giảm.
- Q1 và Q5 chỉ được báo cáo, không dùng để chọn thiết kế. Nếu sau khi sửa trọng số DOC vẫn ở đáy lưới, kết luận là DOC không có giá trị xếp hạng, và giá trị của DOC nằm ở tầng bằng chứng.
- Rò rỉ: không có rò rỉ theo thời gian hay qua gold.

**Lượt Kaggle.** Đổi `DOC_LINKS_VERSION` thành `"v3"`. Cập nhật cạnh cho 86 graph (khoảng 1 giờ), dựng lại danh sách xếp hạng (khoảng 65 phút), chấm lại phần doc. Cùng lượt, lưu thêm điểm tới top 100 cho bước G.

**Trạng thái.** Đã chốt thiết kế ngày 23/10/2026. Chưa viết code.

### 6.11 Định hướng sau thảo luận ngày 18/10/2026

Phần này ghi các quyết định của buổi thảo luận ngày 18/10/2026. Bối cảnh nằm ở mục 12 của `research_context.md`.

**Agent và judge.** Thực nghiệm hiện tại chưa dùng agent. LLM judge đánh giá các node output, tức các node sau này sẽ được đưa cho agent. Agent sẽ được dùng sau để kiểm chứng hiệu quả.

**Output theo loại.** Output gồm AST node và các node bằng chứng (chunk doc, issue cũ, hunk). Mỗi loại là một phần riêng của output.

**Ngưỡng thay cho số lượng cố định.** Số lượng cố định hiện tại (5 chunk doc, 5 issue cũ, 10 hunk) sẽ được thay bằng ngưỡng. Ngưỡng có thể dùng ở ba chỗ: trước khi hop, trước khi vote và trước khi output. Lý do là số issue cũ liên quan thay đổi theo instance. Có instance có 5 đến 10 issue liên quan, có instance không có issue nào, và khi đó đưa đủ 5 issue không liên quan làm loãng context. Điểm embedding và điểm TF-IDF là cosine, có thang cố định, nên đặt được ngưỡng tuyệt đối. BM25 và RRF không có thang cố định. Cách chọn ngưỡng chưa chốt, và sẽ được chọn từ bài báo hoặc kỹ thuật liên quan.

**Khung so sánh.** Giữ toàn bộ khung so sánh với AST, gồm các mức hop và các cách kết hợp nguồn. Câu hỏi giữ nguyên Q1 đến Q7 ở mục 6.2.

**Judge bằng chứng có thêm loại thông tin.** Ngoài điểm liên quan và điểm hữu ích, judge ghi loại thông tin mà phần tử cung cấp. Danh sách loại chưa chốt.

### 6.12 Bộ độ đo và kiểm định đã chốt (21/10/2026)

Mục này thay cho phần độ đo và kiểm định ở mục 6.7 và 6.8 khi hai bên khác nhau. Lý do và bài báo làm cơ sở nằm ở mục 13 của `research_context.md`.

**Bảng 1, phần AST, hai mức.** Mức hàm/lớp: Top@1, Top@5, Top@10, MRR, MAP, Acc@5, Acc@10. Mức file: Top@1, Top@5, Top@10, MRR, MAP, Acc@1, Acc@3, Acc@5. Xếp hạng file lấy điểm cao nhất của hàm/lớp trong file.

**Bảng 3, phần bằng chứng, mỗi loại một bảng.** Pool là hợp của 10 phần tử đầu mỗi loại qua mọi hệ thống, judge chấm một lần. Phần tử hữu ích khi điểm hữu ích từ 2. Mỗi cách lọc (hạn ngạch cố định, các ngưỡng) có một hàng: Precision, Recall, F1, tỷ lệ trả rỗng đúng, tỷ lệ trả rỗng sai, số token trung bình.

**Bảng 4, loại thông tin.** Nguồn × loại thông tin: tỷ lệ phần tử hữu ích có từng loại. Danh sách loại ở mục 13.3 của `research_context.md`.

**Bảng 5, đủ thông tin cho cả tập.** Chỉ cho Q4: tỷ lệ instance được judge chấm "đủ" ở AST và ở +ALL, kèm McNemar.

**Kiểm định.** McNemar cho Top@k, Acc@k và trả rỗng đúng. Kiểm định hoán vị ghép cặp cho MRR, MAP, số node phải đọc (thay nDCG@10 từ ngày 26/10/2026), Precision, Recall và F1, với 10.000 hoán vị (giá trị chọn của đề tài). Holm trong từng độ đo, trên Q1 đến Q7.

**Thay đổi ở judge v4 (mục 6.7).** Số bằng chứng được chấm tăng lên 10 mỗi loại cho pool. Prompt bằng chứng có thêm trường loại thông tin (nhiều nhãn, hai nhãn loại trừ). Có thêm request đủ thông tin cho Q4.

### 6.13 Judge chỉ chấm bằng chứng, và độ đo theo cấu trúc cho node code (26/10/2026)

**Chi phí đo được.** Lượt v4-L5 có 5.515 lần gọi judge, gồm 49,2 triệu token đầu vào, 3,8 triệu token đầu ra và 1,9 triệu token thinking. Theo giá batch, chi phí là khoảng 10,4 USD. Trong đó, 18,7% đầu vào là 466 request history cũ bị chấm lại. Trong số ký tự output, lý do chiếm khoảng một nửa. Không phần phân tích nào đọc lý do.

**Thay đổi ở judge.**
1. Prompt bằng chứng và schema bỏ trường lý do. Judge chỉ cho điểm liên quan, điểm hữu ích và loại thông tin.
2. Mức thinking là MINIMAL thay cho LOW.
3. Judge không chấm node code nữa, nên `#code2` bị bỏ. Lý do thứ nhất là judge chấm node code mà không thấy bản vá, nên nhãn chỉ là phỏng đoán về mức liên quan. Lý do thứ hai là khi chấm lại mọi node để mọi nhãn cùng một cài đặt, phần này chiếm khoảng 56 đến 64% token đầu vào. Ở repo mới, phần này chiếm khoảng hai phần ba.
4. Mỗi batch gồm request của 100 instance.

Prompt đổi nên khóa của mọi request đổi. Lượt chạy tới sẽ chấm lại toàn bộ bằng chứng, khoảng 26 triệu token đầu vào. Ảnh hưởng của cài đặt mới lên nhãn chưa được đo. Bảng độ ổn định của judge (κ từ 0,6 đến 0,8 ở v4-L5) sẽ được đo lại với cài đặt mới.

**Độ đo theo cấu trúc thay cho nDCG@10 theo judge.** Cell `depth-v4` tính số node phải đọc trước khi gặp gold (mục 2) với k = 1, 5 và 10, cùng bảng độ sâu tới gold của các node trong top 10. Graph gồm Function và Class của snapshot, với cạnh `Calls`, `Inherits` và `Defines` theo hai chiều. Kiểm định là kiểm định hoán vị ghép cặp, với Holm trên Q1 đến Q7. Thiết kế chi tiết nằm ở mục 10.1 của `pipeline_design.md`. Cơ sở là Renieris và Reiss (ASE 2003), Cleve và Zeller (ICSE 2005), và Parnin và Orso (ISSTA 2011). Ba bài này chưa được đọc toàn văn.

**Giới hạn.** Độ đo tính từ gold, nên không độc lập với gold. Node cần đọc nhưng ở xa gold trên graph không được tính. DOC lan phiếu qua cạnh `Defines` và `Calls`, nên có lợi sẵn ở độ sâu 1.

### 6.14 Đợt xác nhận trên 10 repo còn lại của tập test (26/10/2026)

> Cập nhật 27/10/2026. Theo quyết định 58, 10 repo này là thêm dữ liệu cho cùng thực nghiệm, không phải tập để xác nhận. Pipeline không cần khóa trước khi chạy. Cách trộn không còn trọng số nào phải chọn (quyết định 57). Phần báo riêng câu hỏi về DOC trên nhóm repo có độ phủ doc từ 5% được giữ tới ngày 28/10/2026, rồi được thay bằng phân tích độ phủ như một biến (mục 6.17). Ngày 27/10/2026, notebook đã gộp 12 repo thành một thực nghiệm, và `V4_PHASE` bị bỏ (mục 14.15). Các đoạn dưới đây mô tả thiết kế ngày 26/10/2026.

**Mục đích.** Đợt này kiểm tra các kết luận rút ra trên Django và SymPy có còn đúng ở repo khác không. Pipeline được khóa trước khi chạy, và không tham số nào được chọn lại trên repo mới.

**Dữ liệu.** Gồm 10 repo còn lại của tập test SWE-bench: scikit-learn, sphinx, matplotlib, pytest, xarray, astropy, pylint, requests, seaborn và flask. Tổng cộng có 1.058 instance, trong đó 105 instance thuộc Lite. Sau đợt này, thực nghiệm phủ toàn bộ tập test, gồm 2.294 instance của 12 repo.

**Câu hỏi về DOC.** Đoạn này mô tả thiết kế ngày 26/10/2026, đã được thay bằng mục 6.17 ngày 28/10/2026. Câu hỏi về DOC chỉ được trả lời trên nhóm repo có độ phủ doc từ 5% trở lên (`V4_DOC_REPOS`). Ở đợt này, nhóm đó gồm scikit-learn (11,9%), xarray (12,7%), astropy (5,6%), seaborn (6,4%) và flask (24,0%), tổng cộng 467 instance. Năm repo còn lại, gồm 591 instance, chỉ dùng cho HIST và ISSUE. Số liệu độ phủ lấy từ `coverage_report.md`. Danh sách được ghi trước khi chạy.

**Pipeline khóa.**
- Từ ngày 27/10/2026, cách trộn là RRF gốc với trọng số bằng nhau, nên không có trọng số nào phải chọn.
- λ và β₁ của Locus lấy từ bài báo, nên không phải chọn.
- Judge dùng cùng cài đặt với đợt main: chỉ chấm bằng chứng, không viết lý do, thinking MINIMAL. Số instance chấm lặp là 30.
- Liên kết ISSUE dùng cùng quy tắc với SymPy, có thêm quy tắc commit squash. Quy tắc này không làm đổi liên kết của SymPy.

**Dự đoán, ghi trước khi chạy.** Dự đoán dựa trên kết quả của đợt main.
- Q2 (+HIST so với AST) và Q4 (+ALL so với AST): tốt hơn có ý nghĩa ở Top@10, MRR và MAP.
- Q1 (+DOC) và Q3 (+ISSUE): chênh lệch nhỏ so với AST.
- Q5 (+ALL so với ALL−DOC): thêm DOC không giúp, và có thể làm kết quả giảm như ở đợt main.
- Q6 (+ALL so với ALL−HIST): bỏ HIST làm kết quả giảm có ý nghĩa.
- Q7 (+ALL so với ALL−ISSUE): không có ý nghĩa.

**Thay đổi trong notebook.**
1. `V4_PHASE` ở cell cấu hình chung chọn đợt, và `SCALE_REPOS` lấy theo đợt.
2. Mỗi đợt có thư mục kết quả riêng (`v4/`, `v4_confirm/`) và thư mục nhãn riêng (`judge_v4/`, `judge_v4_confirm/`). `V4_MAIN_DIR` trỏ tới kết quả của đợt main.
3. `issue-fetch` lấy URL GitHub theo tên repo.
4. `issue-index` dựng mẫu từ khóa đóng issue theo từng repo, và đọc commit squash có "(#N)" ở cuối dòng đầu.
5. `v4-fusion` chọn trọng số trên đợt main khi chạy đợt confirm. Ngày 27/10/2026, phần này bị bỏ cùng việc chọn trọng số.
6. `verify-v4` tính thêm Bảng 1 và kiểm định cho nhóm repo có doc.
7. Cell `manifest` ghi cấu hình, hash của mã từng cell và hash của dữ liệu.

**Yêu cầu khi chạy.**
- Đặt `V4_PHASE = "confirm"` và `GITHUB_TOKEN`. Không có token, việc tải issue mất nhiều giờ.
- File `v4/scale_rows_v4.jsonl` của đợt main phải có trong `WORK_DIR`, vì `v4-fusion` chọn trọng số trên file này.
- Dựng graph là phần tốn nhất. Theo quy tắc 60 ngày, ước tính có tối đa khoảng 200 snapshot. Ước tính này dùng ngày tạo issue thay cho ngày của base commit, nên số thật thấp hơn. Với Django và SymPy, cách ước tính này cho 112 snapshot, trong khi số thật là 86. Cần theo dõi dung lượng của `/kaggle/working`.
- Judge tốn khoảng 21 triệu token đầu vào.

**Rủi ro.**
- Việc sửa cách nối doc (mục 6.10) và việc chọn ngưỡng chưa xong. Nếu chạy đợt confirm trước khi các việc này xong, kết quả chỉ xác nhận pipeline hiện tại. Sau đó nếu pipeline đổi, đợt confirm phải chạy lại.
- requests có ít liên kết ISSUE: trong 992 commit nhánh chính, chỉ 256 là merge commit của PR và không có commit squash.

### 6.15 Dọn notebook (27/10/2026)

Người dùng quyết định notebook chỉ chứa code của pipeline v4. Phân tích chỉ dùng một lần không được đặt trong notebook. Phân tích như vậy chạy ngoài notebook, và kết quả được ghi vào tài liệu. Lý do là notebook được chạy bằng Run All trên Kaggle. Một cell phân tích làm mỗi lượt chạy lâu hơn, và có thể làm Run All dừng khi gặp lỗi.

Các thay đổi trong notebook như sau. Chi tiết nằm ở mục 11 của `pipeline_design.md`.
1. Toàn bộ code của v3 bị bỏ. Đó là 11 cell `%%v3`, cờ `RUN_V3`, magic `%%v3`, `SCALE_RESULTS` và các prompt của judge v3.
2. Ba cell chỉ để phân tích bị bỏ. Đó là `v3-recheck`, `gpu_cuda_check` và `hist-fix-check`. Kết quả của bước D (`hist-fix-check`) được giữ ở mục 6.6 của `pipeline_design.md`.
3. Các đoạn chỉ để phân tích trong cell của pipeline bị bỏ. Đó là các cột của v3 trong `scale_row`, nguồn HIST của v3 và phần embedding message của `hist-build`, các bảng xem nhanh, `hist_locus_best`, mục 10 node đầu của `fusion.json`, và khối nDCG@10 của `verify-v4`.
4. `judge-v4` đọc file nhãn một lần cho mỗi phần batch, thay vì một lần cho mỗi request. Cách cũ tốn thêm khoảng 25 đến 40 phút CPU ở lượt chạy đầy đủ.
5. Khóa của cell trong `manifest` là số thứ tự trong `In` cộng dòng đầu của cell.

Notebook còn 45 cell. Bản cũ và bản mới được chạy trên máy với cùng 12 instance. Mọi cột mà pipeline đọc, trọng số trộn, các bảng của `verify-v4` và `depth-v4`, và 72 request của `judge-v4` đều trùng nhau. Vì vậy file kết quả và nhãn judge hiện có vẫn dùng được.

### 6.16 Xếp hạng node sau hop theo KGCompass (28/10/2026)

Người dùng duyệt thiết kế xếp hạng node sau hop theo công thức của KGCompass (quyết định 59 của `research_context.md`). Thiết kế đầy đủ nằm ở mục 8b của `pipeline_design.md`.

Các thay đổi trong notebook như sau.
1. `v4-config` cài thêm `rapidfuzz` và có thêm các hằng số `KGC_BETA` (0,6), `KGC_ALPHA` (0,3), `KGC_BUDGET` (4), `KGC_W`, `KGC_SEEDS` (10) và `KGC_SRC_MAX` (20.000).
2. Cell mới `graph-proc` nằm sau `issue-index` và trước `v4-fusion`. Cell này thêm vào mỗi dòng của `scale_rows_v4.jsonl` hai danh sách. `graph` đi từ 10 node đầu của AST. `doc_kgc` đi từ đích cạnh `Documents` của 10 chunk trong `doc_cand`. Cell chỉ tính lại dòng có cấu hình khác `KGC_CFG`, nên không phải chạy lại `v4-run`, `hist-proc` hay `issue-index`.
3. `v4-fusion` thêm nguồn GRAPH, cho DOC đọc `doc_kgc`, và thêm hai hệ thống +GRAPH và +ALL+GRAPH.
4. `verify-v4` thêm G1 (+GRAPH so với AST) và G2 (+ALL+GRAPH so với +ALL). Holm được tính riêng cho từng họ trong `V4_FAMILIES`. `depth-v4` tính Holm theo cùng các họ.
5. `manifest` ghi thêm cấu hình của `graph-proc`.

Judge không phải chấm lại, vì pool bằng chứng không đổi. Notebook có 46 cell.

### 6.17 Phân tích ảnh hưởng của độ phủ doc (28/10/2026)

Người dùng cho biết bảng độ phủ của `coverage_report.md` được lập để đo độ phủ doc ảnh hưởng thế nào tới hiệu quả. Vì vậy repo có độ phủ thấp được giữ, và độ phủ được phân tích như một biến (quyết định 60 của `research_context.md`). Thiết kế đầy đủ nằm ở mục 10.2 của `pipeline_design.md`.

Các thay đổi trong notebook như sau.
1. `scale_row` ghi thêm `gold_doc` (số gold có cạnh `Documents`) và `doc_cov` (tỷ lệ Function/Class của snapshot có cạnh `Documents`).
2. `v4-run` dựng lại file kết quả khi có dòng thiếu `gold_doc`.
3. `verify-v4` thêm khối "Ảnh hưởng của độ phủ doc". Khối này gồm bảng C-A và C1 ở mức repo, bảng C-B và C2 ở mức instance, bảng C-C mô tả cơ chế, và Holm của họ C. `_v4_tests` nhận thêm tham số `pairs`. Khối nhóm `V4_DOC_REPOS` bị bỏ.
4. `v4-config` bỏ `V4_DOC_REPOS`, và `manifest` bỏ khóa `doc_repos`.

### 6.18 Judge v5, bằng chứng HIST theo phần lời và độ đo bằng chứng mới (29/10/2026)

**Lý do.**
1. Prompt của judge v4 đo sai thứ cần đo. Judge tồn tại để đánh giá thông tin mà gold không đo được, tức giá trị nội dung của doc, history và issue cũ. Prompt v4 lại định nghĩa "hữu ích" theo việc phần tử chỉ tới code của bản sửa, đặt trần 1 cho phần tử chỉ chung tính năng, và đưa vào mỗi phần tử danh sách hàm/lớp do pipeline suy ra (đích cạnh `Documents` của chunk, hàm/lớp mà commit sửa, hàm/lớp mà bản sửa của báo cáo cũ đổi). Đặt cạnh bản sửa, danh sách này là tín hiệu nối gold. Vì vậy nhãn v4 gần với "phần tử có dẫn tới code của bản sửa không", và phép kiểm J5 ở mục 10 của `experiment_log.md` không độc lập với judge.
2. HIST phải cung cấp phần lời của lịch sử: trước đây cái gì hỏng, vì sao code được sửa, quyết định thiết kế nào đã đưa ra, lỗi tương tự được xử lý ra sao. Việc tìm code là của AST. HIST theo Locus so issue với diff của hunk và khớp tên code (CE), tức làm lại việc của AST.
3. Bảng 3 tính Precision trên mọi instance, nhưng Recall và F1 chỉ trên instance có phần tử hữu ích. Vì vậy F1 bỏ qua đúng những instance mà trả rỗng là đúng.

**Phạm vi.** Tầng xếp hạng không dùng nhãn judge, nên graph, AST, DOC, ISSUE, GRAPH, Bảng 1, Bảng 2, Q1 đến Q7, G1, G2, `depth-v4`, C1 và C2 giữ nguyên. Phải làm lại phần dựa trên nhãn judge: Bảng 3, Bảng 4, độ ổn định của judge, J1 đến J6. HIST đổi cả pool bằng chứng lẫn danh sách hàm/lớp, nên Q2, Q4, Q6 và các hệ thống có HIST được tính lại.

#### 6.18.1 Prompt v5

Mỗi instance có ba request, mỗi nguồn một request. `{issue}` là `problem_statement`. `{patch}` là bản sửa thật. `{elements}` là 10 phần tử của pool, theo định dạng ở mục 6.18.2, cách nhau một dòng trống, thứ tự xáo theo seed của instance như v4.

```text
You are assessing evidence retrieved for a GitHub issue. The evidence is meant to give a developer information that the code alone does not give: what the program is supposed to do, how an API is meant to be used, why the code was written or changed in a certain way, how similar problems happened or were fixed before. Finding the code to change is done by a separate component and is NOT the purpose of this evidence.

Evidence can be:
- passages of the project documentation,
- past commits, shown by their commit message and, when one exists, the ticket or pull request linked to the commit,
- past bug reports that were fixed earlier.
Every piece of evidence existed before the fix was written.

You also see the actual fix of the issue. Use the fix only as a reference to check whether the information in an element is correct and needed for this issue. An element does not need to mention or point to the changed code to be useful. Do not give a high score only because an element mentions the same file, function, class or feature as the fix or the issue.

Judge each element independently of the other elements.

## Issue
{issue}

## Actual fix
```diff
{patch}
```

## Evidence
{elements}

## Step 1: information types
For each element, list every type of information that the element provides FOR THIS ISSUE.
expected_behavior = what the program or the involved code is supposed to do in the situation described by the issue
api_usage = how an API, a data structure or a function involved in the issue is meant to be used
similar_failure = symptoms or conditions of a failure similar to the one in the issue
bug_cause = which code or which program state causes the problem in the issue
code_location = which code is involved in the problem
design_rationale = why the involved code is implemented or was changed in a certain way
past_change = how the involved code changed before, or how a similar problem was fixed before
no_new_information = the element only repeats what the issue already says (use this type alone)
unrelated = the element provides nothing related to the issue (use this type alone)

## Step 2: usefulness for a developer who has the issue but not the fix
3 = gives information that the fix depends on: the exact expected behavior or API contract that the fix must satisfy, the cause of the problem, or how this same problem was fixed before
2 = gives information of at least one type from Step 1 that applies to the specific situation of the issue and that a developer would need to read to understand the issue or decide on the fix
1 = background on the same feature or area that does not address the specific situation of the issue
0 = no help, or the information is wrong or outdated for this issue
If the only types are no_new_information or unrelated, usefulness is 0.
If the only information an element gives is which code is involved (code_location), usefulness is at most 1.

## Step 3: relevance
3 = about exactly the behavior or the code that the fix changes
2 = about closely related behavior, or code on the same execution path as the fix
1 = same feature or area only
0 = unrelated

Return a JSON array with exactly one object per element, in any order:
{"id": "<element id>", "info_types": ["<type>", ...], "usefulness": <0-3>, "relevance": <0-3>}
```

Schema trả về giữ ba trường của v4, thêm thứ tự `info_types`, `usefulness`, `relevance`. `info_types` nhận đúng 9 giá trị trên. Nhãn chỉ hợp lệ khi đủ mọi id. Request có `no_new_information` hoặc `unrelated` đứng cùng loại khác được chấm lại, như v4. Mức thinking MINIMAL, không trường lý do, mỗi phần batch 100 instance, như L8.

**Câu về `code_location` (thêm ngày 30/10/2026).** Câu cuối của bước 2 được thêm sau lượt thử ở máy (mục 6.18.5). Lý do là bản trước có mâu thuẫn. Đầu prompt nói việc tìm code không phải mục đích của bằng chứng, nhưng bước 2 vẫn cho 2 điểm khi phần tử có ít nhất một loại thông tin của bước 1, kể cả khi loại đó chỉ là `code_location`. Cơ sở là chính mục đích đã ghi ở đầu prompt, cùng bài Utility judgments (Zhang và cộng sự, SIGIR 2024, đã đọc toàn văn), vốn cho thấy LLM hay coi phần tử liên quan là hữu ích. Mức trần 1 theo cách prompt v4 dùng mức trần, không lấy từ bài báo nào.

Phép so nhỏ trước và sau khi thêm câu này như sau.
- Mẫu tham chiếu là 237 phần tử của 8 instance trong lượt thử ở máy (4 Django, 4 SymPy). Claude Opus chấm mẫu này theo cùng prompt, và không xem điểm của Gemini trước. Opus chỉ dùng cho phép so nhỏ này, không dùng để chấm lượt đầy đủ.
- Gemini chấm lại cả 48 instance của lượt thử với prompt đã sửa, tức 144 request và 1.437 phần tử. Cả 144 request đều hợp lệ.
- Số phần tử chỉ có `code_location` mà được từ 2 điểm trở lên giảm từ 9 (lần 1) và 11 (lần chấm lặp) với prompt cũ, xuống 1 với prompt đã sửa. Trên 40 instance ngoài mẫu của Opus, con số này giảm từ 8 xuống 1.
- κ trọng số của điểm hữu ích giữa Opus và Gemini tăng từ 0,697 lên 0,721, và tỷ lệ trùng điểm tăng từ 77,6% lên 80,2%. Số phần tử hai bên lệch nhau ở ngưỡng 2 điểm vẫn là 19, với 5 chỗ hết lệch và 5 chỗ lệch mới. κ nhị phân giảm từ 0,569 xuống 0,514.
- Tỷ lệ phần tử hữu ích chung giữ nguyên ở 11,1%. Nhãn trước và sau khi sửa khớp nhau ở κ trọng số 0,838, cao hơn mức 0,734 khi Gemini chấm lặp với cùng prompt. Vì vậy, ngoài đúng chỗ được nhắm tới, các thay đổi khác có thể chỉ là dao động giữa các lần chạy.
- Hai nhóm lệch vẫn còn. Gemini cho 2 điểm cho tài liệu tra cứu chung của cùng thành phần, và bỏ sót những phần tử cần suy luận từ message ngắn. Có một báo cáo cũ bị bỏ nhãn `code_location` nhưng vẫn giữ 2 điểm.

#### 6.18.2 Định dạng phần tử

Quy tắc chung: phần tử chỉ chứa nội dung vốn có của artifact. Thông tin do pipeline suy ra (đích cạnh, hàm/lớp bị sửa theo oracle) không được đưa vào.

DOC (pool là 10 chunk đầu của `doc_cand`, không đổi):

```text
[D<k>] Documentation passage
File: <đường dẫn file doc>
Section: <heading của chunk>
Text:
<toàn văn chunk, tối đa 1.600 ký tự như khi dựng graph>
```

HIST, commit có ticket hoặc PR liên kết (pool là 10 commit, mục 6.18.3):

```text
[H<k>] Past commit <sha 8 ký tự>, committed <YYYY-MM-DD>
Commit message:
<message đầy đủ, lấy bằng git log, không cắt>
Linked ticket or pull request #<số>: <tiêu đề>
<mô tả của ticket hoặc PR, toàn văn>
```

HIST, commit không có liên kết:

```text
[H<k>] Past commit <sha 8 ký tự>, committed <YYYY-MM-DD>
Commit message:
<message đầy đủ, lấy bằng git log, không cắt>
```

Commit có nhiều ticket hoặc PR liên kết thì mỗi liên kết là một khối "Linked ticket or pull request", theo thứ tự số tăng dần.

ISSUE (pool là 10 báo cáo của `issue_cand`, không đổi):

```text
[I<k>] Past bug report #<số>, created <YYYY-MM-DD>: <tiêu đề>
<nội dung báo cáo, toàn văn>
```

So với v4: DOC bỏ dòng "Code elements this passage documents". HIST đổi từ một hunk (message, danh sách hàm/lớp commit sửa, diff) sang một commit (message, ngày, ticket hoặc PR liên kết), không còn diff và danh sách hàm/lớp. ISSUE bỏ danh sách "Functions or classes changed by its fix" và thêm ngày tạo. Ngày được giữ để judge xét mức 0 "outdated".

#### 6.18.3 HIST theo phần lời (`hist-msg`)

**Văn bản của một commit.** text(c) gồm message của c, cộng tiêu đề và mô tả của mọi ticket hoặc PR liên kết với c. Liên kết lấy từ `V4_DIR/issues/<repo>_links.jsonl` của `issue-index`: "Fixed #N" với Django, từ khóa đóng issue hoặc số PR với repo GitHub. Nội dung lấy từ `<repo>_reports.jsonl`.

**Commit được xét.** Commit trên nhánh chính, là tổ tiên của snapshot, có sửa ít nhất một hàm/lớp có trong graph, như `hist-build`. Bỏ commit sửa hơn 50 hàm/lớp (`HIST_MAX_TOUCH`, như `hist_cand`).

**Rò rỉ.** Ticket hoặc PR liên kết chỉ được đưa vào text(c) khi được tạo trước mốc cắt ít nhất 1 ngày và không phải báo cáo của chính instance. Quy tắc giống bộ lọc của ISSUE (mục 7 của `pipeline_design.md`). Liên kết không qua bộ lọc thì bị bỏ khỏi text(c), commit vẫn được xét với message.

**Điểm của commit.** Hai danh sách xếp hạng commit, rồi gộp bằng RRF gốc với k = 60 (quyết định 57).
1. Danh sách lời: commit xếp theo cosine TF-IDF giữa issue và text(c). Tách token, bỏ stop word, Porter và công thức trọng số giữ như NL của Locus (mục 6.3 của `pipeline_design.md`). IDF tính riêng cho từng snapshot trên text(c) của các commit được xét.
2. Danh sách nối AST: commit có sửa ít nhất một hàm/lớp trong 500 node đầu của AST, xếp theo hạng AST tốt nhất trong các hàm/lớp mà nó sửa. Commit không sửa node nào trong 500 node đầu thì không có mặt trong danh sách này.

s(c) = 1/(60 + hạng trong danh sách lời) + 1/(60 + hạng trong danh sách nối AST), số hạng thứ hai bằng 0 khi c không có mặt. Như vậy commit nối tới node AST được ưu tiên, nhưng không bắt buộc. Hòa điểm xếp theo thời điểm commit mới hơn trước, rồi theo sha.

**Pool bằng chứng (`hist_msg_cand`).** 10 commit có s(c) cao nhất. Mỗi phần tử ghi sha, ngày, cosine, hạng AST tốt nhất, các hàm/lớp commit sửa và các liên kết đã qua bộ lọc. Hàm/lớp chỉ dùng cho phân tích, không đưa vào prompt.

**Danh sách hàm/lớp (`doc_ids_hist_msg`).** score(f) = max s(c) trên các commit c đã sửa f, theo quy tắc đại diện bằng phần tử tốt nhất của Locus (A1). Không có Fix và CE. Danh sách dài tối đa 500.

**Hệ thống.** +HIST, +ALL, ALL−DOC, ALL−ISSUE và +ALL+GRAPH dùng danh sách mới. Locus giữ lại thành hệ thống phụ "+HIST (Locus)", để so với các lượt trước.

**Cơ sở.** Locus (Wen, Wu, Cheung, ASE 2016) cho thấy message chia sẻ từ với báo cáo lỗi nhiều hơn code, và cho công thức NL. HAFixAgent và HAFix (Shi và cộng sự) chọn commit theo chỗ code bị nghi, và thấy đưa diff thô cho LLM thường làm kết quả kém hơn. RRF gốc theo Cormack, Clarke, Büttcher (SIGIR 2009). Việc ghép phần lời của commit với ticket hoặc PR, và dùng hạng AST làm danh sách thứ hai, là đề xuất của đề tài.

**Giới hạn đã biết.** Message của Django có trung vị 72 ký tự và 32,7% có phần thân ngoài dòng đầu. Ở SymPy, 92% commit trên nhánh chính là merge của PR, phần thân trung vị 42 ký tự (đo trên 5 năm trước snapshot `838e432e` và `9bf73cc2`). Phần lời chủ yếu đến từ ticket hoặc PR liên kết. Vì vậy pool HIST mới trùng một phần với pool ISSUE. Tỷ lệ trùng được báo cáo. Ở tầng xếp hạng, CE đang đóng góp phần lớn mức tăng của Q2, nên HIST mới có thể kém Locus. Kết quả được báo đúng như vậy.

#### 6.18.4 Độ đo bằng chứng mới (`verify-v4`, phần bằng chứng)

1. Micro Precision, Recall, F1 tính từ tổng TP, FP, FN trên mọi instance (Bacchelli, Lanza, Robbes, ICSE 2010, mục 3.4).
2. Utility tuyến tính T11U = 2·TP − FP cho từng instance, lấy trung bình trên mọi instance (Robertson và Soboroff, TREC 2002 Filtering, mục 2.3). Hệ số 2:1 lấy từ bài.
3. Bảng 2×2: output rỗng hay không, pool có phần tử hữu ích hay không.
4. Recall được gọi là recall trong pool. Mọi cách cắt giữ tối đa 10 phần tử.
5. Bảng 4 thêm số phần tử có từng loại thông tin trên mỗi instance, tính trên mọi phần tử trừ hai nhãn loại trừ.
6. So sánh giữa các nguồn ở Bảng 3 ghi là mô tả. So sánh có ý nghĩa chỉ trong cùng một nguồn: giữa các cách cắt, hoặc giữa judge v4 và v5.
7. J5 chỉ được ghi là phép kiểm độ nhất quán. Độ đúng của judge đo bằng κ giữa judge và người (mục 6.18.6).

Các thay đổi ở tầng xếp hạng làm ngoài notebook trên file hiện có, không chờ judge: hệ thống đối chứng "+ALL, AST hai lần" cho G2, kiểm định hoán vị trong từng snapshot, trung bình theo repo, và bảng riêng cho 10 repo mới.

#### 6.18.5 Chạy thử ở máy

> Cập nhật 29/10/2026. Người dùng yêu cầu không bao giờ có lượt chạy thử trên Kaggle. Lượt thử được chạy ở máy bằng script ngoài notebook, và gọi Gemini bằng `GOOGLE_API_KEY` của `judge-config`. Cơ chế `JUDGE_PILOT_N` (150 instance trên Kaggle) đã được cài rồi bị bỏ trong cùng ngày, nên notebook luôn chạy lượt đầy đủ. Bản kế hoạch cũ dùng mẫu 150 instance theo tỷ lệ của 12 repo.

- Mẫu gồm mọi instance của hai snapshot có graph ở máy. Đó là Django `838e432e` với 19 instance có gold, và SymPy `9bf73cc2` với 29 instance có gold. Với các instance này, máy có graph, history 5 năm trước snapshot, báo cáo và liên kết. Mẫu 150 instance theo tỷ lệ của 12 repo cần dựng graph và history cho khoảng 100 snapshot khác ở máy, nên không được làm.
- Script chạy mọi cell code của notebook trên mẫu này. `judge-v4` chỉ dựng request, rồi script gửi đúng các request đó tới Gemini bằng REST.
- Điều kiện A dùng prompt v4 và phần tử v4. Nhãn lấy từ lượt v4-L8, trên các phần tử DOC và ISSUE có ở cả hai pool.
- Điều kiện B dùng prompt v4, với phần tử DOC bỏ danh sách đích. Phần tử và thứ tự trùng với request DOC của điều kiện C. Mục đích là đo riêng phần nhãn DOC đến từ danh sách đích.
- Điều kiện C dùng prompt v5 và phần tử v5, cho cả ba nguồn. Mọi instance được chấm lặp với thứ tự xáo khác.

**Kết quả lượt thử ở máy (29/10/2026).** Script là `pilot_618.py` và `pilot_analyze.py`, nằm ngoài repo. Điều kiện C có 288 trên 288 request hợp lệ ngay lần gửi đầu, và điều kiện B có 48 trên 48. Lượt thử dùng khoảng 2,0 triệu token đầu vào, gọi trực tiếp, không qua batch.

Kết quả ở máy không trùng hẳn lượt v4-L8 trên cùng instance. `ast_ids` khác ở cả 48 instance. `doc_cand` trùng ở 38 instance, và `issue_cand` trùng ở 30 instance. Danh sách HIST theo Locus khác ở cả 48 instance. Một lý do có thể là history ở máy chỉ bắt đầu từ 5 năm trước snapshot ở máy, còn trên Kaggle history bắt đầu từ 5 năm trước snapshot cũ nhất của repo. Vì vậy, A và C chỉ được so trên phần tử có ở cả hai pool.

| Nguồn | Phần tử hữu ích, A / C (%) | Instance có phần tử hữu ích, A / C (%) | κ trọng số điểm hữu ích, A với C | κ trọng số khi chấm lặp C (v4-L8) |
|---|---|---|---|---|
| DOC | 5,2 / 7,9 | 39,6 / 39,6 | 0,657 (478 phần tử chung) | 0,791 (0,700) |
| HIST | 12,1 / 15,2 | 60,4 / 77,1 | Không so, vì pool khác | 0,700 (0,732) |
| ISSUE | 14,7 / 10,1 | 75,0 / 56,3 | 0,646 (417 phần tử chung) | 0,718 (0,740) |
| Gộp | | | | 0,734 (0,740) |

- Với HIST, A là hunk theo Locus, còn C là commit theo `hist-msg`. Vì vậy hai cột A và C của HIST đo hai pool khác nhau.
- κ của nhãn hữu ích nhị phân khi chấm lặp C là 0,627 (DOC), 0,594 (HIST), 0,482 (ISSUE) và 0,571 (gộp). Ở v4-L8, κ gộp là 0,646.
- B so với A trên 478 phần tử DOC chung có κ trọng số 0,771. Tỷ lệ phần tử hữu ích tăng từ 5,2% lên 6,5% khi bỏ danh sách đích. Như vậy, danh sách đích không làm tăng tỷ lệ hữu ích của DOC ở v4.
- Về kiểm tra độ nhất quán với việc nối gold, tỷ lệ phần tử hữu ích có nối gold của ISSUE giảm từ 27,1% (A) xuống 16,7% (C). Ở DOC, tỷ lệ này gần như giữ nguyên (16,0% và 15,8%). Với HIST, tỷ lệ này là 31,0% ở A (hunk) và 35,6% ở C (commit).
- Ở C, phần tử DOC hữu ích chủ yếu có cách dùng API (68,4%). Phần tử ISSUE hữu ích chủ yếu có lỗi tương tự (75,0%). Phần tử HIST hữu ích chủ yếu có thay đổi trước đây (50,7%) và vị trí code (43,8%). Mọi phần tử có điểm hữu ích 0 đều mang một nhãn loại trừ.
- Theo `usageMetadata`, request của C có trung bình 5.498 token đầu vào ở DOC, 6.056 token ở HIST và 6.915 token ở ISSUE. Request dài nhất có 19.913 token ở HIST và 75.921 token ở ISSUE. Mỗi request có khoảng 380 token đầu ra và 0 token thinking. Ước lượng bằng số ký tự chia 4 thấp hơn số thật từ 13% đến 21%. Với độ dài đo được, lượt đầy đủ cần khoảng 43,2 triệu token đầu vào, tức khoảng 9,1 USD theo đơn giá cận trên của mục 6.18.7.
- Ở tầng xếp hạng trên 48 instance, AST có Top@10 50,0 và MRR 0,286. +HIST theo `hist-msg` có 41,7 và 0,230. +HIST (Locus) có 50,0 và 0,254. Gold nằm trong top 10 của danh sách `hist-msg` ở 13 instance, và của danh sách Locus ở 16 instance. Không chênh lệch nào có ý nghĩa ở 48 instance. Ví dụ, +HIST theo `hist-msg` so với AST có ΔTop@10 −8,3 (McNemar p 0,388) và ΔMRR −0,056 (hoán vị p 0,286).
- Tiêu chí 3 của mục 6.18.6 đạt, vì κ trọng số khi chấm lặp C là 0,734 khi gộp và từ 0,700 trở lên ở mỗi nguồn. Tiêu chí 1 và 2 cần nhãn tay.

#### 6.18.6 Gán nhãn tay và tiêu chí, đặt trước khi chạy

- 150 phần tử lấy từ pool của điều kiện C, 50 mỗi nguồn, mỗi instance tối đa 1 phần tử mỗi nguồn. Người gán nhãn dùng thang v5 và không thấy nhãn của judge. Lượt thử ở máy (mục 6.18.5) có 48 instance có gold, nên mỗi nguồn có tối đa 48 phần tử, tức 144 phần tử.
- Prompt v5 được dùng cho lượt đầy đủ khi đạt cả ba điều kiện:
  1. κ trọng số của điểm hữu ích giữa người và điều kiện C từ 0,6 trở lên;
  2. κ đó không thấp hơn κ giữa người và điều kiện A, tính trên các phần tử DOC và ISSUE có ở cả hai pool;
  3. κ trọng số của điểm hữu ích khi chấm lặp điều kiện C từ 0,6 trở lên.
- Nếu không đạt, giữ prompt v4, và Bảng 3 được ghi là đo mức phần tử dẫn tới code của bản sửa.
- Nhãn v4 được giữ, và luận văn báo cáo cả hai phiên bản.

#### 6.18.7 Chi phí ước tính

Đơn giá ước lượng từ lượt v4-L5: khoảng 10,4 USD cho 49,2 triệu token đầu vào, kèm 3,8 triệu token đầu ra và 1,9 triệu token thinking. Đơn giá này là khoảng 0,21 USD cho mỗi triệu token đầu vào, đã gồm phần đầu ra. Từ L6, judge không viết lý do và thinking là MINIMAL, nên đơn giá thật thấp hơn. Các số dưới đây là cận trên. Độ dài một request lấy từ L8. Prompt v5 dài hơn v4 khoảng 264 token. DOC bỏ trung bình 298 token danh sách đích. ISSUE bỏ trung bình 663 token danh sách hàm/lớp.

| Phần | Request | Token đầu vào mỗi request | Tổng token đầu vào | Chi phí (cận trên) |
|---|---|---|---|---|
| Thử, điều kiện B (DOC) | 150 | khoảng 5.130 | 0,8 triệu | 0,2 USD |
| Thử, điều kiện C | 450 | khoảng 5.600 | 2,5 triệu | 0,5 USD |
| Thử, chấm lặp | 150 | khoảng 5.600 | 0,8 triệu | 0,2 USD |
| Đầy đủ, DOC (phần còn lại) | 2.045 | khoảng 5.400 | 11,0 triệu | 2,3 USD |
| Đầy đủ, ISSUE (phần còn lại) | 2.059 | khoảng 6.240 | 12,8 triệu | 2,7 USD |
| Đầy đủ, HIST (phần còn lại) | 2.064 | khoảng 5.200, có thể từ 4.000 đến 7.000 | 10,7 triệu, có thể từ 8 đến 14 triệu | 2,3 USD, có thể từ 1,7 đến 3,0 USD |
| Đầy đủ, chấm lặp (phần còn lại của 130 instance) | 240 | khoảng 5.600 | 1,3 triệu | 0,3 USD |
| **Tổng** | **7.158** | | **khoảng 40 triệu, có thể từ 37 đến 43 triệu** | **khoảng 8,5 USD, có thể từ 7,9 đến 9,2 USD** |

Độ dài request HIST là ước lượng: phần chung (prompt, issue, bản sửa) khoảng 2.000 token, cộng 10 commit, mỗi commit khoảng 25 token message và khoảng 420 token ticket hoặc PR khi có liên kết, giả định khoảng 70% commit có liên kết. Độ dài thật được đo ở lượt thử.

Cập nhật 29/10/2026. Lượt thử chạy ở máy, nên ba dòng "Thử" của bảng trên không còn tính vào chi phí của Kaggle, và lượt đầy đủ phải chấm mọi request. Theo độ dài đo ở lượt thử (mục 6.18.5), lượt đầy đủ cần khoảng 43,2 triệu token đầu vào, tức khoảng 9,1 USD theo cận trên. Số đo chỉ có từ Django và SymPy.

| Thời gian | Ước tính |
|---|---|
| `hist-msg` trên Kaggle, 12 repo | 10 đến 20 phút, không cần GPU |
| `judge-v4` lượt thử | 15 đến 25 phút |
| `judge-v4` lượt đầy đủ | 60 đến 80 phút, như L6 và L8 |
| `verify-v4` và `depth-v4` | khoảng 6 phút |
| Gán nhãn tay 150 phần tử | 4 đến 6 giờ của người dùng |

`v4-run`, `hist-proc`, `issue-fetch`, `issue-index` và `graph-proc` không phải tính lại.

#### 6.18.8 Thứ tự

1. Phần xếp hạng ngoài notebook trên file hiện có (mục 6.18.4, đoạn cuối).
2. Cài `hist-msg`, prompt v5 và định dạng phần tử v5 vào notebook. Thử trên 12 instance ở `D:\tmp\rgdata` với client Gemini giả.
3. Lượt thử ở máy (mục 6.18.5): điều kiện B và C trên 48 instance, gọi Gemini thật. Đã chạy ngày 29/10/2026.
4. Gán nhãn tay 144 phần tử. Tính κ theo mục 6.18.6.
5. Đạt tiêu chí: chạy lượt Kaggle đầy đủ. Không đạt: giữ v4 và ghi giới hạn.
6. Tính lại Bảng 3, Bảng 4, độ ổn định, J1 đến J6 theo độ đo mới. Ghi lượt vào `experiment_log.md`.
7. Chọn ngưỡng (bước G) trên nhãn mới.

#### 6.18.9 Mặc định đã chọn, đổi được nếu người dùng muốn

- Phần lời của HIST gồm message cộng mô tả ticket hoặc PR liên kết. Comment review chưa được tải, nên không dùng.
- Pool ISSUE giữ điều kiện Fix(b′) khác rỗng, để giới hạn số thay đổi trong lượt này.
- HIST và ISSUE giữ riêng hai nguồn. Tỷ lệ báo cáo xuất hiện ở cả hai pool được báo cáo.

**Trạng thái.** Đã viết kế hoạch ngày 29/10/2026. Bước 1 và bước 2 của mục 6.18.8 đã làm cùng ngày. Bước 1 đã chạy ngoài notebook trên file kết quả của lượt v4-L8, và chưa được ghi vào `experiment_log.md`. Ở bước 2, `hist-msg`, prompt v5, định dạng phần tử v5 và độ đo bằng chứng mới đã được cài vào notebook, rồi chạy thử trên 12 instance ở `D:\tmp\rgdata` với client Gemini giả. `JUDGE_PILOT_N` cũng được cài, rồi bị bỏ cùng ngày. Thiết kế khi cài nằm ở mục 6b, 9 và 10 của `pipeline_design.md`. Bước 3 đã chạy ở máy cùng ngày (mục 6.18.5). Bước 4 trở đi chưa làm.

---

## 7. Cách tổ chức notebook

Mọi cell của v4 nằm trong phần v4 ở cuối notebook. Từ ngày 27/10/2026, notebook không còn code của v3 (mục 6.15).

- Phần v4 dùng đường dẫn riêng, gồm `V4_DIR`, `scale_rows_v4.jsonl` và `judge_v4`.
- Dòng `GOOGLE_API_KEY` giữ nguyên. `GITHUB_TOKEN` là biến thường trong `v4-config`.

| Cell | Việc | Ghi vào |
|---|---|---|
| `v4-md` | Mô tả phần v4 | |
| `v4-config` | Đường dẫn, tham số, `GITHUB_TOKEN`, cờ chạy | |
| `v4-run` | Truy hồi lại với oracle mới, xếp hạng tới 500 | `scale_rows_v4.jsonl` |
| `snapshot-audit` | Kiểm tra snapshot trên 100 instance | `V4_DIR/snapshot_audit.json` |
| `issue-fetch` | Tải ticket Trac và issue/PR GitHub | `V4_DIR/issues/` |
| `issue-index` | Liên kết, lọc, TF-IDF, SimiScore | Thêm cột ISSUE vào `scale_rows_v4.jsonl` |
| `hist-proc` | Dựng chỉ mục hunk, rồi xếp hạng hàm/lớp theo Locus (mục 6.4). Từ ngày 29/10/2026 là hệ thống phụ "+HIST (Locus)" | `history/<repo>_hunks_v2.jsonl`, thêm cột HIST theo Locus vào `scale_rows_v4.jsonl` |
| `hist-msg` | Xếp hạng commit theo phần lời và theo liên kết với AST, rồi xếp hạng hàm/lớp (mục 6.18.3). Nằm sau `issue-index`. Từ ngày 29/10/2026 là nguồn HIST chính | Thêm `doc_ids_hist_msg` và `hist_msg_cand` vào `scale_rows_v4.jsonl` |
| `v4-fusion` | Trộn các nguồn với AST cho 8 hệ thống và 3 biến thể. Cách trộn là RRF gốc (mục 6.6) | `V4_DIR/fusion.json` |
| `judge-v4` | Tạo request bằng chứng, gửi batch, đọc nhãn. Từ ngày 26/10/2026 không còn `#code2`. Từ ngày 29/10/2026 dùng prompt v5 và có `JUDGE_PILOT_N` (mục 6.18) | `judge_v4/` |
| `verify-v4` | Q1 đến Q7 và các bảng phân tích | Output của cell |
| `depth-v4` | Số node phải đọc và độ sâu tới gold, không dùng LLM | Output của cell |
| `manifest` | Ghi cấu hình, hash của mã từng cell và hash của dữ liệu. Đã cài ngày 26/10/2026. Từ ngày 27/10/2026, khóa của cell là số thứ tự trong `In` cộng dòng đầu | `V4_DIR/manifest.json` |

Các thành phần có sẵn được dùng lại gồm `HIST[repo]["units"]`, `_git`, `_tokenize_code`, `get_oracle` và `_file_nodes_at`. Các hàm gọi Gemini của v3 đã được chép sang `judge-v4`, nên việc bỏ v3 không ảnh hưởng tới `judge-v4`.

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

Bạn là người chạy trên Kaggle. Kaggle giới hạn 12 giờ mỗi lần chạy. Vì vậy tôi đề xuất ba lượt. File trong `/kaggle/working` vẫn còn khi mở phiên mới, nên lượt sau dùng lại được kết quả của lượt trước (`experiment_log.md`, các lượt ngày 27/10 và 28/10).

| Lượt | Cell | Điểm dừng |
|---|---|---|
| 1 | `v4-config`, `hist-build`, `v4-run`, `hist-proc`. Thêm `issue-fetch` và `issue-index` khi nguồn ISSUE được làm tiếp | Kết luận hẹp của việc 1.2 không đổi chiều |
| 2 | `snapshot-audit` | Kết quả quyết định cách làm của các lượt chạy sau |
| 3 | `v4-fusion`, `judge-v4`, `verify-v4`, `manifest` | Bạn xem kết quả Q1 đến Q7 |

Cell `hist-proc` dựng chỉ mục hunk một lần, mất khoảng 45 phút đến 1 giờ. Chỉ mục được ghi vào `history/`, nên lượt sau dùng lại được nếu file được lưu.

Nhãn của `judge_v3` nằm trong `/kaggle/working`, và thư mục này vẫn còn khi mở phiên mới. Vì vậy lượt 3 không phải nạp lại nhãn này từ dataset. Từ ngày 26/10/2026, judge không chấm node code nữa, nên lượt 3 cũng không cần nhãn này.

---

## 10. Chi phí

Các con số dưới đây là ước tính. Chúng sẽ được đo lại khi chạy `hist-proc` và `judge-v4`.

| Phần | Ước tính |
|---|---|
| Judge bằng chứng | Bằng chứng HIST là 10 hunk, mỗi hunk kèm message của commit. Ngoài ra còn bản vá, chunk doc và báo cáo cũ. Số token chưa được đo |
| `hist-proc` | Dựng chỉ mục hunk khoảng 45 phút đến 1 giờ trên Kaggle, chỉ một lần. Không gọi LLM |
| Judge `#code2` | Bỏ từ ngày 26/10/2026 |
| Judge, số đo của lượt v4-L5 | 49,2 triệu token đầu vào, 3,8 triệu token đầu ra, 1,9 triệu token thinking, khoảng 10,4 USD theo giá batch |
| `issue-fetch` | Django khoảng 1 phút. SymPy vài phút khi có token |

Batch API rẻ hơn gọi thường 50%. Tier 1 giới hạn 10 triệu token đang xếp hàng, nên mỗi batch chỉ gồm request của 150 instance, như `JUDGE_BATCH_INSTANCES` của v3. Từ ngày 26/10/2026, mỗi batch gồm request của 100 instance.

---

## 11. Rủi ro và cách xử lý

| Rủi ro | Cách xử lý |
|---|---|
| SymPy chỉ có khoảng 57,5% PR ghi số issue, nên ISSUE yếu hơn ở SymPy | Báo độ phủ liên kết riêng cho từng repo trong `verify-v4` |
| ISSUE và HIST dùng chung commit, nên hai nguồn có thể trùng thông tin | Q6 và Q7 đo phần đóng góp riêng của từng nguồn |
| Oracle vẫn dùng chung cho gold, HIST và ISSUE | Đã kiểm tra ở việc 1.1, và vẫn ghi là mối đe dọa trong luận văn |
| Lượt chạy dừng giữa chừng (giới hạn 12 giờ) khi batch judge chưa xong | Mỗi batch được ghi vào `batch_jobs.txt`, và nhãn được ghi vào `labels_<model>.jsonl`. Hai file này vẫn còn ở phiên sau, nên lần chạy sau dùng lại batch đã gửi và không gửi lại request đã có nhãn |
| Thiết kế v4 dựa trên kết quả test của v3 | Không tham số nào được chọn trên dữ liệu (quyết định 57). Phương pháp đã chốt không đổi chỉ vì kết quả xấu |

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

---

## 14. Kế hoạch điều chỉnh notebook theo định hướng 18 đến 21/10/2026

Mục này dùng để giao việc cài đặt. Nó nói cell nào sửa, sửa ở đâu, thêm cell nào, thử trên máy ra sao và chạy theo thứ tự nào. Số dòng tính theo notebook hiện tại (54 cell, bản ngày 16/10/2026, commit 1d9501e). Quyết định nền nằm ở mục 6.11, 6.12 của file này và mục 12, 13 của `research_context.md`.

### 14.0 Quy tắc khi cài đặt

1. Chỉ làm các bước A đến E và H (phần không phụ thuộc F, G). Bước F và G chưa được chốt cách làm: không tự chọn cách trộn hay cách chọn ngưỡng.
2. Chỉ sửa đúng chỗ nêu trong bảng. Mọi bản sửa khác chỉ được nêu ra để người dùng quyết định.
3. Không nguồn nào dùng LLM để tạo xếp hạng; LLM chỉ là judge.
4. `GOOGLE_API_KEY` và `GITHUB_TOKEN` là biến thường trong notebook, để trống khi commit. Không dùng biến môi trường, secret, getpass hay Google Drive. Không commit notebook khi còn key. Không đụng `colab/notebook5f48a387d*.ipynb`.
5. Notebook được ghi lại ở dạng JSON gọn: `ensure_ascii=False`, `separators=(',',':')`, source của mỗi cell là một chuỗi, thứ tự khóa của cell là id, cell_type, source, metadata, outputs, execution_count, không có dòng trống ở cuối file.
6. Mọi cell được thử trên máy (14.11) trước khi ghi vào notebook. Commit thẳng vào `main`, chỉ khi người dùng yêu cầu, luôn kèm diff.
7. Không cần giữ kết quả các lượt Kaggle trước. Notebook được phép chạy lại từ đầu, nên các thay đổi sửa thẳng vào cell hiện có.

### 14.1 Tổng quan

| Bước | Việc | Cell | Phụ thuộc |
|---|---|---|---|
| A | Lưu 10 ứng viên đầu của mỗi loại bằng chứng, kèm điểm gốc | sửa `ec3fc119`, `scale-setup`, `hist-proc`, `v4-config` | Không |
| B | Cài ISSUE | thêm `issue-fetch`, `issue-index` | Không (mặc định ở 14.3) |
| C | Đánh giá phần AST theo bộ độ đo mới | thêm `verify-v4` | Không |
| D | Tìm nguyên nhân Fix làm HIST giảm ở Django | thêm `hist-fix-check` | A |
| E | Kiểm tra snapshot (việc 1.3) | thêm `snapshot-audit` | Không |
| F | Trộn các nguồn | thêm `v4-fusion` | **Chờ chốt cách trộn** |
| G | Ngưỡng ở ba vị trí | thêm `v4-threshold` | **Chờ chốt cách chọn ngưỡng**; cần dữ liệu của A |
| H | Judge v4 | thêm `judge-v4` | A, B; phần `#code2` và `#suff` cần F |
| I | Bảng bằng chứng, loại thông tin, đủ thông tin | mở rộng `verify-v4` | H |
| J | Đóng băng | thêm `manifest` | Mọi bước trên |

### 14.2 Bước A: lưu ứng viên và điểm gốc

| Chỗ sửa | Hiện tại | Sửa thành |
|---|---|---|
| `v4-config`, sau dòng 6 | Chưa có | Thêm `V4_EVID_N = 10` (trần của mỗi loại bằng chứng, bằng kích thước pool) |
| `ec3fc119`, hàm `_search_chunks`, dòng 227 đến 244 | Trả `{"id", "name", "label", "score"}`, với `score` là RRF | Trả thêm `"bm25": bm[i]` và `"cos": vs[i]`. Thứ tự không đổi |
| `scale-setup`, hàm `scale_row`, sau dòng 112 | Chỉ lưu id chunk: 5 chunk của `vote_ast` (`EXP_N_DOC = 5`) và 10 chunk của `search_doc_all`, không có điểm | Thêm `row["doc_cand"]` = `search_doc(q, n=V4_EVID_N)` và `row["doc_cand_all"]` = `search_doc_all(q, n=V4_EVID_N)`; mỗi phần tử gồm id, `score`, `bm25`, `cos` và đích cạnh `Documents` |
| `hist-proc`, vòng ghi kết quả, dòng 230 đến 236 | `hist_locus_best`: hunk tốt nhất của 10 hàm/lớp đầu | Thêm `row["hist_cand"]`: `V4_EVID_N` hunk có điểm `s = NL + α·CE` (dòng 177) cao nhất trong snapshot, mỗi hunk gồm sha 8 ký tự, file, thứ tự hunk, NL, CE và các hàm/lớp hunk sửa. Giữ thêm vector `nl` (dòng 176) để ghi NL riêng |

**Kiểm tra trên máy** với dữ liệu ở 14.11:
- `cos` nằm trong [−1, 1]; 5 phần tử đầu của `doc_cand` trùng `doc_chunks_vote_ast`.
- Hồi quy trên 12 instance: mọi trường đã có trong `D:\tmp\rgdata\v4\scale_rows_v4.jsonl` (bản trước khi sửa) giữ nguyên giá trị; chỉ có thêm `doc_cand`, `doc_cand_all`, `hist_cand`.

### 14.3 Bước B: nguồn ISSUE

Theo mục 6.5, với hai điểm sau.

- **Liên kết Django (21/10/2026):** bắt cả "Fixed #N" lẫn "Refs #N" (kể cả dạng danh sách "Fixed #123, #456") và ghi loại liên kết (`fixed` hoặc `refs`) lên từng cặp ticket, commit. Tính hai biến thể của Fix(b′): chỉ từ `fixed`, và từ `fixed` cộng `refs`. Theo hướng dẫn commit của Django, "Fixed #N" đóng ticket còn "Refs #N" chỉ nhắc tới ticket. Biến thể nào là hệ thống chính **chưa chốt**; trong lúc chờ, các cột `doc_*_issue` dùng biến thể chỉ `fixed`, biến thể còn lại ghi vào `doc_*_issue_refs` để so ngoại tuyến trên Top@k của AST.
- **Mốc thời gian cắt:** mặc định là `created_at` của chính instance (đề xuất ngày 16/10/2026, **chưa xác nhận**). Đặt thành hằng số `ISSUE_CUTOFF = "instance"` trong `v4-config` để đổi được.

Cell:
- `issue-fetch`: tải ticket Trac (CSV, 500 ticket mỗi trang) và issue/PR GitHub của SymPy (cần `GITHUB_TOKEN`); ghi `V4_DIR/issues/`.
- `issue-index`: liên kết báo cáo với đơn vị history, lọc rò rỉ (4 điều kiện ở 6.5), TF-IDF cosine với IDF theo snapshot, SimiScore. Ghi `doc_ids_issue`, `doc_score_issue`, `doc_r_issue`, `doc_gold_issue` (dạng `fused_multi` đọc) và `issue_cand`: `V4_EVID_N` báo cáo cũ đầu kèm cosine, Fix(b′) và loại liên kết.

### 14.4 Bước C: `verify-v4`

Cell mới ở cuối notebook. Bản nháp đã có ở `D:\tmp\rgdata\drafts\verify_v4.py`, đã thử trên 120 instance giả: số mức hàm/lớp trùng `v3-recheck`.
- Bảng 1 ở hai mức: hàm/lớp (Top@1/5/10, MRR, MAP, Acc@5/10) và file (Top@1/5/10, MRR, MAP, Acc@1/3/5); xếp hạng file lấy điểm cao nhất của hàm/lớp trong file.
- Bảng 2 theo độ khó của AST.
- McNemar chính xác cho độ đo đúng/sai; kiểm định hoán vị ghép cặp 10.000 lần (seed 20261021) cho MRR và MAP; Holm trong từng độ đo trên Q1 đến Q7.
- Khi chưa có `V4_FUSED` từ `v4-fusion`, cell dùng tạm 4 hệ thống của v3 (`fused_multi` của `v3-recheck`).

### 14.5 Bước D: nguyên nhân Fix làm HIST giảm ở Django

Cell phân tích, không đổi pipeline. Dùng `doc_ids_hist_locus_nlce` và `doc_ids_hist_locus`.
1. Đếm tỷ lệ đơn vị khớp `fix|bug` (A2): Django 58%, SymPy 26%. Nếu gần như mọi commit Django đều khớp thì Fix chỉ còn đếm số lần hàm bị sửa.
2. So Top@10 khi bỏ Fix (NL+CE) và khi đủ, tách theo số lần hàm bị sửa.
3. Thử A3 khác: t = 0 ở đơn vị cũ nhất trong 5 năm trước snapshot thay vì đơn vị cũ nhất của file history.
Kết quả quyết định có sửa A2, A3 hay báo Fix như một thành phần không hợp với Django. Không tự sửa A2, A3.

### 14.6 Bước E: kiểm tra snapshot

Theo mục 5.2: 100 instance (69 Django, 31 SymPy, seed cố định), build graph và history tại đúng base commit, so phần gold mất, khoảng trống history và chênh lệch Top@10 của AST. Điểm dừng: chênh Top@10 từ 3 điểm % hoặc khoảng trống history chứa commit sửa gold ở từ 10% instance. Cần GPU (build 100 graph); trên CPU mỗi graph mất khoảng 20 phút cho bước embed.

### 14.7 Bước F và G: chờ quyết định

- `v4-fusion` tạo `V4_FUSED` (tên hệ thống → hàm nhận dòng kết quả, trả danh sách id) cho 8 hệ thống ở mục 6.1. Cách trộn chưa chốt; yêu cầu là không tự đặt trần.
- `v4-threshold` áp ngưỡng ở ba vị trí (trước hop, trước vote, trước output) lên dữ liệu của bước A. Nhờ A lưu sẵn ứng viên và điểm, mọi ngưỡng được thử ngoại tuyến trên pool đã chấm. Cách chọn ngưỡng chưa chốt.

### 14.8 Bước H: `judge-v4`

Các hàm `parse_judgment` (dòng 40), `run_batch` (dòng 159) của `judge-run` và `_request`, `_items`, `_code_of` của `judge-pool` nằm trong cell bị chặn bởi `%%v3`, nên được chép sang `judge-v4` như `fused_multi` đã chép sang `v3-recheck`.

| Request | Nội dung | Chờ |
|---|---|---|
| `#ev-doc`, `#ev-hist`, `#ev-issue` | Pool 10 phần tử mỗi loại từ `doc_cand`, `hist_cand`, `issue_cand`; judge xem bản vá; mỗi phần tử có lý do, điểm liên quan, điểm hữu ích và danh sách loại thông tin (nhiều nhãn, hai nhãn loại trừ); xáo thứ tự | A, B |
| `#code2` | Node mới vào top 10 của một hệ thống, chưa có nhãn ở `judge_v3`; prompt cũ | F |
| `#suff` | Nhãn "đủ thông tin" cho cả K(p), chỉ AST và +ALL; chạy thử 50 instance để đo token trước | F, G |

JSON schema của request bằng chứng thêm trường `info_types` dạng mảng enum. Khóa nhãn có hash của input. Nhãn ghi vào `judge_v4/`. Kiểm tra trên máy bằng client Gemini giả: mọi alias có nhãn, nhãn loại trừ không đi cùng nhãn khác, hash đổi khi input đổi.

### 14.9 Thứ tự chạy

Đợt 1, sau khi A, B, C, D đã cài và thử trên máy: một lượt chạy từ đầu gồm các cell dựng graph và history, `v4-config`, `v4-run`, `hist-proc`, `issue-fetch`, `issue-index`, `hist-fix-check`, `verify-v4`, và phần `#ev-*` của `judge-v4`. `snapshot-audit` chạy riêng trên máy có GPU.

Đợt 2, khi F và G được chốt: `v4-fusion`, `v4-threshold`, phần `#code2`, `#suff` của `judge-v4`, `verify-v4` (đủ các bảng), `manifest`.

### 14.10 Còn chờ người dùng

> Cập nhật 22/10/2026. Ngày 21/10, người dùng giao cho Claude tự quyết định các mục 1 và 2. Mục 3 đã chốt một nửa.

1. Biến thể của liên kết Django: **giữ chỉ "Fixed #N"** làm hệ thống chính. Lượt v4-L4 cho thấy thêm "Refs #N" không giúp (Top@10 của +ISSUE là 56,7 khi chỉ dùng Fixed, 56,4 khi thêm Refs).
2. Mốc thời gian cắt của ISSUE: **giữ `ISSUE_CUTOFF = "instance"`**, tức thời điểm tạo báo cáo của chính instance. Đổi được bằng hằng số này. Từ ngày 22/10, `issue-index` tự tính lại khi hằng số đổi.
3. Cách trộn (F): **đã chốt** RRF có trọng số theo nguồn, chọn bằng kiểm định chéo 5 phần (mục 14.12). Ngày 27/10/2026, cách này được thay bằng RRF gốc với trọng số bằng nhau (mục 6.6). Cách chọn ngưỡng (G): còn chờ.
4. Thành phần Fix của HIST (mục 14.5): kết quả của bước D nằm ở mục 3 của `experiment_log.md`. Chưa sửa A2 hay A3, theo mục 14.5.

### 14.11 Dữ liệu thử và môi trường trên matthew-pc (21/10/2026)

Dữ liệu ở `D:\tmp\rgdata`, dựng bằng `build_testdata.py` (cùng thư mục). Script chạy chính các cell của notebook theo thứ tự, chỉ đổi `WORK_DIR`, `REPO_DIR`, nguồn SWE-bench (đọc parquet cục bộ thay `load_dataset` ở `scale-data` và `hist-proc`) và giữ 6 instance đầu (theo id) của mỗi snapshot. Mọi bước có bộ nhớ đệm trên đĩa, chạy lại thì đi tiếp.

| Dữ liệu | Nội dung |
|---|---|
| `repos/django`, `repos/sympy` | Bản clone đầy đủ (mọi nhánh, đối chiếu sha256 khi chép), remote là GitHub; thư mục làm việc để trống, notebook tự checkout |
| `swe_full_test.parquet`, `swe_lite_test.parquet` | `princeton-nlp/SWE-bench` và `SWE-bench_Lite`, split test, lấy từ bộ nhớ đệm Hugging Face của máy |
| `django_graph_838e432e.json` | 16.587 node, 42.037 cạnh, 71 MB, cạnh Documents v2; embed trên CPU mất 17 phút |
| `sympy_graph_9bf73cc2.json` | 19.000 node, 362.732 cạnh, 136 MB, cạnh Documents v2; embed trên CPU mất 20 phút |
| `history/` | Lớp history v2: django 9.456 commit trên nhánh chính (4.829 sửa ít nhất một hàm/lớp), sympy 3.254 commit (2.443); kèm hunk và embedding message |
| `v4/scale_rows_v4.jsonl` | 12 instance (6 mỗi snapshot) đã qua `v4-run` và `hist-proc`, làm mốc hồi quy cho bước A |
| `drafts/verify_v4.py` | Bản nháp của `verify-v4` |

Snapshot `838e432e` có 22 instance, `9bf73cc2` có 29. Tập test có 850 instance Django và 386 SymPy trước khi lọc instance không có gold hàm/lớp.

Môi trường:
- Python trên Windows: venv `D:\tmp\rgvenv` (Python 3.12.10, torch 2.14.1+cpu, sentence-transformers 6.1.0, transformers 5.19, tree_sitter 0.26, tree_sitter_python 0.25, gitpython, rank_bm25, unidiff, pandas, scipy, huggingface_hub). Ngày 21/10 đã cài thêm `nltk` 3.10.3 và `nbformat` 5.11.1. `datasets` không cần vì đã có parquet.
- Bộ nhớ đệm Hugging Face ở `C:\Users\matthew.phat.tran\.cache\huggingface` có `BAAI/bge-small-en-v1.5` và SWE-bench. Không có `BAAI/bge-reranker-base`. Chỉ `_ce_scores` (`ec3fc119`, dòng 336) gọi `_get_ce`; lượt dựng dữ liệu chạy hết `v4-run` và `hist-proc` khi không có model này, nên đường chạy v4 không cần nó.
- Chạy script: `D:\tmp\rgvenv\Scripts\python.exe D:\tmp\rgdata\build_testdata.py D:\RepoGraph\colab\build_graph_flask_colab.ipynb D:\tmp\rgdata 6`.
- Dữ liệu trên được dựng trên Linux (cloud), rồi chép về. Script chưa được chạy bằng Python trên Windows. Máy ảo Linux mà Claude dùng trên matthew-pc dừng mọi lệnh sau 3 phút và không vào được Hugging Face, nên không dùng được để dựng graph.
- `build_testdata.py` có một lỗi khi chạy trên Windows. Ở dòng 46 và 47, `re.sub` hiểu `\t` trong đường dẫn Windows là ký tự tab. Các lượt thử từ ngày 21/10 dùng một harness riêng trong scratchpad của Claude, đã tránh lỗi này. Harness giữ thứ tự cell như script, cho phép thay cell bằng bản sửa, và ghi kết quả vào thư mục `D:\tmp\rgdata\v4_*` mới. File `v4/scale_rows_v4.jsonl` không bị ghi đè.
- Kết quả trên Windows lệch nhẹ so với dữ liệu dựng trên Linux (115 trên 1.224 trường của 12 instance). Lý do là thứ tự node bằng điểm trong `_rrf` và sai khác nhỏ của embedding. Vì vậy các phép hồi quy so hai lượt trên cùng máy, cùng `PYTHONHASHSEED`.

### 14.12 Trạng thái sau các lượt chạy ngày 21 và 22/10/2026

Kết quả và thời gian của từng lượt nằm ở `experiment_log.md`. Mã lượt (v4-L1 đến v4-L4) dùng chung với file đó.

| Bước | Trạng thái | Ghi chú |
|---|---|---|
| A | Đã chạy (v4-L3) | `doc_cand`, `doc_cand_all`, `hist_cand`. Từ v4-L4, `hist_cand` bỏ hunk của commit sửa hơn 50 hàm/lớp |
| B | Đã chạy (v4-L2a) | `issue-fetch` đi theo link "next" của GitHub. `issue-index` có dấu cách tính từ 22/10, chưa chạy trên Kaggle |
| C | Đã chạy (v4-L2a, v4-L4) | Đã sửa hai lỗi của bản nháp: lấy file từ id, và hạng của gold không tìm thấy |
| D | Đã chạy (v4-L2a) | Fix kéo hàm bị sửa nhiều lần lên đầu danh sách ở Django |
| E | Chưa làm | Cần GPU |
| F | Đã chạy (v4-L4) | RRF có trọng số theo nguồn, chọn bằng kiểm định chéo 5 phần. RRF trọng số bằng nhau là đối chứng. Từ 27/10/2026 dùng RRF gốc với trọng số bằng nhau (mục 14.14) |
| G | Chưa làm | Cần bảng bằng chứng của bước I |
| H, phần `#ev-*` | Đã chạy (v4-L4) | 3.561 trên 3.561 request có nhãn |
| H, phần `#code2` | Đã cài (22/10), chưa chạy trên Kaggle | Kèm chấm lặp 100 instance để đo độ ổn định của judge |
| H, phần `#suff` | Chưa làm | Cần G |
| I | Đã cài (22/10), chưa chạy trên Kaggle | Bảng 3, Bảng 4, độ ổn định của judge, nDCG@10 |
| J | Chưa làm | |

**Quyết định trong lúc cài đặt.** Các quyết định dưới đây không có sẵn trong mục 14.2 đến 14.8.

1. `ISSUE_CUTOFF = "instance"` được hiểu là thời điểm tạo báo cáo của chính instance, theo đề xuất ở mục 9.4 của `research_context.md`. Khi nhận ra nhiều báo cáo, mốc cắt là báo cáo mới nhất tạo trước `created_at`. Khi không nhận ra báo cáo nào, mốc cắt là `created_at`. Giá trị `"pr"` dùng `created_at` của SWE-bench.
2. TF-IDF của ISSUE dùng `TfidfTransformer(sublinear_tf=True)` của scikit-learn với IDF mặc định, theo mục 6.5. Stop word chỉ gồm stop word tiếng Anh.
3. `issue_cand_refs` được ghi thêm cho biến thể có "Refs". Pool của judge chỉ lấy `issue_cand`.
4. Bước F ban đầu dùng RRF gốc với trọng số bằng nhau. Ở lượt v4-L2b, cách này làm +DOC và +ISSUE kém hơn AST rõ rệt, vì nguồn yếu có lá phiếu ngang AST. Bước F vì vậy chuyển sang RRF có trọng số theo nguồn. Trọng số được chọn bằng kiểm định chéo 5 phần theo MAP, nên không instance nào được đánh giá bằng trọng số chọn trên chính nó. Cơ sở là Bruch và cộng sự (ACM TOIS 2023): trộn có trọng số tốt hơn RRF khi trọng số được chọn bằng dữ liệu. Ngày 27/10/2026, việc chọn trọng số bị bỏ theo quyết định của người dùng, vì nó chọn tham số trên chính dữ liệu của đề tài. Bước F quay về RRF gốc với trọng số bằng nhau.
5. Bằng chứng HIST giữ đủ danh sách hàm/lớp mà commit đã sửa (mục 6.7). Từ v4-L4, hunk của commit sửa hơn 50 hàm/lớp bị bỏ khỏi `hist_cand`, theo ROSE và ngưỡng `HIST_MAX_TOUCH` của `hist-build`. Xếp hạng HIST không đổi.
6. Không chạy thử judge riêng trên vài chục instance. Prompt của judge giữ như bản đã cài.
7. Để kết quả lặp lại được: `_rrf` xếp node bằng điểm theo id (22/10), `issue-index` tự tính lại khi `ISSUE_CUTOFF` hoặc cách tính đổi (22/10), và `v4-run` tự dựng lại file kết quả khi thiếu dữ liệu bước A hoặc khi cách xếp hạng AST đổi (`V4_RANK_RULE`, 22/10).

**Việc tiếp theo, theo mức quan trọng.**

1. Dựng lại file kết quả với `_rrf` mới, để số liệu lặp lại được. Code đã cài, cần một lượt Kaggle (khoảng 65 phút cho `v4-run`).
2. Bước I: bảng bằng chứng từ nhãn judge. Code đã cài, cần cùng lượt Kaggle đó.
3. Bước G: chọn ngưỡng ngoại tuyến trên nhãn của pool.
4. Sửa cách nối doc với code (mục 6.10), trước khi đóng băng. Thiết kế đã chốt ngày 23/10/2026. Bước đầu là đo trước khi sửa trên `scale_rows_v4.jsonl`.
5. `#code2` và nDCG@10. Code đã cài, cần cùng lượt Kaggle đó.
6. Đo độ ổn định của judge bằng cách chấm lặp một mẫu. Code đã cài, cần cùng lượt Kaggle đó.
7. `#suff` cho Q4, sau bước G.
8. Chốt thành phần Fix (mục 14.10, ý 4).
9. Đóng băng (bước J), rồi giai đoạn 3.
10. Dọn notebook rồi commit. Notebook đang chứa `GOOGLE_API_KEY`, cell `verify-v4` mang id mới, và có một cell trống.

### 14.13 Trạng thái sau các thay đổi ngày 26/10/2026

| Phần | Trạng thái | Ghi chú |
|---|---|---|
| H, phần `#ev-*` và chấm lặp | Đã chạy (v4-L5). Cài đặt mới đã cài | Không lý do, thinking MINIMAL, batch 100 instance. Lượt tới chấm lại toàn bộ |
| H, phần `#code2` | Đã chạy (v4-L5), rồi bỏ ngày 26/10 | Thay bằng `depth-v4` (mục 6.13) |
| I | Đã chạy (v4-L5) | Phần nDCG@10 theo judge tự bỏ qua khi không có nhãn node code |
| `depth-v4` | Đã cài, đã chạy thử trên 12 instance mẫu | Số node phải đọc và độ sâu tới gold |
| Đợt confirm (mục 6.14) | Đã cài, đã chạy thử `v4-fusion` và `manifest` trên 12 instance mẫu | `V4_PHASE`, thư mục riêng, ISSUE cho mọi repo GitHub, trọng số chọn trên đợt main, nhóm repo có doc |
| `manifest` | Đã cài | Giá trị key được xóa trước khi băm |

**Việc tiếp theo.**
1. Lượt Kaggle với cài đặt judge mới và `depth-v4`, trên Django và SymPy.
2. Khóa pipeline: quyết định về việc sửa cách nối doc (mục 6.10) và việc chọn ngưỡng.
3. Lượt Kaggle của đợt confirm (`V4_PHASE = "confirm"`), sau khi pipeline được khóa.

### 14.14 Trạng thái sau các thay đổi ngày 27/10/2026

| Phần | Trạng thái | Ghi chú |
|---|---|---|
| Dọn notebook (mục 6.15) | Đã cài, đã chạy thử trên 12 instance mẫu | Bỏ v3 và code chỉ để phân tích. Notebook còn 45 cell. Kết quả trùng bản cũ |
| `hist-fix-check` | Đã bỏ khỏi notebook | Kết quả của bước D giữ ở mục 6.6 của `pipeline_design.md` |
| `judge-v4` | Đã sửa, chưa chạy trên Kaggle | Đọc file nhãn một lần cho mỗi phần batch |
| `manifest` | Đã sửa, chưa chạy trên Kaggle | Khóa của cell là số thứ tự trong `In` cộng dòng đầu |
| `v4-fusion` | Đã sửa, đã chạy thử trên 12 instance mẫu, chưa chạy trên Kaggle | RRF gốc của Cormack và cộng sự, trọng số bằng nhau, k = 60. Lưới trọng số, kiểm định chéo và 7 hệ thống đối chứng bị bỏ, nên còn 11 hệ thống. `manifest` ghi phương pháp trộn và k thay cho trọng số. Cần một lượt Run All trên Kaggle, khoảng 10 phút, không gọi judge |
| Các phần còn lại của mục 14.13 | Không đổi | |

**Việc tiếp theo.**
1. Lượt Kaggle với cài đặt judge mới và `depth-v4`, trên Django và SymPy.
2. Khóa pipeline, tức là quyết định về việc sửa cách nối doc (mục 6.10) và việc chọn ngưỡng.
3. Lượt Kaggle của đợt confirm (`V4_PHASE = "confirm"`), sau khi pipeline được khóa.
4. Quyết định bỏ hay giữ các cột `doc_r_*` và `doc_gold_*`, vì không cell nào còn đọc chúng.

### 14.15 Trạng thái sau lượt v4-L7 (27/10/2026)

Mục này thay cho phần "Việc tiếp theo" của mục 14.13 và 14.14.

| Phần | Trạng thái | Ghi chú |
|---|---|---|
| Judge chỉ chấm bằng chứng, không viết lý do, thinking MINIMAL | Đã chạy (v4-L6) | 3.861 trên 3.861 request có nhãn. κ của nhãn hữu ích khi gộp là 0,627 |
| `depth-v4` | Đã chạy (v4-L6, v4-L7) | Kết quả ở mục 8 và 9 của `experiment_log.md` |
| `v4-fusion` dùng RRF gốc | Đã chạy (v4-L7) | Hàng của 8 hệ thống chính trùng hàng "(RRF)" cùng tên ở v4-L6 |
| `cell-files` | Đã khôi phục, đã chạy (v4-L7) | Cell bị mất trong bản notebook quay về từ v4-L6 |
| `manifest` | Đã chạy (v4-L6, v4-L7) | v4-L6 ghi 0 cell vì `In` rỗng. v4-L7 ghi đủ 31 cell |
| `issue-index`, dấu cách tính | Đã chạy (v4-L6, v4-L7) | Dấu lấy mã của cell từ `In`. Khi `In` rỗng, dấu chỉ dựa trên cấu hình |
| Không chia dữ liệu (quyết định 58) | Đã cài, đã chạy thử trên 12 instance mẫu, chưa chạy trên Kaggle | `V4_PHASE` và hai thư mục riêng của đợt confirm bị bỏ. `SCALE_REPOS` gồm 12 repo. Kết quả ở `v4/`, nhãn ở `judge_v4/`. Mẫu chấm lặp là 130 instance trên mọi repo |

**Việc còn chờ quyết định hoặc chưa làm.**
1. Lượt Kaggle trên cả 12 repo của tập test. Cần `GITHUB_TOKEN`, và cần kiểm tra trước xem `/kaggle/working` còn graph cũ của 10 repo mới từ lượt v2 hay không.
2. Sửa cách nối doc với code (mục 6.10). Tiêu chí của mục này cần được chốt lại cho RRF gốc trước khi sửa.
3. Chọn ngưỡng cho số bằng chứng được giữ (bước G).
4. Bỏ việc phụ thuộc vào `In` ở `manifest` và ở dấu cách tính của `issue-index`, vì hai cell không báo lỗi khi `In` rỗng.
5. Quyết định về thành phần Fix của HIST. Ở v4-L7, Fix vẫn không thêm gì.
6. Kiểm tra snapshot trên 100 instance (việc 1.3).
7. Quyết định bỏ hay giữ các cột `doc_r_*` và `doc_gold_*`.

### 14.16 Trạng thái sau thay đổi ngày 28/10/2026

| Phần | Trạng thái | Ghi chú |
|---|---|---|
| Xếp hạng node sau hop theo KGCompass (`graph-proc`, mục 6.16) | Đã cài, đã chạy (v4-L8) | Trường cũ, danh sách của các hệ thống không có DOC, và 72 request của judge trùng bản cũ. l và S khớp với phép tính độc lập. Chi tiết ở mục 12 của `experiment_log.md` |
| `v4-fusion`, `verify-v4`, `depth-v4`, `manifest` | Đã sửa, đã chạy thử trên 12 instance mẫu | Thêm GRAPH, +GRAPH, +ALL+GRAPH, G1, G2 và họ Holm riêng. DOC đọc `doc_kgc` |

Ở 12 instance mẫu, số ứng viên trong ngân sách 4 có trung vị khoảng 5.500 đến 6.000 node, và có instance tới 11.246 node. Ngân sách 4 đi qua nhiều file và nhiều cạnh gọi, nên phần lớn thứ tự do độ giống văn bản quyết định. `graph-proc` mất dưới 1 giây cho mỗi instance trên máy. Venv thử nghiệm `D:\tmp\rgvenv` chưa có `rapidfuzz`, nên lượt thử dùng một bản cài riêng ngoài venv.

**Việc còn chờ quyết định hoặc chưa làm.** Danh sách ở mục 14.15 giữ nguyên, cộng thêm một việc.
8. Chạy `graph-proc` trên Kaggle cùng lượt 12 repo. Không phải chạy lại `v4-run`, `hist-proc`, `issue-index` hay judge. Sau lượt đó, phân tích ngoài notebook sẽ báo l của gold đầu tiên trong GRAPH, và tỷ lệ instance có gold là ứng viên của GRAPH nhưng nằm ngoài 500 node đầu của AST.

### 14.17 Trạng thái sau thay đổi thứ hai ngày 28/10/2026

| Phần | Trạng thái | Ghi chú |
|---|---|---|
| Phân tích ảnh hưởng của độ phủ doc (mục 6.17) | Đã cài, đã chạy (v4-L8) | `gold_doc` và `doc_cov` khớp với phép tính độc lập. `doc_cov` của Django và SymPy là 17,7% và 8,2%, khớp `coverage_report.md`. Khối phân tích được thử thêm trên dữ liệu giả 12 repo. Chi tiết ở mục 12 của `experiment_log.md` |
| Nhóm repo có doc (`V4_DOC_REPOS`) | Đã bỏ | Thay bằng phân tích độ phủ như một biến |

Thay đổi này cần có trước lượt Kaggle 12 repo. Nếu lượt đó chạy trước, lượt kế tiếp sẽ phải tính lại mọi instance, vì `v4-run` dựng lại file khi thiếu `gold_doc`.

### 14.18 Trạng thái sau đánh giá ngày 29/10/2026

| Phần | Trạng thái | Ghi chú |
|---|---|---|
| Judge v5 và độ đo bằng chứng mới (mục 6.18) | Đã cài, đã chạy thử trên 12 instance mẫu với client Gemini giả | Prompt v4 đo mức phần tử dẫn tới code của bản sửa, không đo giá trị nội dung |
| Lượt thử của judge v5 ở máy (mục 6.18.5) | Đã chạy trên 48 instance của Django và SymPy, gọi Gemini thật | Tiêu chí 3 đạt (κ trọng số khi chấm lặp 0,734). Tiêu chí 1 và 2 chờ nhãn tay. Không còn chế độ chạy thử trên Kaggle |
| HIST theo phần lời (`hist-msg`, mục 6.18.3) | Đã cài, đã chạy thử trên 12 instance mẫu | Thay Locus ở các hệ thống chính. Locus giữ thành hệ thống phụ "+HIST (Locus)" |
| Phân tích tầng xếp hạng ngoài notebook (bước 1 của mục 6.18.8) | Đã chạy trên file kết quả của v4-L8 | Kiểm định đổi dấu theo khối snapshot, trung bình theo repo, bảng riêng cho 10 repo mới. Chưa ghi vào `experiment_log.md` |
| Đối chứng G2 "+ALL, AST hai lần" | Đã đo ngoài notebook | Top@1 20,6, Top@10 58,8, MRR 0,332, so với 21,1, 60,0 và 0,336 của +ALL+GRAPH. GRAPH và AST trùng trung vị 8 trên 10 node đầu |
| Mục 6.10, sửa cách nối doc | Cần viết lại | Thay đổi 2 lỗi thời vì DOC dùng `doc_kgc`. Thay đổi 3 không đạt điều kiện: chunk ngắn chiếm 12,2% pool SymPy và có tỷ lệ hữu ích cao hơn |

**Việc tiếp theo.** Theo thứ tự ở mục 6.18.8. Danh sách ở mục 14.15 và 14.16 giữ nguyên, trừ việc 2 (sửa cách nối doc), lùi sau lượt judge v5.
