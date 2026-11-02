# Nhật ký thực nghiệm RepoGraph

Cập nhật ngày 28/10/2026.

File này ghi lại từng lượt chạy thực nghiệm, để so kết quả giữa các lượt. Mỗi lượt ghi cấu hình, kỹ thuật đã dùng, thời gian chạy, kết quả, đánh giá và sự cố. Định nghĩa độ đo nằm ở mục 13 của `research_context.md`. Thiết kế của từng kỹ thuật nằm ở `pipeline_design.md`. Kế hoạch nằm ở mục 14 của `planning.md`.

**Quy ước.**
- Giờ chạy là giờ UTC, lấy từ metadata của cell trong notebook tải về từ Kaggle.
- Số liệu lấy từ output của cell trong notebook. Top@k, Acc@k tính theo phần trăm. MRR, MAP và nDCG tính từ 0 đến 1. Hạng được tính tới 500.
- Dấu ✓ trong bảng kiểm định nghĩa là có ý nghĩa sau hiệu chỉnh Holm, với p < 0,05.
- Lượt v2 và v3 chỉ được tóm tắt. Chi tiết của chúng nằm ở mục 5 và 7.9 của `research_context.md`.

---

## 1. Bảng tổng hợp các lượt

| Mã | Ngày (UTC) | Instance | Thay đổi chính | AST Top@10 / MRR / MAP | Hệ thống tốt nhất | Ghi chú |
|---|---|---|---|---|---|---|
| v2 | Trước v3 | 1.924 (12 repo, tập test) | AST và DOC trên 12 repo | Xem `research_context.md` mục 5 | DOC | Kết quả theo judge không còn đáng tin |
| v3 | Trước 14/10/2026 | 1.006 (tập test của Django, SymPy) | Thêm lớp history, judge mới | Hit@10 57,3 | DOC+HIST: Hit@10 62,4 | Oracle cũ |
| v4-L1 | 15/10/2026 | 1.187 | Oracle mới, xếp hạng tới 500, HIST theo Locus (chưa trộn) | 55,5 / 0,345 / 0,266 | DOC+HIST (v3): 61,2 / 0,356 / 0,276 | Kết luận hẹp giữ nguyên |
| v4-L2a | 21/10/2026, 10:48 | 1.187 | Thêm ISSUE, `hist-fix-check`, `verify-v4` hai mức | 55,5 / 0,345 / 0,266 | DOC+HIST (v3) | Judge 0 request, vì file kết quả cũ chưa được dựng lại |
| v4-L2b | 21/10/2026, 11:22 | 1.187 | `v4-fusion` với RRF trọng số bằng nhau | 55,5 / 0,345 / 0,266 | +HIST: 62,4 / 0,393 / 0,309 | DOC và ISSUE làm kết quả kém đi |
| v4-L3 | 21/10/2026, 20:11 | 1.187 | Dựng lại file kết quả (có dữ liệu bước A), trộn có trọng số chọn bằng kiểm định chéo | 55,5 / 0,344 / 0,265 | Chưa có (`verify-v4` không chạy) | Judge dừng ở batch 5 vì hết hạn mức Gemini |
| v4-L4 | 22/10/2026, 03:31 | 1.187 | Bỏ hunk của commit lớn khỏi bằng chứng HIST, judge chấm đủ | 55,5 / 0,344 / 0,265 | ALL−DOC: 62,3 / 0,398 / 0,312. +ALL: 62,2 / 0,392 / 0,308 | Lượt đầy đủ đầu tiên của v4 |
| v4-L5 | 22/10/2026, 16:01 | 1.187 | Dựng lại file kết quả với `_rrf` xếp hòa theo id; judge chấm `#code2` và chấm lặp; bảng bằng chứng, độ ổn định của judge, nDCG@10 | 55,5 / 0,345 / 0,265 | ALL−DOC: 62,1 / 0,402 / 0,316. +ALL: 62,3 / 0,389 / 0,306 | Thêm DOC vào HIST và ISSUE làm Top@1, MRR, MAP giảm có ý nghĩa |
| v4-L6 | 27/10/2026, 04:38 | 1.187 | Judge chỉ chấm bằng chứng, không viết lý do, thinking MINIMAL; thêm `depth-v4`; notebook đã dọn | 55,5 / 0,345 / 0,265 | Như L5 | Xếp hạng trùng L5 ở mọi ô. `manifest` không băm được cell nào |
| v4-L7 | 27/10/2026, 07:54 | 1.187 | RRF gốc, trọng số bằng nhau, k = 60; không tham số nào chọn trên dữ liệu | 55,5 / 0,345 / 0,265 | +HIST: 62,4 / 0,393 / 0,309 | +ALL tốt hơn AST ở Top@10, kém hơn ở Top@1 và MAP. `manifest` băm đủ 31 cell |
| v4-L8 | 28/10/2026, 07:24 | 2.214 (12 repo, tập test) | Thêm 10 repo; GRAPH và DOC mới theo KGCompass (`graph-proc`); phân tích độ phủ doc; sửa cách đọc output của git | 54,2 / 0,331 / 0,247 | +HIST: 59,3 / 0,375 / 0,283. +ALL+GRAPH có Top@10 cao nhất (60,0) | +ALL không còn tốt hơn AST ở Top@10. GRAPH và DOC mới không đạt tiêu chí đặt trước |

---

## 2. Lượt v4-L1 (15/10/2026)

**Cấu hình.** Oracle mới (việc 1.1). Xếp hạng AST được lưu tới 500 node. Bốn hệ thống của v3 được tính lại với đúng cấu hình trộn mà v3 đã chọn: DOC với p = 0,1 và h = 1, HIST (v3) với 10 commit, p = 0,25 và h = 3, DOC+HIST với h = 3. HIST theo Locus được tính nhưng chưa trộn với AST.

**Thời gian.** `hist-build` mất 29,3 phút. `v4-run` mất 54,8 phút. `hist-proc` mất 30,6 phút, gồm cả bước dựng chỉ mục hunk.

**Kết quả, mức hàm/lớp.**

| Hệ thống | Top@1 | Top@5 | Top@10 | MRR | MAP | Acc@10 |
|---|---|---|---|---|---|---|
| AST | 23,9 | 45,6 | 55,5 | 0,345 | 0,266 | 33,6 |
| DOC (v3) | 23,9 | 46,7 | 57,4 | 0,349 | 0,268 | 35,8 |
| HIST (v3) | 23,9 | 50,7 | 59,7 | 0,354 | 0,274 | 36,9 |
| DOC+HIST (v3) | 23,9 | 51,2 | 61,2 | 0,356 | 0,276 | 38,4 |

McNemar cho Top@10 (số instance chỉ hệ thống thứ nhất trúng / chỉ hệ thống thứ hai trúng): DOC so với AST là 26 / 4. HIST so với AST là 71 / 21. DOC+HIST so với AST là 87 / 19.

**HIST theo Locus đứng riêng, Top@10.**

| Repo | AST | Chỉ NL | NL+CE | Đủ, có Fix |
|---|---|---|---|---|
| Django | 56,6 | 53,2 | 57,7 | 43,1 |
| SymPy | 53,0 | 44,5 | 50,3 | 48,9 |

**Đánh giá.** Kết luận hẹp (DOC+HIST tốt hơn AST) vẫn đúng với oracle mới. Thành phần Fix làm HIST đứng riêng giảm mạnh ở Django.

---

## 3. Lượt v4-L2a (21/10/2026, 10:48)

**Thay đổi so với L1.** Các cell mới hoặc đã sửa theo mục 14 của `planning.md`:
- Bước A: lưu ứng viên bằng chứng kèm điểm gốc.
- Bước B: nguồn ISSUE (`issue-fetch`, `issue-index`).
- Bước C: `verify-v4`.
- Bước D: `hist-fix-check`.
- Bước H, phần bằng chứng: `judge-v4`.

**Sự cố.**
1. Lần chạy đầu dừng ở `issue-fetch` với lỗi 422 của GitHub. GitHub chỉ nhận tham số `page` cho 1.000 mục đầu. Cell được sửa để đi theo link "next" có con trỏ `after`.
2. File `scale_rows_v4.jsonl` của L1 chưa được đổi tên. `v4-run` và `hist-proc` bỏ qua các dòng đã có, nên dữ liệu bước A không được tạo, và `judge-v4` tạo 0 request.

**Thời gian.** `issue-fetch` mất 8,3 phút (242 trang GitHub, có token). `issue-index` mất 1,4 phút. `hist-fix-check` mất 3,0 phút.

**Kết quả ISSUE.**

| Chỉ số | Django | SymPy |
|---|---|---|
| Số báo cáo cũ | 19.388 ticket Trac (fixed) | 9.607 issue (trong 24.139 mục, có 14.532 PR) |
| Báo cáo nối được tới đơn vị history | 52,8% | 27,5% |
| Cặp liên kết | 10.089 fixed, 3.621 refs | 2.678 fixed |
| Nhận ra báo cáo của chính instance | 98,7% | 95,4% |
| Mốc cắt lấy từ báo cáo của instance | 96,3% | 94,3% |
| Báo cáo cũ dùng được mỗi instance, trung vị | 5.410 (thêm Refs: 5.608) | 1.075 |
| Mức trần | 83,2% (thêm Refs: 88,1%) | 63,4% |
| Top@10 của ISSUE đứng riêng | 21,1% (thêm Refs: 21,4%) | 18,6% |

**Kết quả `hist-fix-check` (bước D).**

| Chỉ số | Django | SymPy |
|---|---|---|
| Đơn vị khớp `fix\|bug`, trên mọi đơn vị | 59,5% | 25,3% |
| Đơn vị khớp `fix\|bug`, trên đơn vị có touch | 68,9% | 27,5% |
| Trung vị số lần bị sửa của 10 hàm/lớp đầu, bỏ Fix | 6,5 | 5,5 |
| Như trên, có Fix | 37,5 | 6,5 |
| Top@10 khi bỏ Fix (NL+CE) | 57,7 | 50,3 |
| Top@10 khi có Fix, A3 hiện tại | 43,1 | 48,9 |
| Top@10 khi có Fix, A3 khác (t = 0 ở đơn vị cũ nhất trong 5 năm trước snapshot) | 51,6 | 50,3 |

Ở Django, Fix làm Top@10 giảm ở mọi nhóm số lần gold bị sửa, từ 10,5 tới 24,2 điểm. Ở SymPy, mức thay đổi chỉ từ −4,6 tới +0,9 điểm. Fix kéo các hàm bị sửa nhiều lần lên đầu danh sách. A3 khác giảm được một phần thiệt hại nhưng không xóa hết.

**`verify-v4` hai mức, với bốn hệ thống của v3 (chưa có `v4-fusion`).**

| Hệ thống | Hàm/lớp Top@10 | Hàm/lớp MAP | File Top@1 | File Top@10 | File MAP |
|---|---|---|---|---|---|
| AST | 55,5 | 0,266 | 47,3 | 85,6 | 0,558 |
| +DOC (v3) | 57,4 | 0,268 | 47,3 | 86,1 | 0,562 |
| +HIST (v3) | 59,7 | 0,274 | 47,3 | 87,0 | 0,563 |
| DOC+HIST (v3) | 61,2 | 0,276 | 47,3 | 87,1 | 0,564 |

Số mức hàm/lớp trùng `v3-recheck`, đúng như dự kiến.

---

## 4. Lượt v4-L2b (21/10/2026, 11:22)

**Thay đổi so với L2a.** Thêm `v4-fusion` với RRF gốc (Cormack, Clarke, Büttcher, SIGIR 2009). Hằng số là k = 60, mọi danh sách có trọng số bằng nhau, không giữ cố định đầu danh sách AST. Mỗi nguồn xếp theo bằng chứng của chính nó.

**Kết quả, mức hàm/lớp.**

| Hệ thống | Top@1 | Top@5 | Top@10 | Acc@10 | MRR | MAP |
|---|---|---|---|---|---|---|
| AST | 23,9 | 45,6 | 55,5 | 33,6 | 0,345 | 0,266 |
| +DOC | 11,7 | 28,9 | 43,7 | 25,0 | 0,215 | 0,161 |
| +HIST | 27,9 | 52,0 | 62,4 | 39,1 | 0,393 | 0,309 |
| +ISSUE | 16,9 | 35,6 | 48,8 | 26,2 | 0,268 | 0,198 |
| +ALL | 19,1 | 46,8 | 59,6 | 36,4 | 0,318 | 0,241 |
| ALL−DOC | 21,4 | 45,3 | 57,0 | 34,1 | 0,330 | 0,251 |
| ALL−HIST | 14,6 | 36,1 | 49,4 | 28,8 | 0,257 | 0,193 |
| ALL−ISSUE | 17,5 | 47,6 | 62,4 | 39,8 | 0,310 | 0,241 |

| Câu hỏi | ΔTop@1 | ΔTop@10 | ΔMRR | ΔMAP |
|---|---|---|---|---|
| Q1: +DOC so với AST | −12,2 ✓ | −11,8 ✓ | −0,130 ✓ | −0,105 ✓ |
| Q2: +HIST so với AST | +4,0 ✓ | +6,9 ✓ | +0,048 ✓ | +0,044 ✓ |
| Q3: +ISSUE so với AST | −7,0 ✓ | −6,7 ✓ | −0,077 ✓ | −0,068 ✓ |
| Q4: +ALL so với AST | −4,8 ✓ | +4,0 ✓ | −0,027 | −0,025 ✓ |
| Q5: +ALL so với ALL−DOC | −2,3 | +2,5 ✓ | −0,012 | −0,009 |
| Q6: +ALL so với ALL−HIST | +4,5 ✓ | +10,2 ✓ | +0,061 ✓ | +0,048 ✓ |
| Q7: +ALL so với ALL−ISSUE | +1,6 | −2,9 ✓ | +0,008 | +0,000 |

**Đánh giá.** RRF trọng số bằng nhau cho DOC và ISSUE một lá phiếu ngang AST. Hai danh sách này yếu hơn AST nhiều, nên các node đầu của chúng đẩy gold của AST xuống. Ở v3, DOC với trọng số 0,1 thì tăng Top@10 thêm 1,9 điểm. Như vậy kết quả phụ thuộc rất nhiều vào trọng số. Lượt này dẫn tới quyết định trộn có trọng số theo nguồn.

---

## 5. Lượt v4-L3 (21/10/2026, 20:11)

**Thay đổi so với L2b.**
- `v4-run` tự nhận ra file kết quả thiếu dữ liệu bước A, đổi tên file đó thành `scale_rows_v4_truoc_buoc_A.jsonl`, rồi tính lại mọi instance.
- `v4-fusion` chuyển sang RRF có trọng số theo nguồn: score(d) = 1/(60 + hạng AST) + Σ_s w_s/(60 + hạng trong nguồn s). Lưới w_s gồm 0,05; 0,1; 0,2; 0,3; 0,5; 0,75; 1; 1,5; 2 và 3. Trọng số được chọn bằng kiểm định chéo 5 phần theo MAP, với seed 20261021. RRF trọng số bằng nhau được giữ làm 7 hệ thống đối chứng.

**Thời gian.** `v4-run` mất 65,1 phút. `hist-proc` mất 3,9 phút. `v4-fusion` mất 1,2 phút. `judge-v4` dừng sau 17,8 phút.

**Trọng số đã chọn (giống hệt ở L4).**

| Hệ thống | Trọng số của từng nguồn ở 5 phần |
|---|---|
| +DOC | 0,05 ở cả 5 phần |
| +HIST | 0,75; 1; 0,75; 1; 1,5 |
| +ISSUE | 0,05; 0,1; 0,05; 0,05; 0,05 |
| +ALL (DOC / HIST / ISSUE) | 0,05 / 0,75 đến 1,5 / 0,05 đến 0,2 |
| ALL−ISSUE (DOC / HIST) | 0,05 / 0,75 đến 2 |

DOC luôn ở giá trị nhỏ nhất của lưới. HIST ngang AST. ISSUE chỉ góp rất nhẹ.

**Judge.** Độ dài request (token, ước lượng bằng số ký tự chia 4):

| Loại | Trung bình | p90 | Lớn nhất |
|---|---|---|---|
| ev-doc | 5.012 | 6.191 | 13.867 |
| ev-hist | 38.124 | 92.909 | 776.708 |
| ev-issue | 5.636 | 8.966 | 63.951 |

Bốn batch đầu (600 instance Django, mỗi batch 3,4 đến 3,7 triệu token) chấm xong, với 1.799 trên 1.800 request hợp lệ. Batch 5 bị Gemini từ chối với lỗi 429 "You exceeded your current quota". Lúc đó không còn batch nào đang xếp hàng, nên nguyên nhân là hạn mức của tài khoản.

**Sự cố.** Request HIST quá dài. Commit sửa hơn 50 hàm/lớp chỉ chiếm 1,0% số commit của Django và 2,4% của SymPy. Nhưng chúng chứa 25% và 39% số hunk, và mỗi hunk kéo theo danh sách tới hơn 1.500 hàm/lớp.

---

## 6. Lượt v4-L4 (22/10/2026, 03:31), lượt đầy đủ

**Thay đổi so với L3.** `hist-proc` bỏ hunk của commit sửa hơn 50 hàm/lớp (`HIST_MAX_TOUCH`) khỏi bằng chứng HIST (`hist_cand`), và bù bằng hunk kế tiếp. Xếp hạng HIST không đổi. Cơ sở là ROSE (bỏ transaction chạm hơn 30 thực thể) và ngưỡng đã có ở `hist-build`.

**Thời gian.** `hist-proc` mất 3,4 phút. `hist-fix-check` mất 2,4 phút. `v4-fusion` mất 1,1 phút. `judge-v4` mất 61,7 phút.

**Judge.** Request ev-hist giờ có trung bình 6.011 token (p90 8.515, lớn nhất 34.354). Bốn batch đầu chấm lại 466 request, chủ yếu là request ev-hist có nội dung đổi sau khi bỏ commit lớn. Batch 5 đến 8 gồm 1.761 request, mỗi batch 2,4 đến 2,6 triệu token. Kết quả là 3.561 trên 3.561 request có nhãn. Một request được chấm lại bằng gọi thường. Nhãn chưa được phân tích, vì bảng bằng chứng (bước I) chưa cài.

**Kết quả, mức hàm/lớp, gộp hai repo.**

| Hệ thống | Top@1 | Top@5 | Top@10 | Acc@5 | Acc@10 | MRR | MAP |
|---|---|---|---|---|---|---|---|
| AST | 23,8 | 45,7 | 55,5 | 26,3 | 33,6 | 0,344 | 0,265 |
| +DOC | 22,4 | 46,7 | 56,4 | 26,5 | 34,5 | 0,340 | 0,259 |
| +HIST | 27,5 | 52,3 | 62,1 | 31,8 | 38,6 | 0,390 | 0,306 |
| +ISSUE | 24,3 | 46,7 | 56,7 | 26,9 | 34,0 | 0,355 | 0,272 |
| +ALL | 27,7 | 52,8 | 62,2 | 32,2 | 38,8 | 0,392 | 0,308 |
| ALL−DOC | 28,7 | 52,6 | 62,3 | 31,7 | 38,9 | 0,398 | 0,312 |
| ALL−HIST | 23,6 | 48,6 | 58,0 | 28,4 | 35,3 | 0,355 | 0,273 |
| ALL−ISSUE | 26,8 | 52,4 | 61,8 | 32,1 | 38,7 | 0,385 | 0,303 |
| +HIST (chỉ NL) | 25,2 | 49,3 | 59,2 | 29,7 | 36,4 | 0,367 | 0,285 |
| +HIST (NL+CE) | 26,9 | 52,1 | 62,3 | 32,4 | 39,4 | 0,385 | 0,308 |
| +ISSUE (thêm Refs) | 24,8 | 46,7 | 56,4 | 27,0 | 33,8 | 0,357 | 0,274 |
| +DOC (RRF) | 11,6 | 29,0 | 43,6 | 14,6 | 25,0 | 0,215 | 0,161 |
| +HIST (RRF) | 28,0 | 51,9 | 62,4 | 31,7 | 39,1 | 0,394 | 0,310 |
| +ISSUE (RRF) | 16,8 | 35,6 | 48,9 | 18,9 | 26,3 | 0,268 | 0,198 |
| +ALL (RRF) | 19,1 | 46,8 | 59,6 | 26,1 | 36,4 | 0,318 | 0,241 |

**Kiểm định, mức hàm/lớp.**

| Câu hỏi | ΔTop@1 | ΔTop@5 | ΔTop@10 | ΔMRR | ΔMAP | Instance tốt hơn / kém hơn |
|---|---|---|---|---|---|---|
| Q1: +DOC so với AST | −1,3 | +1,0 | +0,8 ✓ | −0,004 | −0,006 | 15,7% / 16,8% |
| Q2: +HIST so với AST | +3,8 ✓ | +6,7 ✓ | +6,6 ✓ | +0,046 ✓ | +0,041 ✓ | 49,5% / 24,2% |
| Q3: +ISSUE so với AST | +0,5 | +1,0 | +1,2 ✓ | +0,011 | +0,007 | 26,8% / 20,4% |
| **Q4: +ALL so với AST** | **+4,0 ✓** | **+7,2 ✓** | **+6,7 ✓** | **+0,048 ✓** | **+0,043 ✓** | **49,2% / 25,5%** |
| Q5: +ALL so với ALL−DOC | −1,0 | +0,3 | −0,2 | −0,006 | −0,005 | 16,8% / 20,4% |
| Q6: +ALL so với ALL−HIST | +4,1 ✓ | +4,2 ✓ | +4,2 ✓ | +0,037 ✓ | +0,035 ✓ | 45,8% / 25,9% |
| Q7: +ALL so với ALL−ISSUE | +0,9 | +0,4 | +0,4 | +0,007 | +0,005 | 29,0% / 21,8% |

**Kết quả, mức file, gộp hai repo.**

| Hệ thống | Top@1 | Top@5 | Top@10 | Acc@1 | Acc@5 | MRR | MAP |
|---|---|---|---|---|---|---|---|
| AST | 47,3 | 76,7 | 85,6 | 35,9 | 64,2 | 0,606 | 0,558 |
| +DOC | 47,6 | 77,3 | 86,0 | 35,8 | 64,6 | 0,610 | 0,560 |
| +HIST | 52,9 | 77,6 | 86,4 | 41,2 | 65,0 | 0,641 | 0,594 |
| +ISSUE | 47,5 | 77,8 | 86,0 | 36,1 | 64,9 | 0,611 | 0,562 |
| +ALL | 51,6 | 78,1 | 85,8 | 39,9 | 65,0 | 0,635 | 0,587 |
| ALL−DOC | 52,1 | 78,1 | 86,8 | 40,7 | 65,2 | 0,638 | 0,592 |

Ở mức file, Q2 và Q4 có ý nghĩa ở Top@1 (+5,6 và +4,3), MRR và MAP. Top@10 mức file không đổi có ý nghĩa ở câu nào, vì AST đã đạt 85,6%.

**Theo repo, mức hàm/lớp, Top@10 / MRR.**

| Hệ thống | Django (821 instance) | SymPy (366 instance) |
|---|---|---|
| AST | 56,6 / 0,343 | 53,0 / 0,348 |
| +HIST | 64,1 / 0,397 | 57,7 / 0,375 |
| +ALL | 63,7 / 0,400 | 58,7 / 0,375 |
| ALL−DOC | 64,1 / 0,407 | 58,5 / 0,378 |

**Theo độ khó của AST, +ALL so với AST.**

| Nhóm | Tốt hơn | Kém hơn |
|---|---|---|
| Gold đã ở top 10 (659 instance) | 34,9% | 29,4% |
| Gold ở hạng 11 đến 100 (308 instance) | 76,3% | 23,1% |
| Gold ngoài hạng 100 (220 instance) | 54,1% | 17,3% |

**Theo việc issue có nêu tên gold, Top@10 / MRR.**

| Hệ thống | Có nêu tên (572 instance) | Không nêu tên (615 instance) |
|---|---|---|
| AST | 72,4 / 0,494 | 39,8 / 0,205 |
| +HIST | 79,2 / 0,556 | 46,2 / 0,236 |
| +ISSUE | 72,9 / 0,501 | 41,6 / 0,219 |
| +ALL | 78,7 / 0,549 | 46,8 / 0,246 |

**Đánh giá.**
- Truy xuất đa nguồn tốt hơn chỉ dùng code ở mọi độ đo chính, có ý nghĩa thống kê (Q4).
- Gần như toàn bộ phần tăng đến từ HIST. +HIST đứng riêng gần bằng +ALL. DOC và ISSUE không thêm gì khi đã có HIST (Q5, Q7).
- Trong HIST, CE đóng góp nhiều nhất: +3,1 điểm Top@10 so với chỉ dùng NL. Fix không thêm gì sau khi trộn.
- Trộn có trọng số sửa được thiệt hại của RRF trọng số bằng nhau. Ví dụ, Top@10 của +DOC là 56,4 so với 43,6, và của +ALL là 62,2 so với 59,6.
- Liên kết "Refs" của Django không giúp.
- Giá trị của DOC và ISSUE như nội dung cho agent chưa được đánh giá. Phần này cần bảng bằng chứng từ nhãn judge.

**Giới hạn.** Cách trộn, lưới trọng số và tiêu chí MAP được chọn sau khi đã thấy L2b. Vì vậy đây vẫn là thực nghiệm khám phá, và cần xác nhận ở giai đoạn 3.

---

## 7. Lượt v4-L5 (22/10/2026, 16:01)

**Thay đổi so với L4.**
- `_rrf` ở cell `ec3fc119` xếp node bằng điểm theo id. `v4-run` có `V4_RANK_RULE = "rrf-tie-id"`, nên file kết quả được dựng lại. Mục đích là để số liệu lặp lại được giữa các lượt (mục 11).
- `issue-index` có dấu cách tính (`54c905e4dbca`), để tự tính lại khi `ISSUE_CUTOFF` hoặc cách tính đổi.
- `judge-v4` chấm thêm `#code2` (node code mới vào top 10 của 8 hệ thống chính mà chưa có nhãn của judge v3) và chấm lặp 100 instance với thứ tự phần tử khác.
- `verify-v4` chạy phần bằng chứng lần đầu: Bảng 3 (độ đo của từng loại bằng chứng), Bảng 4 (loại thông tin), độ ổn định của judge và nDCG@10 theo judge.

**Cấu hình.** Giống L4. `V4_EVID_N = 10`, `ISSUE_CUTOFF = "instance"`, `HIST_MAX_TOUCH = 50`. Lưới trọng số và kiểm định chéo 5 phần như mục 5, seed 20261021. Chấm lặp lấy 100 instance với seed 20261022. Judge là gemini-3.1-flash-lite qua Batch API, mỗi batch 150 instance.

Trọng số chọn được gần như giống L4. So với các giá trị đã ghi cho L4, +ALL ở phần 0 chọn DOC 0,1 thay cho 0,05, và ALL−ISSUE chọn HIST từ 0,75 đến 1,5 thay cho 0,75 đến 2. L4 không ghi trọng số của ALL−DOC và ALL−HIST.

| Hệ thống | Trọng số của từng nguồn ở 5 phần |
|---|---|
| +DOC | 0,05 ở cả 5 phần |
| +HIST | 0,75; 1; 0,75; 1; 1,5 |
| +ISSUE | 0,05; 0,1; 0,05; 0,05; 0,05 |
| +ALL (DOC / HIST / ISSUE) | 0,1 / 0,75 / 0,05; 0,05 / 1,5 / 0,2; 0,05 / 1 / 0,1; 0,05 / 1 / 0,1; 0,05 / 1 / 0,2 |
| ALL−DOC (HIST / ISSUE) | 1 / 0,1 ở cả 5 phần |
| ALL−HIST (DOC / ISSUE) | 0,05 / 0,1, riêng phần 3 là 0,05 / 0,05 |
| ALL−ISSUE (DOC / HIST) | 0,05 / 0,75 đến 1,5 |

**Thời gian.** Lượt chạy Run All hai lần trong cùng phiên Kaggle. Output trong notebook là của lần thứ hai, bắt đầu lúc 16:01. Ở lần thứ hai, `v4-run` và `hist-proc` không còn instance nào phải tính, nên file kết quả đã được dựng lại ở lần đầu. Số liệu của AST khác L4 cũng cho thấy điều này. Output và thời gian của lần đầu không còn. Ở lần thứ hai, `hist-fix-check` mất 3,2 phút, `v4-fusion` mất 1,2 phút, `judge-v4` mất 96,7 phút và `verify-v4` mất 1,3 phút.

**Judge.** 5.044 trên 5.044 request có nhãn: 3.561 request bằng chứng, 1.183 request `#code2` và 300 request chấm lặp. Nhãn node code của judge v3 được dùng lại cho 14.758 cặp (instance, node).

| Loại | Request | Độ dài trung bình (token) | p90 | Lớn nhất |
|---|---|---|---|---|
| `#code2` | 1.183 | 11.368 | 27.210 | 90.693 |
| Chấm lặp, doc | 100 | 5.047 | 6.640 | 10.257 |
| Chấm lặp, history | 100 | 6.082 | 8.949 | 12.644 |
| Chấm lặp, issue cũ | 100 | 5.395 | 8.973 | 18.198 |

Độ dài ước lượng bằng số ký tự chia 4. Request bằng chứng giữ nguyên độ dài như L4.

**Kết quả, mức hàm/lớp, gộp hai repo.**

| Hệ thống | Top@1 | Top@5 | Top@10 | Acc@5 | Acc@10 | MRR | MAP |
|---|---|---|---|---|---|---|---|
| AST | 23,8 | 45,6 | 55,5 | 26,2 | 33,6 | 0,345 | 0,265 |
| +DOC | 22,5 | 46,6 | 56,4 | 26,5 | 34,5 | 0,340 | 0,259 |
| +HIST | 27,5 | 52,3 | 62,1 | 31,8 | 38,6 | 0,390 | 0,306 |
| +ISSUE | 24,3 | 46,6 | 56,7 | 26,8 | 34,0 | 0,355 | 0,273 |
| +ALL | 27,3 | 53,1 | 62,3 | 32,4 | 38,9 | 0,389 | 0,306 |
| ALL−DOC | 29,3 | 52,8 | 62,1 | 32,1 | 38,8 | 0,402 | 0,316 |
| ALL−HIST | 23,3 | 48,5 | 57,7 | 28,4 | 35,2 | 0,352 | 0,271 |
| ALL−ISSUE | 26,8 | 52,5 | 62,1 | 32,0 | 39,1 | 0,385 | 0,303 |
| +HIST (chỉ NL) | 24,9 | 49,5 | 59,6 | 29,8 | 37,0 | 0,366 | 0,286 |
| +HIST (NL+CE) | 26,7 | 52,3 | 62,3 | 32,1 | 39,6 | 0,384 | 0,306 |
| +ISSUE (thêm Refs) | 24,8 | 46,6 | 56,4 | 26,9 | 33,8 | 0,357 | 0,275 |
| +DOC (RRF) | 11,7 | 28,9 | 43,6 | 14,6 | 25,0 | 0,215 | 0,161 |
| +HIST (RRF) | 27,9 | 51,9 | 62,4 | 31,6 | 39,1 | 0,393 | 0,309 |
| +ISSUE (RRF) | 16,9 | 35,7 | 48,8 | 19,0 | 26,2 | 0,268 | 0,198 |
| +ALL (RRF) | 19,1 | 46,8 | 59,6 | 26,1 | 36,4 | 0,318 | 0,241 |

**Kiểm định, mức hàm/lớp.** ΔMRR được tính từ bảng trên, nên có thể lệch 0,001 do làm tròn.

| Câu hỏi | ΔTop@1 | ΔTop@5 | ΔTop@10 | ΔMRR | ΔMAP | Instance tốt hơn / kém hơn |
|---|---|---|---|---|---|---|
| Q1: +DOC so với AST | −1,3 | +1,0 | +0,8 ✓ | −0,005 | −0,006 | 15,7% / 16,8% |
| Q2: +HIST so với AST | +3,7 ✓ | +6,7 ✓ | +6,6 ✓ | +0,045 ✓ | +0,041 ✓ | 49,5% / 24,3% |
| Q3: +ISSUE so với AST | +0,5 | +1,0 | +1,2 ✓ | +0,010 | +0,008 | 26,5% / 20,2% |
| **Q4: +ALL so với AST** | **+3,5 ✓** | **+7,5 ✓** | **+6,7 ✓** | **+0,044 ✓** | **+0,041 ✓** | **49,0% / 25,9%** |
| Q5: +ALL so với ALL−DOC | −2,0 ✓ | +0,3 | +0,2 | −0,013 ✓ | −0,010 ✓ | 16,2% / 20,8% |
| Q6: +ALL so với ALL−HIST | +4,0 ✓ | +4,5 ✓ | +4,5 ✓ | +0,037 ✓ | +0,035 ✓ | 46,2% / 25,9% |
| Q7: +ALL so với ALL−ISSUE | +0,5 | +0,6 | +0,2 | +0,004 | +0,003 | 26,8% / 22,9% |

**Kết quả, mức file, gộp hai repo.**

| Hệ thống | Top@1 | Top@5 | Top@10 | Acc@1 | Acc@5 | MRR | MAP |
|---|---|---|---|---|---|---|---|
| AST | 47,2 | 76,8 | 85,6 | 35,8 | 64,3 | 0,605 | 0,558 |
| +DOC | 47,6 | 77,4 | 86,0 | 35,8 | 64,7 | 0,610 | 0,561 |
| +HIST | 52,9 | 77,6 | 86,4 | 41,2 | 65,0 | 0,641 | 0,594 |
| +ISSUE | 47,4 | 77,9 | 86,0 | 36,0 | 65,0 | 0,610 | 0,561 |
| +ALL | 51,6 | 78,2 | 85,8 | 40,0 | 64,9 | 0,635 | 0,588 |
| ALL−DOC | 52,4 | 78,0 | 86,4 | 40,8 | 65,1 | 0,640 | 0,593 |

Ở mức file, Q2 và Q4 có ý nghĩa ở Top@1 (+5,7 và +4,5), Acc@1, MRR và MAP. Q6 chỉ có ý nghĩa ở Acc@1. Q3 có ý nghĩa ở Top@5 (+1,1). Top@10 mức file không đổi có ý nghĩa ở câu nào.

**Theo repo, mức hàm/lớp, Top@10 / MRR.**

| Hệ thống | Django (821 instance) | SymPy (366 instance) |
|---|---|---|
| AST | 56,6 / 0,343 | 53,0 / 0,349 |
| +HIST | 64,1 / 0,397 | 57,7 / 0,375 |
| +ALL | 63,8 / 0,398 | 58,7 / 0,371 |
| ALL−DOC | 63,7 / 0,410 | 58,5 / 0,385 |

**Theo độ khó của AST, +ALL so với AST.**

| Nhóm | Tốt hơn | Kém hơn |
|---|---|---|
| Gold đã ở top 10 (659 instance) | 34,6% | 30,0% |
| Gold ở hạng 11 đến 100 (308 instance) | 76,3% | 23,1% |
| Gold ngoài hạng 100 (220 instance) | 54,1% | 17,3% |

**Theo việc issue có nêu tên gold, Top@10 / MRR.**

| Hệ thống | Có nêu tên (572 instance) | Không nêu tên (615 instance) |
|---|---|---|
| AST | 72,4 / 0,495 | 39,8 / 0,205 |
| +HIST | 79,2 / 0,556 | 46,2 / 0,236 |
| +ISSUE | 72,9 / 0,502 | 41,6 / 0,219 |
| +ALL | 78,7 / 0,549 | 47,0 / 0,241 |

**Bằng chứng (Bảng 3).** Mỗi loại có pool 10 phần tử đầu mỗi instance. Judge xem bản vá thật. Phần tử hữu ích là phần tử có điểm hữu ích từ 2 trở lên, trên thang 0 đến 3.

| Nguồn | Phần tử | Instance có ít nhất 1 phần tử hữu ích | Điểm hữu ích 0 / 1 / 2 / 3 (%) |
|---|---|---|---|
| DOC | 11.870 | 50,8% | 55,2 / 35,3 / 8,6 / 0,9 |
| HIST | 11.870 | 77,4% | 41,4 / 36,3 / 16,0 / 6,2 |
| ISSUE | 11.858 | 79,2% | 48,0 / 35,6 / 13,2 / 3,2 |

| Nguồn | Giữ | Precision | Recall | F1 | Token TB |
|---|---|---|---|---|---|
| DOC | top-1 | 0,241 | 0,288 | 0,336 | 350 |
| DOC | top-3 | 0,168 | 0,557 | 0,388 | 1.056 |
| DOC | top-5 (hạn ngạch hiện tại) | 0,135 | 0,727 | 0,365 | 1.751 |
| DOC | top-10 | 0,095 | 1,000 | 0,301 | 3.519 |
| HIST | top-1 | 0,349 | 0,168 | 0,228 | 431 |
| HIST | top-3 | 0,302 | 0,408 | 0,367 | 1.313 |
| HIST | top-5 | 0,268 | 0,595 | 0,405 | 2.245 |
| HIST | top-10 (hạn ngạch hiện tại) | 0,223 | 1,000 | 0,421 | 4.518 |
| ISSUE | top-1 | 0,351 | 0,241 | 0,294 | 379 |
| ISSUE | top-3 | 0,259 | 0,502 | 0,371 | 1.163 |
| ISSUE | top-5 (hạn ngạch hiện tại) | 0,215 | 0,673 | 0,365 | 2.055 |
| ISSUE | top-10 | 0,164 | 1,000 | 0,330 | 4.143 |

Recall tính trong pool 10 phần tử, nên top-10 luôn có recall 1. Cột trả rỗng đúng và trả rỗng sai đều bằng 0, vì chưa có ngưỡng nào.

**Loại thông tin (Bảng 4).** Tỷ lệ (%) phần tử hữu ích có từng loại; một phần tử có thể có nhiều loại.

| Nguồn | Hành vi mong đợi | Cách dùng API | Lỗi tương tự | Nguyên nhân lỗi | Vị trí code | Lý do thiết kế | Thay đổi trước đây |
|---|---|---|---|---|---|---|---|
| DOC | 53,5 | 49,9 | 3,6 | 7,3 | 38,7 | 20,4 | 3,2 |
| HIST | 6,3 | 24,5 | 7,5 | 20,7 | 80,6 | 12,0 | 55,6 |
| ISSUE | 12,3 | 12,0 | 53,2 | 29,2 | 74,8 | 12,9 | 22,2 |

Trên mọi phần tử, tỷ lệ bị chấm "không liên quan" là 50,7% (DOC), 36,9% (HIST) và 46,8% (ISSUE). Tỷ lệ "không có thông tin mới" là 3,6%, 2,8% và 0,4%.

**Độ ổn định của judge.** 100 instance, mỗi phần tử chấm hai lần với thứ tự trong prompt xáo khác.

| Nguồn | Cặp phần tử | Trùng điểm hữu ích | κ nhãn hữu ích (≥ 2) | κ trọng số, điểm hữu ích | κ trọng số, điểm liên quan | Jaccard loại thông tin |
|---|---|---|---|---|---|---|
| DOC | 1.000 | 72,7% | 0,615 | 0,720 | 0,787 | 0,686 |
| HIST | 1.000 | 63,5% | 0,624 | 0,739 | 0,780 | 0,602 |
| ISSUE | 997 | 68,1% | 0,629 | 0,730 | 0,806 | 0,641 |
| Gộp | 2.997 | 68,1% | 0,629 | 0,736 | 0,795 | 0,643 |

**nDCG@10 theo judge.** Điểm liên quan 0 đến 3 của node code. Tám hệ thống chính có nhãn cho 100% node trong top 10. Kiểm định chạy trên 1.184 instance.

| Hệ thống | nDCG@10 |
|---|---|
| AST | 0,565 |
| +DOC | 0,571 |
| +HIST | 0,632 |
| +ISSUE | 0,575 |
| +ALL | 0,638 |
| ALL−DOC | 0,638 |
| ALL−HIST | 0,586 |
| ALL−ISSUE | 0,635 |

Q1 (+0,006), Q2 (+0,067), Q3 (+0,010), Q4 (+0,073) và Q6 (+0,052) có ý nghĩa sau Holm. Q5 (+0,000) và Q7 (+0,002) không có ý nghĩa. Hai biến thể của HIST (83,6% và 86,1%) và các hệ thống RRF trọng số bằng nhau (45,6% đến 99,5%) chưa có nhãn cho mọi node trong top 10, nên nDCG của chúng chưa so được.

**Đánh giá.**
- Kết luận chính giữ nguyên. +ALL tốt hơn AST ở mọi độ đo chính, theo gold và theo nDCG@10 của judge.
- Thêm DOC khi đã có HIST và ISSUE làm Top@1, MRR và MAP giảm có ý nghĩa (Q5). Ở L4, mức giảm này chưa có ý nghĩa. Trọng số của DOC đã ở mức nhỏ nhất của lưới (0,05), và lưới không có 0. Theo nDCG@10 của judge, Q5 không đổi. Theo khung lập luận, tác động âm là lỗi phương pháp, nên việc sửa cách nối doc với code cần làm trước khi đóng băng.
- Mỗi nguồn cho một loại thông tin khác nhau. DOC chủ yếu cho hành vi mong đợi và cách dùng API. HIST cho vị trí code và thay đổi trước đây. ISSUE cho lỗi tương tự. Đây là số liệu đầu tiên về giá trị nội dung của DOC và ISSUE, hai nguồn không cải thiện xếp hạng khi đã có HIST.
- Phần tử hữu ích tập trung ở đầu danh sách. Precision ở top-1 cao hơn ở top-10 ở cả ba nguồn. Điều này ủng hộ việc chọn ngưỡng (bước G), giờ đã làm được vì pool đã có nhãn.
- Judge khá ổn định: κ từ 0,6 đến 0,8, mức đồng thuận khá cao theo thang của Landis và Koch (1977). Mức ổn định gần như nhau ở ba nguồn.
- Fix vẫn không thêm gì sau khi trộn. +HIST (NL+CE) đạt Top@10 62,3, còn +HIST đủ đạt 62,1.
- So với L4, AST lệch khoảng 1 instance, do thứ tự node bằng điểm đổi sang theo id. +ALL lệch nhiều hơn một chút (Top@1 27,7 thành 27,3), vì phần 0 chọn trọng số DOC khác.

**Giới hạn.** Như L4. Cách trộn và lưới trọng số được chọn sau khi đã xem kết quả trên cùng 1.187 instance, nên đây vẫn là thực nghiệm khám phá.

**Sự cố.**
- Cell đầu của lần Run All thứ hai mang số thực thi 43, nên trước đó kernel đã chạy 42 cell. Con số này khớp với một lần Run All dừng ở `judge-v4`. Số thực thi 84 không có trong notebook; đó có thể là một lần chạy `judge-v4` bị ngắt, trước lần thành công mang số 85. Lần cuối nối tiếp các batch đã gửi. Notebook không giữ output của các lần trước, nên không rõ lý do dừng.
- Ở lần cuối, batch phần 5 trả 0 kết quả hợp lệ cho 1 request, và batch phần 8 trả 168 trên 169. Hai request còn thiếu được chấm lại bằng gọi thường.

---

## 8. Lượt v4-L6 (27/10/2026, 04:38)

**Thay đổi so với L5.**
- Judge chỉ chấm bằng chứng, theo mục 6.13 của `planning.md`. Prompt và schema không còn trường lý do. Mức thinking là MINIMAL thay cho LOW. Mỗi batch gồm request của 100 instance thay cho 150. Phần `#code2` bị bỏ, nên nDCG@10 theo judge không còn được tính.
- Cell `depth-v4` được thêm vào. Cell này tính số node phải đọc trước khi gặp gold và độ sâu tới gold, theo mục 10.1 của `pipeline_design.md`.
- Phần cài cho đợt confirm được thêm vào, theo mục 6.14 của `planning.md`. Lượt này chạy với `V4_PHASE = "main"`.
- Notebook được dọn theo mục 6.15 của `planning.md`. Code của v3 bị bỏ, cùng ba cell chỉ để phân tích là `v3-recheck`, `gpu_cuda_check` và `hist-fix-check`. `judge-v4` đọc file nhãn một lần cho mỗi phần batch. Khóa của cell trong `manifest` là số thứ tự trong `In` cộng dòng đầu của cell.
- Code của `issue-index` đổi khi dọn notebook. Vì vậy dấu cách tính đổi từ `54c905e4dbca` sang `bf41ef497580`, và ISSUE được tính lại cho 1.187 instance. `v4-run` và `hist-proc` không phải tính lại instance nào, vì file kết quả của L5 vẫn khớp.

**Cấu hình.** Phần truy hồi và phần trộn giống L5. `V4_EVID_N = 10`, `ISSUE_CUTOFF = "instance"`, `HIST_MAX_TOUCH = 50`. Lưới trọng số và kiểm định chéo 5 phần như mục 5, seed 20261021. Chấm lặp lấy 100 instance với seed 20261022. Judge là gemini-3.1-flash-lite qua Batch API. `depth-v4` dùng k = 1, 5 và 10, các cạnh `Calls`, `Defines` và `Inherits` theo hai chiều, và độ sâu tối đa 3 trong bảng độ sâu. Lượt chạy là một lần Run All trong kernel mới, với số thực thi từ 1 tới 31.

Trọng số chọn được giống hệt L5 ở mọi hệ thống mà mục 7 đã ghi. Ba hệ thống mà mục 7 chưa ghi có trọng số như sau. +HIST (chỉ NL) nhận 1 ở cả 5 phần. +HIST (NL+CE) nhận 1; 1,5; 3; 1; 1,5. +ISSUE (thêm Refs) nhận 0,05 ở cả 5 phần.

**Thời gian.** Cả lượt mất 86,5 phút. `doc-links-v2` mất 1,7 phút, vì cả 86 graph đều lấy từ cache. `issue-index` mất 1,5 phút. `v4-fusion` mất 0,7 phút. `judge-v4` mất 77,1 phút. `verify-v4` mất 0,8 phút. `depth-v4` mất 2,9 phút.

**Judge.** 3.861 trên 3.861 request có nhãn. Trong đó có 3.561 request bằng chứng và 300 request chấm lặp. Request được chia thành 12 phần. Mỗi phần có từ 273 đến 342 request, và khoảng 1,7 đến 1,9 triệu token đầu vào theo ước lượng. Phần 5 trả 332 trên 333 kết quả hợp lệ. Request còn thiếu được chấm lại bằng gọi thường.

| Loại | Request | Độ dài trung bình (token) | p90 | Lớn nhất |
|---|---|---|---|---|
| Bằng chứng, doc | 1.187 | 4.995 | 6.174 | 13.850 |
| Bằng chứng, history | 1.187 | 5.994 | 8.498 | 34.338 |
| Bằng chứng, issue cũ | 1.187 | 5.619 | 8.950 | 63.934 |
| Chấm lặp, doc | 100 | 5.030 | 6.624 | 10.240 |
| Chấm lặp, history | 100 | 6.065 | 8.933 | 12.628 |
| Chấm lặp, issue cũ | 100 | 5.378 | 8.957 | 18.181 |

Độ dài ước lượng bằng số ký tự chia 4.

**Kết quả xếp hạng.** File kết quả không được dựng lại, và ISSUE tính lại cho đúng số cũ. Vì vậy các bảng sau trùng L5 ở mọi ô đã ghi trong mục 7: Bảng 1 ở mức hàm/lớp và mức file, bảng kiểm định mức hàm/lớp, phần kiểm định mức file, bảng theo repo, bảng theo độ khó và bảng theo việc issue nêu tên gold.

Output của lượt này có thêm vài số mà mục 7 chưa ghi.
- Ở nhóm issue nêu tên gold (572 instance), Top@10 của +HIST (chỉ NL) là 74,5, và của +HIST (NL+CE) là 79,7. Ở nhóm không nêu tên (615 instance), hai số này là 45,9 và 46,0. Như vậy CE chỉ giúp khi issue có nêu tên code.
- Ở nhóm issue không nêu tên gold, +DOC làm Top@1 giảm từ 11,2 xuống 8,9.
- Ở SymPy, +HIST (chỉ NL) kém AST ở Top@1 (21,9 so với 25,4) và ở MRR (0,329 so với 0,349).
- Theo độ khó, +DOC so với AST ở nhóm gold ngoài hạng 100 (220 instance) có 6,4% instance tốt hơn và 22,7% instance kém hơn.
- Ở mức file, Q7 có ΔTop@1 là −1,4 (27 / 44 instance) và ΔMAP là −0,008. Cả hai không có ý nghĩa sau Holm.

**Bằng chứng (Bảng 3).** Mỗi loại có pool 10 phần tử đầu mỗi instance. Pool giống hệt L5, nên chênh lệch so với L5 là do cài đặt judge mới. Judge xem bản vá thật. Phần tử hữu ích là phần tử có điểm hữu ích từ 2 trở lên, trên thang 0 đến 3.

| Nguồn | Phần tử | Instance có ít nhất 1 phần tử hữu ích | Điểm hữu ích 0 / 1 / 2 / 3 (%) |
|---|---|---|---|
| DOC | 11.870 | 46,2% (L5 là 50,8%) | 51,7 / 40,5 / 7,4 / 0,5 |
| HIST | 11.870 | 74,1% (L5 là 77,4%) | 30,9 / 49,8 / 15,1 / 4,2 |
| ISSUE | 11.858 | 77,7% (L5 là 79,2%) | 37,9 / 46,4 / 13,1 / 2,7 |

| Nguồn | Giữ | Precision | Recall | F1 | Token TB |
|---|---|---|---|---|---|
| DOC | top-1 | 0,211 | 0,305 | 0,346 | 350 |
| DOC | top-3 | 0,151 | 0,602 | 0,398 | 1.056 |
| DOC | top-5 (hạn ngạch hiện tại) | 0,114 | 0,751 | 0,352 | 1.751 |
| DOC | top-10 | 0,079 | 1,000 | 0,280 | 3.519 |
| HIST | top-1 | 0,330 | 0,186 | 0,244 | 431 |
| HIST | top-3 | 0,270 | 0,427 | 0,361 | 1.313 |
| HIST | top-5 | 0,237 | 0,607 | 0,387 | 2.245 |
| HIST | top-10 (hạn ngạch hiện tại) | 0,193 | 1,000 | 0,389 | 4.518 |
| ISSUE | top-1 | 0,361 | 0,257 | 0,312 | 379 |
| ISSUE | top-3 | 0,259 | 0,518 | 0,380 | 1.163 |
| ISSUE | top-5 (hạn ngạch hiện tại) | 0,211 | 0,692 | 0,369 | 2.055 |
| ISSUE | top-10 | 0,157 | 1,000 | 0,323 | 4.143 |

Recall tính trong pool 10 phần tử, nên top-10 luôn có recall 1. Precision tính trên mọi instance, còn Recall và F1 chỉ tính trên instance có phần tử hữu ích trong pool. Vì vậy F1 có thể lớn hơn cả Precision lẫn Recall. Cột trả rỗng đúng và trả rỗng sai đều bằng 0, vì chưa có ngưỡng nào.

**Loại thông tin (Bảng 4).** Tỷ lệ (%) phần tử hữu ích có từng loại. Một phần tử có thể có nhiều loại.

| Nguồn | Hành vi mong đợi | Cách dùng API | Lỗi tương tự | Nguyên nhân lỗi | Vị trí code | Lý do thiết kế | Thay đổi trước đây |
|---|---|---|---|---|---|---|---|
| DOC | 52,4 | 53,0 | 3,1 | 5,9 | 59,0 | 12,7 | 2,2 |
| HIST | 5,5 | 20,1 | 3,6 | 24,0 | 94,0 | 5,6 | 59,6 |
| ISSUE | 8,2 | 12,5 | 45,4 | 32,7 | 89,5 | 7,0 | 30,0 |

Trên mọi phần tử, tỷ lệ bị chấm "không liên quan" là 45,9% (DOC), 26,7% (HIST) và 36,1% (ISSUE). Ở L5, ba tỷ lệ này là 50,7%, 36,9% và 46,8%. Tỷ lệ "không có thông tin mới" là 5,4%, 3,2% và 0,9%.

**Độ ổn định của judge.** 100 instance, mỗi phần tử chấm hai lần với thứ tự trong prompt xáo khác.

| Nguồn | Cặp phần tử | Trùng điểm hữu ích | κ nhãn hữu ích (≥ 2) | κ trọng số, điểm hữu ích | κ trọng số, điểm liên quan | Jaccard loại thông tin |
|---|---|---|---|---|---|---|
| DOC | 1.000 | 75,4% | 0,616 | 0,713 | 0,760 | 0,629 |
| HIST | 1.000 | 68,7% | 0,565 | 0,719 | 0,763 | 0,643 |
| ISSUE | 997 | 71,1% | 0,687 | 0,740 | 0,796 | 0,612 |
| Gộp | 2.997 | 71,7% | 0,627 | 0,733 | 0,780 | 0,628 |

**Số node phải đọc (`depth-v4`, lần đầu trên Kaggle).** Không instance nào bị bỏ vì thiếu gold trong graph. Giá trị càng thấp càng tốt.

| Hệ thống | Trung vị @1 | Trung vị @5 | Trung vị @10 | Trung bình @1 | Trung bình @5 | Trung bình @10 | Không tới được gold @10 (%) |
|---|---|---|---|---|---|---|---|
| AST | 64,3 | 16,2 | 7,0 | 1.720,4 | 841,9 | 704,4 | 0,3 |
| +DOC | 67,0 | 15,7 | 7,0 | 1.702,0 | 829,0 | 699,9 | 0,3 |
| +HIST | 41,0 | 5,0 | 5,0 | 1.513,0 | 816,5 | 673,6 | 0,4 |
| +ISSUE | 65,5 | 16,0 | 6,0 | 1.725,1 | 813,0 | 704,2 | 0,3 |
| +ALL | 44,5 | 5,0 | 5,0 | 1.492,5 | 827,0 | 673,7 | 0,4 |
| ALL−DOC | 43,0 | 5,0 | 5,0 | 1.545,6 | 813,6 | 647,2 | 0,4 |
| ALL−HIST | 66,0 | 13,3 | 6,0 | 1.685,1 | 776,3 | 696,3 | 0,3 |
| ALL−ISSUE | 43,0 | 5,0 | 5,0 | 1.498,9 | 790,9 | 659,8 | 0,4 |
| +HIST (chỉ NL) | 60,0 | 11,5 | 6,0 | 1.644,2 | 877,2 | 696,4 | 0,4 |
| +HIST (NL+CE) | 37,0 | 5,0 | 5,0 | 1.513,3 | 813,6 | 686,6 | 0,5 |
| +ISSUE (thêm Refs) | 64,5 | 16,0 | 7,0 | 1.759,7 | 823,0 | 703,7 | 0,3 |
| +DOC (RRF) | 307,5 | 112,3 | 41,0 | 2.009,6 | 1.430,5 | 980,2 | 0,8 |
| +HIST (RRF) | 43,0 | 5,0 | 5,0 | 1.533,5 | 840,2 | 668,9 | 0,4 |
| +ISSUE (RRF) | 286,0 | 59,0 | 38,7 | 1.975,2 | 1.288,6 | 1.027,8 | 0,6 |
| +ALL (RRF) | 130,0 | 23,0 | 7,0 | 1.597,8 | 910,2 | 732,5 | 0,6 |

Kiểm định hoán vị ghép cặp trên trung bình, 10.000 hoán vị. Δ âm nghĩa là hệ thống thứ nhất phải đọc ít hơn. Không ô nào có ý nghĩa sau Holm. Giá trị Holm nhỏ nhất là 0,1666, ở Q4 với k = 1.

| Câu hỏi | Δ @1 (p) | Δ @5 (p) | Δ @10 (p) |
|---|---|---|---|
| Q1: +DOC so với AST | −18,5 (0,7081) | −12,8 (0,2048) | −4,5 (0,3909) |
| Q2: +HIST so với AST | −207,5 (0,0292) | −25,3 (0,6402) | −30,9 (0,5164) |
| Q3: +ISSUE so với AST | +4,7 (0,9499) | −28,9 (0,1311) | −0,3 (0,9691) |
| Q4: +ALL so với AST | −228,0 (0,0238) | −14,9 (0,7820) | −30,8 (0,5304) |
| Q5: +ALL so với ALL−DOC | −53,2 (0,0823) | +13,4 (0,4303) | +26,5 (0,3041) |
| Q6: +ALL so với ALL−HIST | −192,7 (0,0393) | +50,7 (0,3183) | −22,7 (0,6460) |
| Q7: +ALL so với ALL−ISSUE | −6,4 (0,8945) | +36,1 (0,1153) | +13,9 (0,4918) |

p trong ngoặc là p thô, chưa hiệu chỉnh.

**Độ sâu tới gold.** Tỷ lệ (%) node trong top 10 ở từng độ sâu, lấy trung bình theo instance. Độ sâu 0 là chính gold.

| Hệ thống | 0 | 1 | 2 | 3 | Xa hơn 3 |
|---|---|---|---|---|---|
| AST | 7,5 | 10,6 | 15,4 | 19,0 | 47,6 |
| +DOC | 7,6 | 10,7 | 15,5 | 19,1 | 47,1 |
| +HIST | 8,6 | 11,4 | 17,9 | 18,1 | 44,0 |
| +ISSUE | 7,6 | 10,7 | 15,7 | 18,9 | 47,0 |
| +ALL | 8,6 | 11,4 | 18,1 | 18,1 | 43,7 |
| ALL−DOC | 8,6 | 11,5 | 18,0 | 17,9 | 44,0 |
| ALL−HIST | 7,8 | 10,8 | 16,0 | 19,1 | 46,3 |
| ALL−ISSUE | 8,6 | 11,4 | 18,1 | 18,0 | 43,8 |
| +HIST (chỉ NL) | 8,0 | 11,1 | 17,4 | 17,4 | 46,2 |
| +HIST (NL+CE) | 8,6 | 12,0 | 18,3 | 17,5 | 43,7 |
| +ISSUE (thêm Refs) | 7,6 | 10,7 | 15,6 | 18,9 | 47,2 |
| +DOC (RRF) | 5,9 | 9,9 | 15,4 | 20,3 | 48,6 |
| +HIST (RRF) | 8,6 | 11,5 | 17,8 | 18,0 | 44,1 |
| +ISSUE (RRF) | 5,9 | 7,8 | 18,0 | 22,3 | 45,9 |
| +ALL (RRF) | 8,2 | 11,1 | 19,2 | 20,2 | 41,2 |

**Đánh giá.**
- Kết luận về xếp hạng giữ nguyên. Số liệu lặp lại đúng từng ô. File kết quả cũ được đọc lại, ISSUE tính lại cho cùng kết quả, và trọng số trộn chọn lại giống hệt.
- Cài đặt judge mới cho ít điểm 0 hơn, nhiều điểm 1 hơn, và hơi ít phần tử hữu ích hơn. Thứ tự giữa ba nguồn giữ nguyên. DOC yếu nhất, còn HIST và ISSUE gần nhau. Độ ổn định gần như không đổi, với κ nhãn hữu ích khi gộp là 0,627 so với 0,629 ở L5. Riêng HIST giảm từ 0,624 xuống 0,565, còn ISSUE tăng từ 0,629 lên 0,687. Judge không có đáp án chuẩn để so, nên không biết cài đặt nào chấm đúng hơn.
- Mỗi nguồn vẫn cho một loại thông tin riêng. DOC cho hành vi mong đợi và cách dùng API. HIST cho vị trí code và thay đổi trước đây. ISSUE cho lỗi tương tự và nguyên nhân lỗi.
- Ở k = 1, trung vị số node phải đọc giảm từ 64,3 (AST) xuống 41,0 (+HIST) và 44,5 (+ALL). Ở k = 5 và k = 10, trung vị gần như chỉ phản ánh Top@k. Lý do là hơn nửa số instance có gold trong top 10, và khi đó giá trị bằng hạng của gold.
- Không câu hỏi nào có chênh lệch số node phải đọc có ý nghĩa sau Holm, ở mọi k. Kiểm định chạy trên trung bình, và trung bình bị một số ít instance phải đọc hàng nghìn node chi phối. Theo kế hoạch phân tích, kết luận là chưa thấy chênh lệch có ý nghĩa ở độ đo này. Trung vị chỉ dùng để mô tả.
- Tỷ lệ node trong top 10 cách gold tối đa 2 bước tăng từ 33,5% (AST) lên 38,1% (+ALL). +DOC gần như trùng AST, kể cả ở độ sâu 1 (10,7% so với 10,6%), dù DOC lan phiếu qua chính các cạnh mà độ đo dùng.
- DOC vẫn không có giá trị xếp hạng. Theo mục 6.10 của `planning.md`, kết luận cuối về DOC chờ việc sửa cách nối doc với code.

**Giới hạn.** Như L5. Có thêm hai điểm. Thứ nhất, kiểm định số node phải đọc chạy trên trung bình, nên bị đuôi dài chi phối. Đây là tính chất của thiết kế đã duyệt, không phải lỗi code. Thứ hai, ba bài làm cơ sở cho độ đo này chưa được đọc toàn văn.

**Sự cố.**
- `manifest` in "0 cell đã băm". Manifest chỉ có hash của 8 trên 8 file dữ liệu, không có hash nào của code. Mục 6.9 của `planning.md` yêu cầu hash mã của từng cell, nên lượt này không chứng minh được code nào đã tạo ra kết quả. Nguyên nhân chưa rõ. Việc này cần xong trước khi khóa pipeline, vì đợt confirm phải so manifest với đợt main.
- Phần 5 của judge thiếu 1 kết quả hợp lệ. Request đó được chấm lại bằng gọi thường.

---

## 9. Lượt v4-L7 (27/10/2026, 07:54)

**Thay đổi so với L6.**
- `v4-fusion` dùng RRF gốc của Cormack, Clarke và Büttcher (SIGIR 2009). Mọi danh sách có trọng số 1, và k = 60. Lưới trọng số, kiểm định chéo và 7 hệ thống đối chứng bị bỏ, nên còn 11 hệ thống. Lý do là không tham số nào được chọn trên dữ liệu của đề tài (quyết định 57 của `research_context.md`).
- `manifest` ghi phương pháp trộn và k thay cho trọng số.
- Cell `cell-files` được khôi phục. Cell này định nghĩa `_SKIP_DIRS`, `_SKIP_FILES` và `get_python_files`. Cell bị mất trong bản notebook quay về từ L6. L6 không gặp lỗi, vì không phải tính lại instance nào và mọi graph đều lấy từ cache.
- Ở L6, `In` rỗng, nên dấu cách tính của `issue-index` chỉ dựa trên cấu hình. Ở lượt này, dấu được tính từ mã của cell (`4172b591e4be`), nên ISSUE được tính lại cho 1.187 instance. Kết quả của ISSUE trùng L6.

**Cấu hình.** Truy hồi, các nguồn và judge giống L6. `V4_RRF_K = 60`. Lượt chạy là một lần Run All trong editor của Kaggle, trong kernel mới. Thư mục `/kaggle/working` còn file của L6, nên `v4-run` và `hist-proc` không phải tính lại instance nào.

**Thời gian.** Cả lượt mất 10,7 phút. `doc-links-v2` mất 1,7 phút. `issue-index` mất 1,5 phút. `v4-fusion` mất 5 giây. `judge-v4` mất 2,1 phút và không gửi request nào, vì 3.861 trên 3.861 request đã có nhãn. `verify-v4` mất 0,6 phút. `depth-v4` mất 2,7 phút.

**Kết quả, mức hàm/lớp, gộp hai repo.** Hàng của 8 hệ thống chính trùng hàng "(RRF)" cùng tên ở L6.

| Hệ thống | Top@1 | Top@5 | Top@10 | Acc@5 | Acc@10 | MRR | MAP |
|---|---|---|---|---|---|---|---|
| AST | 23,8 | 45,6 | 55,5 | 26,2 | 33,6 | 0,345 | 0,265 |
| +DOC | 11,7 | 28,9 | 43,6 | 14,6 | 25,0 | 0,215 | 0,161 |
| +HIST | 27,9 | 51,9 | 62,4 | 31,6 | 39,1 | 0,393 | 0,309 |
| +ISSUE | 16,9 | 35,7 | 48,8 | 19,0 | 26,2 | 0,268 | 0,198 |
| +ALL | 19,1 | 46,8 | 59,6 | 26,1 | 36,4 | 0,318 | 0,241 |
| ALL−DOC | 21,4 | 45,3 | 57,0 | 25,2 | 34,1 | 0,330 | 0,250 |
| ALL−HIST | 14,5 | 36,1 | 49,5 | 19,7 | 28,8 | 0,257 | 0,193 |
| ALL−ISSUE | 17,5 | 47,6 | 62,4 | 28,5 | 39,8 | 0,310 | 0,241 |
| +HIST (chỉ NL) | 24,9 | 49,5 | 59,6 | 29,8 | 37,0 | 0,366 | 0,286 |
| +HIST (NL+CE) | 27,6 | 52,1 | 62,9 | 32,1 | 39,5 | 0,391 | 0,309 |
| +ISSUE (thêm Refs) | 17,1 | 35,8 | 48,3 | 19,0 | 26,1 | 0,269 | 0,199 |

**Kiểm định, mức hàm/lớp.** ΔMRR được tính từ bảng trên, nên có thể lệch 0,001 do làm tròn.

| Câu hỏi | ΔTop@1 | ΔTop@5 | ΔTop@10 | ΔMRR | ΔMAP | Instance tốt hơn / kém hơn |
|---|---|---|---|---|---|---|
| Q1: +DOC so với AST | −12,1 ✓ | −16,7 ✓ | −11,9 ✓ | −0,130 ✓ | −0,104 ✓ | 17,8% / 65,2% |
| Q2: +HIST so với AST | +4,0 ✓ | +6,3 ✓ | +6,9 ✓ | +0,048 ✓ | +0,044 ✓ | 49,5% / 23,8% |
| Q3: +ISSUE so với AST | −6,9 ✓ | −9,9 ✓ | −6,7 ✓ | −0,077 ✓ | −0,067 ✓ | 31,3% / 53,4% |
| **Q4: +ALL so với AST** | **−4,7 ✓** | **+1,3** | **+4,0 ✓** | **−0,027** | **−0,024 ✓** | **44,1% / 39,3%** |
| Q5: +ALL so với ALL−DOC | −2,3 | +1,5 | +2,5 ✓ | −0,012 | −0,009 | 18,8% / 52,8% |
| Q6: +ALL so với ALL−HIST | +4,6 ✓ | +10,8 ✓ | +10,1 ✓ | +0,061 ✓ | +0,049 ✓ | 54,7% / 19,9% |
| Q7: +ALL so với ALL−ISSUE | +1,6 | −0,8 | −2,9 ✓ | +0,008 | +0,000 | 30,1% / 45,3% |

Acc@10 thay đổi có ý nghĩa ở mọi câu hỏi. Ở Q4, Acc@10 tăng 2,8 điểm. Ở Q5, Acc@10 tăng 2,3 điểm. Ở Q7, Acc@10 giảm 3,4 điểm.

**Kết quả, mức file, gộp hai repo.**

| Hệ thống | Top@1 | Top@5 | Top@10 | Acc@1 | Acc@5 | MRR | MAP |
|---|---|---|---|---|---|---|---|
| AST | 47,2 | 76,8 | 85,6 | 35,8 | 64,3 | 0,605 | 0,558 |
| +DOC | 35,6 | 68,1 | 84,4 | 26,5 | 54,0 | 0,496 | 0,452 |
| +HIST | 52,6 | 78,1 | 86,1 | 41,0 | 65,3 | 0,640 | 0,594 |
| +ISSUE | 35,3 | 67,7 | 80,3 | 26,3 | 53,6 | 0,499 | 0,451 |
| +ALL | 43,6 | 77,4 | 85,9 | 33,1 | 63,3 | 0,587 | 0,536 |
| ALL−DOC | 41,0 | 73,5 | 83,7 | 30,5 | 59,4 | 0,557 | 0,506 |

Ở mức file, Q4 không có ý nghĩa ở độ đo nào. Q2 tốt hơn có ý nghĩa ở Top@1 (+5,4), Acc@1, MRR và MAP. Q1 kém hơn có ý nghĩa ở mọi độ đo trừ Top@10. Q3 kém hơn có ý nghĩa ở mọi độ đo. Q5 tốt hơn có ý nghĩa ở Top@5 (+4,0), Top@10 (+2,2), Acc@3, Acc@5, MRR và MAP. Q6 tốt hơn có ý nghĩa ở mọi độ đo. Q7 không có ý nghĩa ở độ đo nào.

**Theo repo, mức hàm/lớp, Top@10 / MRR.**

| Hệ thống | Django (821 instance) | SymPy (366 instance) |
|---|---|---|
| AST | 56,6 / 0,343 | 53,0 / 0,349 |
| +HIST | 64,3 / 0,401 | 58,2 / 0,376 |
| +ALL | 60,3 / 0,323 | 57,9 / 0,309 |
| ALL−DOC | 56,9 / 0,335 | 57,4 / 0,319 |

**Theo độ khó của AST, +ALL so với AST.**

| Nhóm | Tốt hơn | Kém hơn |
|---|---|---|
| Gold đã ở top 10 (659 instance) | 27,2% | 51,4% |
| Gold ở hạng 11 đến 100 (308 instance) | 72,4% | 26,9% |
| Gold ngoài hạng 100 (220 instance) | 55,5% | 20,0% |

**Theo việc issue có nêu tên gold, Top@10 / MRR.**

| Hệ thống | Có nêu tên (572 instance) | Không nêu tên (615 instance) |
|---|---|---|
| AST | 72,4 / 0,495 | 39,8 / 0,205 |
| +HIST | 79,4 / 0,558 | 46,7 / 0,240 |
| +ISSUE | 57,5 / 0,322 | 40,7 / 0,217 |
| +ALL | 75,7 / 0,424 | 44,6 / 0,220 |

**Bằng chứng.** Nhãn judge không đổi, nên Bảng 3, Bảng 4 và độ ổn định của judge trùng L6 ở mọi ô (mục 8).

**Số node phải đọc.** Không instance nào bị bỏ vì thiếu gold trong graph. Giá trị càng thấp càng tốt.

| Hệ thống | Trung vị @1 | Trung vị @5 | Trung vị @10 | Trung bình @1 | Trung bình @5 | Trung bình @10 | Không tới được gold @10 (%) |
|---|---|---|---|---|---|---|---|
| AST | 64,3 | 16,2 | 7,0 | 1.720,4 | 841,9 | 704,4 | 0,3 |
| +DOC | 307,5 | 112,3 | 41,0 | 2.009,6 | 1.430,5 | 980,2 | 0,8 |
| +HIST | 43,0 | 5,0 | 5,0 | 1.533,5 | 840,2 | 668,9 | 0,4 |
| +ISSUE | 286,0 | 59,0 | 38,7 | 1.975,2 | 1.288,6 | 1.027,8 | 0,6 |
| +ALL | 130,0 | 23,0 | 7,0 | 1.597,8 | 910,2 | 732,5 | 0,6 |
| ALL−DOC | 168,2 | 29,0 | 7,0 | 1.801,0 | 941,2 | 751,8 | 0,4 |
| ALL−HIST | 245,0 | 61,5 | 26,5 | 1.836,6 | 1.283,0 | 1.032,8 | 0,8 |
| ALL−ISSUE | 134,0 | 15,5 | 6,0 | 1.697,4 | 816,7 | 669,3 | 0,4 |
| +HIST (chỉ NL) | 60,0 | 11,5 | 6,0 | 1.644,2 | 877,2 | 696,4 | 0,4 |
| +HIST (NL+CE) | 34,0 | 5,0 | 5,0 | 1.483,9 | 797,2 | 652,5 | 0,4 |
| +ISSUE (thêm Refs) | 281,5 | 59,5 | 42,0 | 1.976,1 | 1.300,7 | 1.010,9 | 0,6 |

Kiểm định hoán vị ghép cặp trên trung bình, 10.000 hoán vị. Δ âm nghĩa là hệ thống thứ nhất phải đọc ít hơn. Dấu ✓ là có ý nghĩa sau Holm. p trong ngoặc là p thô.

| Câu hỏi | Δ @1 (p) | Δ @5 (p) | Δ @10 (p) |
|---|---|---|---|
| Q1: +DOC so với AST | +289,1 (0,0130) | +588,6 (0,0001) ✓ | +275,8 (0,0001) ✓ |
| Q2: +HIST so với AST | −186,9 (0,0530) | −1,6 (0,9787) | −35,5 (0,4600) |
| Q3: +ISSUE so với AST | +254,7 (0,0367) | +446,7 (0,0001) ✓ | +323,3 (0,0001) ✓ |
| Q4: +ALL so với AST | −122,6 (0,2650) | +68,3 (0,2645) | +28,0 (0,6162) |
| Q5: +ALL so với ALL−DOC | −203,2 (0,0188) | −31,0 (0,6050) | −19,3 (0,6660) |
| Q6: +ALL so với ALL−HIST | −238,8 (0,0015) ✓ | −372,9 (0,0001) ✓ | −300,3 (0,0001) ✓ |
| Q7: +ALL so với ALL−ISSUE | −99,6 (0,2878) | +93,5 (0,0526) | +63,2 (0,1510) |

**Độ sâu tới gold.** Tỷ lệ (%) node trong top 10 ở từng độ sâu, lấy trung bình theo instance. Độ sâu 0 là chính gold.

| Hệ thống | 0 | 1 | 2 | 3 | Xa hơn 3 |
|---|---|---|---|---|---|
| AST | 7,5 | 10,6 | 15,4 | 19,0 | 47,6 |
| +DOC | 5,9 | 9,9 | 15,4 | 20,3 | 48,6 |
| +HIST | 8,6 | 11,5 | 17,8 | 18,0 | 44,1 |
| +ISSUE | 5,9 | 7,8 | 18,0 | 22,3 | 45,9 |
| +ALL | 8,2 | 11,1 | 19,2 | 20,2 | 41,2 |
| ALL−DOC | 7,6 | 10,1 | 18,7 | 19,3 | 44,4 |
| ALL−HIST | 6,5 | 9,8 | 18,1 | 22,2 | 43,3 |
| ALL−ISSUE | 8,7 | 12,3 | 18,1 | 19,3 | 41,6 |
| +HIST (chỉ NL) | 8,0 | 11,1 | 17,4 | 17,4 | 46,2 |
| +HIST (NL+CE) | 8,6 | 11,7 | 18,2 | 17,6 | 43,9 |
| +ISSUE (thêm Refs) | 5,9 | 7,8 | 18,2 | 22,2 | 45,9 |

**Đánh giá.**
- HIST giúp định vị tốt hơn AST ở mọi độ đo chính, có ý nghĩa (Q2). Thêm HIST vào DOC và ISSUE cũng tốt hơn có ý nghĩa ở mọi độ đo (Q6). +HIST là hệ thống tốt nhất ở Top@1, MRR và MAP.
- +ALL so với AST cho kết quả hai chiều (Q4). Top@10 và Acc@10 tăng có ý nghĩa. Top@1 và MAP giảm có ý nghĩa. MRR không đổi có ý nghĩa. Ở mức file, +ALL không khác AST có ý nghĩa.
- DOC và ISSUE đứng riêng làm kết quả kém hơn AST có ý nghĩa ở mọi độ đo (Q1, Q3). Danh sách của hai nguồn này yếu hơn AST nhiều, nhưng RRF gốc cho mọi danh sách lá phiếu ngang nhau. Bài của Cormack không thử trường hợp này.
- Khi đã có HIST và ISSUE, thêm DOC chỉ tăng Top@10 (Q5). Khi đã có DOC và HIST, thêm ISSUE làm Top@10 và Acc@10 giảm (Q7).
- +ALL giúp ở ca khó và gây hại ở ca dễ. Khi gold đã ở top 10 của AST, +ALL làm 51,4% instance kém hơn. Khi gold ở hạng 11 đến 100, +ALL làm 72,4% instance tốt hơn.
- Trong HIST, CE đóng góp nhiều nhất. Top@10 là 59,6 khi chỉ dùng NL và 62,9 khi dùng NL+CE. Fix vẫn không thêm gì, vì bản đủ đạt 62,4.
- Liên kết "Refs" của Django vẫn không giúp (Top@10 48,3 so với 48,8).
- Số node phải đọc chỉ khác có ý nghĩa ở ba câu hỏi. +DOC và +ISSUE phải đọc nhiều hơn AST ở k = 5 và 10. Thêm HIST vào DOC và ISSUE giảm số node phải đọc ở mọi k. Q2 và Q4 không có ý nghĩa.
- So với L4 đến L6, kết luận về +ALL đổi chiều ở Top@1 và MAP. Kết luận cũ "+ALL tốt hơn AST ở mọi độ đo" chỉ đúng với trọng số chọn trên dữ liệu.

**Giới hạn.** Kết quả mới có trên hai repo. Kiểm định coi từng instance là độc lập, dù nhiều instance dùng chung snapshot, doc và history. Snapshot là phép xấp xỉ. Bài của Cormack không thử trộn danh sách mạnh với các danh sách yếu hơn nhiều. Kiểm định số node phải đọc chạy trên trung bình, nên bị đuôi dài chi phối.

**Sự cố.** Không có. Manifest băm được 31 cell, nên ở lượt này `In` có ghi mã cell. Nguyên nhân `In` rỗng ở L6 chưa rõ.

---

## 10. Lượt v4-L8 (28/10/2026, 07:24)

**Thay đổi so với L7.**
- Thực nghiệm gồm cả 12 repo của tập test SWE-bench, thay cho Django và SymPy (quyết định 58 của `research_context.md`). File kết quả có 2.294 dòng. `verify-v4` đánh giá 2.214 instance. 80 dòng còn lại có cờ `skip` hoặc không có gold, nên không được tính.
- Cell mới `graph-proc` xếp hạng node sau hop theo KGCompass (mục 6.16 của `planning.md`, mục 8b của `pipeline_design.md`). Cell này tạo hai danh sách. GRAPH đi từ 10 node đầu của AST. DOC mới (`doc_kgc`) đi từ đích cạnh `Documents` của 10 chunk trong `doc_cand`, và thay danh sách `vote_ast` khi trộn. Có thêm hai hệ thống +GRAPH và +ALL+GRAPH, và hai câu hỏi G1, G2 với họ Holm riêng.
- `verify-v4` có thêm khối phân tích ảnh hưởng của độ phủ doc (mục 6.17 của `planning.md`, mục 10.2 của `pipeline_design.md`). `scale_row` ghi thêm `gold_doc` và `doc_cov`. Nhóm `V4_DOC_REPOS` bị bỏ.
- Mẫu chấm lặp của judge có 130 instance, lấy trên mọi repo. L7 dùng 100 instance.
- Cách đọc output của git trong `hist-build` được sửa sau hai lần dừng ghi ở mục Sự cố. `build_history` dùng `git log -z`, nên các commit được ngăn bằng ký tự NUL thay cho 0x1e. `_git` đọc stdout dạng bytes và chỉ đổi CRLF thành LF, nên CR đứng riêng được giữ nguyên. Trên Django và SymPy ở máy, output của bản mới trùng bản cũ từng ký tự. Vì vậy history, danh sách HIST và request judge của hai repo này không đổi.
- Notebook tự xử lý file dở dang sau một lần dừng giữa chừng. `load_history` build lại history khi số dòng của file khác số commit mà `git log` trả về. `load_hunks` dựng lại file hunk khi file này chưa có hoặc cũ hơn file history. `build_hunks` duyệt xong mới ghi file, nên lần dựng dừng giữa chừng không để lại file thiếu. Trên Django ở máy, file đủ 9.456 dòng không bị build lại, file cụt 3.000 dòng được build lại, và file thiếu được build. File hunk của bản cũ và bản mới trùng từng byte (470 hunk). Khi dừng giữa chừng, bản cũ để lại file 98 dòng, còn bản mới không để lại file nào.

**Cấu hình.** Truy hồi AST và HIST giống L7. Locus dùng λ = 5 và β₁ = 0,1. `HIST_YEARS = 5`, `HIST_MAX_TOUCH = 50`, `ISSUE_CUTOFF = "instance"`, `V4_EVID_N = 10`. `graph-proc` dùng β = 0,6, α = 0,3, ngân sách 4, 10 node xuất phát và tối đa 20.000 ký tự source. Trọng số cạnh là 0,25 cho cạnh từ issue tới node xuất phát và cạnh `Defines`, 0,5 cho `Documents`, và 1,0 cho `Calls` và `Inherits`. Cách trộn là RRF gốc với trọng số bằng nhau và k = 60, cho 13 hệ thống. Judge là gemini-3.1-flash-lite qua Batch API, thinking MINIMAL. Mỗi phần batch gồm tối đa 100 instance. Chấm lặp dùng seed 20261022. Kiểm định hoán vị dùng 10.000 hoán vị với seed 20261021. `depth-v4` dùng k = 1, 5 và 10, các cạnh `Calls`, `Defines` và `Inherits` theo hai chiều, và độ sâu tối đa 3.

Lượt chạy bắt đầu bằng Run All trong kernel mới. Thư mục `/kaggle/working` còn file của các lần chạy hỏng trước đó trong ngày. Các file này gồm 279 graph, history của 12 repo (file của pylint bị cụt), báo cáo issue của Django và SymPy, và file kết quả đủ 2.294 dòng. Vì vậy `doc-links-v2` và các cell sau lấy cả 279 graph từ cache, và `v4-run` không phải tính lại instance nào.

**Thời gian.** Cả lượt mất 3 giờ 16 phút, từ 07:24 tới 10:40. `doc-links-v2` mất 2,5 phút. `hist-build` mất 3,9 phút. `hist-proc` mất 26,4 phút. `issue-fetch` mất 44,5 phút để tải nốt báo cáo của 10 repo mới. `issue-index` mất 2,6 phút. `graph-proc` mất 32,3 phút. `v4-fusion` mất 5 giây. `judge-v4` mất 63,0 phút. `verify-v4` mất 1,5 phút. `depth-v4` mất 4,7 phút. Từ 08:00 tới 08:11, không cell nào còn ghi giờ chạy (mục Sự cố).

**Judge.** 7.007 trên 7.007 request có nhãn. Trong đó có 6.618 request bằng chứng và 389 request chấm lặp. 3.588 request đã có nhãn từ trước. 3.419 request còn lại được gửi trong 23 phần, tổng cộng khoảng 23,7 triệu token đầu vào theo ước lượng. Mọi phần kết thúc với trạng thái SUCCEEDED và trả đủ kết quả hợp lệ.

| Loại | Request | Độ dài trung bình (token) | p90 | Lớn nhất |
|---|---|---|---|---|
| Bằng chứng, doc | 2.195 | 5.430 | 6.773 | 68.168 |
| Bằng chứng, history | 2.214 | 6.694 | 9.749 | 68.935 |
| Bằng chứng, issue cũ | 2.209 | 6.643 | 10.695 | 70.428 |
| Chấm lặp, doc | 130 | 5.400 | 6.904 | 20.738 |
| Chấm lặp, history | 130 | 6.676 | 10.012 | 20.781 |
| Chấm lặp, issue cũ | 129 | 6.434 | 10.562 | 29.124 |

Độ dài ước lượng bằng số ký tự chia 4.

**Kết quả, mức hàm/lớp, gộp 12 repo.**

| Hệ thống | Top@1 | Top@5 | Top@10 | Acc@5 | Acc@10 | MRR | MAP |
|---|---|---|---|---|---|---|---|
| AST | 22,4 | 44,4 | 54,2 | 23,0 | 30,3 | 0,331 | 0,247 |
| +DOC | 11,4 | 27,5 | 39,5 | 12,3 | 20,3 | 0,204 | 0,148 |
| +HIST | 26,4 | 50,2 | 59,3 | 27,3 | 34,2 | 0,375 | 0,283 |
| +ISSUE | 16,4 | 33,2 | 44,4 | 15,7 | 21,4 | 0,254 | 0,181 |
| +ALL | 18,5 | 44,1 | 55,6 | 22,0 | 30,4 | 0,306 | 0,228 |
| ALL−DOC | 20,1 | 42,8 | 54,4 | 20,8 | 29,5 | 0,313 | 0,229 |
| ALL−HIST | 14,5 | 35,2 | 46,3 | 16,4 | 24,0 | 0,249 | 0,180 |
| ALL−ISSUE | 17,9 | 44,9 | 57,5 | 22,9 | 33,5 | 0,303 | 0,228 |
| +GRAPH | 17,2 | 39,8 | 53,8 | 19,8 | 29,9 | 0,285 | 0,221 |
| +ALL+GRAPH | 21,1 | 48,3 | 60,0 | 25,6 | 35,0 | 0,336 | 0,258 |
| +HIST (chỉ NL) | 24,0 | 47,9 | 57,0 | 26,1 | 32,8 | 0,352 | 0,266 |
| +HIST (NL+CE) | 26,3 | 50,0 | 59,7 | 27,6 | 34,6 | 0,375 | 0,284 |
| +ISSUE (thêm Refs) | 16,4 | 33,2 | 44,2 | 15,7 | 21,4 | 0,254 | 0,182 |

**Kiểm định, mức hàm/lớp.** ΔMRR được tính từ bảng trên, nên có thể lệch 0,001 do làm tròn. Cột cuối là tỷ lệ instance có hạng gold tốt nhất tốt hơn / kém hơn.

| Câu hỏi | ΔTop@1 | ΔTop@5 | ΔTop@10 | ΔMRR | ΔMAP | Instance tốt hơn / kém hơn |
|---|---|---|---|---|---|---|
| Q1: +DOC so với AST | −11,0 ✓ | −16,9 ✓ | −14,7 ✓ | −0,127 ✓ | −0,099 ✓ | 23,3% / 59,3% |
| Q2: +HIST so với AST | +4,0 ✓ | +5,8 ✓ | +5,1 ✓ | +0,044 ✓ | +0,036 ✓ | 46,9% / 26,6% |
| Q3: +ISSUE so với AST | −6,1 ✓ | −11,2 ✓ | −9,8 ✓ | −0,077 ✓ | −0,065 ✓ | 29,1% / 54,3% |
| **Q4: +ALL so với AST** | **−3,9 ✓** | **−0,4** | **+1,4** | **−0,025 ✓** | **−0,018 ✓** | **42,6% / 39,5%** |
| Q5: +ALL so với ALL−DOC | −1,6 ✓ | +1,3 | +1,1 | −0,007 | 0,000 | 29,7% / 41,6% |
| Q6: +ALL so với ALL−HIST | +4,1 ✓ | +8,9 ✓ | +9,3 ✓ | +0,057 ✓ | +0,049 ✓ | 51,9% / 22,5% |
| Q7: +ALL so với ALL−ISSUE | +0,6 | −0,9 | −1,9 ✓ | +0,003 | 0,000 | 28,7% / 48,3% |
| G1: +GRAPH so với AST | −5,2 ✓ | −4,7 ✓ | −0,4 | −0,046 ✓ | −0,026 ✓ | 34,5% / 40,1% |
| G2: +ALL+GRAPH so với +ALL | +2,6 ✓ | +4,2 ✓ | +4,5 ✓ | +0,030 ✓ | +0,030 ✓ | 43,8% / 23,6% |
| ALL−ISSUE so với AST (cặp phụ) | −4,6 (p < 0,0001) | +0,5 (p = 0,65) | +3,3 | −0,028 (p = 0,0002) | −0,019 (p = 0,0014) | 42,9% / 37,3% |

Acc@10 thay đổi có ý nghĩa ở Q1 (−10,0), Q2 (+3,9), Q3 (−8,9), Q6 (+6,4), Q7 (−3,1) và G2 (+4,6). Ở G1, Acc@5 giảm 3,2 điểm và có ý nghĩa. Cặp ALL−ISSUE so với AST là cặp phụ, nên không có Holm. Hàng của cặp này ghi p thô. p của Top@10, Acc@5 và Acc@10 của cặp này không đọc được (mục Sự cố).

**Kết quả, mức file, gộp 12 repo.**

| Hệ thống | Top@1 | Top@5 | Top@10 | Acc@1 | Acc@5 | MRR | MAP |
|---|---|---|---|---|---|---|---|
| AST | 47,8 | 77,4 | 86,4 | 36,2 | 65,0 | 0,611 | 0,568 |
| +DOC | 34,6 | 64,1 | 83,2 | 25,5 | 50,9 | 0,485 | 0,445 |
| +HIST | 51,6 | 77,8 | 86,0 | 39,0 | 64,9 | 0,637 | 0,592 |
| +ISSUE | 34,7 | 66,3 | 80,0 | 25,7 | 52,4 | 0,493 | 0,450 |
| +ALL | 41,6 | 77,4 | 85,9 | 31,3 | 63,1 | 0,571 | 0,526 |
| ALL−DOC | 39,8 | 73,8 | 84,3 | 29,4 | 59,6 | 0,551 | 0,504 |
| ALL−HIST | 34,8 | 70,7 | 81,7 | 25,8 | 56,4 | 0,513 | 0,469 |
| ALL−ISSUE | 42,7 | 78,3 | 86,7 | 32,2 | 64,1 | 0,582 | 0,540 |
| +GRAPH | 39,9 | 76,2 | 86,9 | 30,3 | 63,2 | 0,553 | 0,516 |
| +ALL+GRAPH | 45,8 | 80,4 | 89,0 | 34,9 | 66,5 | 0,610 | 0,567 |
| +HIST (chỉ NL) | 48,7 | 77,1 | 85,5 | 37,0 | 64,1 | 0,617 | 0,576 |
| +HIST (NL+CE) | 52,7 | 79,2 | 86,1 | 40,1 | 66,2 | 0,647 | 0,602 |
| +ISSUE (thêm Refs) | 34,8 | 66,4 | 79,9 | 25,9 | 52,5 | 0,494 | 0,450 |

Ở mức file, Q2 tốt hơn có ý nghĩa ở Top@1 (+3,7), Acc@1, MRR và MAP. Q2 không khác có ý nghĩa ở Top@5, Top@10, Acc@3 và Acc@5. Q4 kém hơn có ý nghĩa ở Top@1 (−6,2), Acc@1, Acc@3, MRR và MAP. Q1 và Q3 kém hơn có ý nghĩa ở mọi độ đo. Q5 tốt hơn có ý nghĩa ở Top@5 (+3,7), Top@10 (+1,6), Acc@1, Acc@3, Acc@5, MRR và MAP. Q6 tốt hơn có ý nghĩa ở mọi độ đo. Q7 kém hơn có ý nghĩa ở Acc@3, MRR và MAP. G1 kém hơn có ý nghĩa ở mọi độ đo trừ Top@10. G2 tốt hơn có ý nghĩa ở mọi độ đo.

**Theo repo, mức hàm/lớp, Top@10 / MRR.**

| Repo (instance) | AST | +DOC | +HIST | +ISSUE | +ALL | +ALL+GRAPH |
|---|---|---|---|---|---|---|
| astropy (89) | 57,3 / 0,338 | 43,8 / 0,237 | 62,9 / 0,397 | 34,8 / 0,167 | 52,8 / 0,246 | 62,9 / 0,311 |
| django (821) | 56,6 / 0,343 | 42,0 / 0,216 | 64,3 / 0,401 | 48,6 / 0,284 | 60,9 / 0,346 | 65,5 / 0,368 |
| flask (11) | 63,6 / 0,292 | 63,6 / 0,288 | 72,7 / 0,331 | 45,5 / 0,211 | 63,6 / 0,421 | 63,6 / 0,403 |
| matplotlib (180) | 58,9 / 0,355 | 36,1 / 0,190 | 63,9 / 0,412 | 45,6 / 0,292 | 58,9 / 0,296 | 63,9 / 0,365 |
| pylint (53) | 47,2 / 0,259 | 35,8 / 0,198 | 50,9 / 0,353 | 28,3 / 0,148 | 49,1 / 0,248 | 50,9 / 0,307 |
| pytest (117) | 26,5 / 0,148 | 22,2 / 0,124 | 34,2 / 0,166 | 29,1 / 0,194 | 35,9 / 0,209 | 35,9 / 0,192 |
| requests (43) | 58,1 / 0,245 | 53,5 / 0,162 | 69,8 / 0,317 | 58,1 / 0,356 | 60,5 / 0,362 | 69,8 / 0,347 |
| scikit-learn (223) | 69,1 / 0,438 | 54,7 / 0,325 | 66,4 / 0,444 | 48,9 / 0,298 | 63,2 / 0,363 | 72,2 / 0,410 |
| seaborn (22) | 50,0 / 0,335 | 36,4 / 0,178 | 54,5 / 0,415 | 40,9 / 0,253 | 40,9 / 0,208 | 45,5 / 0,273 |
| sphinx (182) | 40,1 / 0,247 | 17,6 / 0,058 | 45,1 / 0,286 | 27,5 / 0,182 | 39,0 / 0,212 | 41,2 / 0,246 |
| sympy (366) | 53,0 / 0,349 | 42,3 / 0,197 | 58,2 / 0,376 | 49,2 / 0,232 | 55,5 / 0,299 | 57,4 / 0,325 |
| xarray (107) | 54,2 / 0,334 | 31,8 / 0,227 | 49,5 / 0,370 | 42,1 / 0,220 | 48,6 / 0,257 | 54,2 / 0,283 |

**Theo độ khó của AST, mức hàm/lớp.** Mỗi ô là tỷ lệ instance tốt hơn / kém hơn. Nhóm chia theo hạng của gold ở AST.

| Câu hỏi | Tất cả (2.214) | Gold trong top 10 (1.200) | Hạng 11 đến 100 (595) | Ngoài hạng 100 (419) |
|---|---|---|---|---|
| Q1: +DOC so với AST | 23,3% / 59,3% | 15,0% / 67,7% | 37,3% / 60,3% | 27,0% / 33,7% |
| Q2: +HIST so với AST | 46,9% / 26,6% | 34,7% / 28,3% | 68,6% / 29,7% | 51,1% / 17,4% |
| Q3: +ISSUE so với AST | 29,1% / 54,3% | 20,7% / 61,9% | 45,2% / 53,9% | 30,5% / 33,2% |
| Q4: +ALL so với AST | 42,6% / 39,5% | 25,8% / 50,9% | 67,7% / 31,1% | 55,1% / 18,6% |
| Q5: +ALL so với ALL−DOC | 29,7% / 41,6% | 28,5% / 35,6% | 33,8% / 53,9% | 27,2% / 41,1% |
| Q6: +ALL so với ALL−HIST | 51,9% / 22,5% | 49,9% / 18,4% | 59,7% / 31,3% | 46,3% / 22,0% |
| Q7: +ALL so với ALL−ISSUE | 28,7% / 48,3% | 24,6% / 46,3% | 36,6% / 58,2% | 29,1% / 40,1% |
| G1: +GRAPH so với AST | 34,5% / 40,1% | 25,1% / 41,0% | 47,7% / 49,9% | 42,7% / 23,6% |
| G2: +ALL+GRAPH so với +ALL | 43,8% / 23,6% | 48,8% / 6,2% | 37,3% / 51,1% | 38,7% / 34,6% |
| ALL−ISSUE so với AST | 42,9% / 37,3% | 25,8% / 47,8% | 70,6% / 29,1% | 52,5% / 18,9% |

**Theo việc issue có nêu tên gold, mức hàm/lớp, Top@10 / MRR.**

| Hệ thống | Có nêu tên (1.078 instance) | Không nêu tên (1.136 instance) |
|---|---|---|
| AST | 70,1 / 0,471 | 39,1 / 0,199 |
| +DOC | 56,6 / 0,316 | 23,3 / 0,097 |
| +HIST | 76,2 / 0,529 | 43,2 / 0,230 |
| +ISSUE | 54,9 / 0,321 | 34,5 / 0,190 |
| +ALL | 72,9 / 0,422 | 39,1 / 0,197 |
| +ALL+GRAPH | 76,6 / 0,459 | 44,3 / 0,220 |
| +HIST (chỉ NL) | 71,7 / 0,486 | 43,0 / 0,225 |
| +HIST (NL+CE) | 77,0 / 0,532 | 43,2 / 0,225 |

**Ảnh hưởng của độ phủ doc, mức repo (bảng C-A và C1).** Độ phủ doc là tỷ lệ Function/Class của snapshot có cạnh `Documents`. Các cột Δ là ΔMRR theo repo. Bảng xếp theo độ phủ tăng dần.

| Repo | Instance | Độ phủ doc (%) | Instance có gold có doc (%) | +DOC so với AST | +ALL so với ALL−DOC | +HIST so với AST | +GRAPH so với AST |
|---|---|---|---|---|---|---|---|
| pylint | 53 | 0,1 | 5,7 | −0,060 | 0,000 | +0,094 | −0,026 |
| matplotlib | 180 | 2,8 | 18,3 | −0,166 | −0,065 | +0,057 | −0,082 |
| pytest | 117 | 3,1 | 12,0 | −0,024 | −0,013 | +0,018 | −0,018 |
| sphinx | 182 | 3,2 | 3,8 | −0,189 | −0,030 | +0,039 | −0,025 |
| requests | 43 | 4,9 | 11,6 | −0,083 | −0,054 | +0,072 | −0,010 |
| astropy | 89 | 5,4 | 29,2 | −0,101 | −0,036 | +0,059 | −0,031 |
| sympy | 366 | 6,3 | 37,7 | −0,151 | −0,020 | +0,027 | −0,079 |
| seaborn | 22 | 7,9 | 22,7 | −0,157 | −0,070 | +0,079 | +0,020 |
| xarray | 107 | 12,2 | 43,9 | −0,108 | +0,022 | +0,035 | −0,003 |
| scikit-learn | 223 | 13,4 | 52,5 | −0,113 | +0,020 | +0,006 | −0,056 |
| django | 821 | 17,7 | 25,7 | −0,127 | +0,011 | +0,058 | −0,042 |
| flask | 11 | 23,8 | 54,5 | −0,003 | +0,128 | +0,039 | +0,020 |

ρ của Spearman giữa độ phủ doc và Δ trung bình của repo, trên 12 repo. p tính bằng hoán vị nhãn repo.

| So sánh | ρ Top@1 (p) | ρ Top@10 (p) | ρ Acc@10 (p) | ρ MRR (p) | ρ MAP (p) |
|---|---|---|---|---|---|
| +DOC so với AST | 0,014 (0,971) | 0,084 (0,798) | 0,161 (0,618) | 0,077 (0,815) | 0,077 (0,815) |
| +ALL so với ALL−DOC | 0,525 (0,081) | 0,231 (0,475) | 0,599 (0,041) | 0,539 (0,069) | 0,559 (0,059) |
| +HIST so với AST | −0,303 (0,338) | 0,049 (0,886) | 0,231 (0,466) | −0,252 (0,429) | −0,238 (0,466) |
| +GRAPH so với AST | 0,162 (0,622) | 0,217 (0,501) | 0,274 (0,385) | 0,238 (0,463) | −0,007 (0,992) |

**Ảnh hưởng của độ phủ doc, mức instance (bảng C-B, C2 và C-C).** Nhóm "gold có doc" gồm 612 instance có ít nhất một gold có cạnh `Documents`. Nhóm còn lại gồm 1.602 instance. Cột hiệu là Δ của nhóm có doc trừ Δ của nhóm không có. p tính bằng hoán vị nhãn nhóm trong từng repo.

| So sánh | ΔTop@1, có doc / không | Hiệu Top@1 (p) | ΔMRR, có doc / không | Hiệu MRR (p) |
|---|---|---|---|---|
| +DOC so với AST | −5,2 / −13,2 | +8,0 (0,0001) | −0,039 / −0,162 | +0,123 (0,0001) |
| +ALL so với ALL−DOC | +4,9 / −4,1 | +9,0 (0,0001) | +0,066 / −0,035 | +0,101 (0,0001) |
| +HIST so với AST | +4,6 / +3,7 | +0,8 (0,6811) | +0,051 / +0,042 | +0,009 (0,5739) |
| +GRAPH so với AST | −12,9 / −2,3 | −10,6 (0,0001) | −0,110 / −0,022 | −0,088 (0,0001) |

- Ở nhóm gold có doc, +DOC giữ gần nguyên Top@10 của AST (73,5 so với 73,4). Top@1 giảm từ 39,7 xuống 34,5 (p thô 0,0206), và MRR giảm từ 0,514 xuống 0,475 (p thô 0,0163). Ở nhóm còn lại, Top@10 giảm từ 46,9 xuống 26,5, và MRR giảm từ 0,262 xuống 0,100.
- Trong nhóm gold có doc, +DOC tăng Top@10 thêm 1,3 điểm khi issue nêu tên gold (460 instance), và giảm 3,3 điểm khi issue không nêu tên (152 instance).
- Ở 612 instance của nhóm gold có doc, gold nằm trong top 10 của DOC ở 49,3% instance, và nằm trong danh sách DOC ở 89,4% instance. Ở 74,7% instance, có chunk trong `doc_cand` nối tới gold. Riêng sphinx có 7 instance trong nhóm này, và không chunk nào của `doc_cand` nối tới gold.
- Họ C gồm C1 và C2 của +DOC so với AST, với Holm trong từng độ đo. C1 không có ý nghĩa ở độ đo nào, với Holm nhỏ nhất là 0,5469. C2 có ý nghĩa ở mọi độ đo, với Holm là 0,0002.

**Bằng chứng (Bảng 3).** Mỗi loại có pool 10 phần tử đầu mỗi instance. Phần tử hữu ích là phần tử có điểm hữu ích từ 2 trở lên, trên thang 0 đến 3. Số trong ngoặc là số của L7 trên Django và SymPy.

| Nguồn | Instance | Phần tử | Instance có ít nhất 1 phần tử hữu ích | Điểm hữu ích 0 / 1 / 2 / 3 (%) |
|---|---|---|---|---|
| DOC | 2.195 | 21.780 | 37,8% (46,2%) | 57,3 / 36,5 / 5,8 / 0,3 |
| HIST | 2.214 | 22.140 | 68,7% (74,1%) | 35,2 / 47,4 / 13,5 / 4,0 |
| ISSUE | 2.209 | 22.041 | 73,7% (77,7%) | 42,8 / 43,0 / 11,8 / 2,4 |

| Nguồn | Giữ | Precision | Recall | F1 | Token TB |
|---|---|---|---|---|---|
| DOC | top-1 | 0,166 | 0,298 | 0,337 | 367 |
| DOC | top-3 | 0,115 | 0,583 | 0,377 | 1.112 |
| DOC | top-5 (hạn ngạch hiện tại) | 0,089 | 0,748 | 0,341 | 1.843 |
| DOC | top-10 | 0,061 | 1,000 | 0,268 | 3.666 |
| HIST | top-1 | 0,296 | 0,180 | 0,236 | 468 |
| HIST | top-3 | 0,242 | 0,415 | 0,351 | 1.432 |
| HIST | top-5 | 0,211 | 0,591 | 0,374 | 2.437 |
| HIST | top-10 (hạn ngạch hiện tại) | 0,175 | 1,000 | 0,382 | 4.929 |
| ISSUE | top-1 | 0,326 | 0,258 | 0,308 | 460 |
| ISSUE | top-3 | 0,240 | 0,530 | 0,379 | 1.405 |
| ISSUE | top-5 (hạn ngạch hiện tại) | 0,193 | 0,697 | 0,360 | 2.412 |
| ISSUE | top-10 | 0,142 | 1,000 | 0,311 | 4.879 |

Cách tính Precision, Recall và F1 giống mục 8.

**Loại thông tin (Bảng 4).** Tỷ lệ (%) phần tử hữu ích có từng loại. Một phần tử có thể có nhiều loại.

| Nguồn | Hành vi mong đợi | Cách dùng API | Lỗi tương tự | Nguyên nhân lỗi | Vị trí code | Lý do thiết kế | Thay đổi trước đây |
|---|---|---|---|---|---|---|---|
| DOC | 49,9 | 54,6 | 3,9 | 5,8 | 58,8 | 12,9 | 4,6 |
| HIST | 6,8 | 22,2 | 3,6 | 26,2 | 94,0 | 5,8 | 53,4 |
| ISSUE | 8,3 | 12,9 | 47,1 | 33,6 | 90,1 | 6,1 | 25,3 |

Trên mọi phần tử, tỷ lệ bị chấm "không liên quan" là 51,2% (DOC), 30,5% (HIST) và 41,1% (ISSUE). Tỷ lệ "không có thông tin mới" là 6,1%, 3,9% và 1,0%.

**Độ ổn định của judge.** 130 instance, mỗi phần tử chấm hai lần với thứ tự trong prompt xáo khác.

| Nguồn | Cặp phần tử | Trùng điểm hữu ích | κ nhãn hữu ích (≥ 2) | κ trọng số, điểm hữu ích | κ trọng số, điểm liên quan | Jaccard loại thông tin |
|---|---|---|---|---|---|---|
| DOC | 1.290 | 76,4% | 0,610 | 0,700 | 0,773 | 0,661 |
| HIST | 1.300 | 69,1% | 0,656 | 0,732 | 0,808 | 0,666 |
| ISSUE | 1.290 | 70,6% | 0,634 | 0,740 | 0,777 | 0,646 |
| Gộp | 3.880 | 72,0% | 0,646 | 0,740 | 0,797 | 0,658 |

**Số node phải đọc.** Không instance nào bị bỏ vì thiếu gold trong graph. Giá trị càng thấp càng tốt.

| Hệ thống | Trung vị @1 | Trung vị @5 | Trung vị @10 | Trung bình @1 | Trung bình @5 | Trung bình @10 | Không tới được gold @10 (%) |
|---|---|---|---|---|---|---|---|
| AST | 67,2 | 17,0 | 8,0 | 1.242,9 | 627,4 | 525,8 | 0,3 |
| +DOC | 268,0 | 102,2 | 45,2 | 1.513,9 | 1.013,0 | 813,0 | 0,5 |
| +HIST | 50,0 | 5,0 | 5,0 | 1.145,4 | 636,7 | 518,3 | 0,5 |
| +ISSUE | 272,5 | 86,0 | 55,2 | 1.441,1 | 952,5 | 782,5 | 0,8 |
| +ALL | 159,0 | 28,0 | 8,0 | 1.267,8 | 674,3 | 563,4 | 0,5 |
| ALL−DOC | 190,8 | 34,2 | 8,0 | 1.337,3 | 724,3 | 582,4 | 0,6 |
| ALL−HIST | 291,0 | 52,0 | 38,2 | 1.489,3 | 832,5 | 723,4 | 0,6 |
| ALL−ISSUE | 129,2 | 18,4 | 7,0 | 1.235,2 | 634,0 | 521,7 | 0,5 |
| +GRAPH | 141,0 | 18,5 | 9,0 | 1.467,2 | 698,4 | 523,4 | 0,3 |
| +ALL+GRAPH | 103,5 | 13,1 | 6,0 | 1.166,2 | 611,2 | 517,4 | 0,5 |
| +HIST (chỉ NL) | 64,5 | 13,5 | 6,0 | 1.211,0 | 670,0 | 536,9 | 0,6 |
| +HIST (NL+CE) | 41,7 | 5,0 | 5,0 | 1.110,9 | 612,4 | 506,1 | 0,5 |
| +ISSUE (thêm Refs) | 268,1 | 87,5 | 56,4 | 1.441,6 | 959,0 | 773,5 | 0,8 |

Kiểm định hoán vị ghép cặp trên trung bình, 10.000 hoán vị. Δ âm nghĩa là hệ thống thứ nhất phải đọc ít hơn. Dấu ✓ là có ý nghĩa sau Holm. p trong ngoặc là p thô.

| Câu hỏi | Δ @1 (p) | Δ @5 (p) | Δ @10 (p) |
|---|---|---|---|
| Q1: +DOC so với AST | +271,1 (0,0001) ✓ | +385,5 (0,0001) ✓ | +287,2 (0,0001) ✓ |
| Q2: +HIST so với AST | −97,5 (0,0726) | +9,3 (0,7658) | −7,5 (0,7936) |
| Q3: +ISSUE so với AST | +198,3 (0,0038) ✓ | +325,0 (0,0001) ✓ | +256,7 (0,0001) ✓ |
| Q4: +ALL so với AST | +24,9 (0,6935) | +46,9 (0,1519) | +37,6 (0,2340) |
| Q5: +ALL so với ALL−DOC | −69,5 (0,1970) | −49,9 (0,0932) | −19,0 (0,4113) |
| Q6: +ALL so với ALL−HIST | −221,5 (0,0001) ✓ | −158,2 (0,0001) ✓ | −160,0 (0,0001) ✓ |
| Q7: +ALL so với ALL−ISSUE | +32,6 (0,4095) | +40,3 (0,0868) | +41,7 (0,1010) |
| G1: +GRAPH so với AST | +224,3 (0,0001) ✓ | +70,9 (0,0050) ✓ | −2,4 (0,6436) |
| G2: +ALL+GRAPH so với +ALL | −101,5 (0,0112) ✓ | −63,1 (0,0121) ✓ | −46,0 (0,0567) |
| ALL−ISSUE so với AST (cặp phụ) | −7,6 (0,8947) | +6,6 (0,8302) | −4,0 (0,8838) |

**Độ sâu tới gold.** Tỷ lệ (%) node trong top 10 ở từng độ sâu, lấy trung bình theo instance. Độ sâu 0 là chính gold.

| Hệ thống | 0 | 1 | 2 | 3 | Xa hơn 3 |
|---|---|---|---|---|---|
| AST | 7,8 | 10,3 | 15,9 | 20,3 | 45,7 |
| +DOC | 5,6 | 8,8 | 16,8 | 20,9 | 47,9 |
| +HIST | 8,7 | 11,0 | 18,5 | 19,4 | 42,3 |
| +ISSUE | 5,7 | 7,5 | 19,1 | 24,0 | 43,8 |
| +ALL | 8,0 | 10,4 | 20,6 | 21,7 | 39,3 |
| ALL−DOC | 7,5 | 9,6 | 19,7 | 21,4 | 41,8 |
| ALL−HIST | 6,4 | 9,0 | 19,5 | 22,5 | 42,5 |
| ALL−ISSUE | 8,5 | 11,2 | 19,2 | 20,5 | 40,7 |
| +GRAPH | 7,8 | 10,0 | 16,4 | 19,9 | 46,0 |
| +ALL+GRAPH | 8,9 | 11,8 | 21,0 | 20,4 | 38,0 |
| +HIST (chỉ NL) | 8,2 | 10,5 | 18,0 | 19,2 | 44,1 |
| +HIST (NL+CE) | 8,7 | 11,2 | 18,5 | 19,2 | 42,3 |
| +ISSUE (thêm Refs) | 5,6 | 7,4 | 19,2 | 23,9 | 43,9 |

**Đánh giá.**
- HIST giúp định vị tốt hơn AST ở mọi độ đo chính, có ý nghĩa (Q2). ΔMRR của +HIST dương ở cả 12 trên 12 repo. Thêm HIST vào DOC và ISSUE cũng tốt hơn có ý nghĩa ở mọi độ đo (Q6). +HIST là hệ thống tốt nhất ở Top@1, Top@5 và MRR. +HIST (NL+CE) có MRR bằng +HIST và có MAP cao nhất.
- +ALL không tốt hơn AST (Q4). Top@1, MRR và MAP kém hơn có ý nghĩa. Top@10 chỉ tăng 1,4 điểm, và mức tăng này không có ý nghĩa. Ở L7 trên hai repo, Top@10 tăng 4,0 điểm và có ý nghĩa. Kết luận "+ALL tốt hơn AST ở Top@10" của L7 không còn đúng khi chạy đủ 12 repo.
- ALL−ISSUE, tức DOC+HIST, tăng Top@10 thêm 3,3 điểm so với AST. Nhưng Top@1, MRR và MAP kém hơn theo p thô. So với chỉ DOC, DOC+HIST tốt hơn nhiều ở mọi độ đo của Bảng 1. Cặp này chưa được kiểm định riêng.
- DOC mới và GRAPH không đạt tiêu chí đặt trước ở mục 8b của `pipeline_design.md`. Q1 kém hơn có ý nghĩa ở mọi độ đo. G1 không tốt hơn ở độ đo nào, và kém hơn có ý nghĩa ở Top@1, Top@5, Acc@5, MRR và MAP.
- Thêm GRAPH vào +ALL làm kết quả tốt hơn có ý nghĩa ở mọi độ đo (G2). +ALL+GRAPH có Top@10 và Acc@10 cao nhất ở mức hàm/lớp, và Top@5, Top@10 cao nhất ở mức file. Dù vậy, +ALL+GRAPH vẫn kém +HIST ở Top@1, MRR và MAP. Có một giả thuyết chưa được kiểm tra. GRAPH đi từ 10 node đầu của AST, nên thêm GRAPH có thể chỉ trả lại phần lá phiếu của AST mà DOC và ISSUE đã làm loãng.
- Khi đã có HIST và ISSUE, thêm DOC không giúp ở mức hàm/lớp, và Top@1 còn giảm có ý nghĩa (Q5). Ở mức file, thêm DOC tốt hơn có ý nghĩa ở hầu hết độ đo, giống L7. Khi đã có DOC và HIST, thêm ISSUE làm Top@10 và Acc@10 giảm có ý nghĩa (Q7), giống L7.
- Độ phủ doc của repo không liên quan tới hiệu quả của +DOC so với AST (C1). Ở +ALL so với ALL−DOC, bốn repo có độ phủ cao nhất (xarray, scikit-learn, django, flask) là bốn repo duy nhất có ΔMRR dương. Tuy vậy, ρ của MRR là 0,539 với p = 0,069, nên xu hướng này chưa có ý nghĩa trên 12 repo.
- Ở mức instance, việc gold có cạnh `Documents` quyết định hiệu quả của DOC (C2). Khi gold có doc, thêm DOC vào HIST và ISSUE làm MRR tăng 0,066. Khi gold không có doc, MRR giảm 0,035. Với HIST, hai nhóm không khác nhau, nên phép đối chứng này cho kết quả đúng như dự kiến. Chỉ 27,6% instance có gold có doc. Ở phần còn lại, danh sách DOC không thể chứa gold qua cạnh doc, nhưng RRF gốc vẫn cho danh sách đó một lá phiếu ngang AST.
- Mẫu theo độ khó giống L7. Các hệ thống có DOC hoặc ISSUE giúp ở ca khó, và gây hại ở ca mà AST đã tìm đúng. HIST là nguồn duy nhất có tỷ lệ instance tốt hơn lớn hơn tỷ lệ kém hơn ở cả ba nhóm.
- Trên 12 repo, tỷ lệ instance có phần tử hữu ích thấp hơn L7 ở cả ba nguồn. Thứ tự giữa ba nguồn giữ nguyên. DOC yếu nhất, còn ISSUE và HIST gần nhau. κ nhãn hữu ích khi gộp là 0,646, so với 0,627 ở L7.
- Judge chấm bằng chứng của ISSUE là hữu ích nhiều nhất, nhưng danh sách hàm/lớp của ISSUE kém hơn AST (Q3). Hai số đo này đo hai việc khác nhau. Judge chấm từng báo cáo cũ. Q3 đo danh sách hàm/lớp suy ra từ các báo cáo đó.
- Trong HIST, CE vẫn đóng góp nhiều nhất. Top@10 là 57,0 khi chỉ dùng NL, và 59,7 khi dùng NL+CE. CE chỉ giúp khi issue nêu tên gold (71,7 lên 77,0, so với 43,0 lên 43,2). Fix vẫn không thêm gì, vì bản đủ đạt 59,3. Liên kết "Refs" vẫn không giúp (Top@10 44,2 so với 44,4).
- Số node phải đọc khác có ý nghĩa ở Q1, Q3 và Q6 ở mọi k. Ở L7, Q1 và Q3 chỉ có ý nghĩa ở k = 5 và 10. G1 phải đọc nhiều hơn AST ở k = 1 và 5. G2 phải đọc ít hơn +ALL ở k = 1 và 5. Q2 và Q4 không có ý nghĩa.
- Ở Django và SymPy, số liệu theo repo của AST và +HIST trùng L7 ở từng ô. Như vậy kết quả của hai repo này lặp lại được.

**Giới hạn.** Như L7. Có thêm ba điểm. Thứ nhất, C1 chỉ có 12 điểm dữ liệu, và flask (11 instance) với seaborn (22 instance) có ít instance. Thứ hai, nhóm gold có doc có AST mạnh hơn hẳn nhóm còn lại (MRR 0,514 so với 0,262), nên C2 lẫn cả ảnh hưởng của độ khó. Thứ ba, giả thuyết về G2 chưa được kiểm tra.

**Sự cố.**
- Trước lượt này, hai lần chạy trên Kaggle trong ngày dừng ở `hist-build`. Lần đầu báo `ValueError: not enough values to unpack (expected 4, got 1)`, vì message của một commit chứa ký tự 0x1e. Chưa xác định được repo và commit đó. Lần thứ hai báo `UnidiffParseError` (`Hunk diff line expected`), vì một file `.py` có ký tự CR đứng riêng, và `text=True` đổi CR đó thành xuống dòng. Hai lỗi đã được sửa như mục Thay đổi.
- Lần chạy thứ ba dừng ở `hist-proc` với `ValueError: zero-size array to reduction operation`. Lần chạy thứ hai đã dừng giữa lúc ghi history của pylint, và để lại file cụt. `load_history` cũ coi file cụt là file đủ. Snapshot cũ nhất của pylint không còn commit tổ tiên nào trong file, nên ma trận hunk không có dòng nào. Lỗi này đã được sửa như mục Thay đổi. Ở lượt này, `load_history` tự build lại history của pylint (5.399 commit). `hist-proc` dựng lại file hunk của seaborn, requests, pylint, pytest, scikit-learn và sphinx, vì các file này chưa có hoặc cũ hơn file history.
- Lượt này không phải một lần Run All liền mạch. Số thực thi 25 không còn trong notebook. `v4-config` được chạy lại lúc 08:11 với số 26, rồi các cell từ `issue-fetch` chạy tiếp theo thứ tự. `issue-fetch` tải tiếp scikit-learn từ trang 140, tức phần trước đã được tải ở lần chạy số 25. Output không cho biết vì sao lần chạy đó dừng.
- Các bảng kiểm định của `verify-v4` có hơn 20 cột, nên pandas ẩn các cột ở giữa khi hiển thị. Các cột bị ẩn là b / c và p của Top@10, Acc@5 và Acc@10, ΔAcc@5, ΔAcc@10 và ΔMRR. Cột Holm vẫn hiện đủ. Vì vậy p của Top@10, Acc@5 và Acc@10 của cặp phụ không đọc được. Notebook chưa được sửa ở chỗ này.
- Phân tích ngoài notebook ở việc 8 của mục 14.16 trong `planning.md` chưa làm. Phân tích này báo l của gold đầu tiên trong GRAPH, và tỷ lệ instance có gold là ứng viên của GRAPH nhưng nằm ngoài 500 node đầu của AST.

**Phân tích chi tiết của judge.** Phần này được tính ngày 29/10/2026, ngoài notebook. Dữ liệu là ba file của lượt này: `judge_v4/pool.jsonl`, `judge_v4/labels_gemini-3.1-flash-lite.jsonl` và `v4/scale_rows_v4.jsonl`. Script dùng lại nguyên các hàm của cell `v4-fusion` và `verify-v4`. Số đối chiếu khớp với Bảng 1 và Bảng 3 ở trên. Các số đó là Top@10 và MRR của AST, +DOC, +HIST và +ISSUE, cùng với số instance, số phần tử, tỷ lệ instance có phần tử hữu ích và P@1 của ba nguồn.

Các khái niệm dùng trong phần này như sau.
- Pool của một nguồn là 10 phần tử bằng chứng đầu tiên theo điểm gốc của nguồn đó, như ở Bảng 3.
- Một phần tử là hữu ích khi judge cho điểm hữu ích từ 2 trở lên.
- Một phần tử nối tới gold khi nó dẫn tới một hàm hoặc lớp mà bản vá thật đã sửa. Với DOC, chunk có cạnh `Documents` tới gold (trường `targets` của `doc_cand`). Với HIST, chính hunk đó sửa gold (trường `ids` của `hist_cand`, tính trên riêng hunk đó). Với ISSUE, bản sửa của báo cáo cũ có đụng gold (trường `fix` của `issue_cand`).
- Tín hiệu nối tới gold chỉ dựa vào cấu trúc code, nên nó khách quan hơn nhãn của judge. Phần này dùng tín hiệu đó để kiểm tra nhãn của judge.

**J1. Điểm liên quan và điểm hữu ích.** Tỷ lệ (%) tính trên mọi phần tử của từng nguồn. Điểm liên quan trung bình là 0,61 (DOC), 1,01 (HIST) và 0,83 (ISSUE). Điểm hữu ích trung bình là 0,49, 0,86 và 0,74.

| Nguồn | Điểm liên quan | Hữu ích 0 | Hữu ích 1 | Hữu ích 2 | Hữu ích 3 | Tổng |
|---|---|---|---|---|---|---|
| DOC | 0 | 52,8 | 0,0 | 0,0 | 0,0 | 52,8 |
|  | 1 | 4,5 | 31,2 | 0,1 | 0,0 | 35,8 |
|  | 2 | 0,0 | 5,0 | 4,0 | 0,0 | 9,0 |
|  | 3 | 0,0 | 0,4 | 1,8 | 0,3 | 2,4 |
|  | Tổng | 57,3 | 36,5 | 5,8 | 0,3 | 100,0 |
| HIST | 0 | 29,3 | 0,0 | 0,0 | 0,0 | 29,3 |
|  | 1 | 5,8 | 41,9 | 0,1 | 0,0 | 47,9 |
|  | 2 | 0,0 | 5,2 | 9,9 | 0,1 | 15,2 |
|  | 3 | 0,0 | 0,3 | 3,5 | 3,9 | 7,7 |
|  | Tổng | 35,2 | 47,4 | 13,5 | 4,0 | 100,0 |
| ISSUE | 0 | 39,9 | 0,0 | 0,0 | 0,0 | 39,9 |
|  | 1 | 2,9 | 38,4 | 0,0 | 0,0 | 41,3 |
|  | 2 | 0,0 | 4,6 | 9,8 | 0,0 | 14,5 |
|  | 3 | 0,0 | 0,0 | 2,0 | 2,3 | 4,3 |
|  | Tổng | 42,8 | 43,0 | 11,8 | 2,4 | 100,0 |

Hai điểm này rất nhất quán với nhau. Điểm hữu ích gần như không bao giờ cao hơn điểm liên quan. Mỗi ô có điểm hữu ích cao hơn điểm liên quan chiếm không quá 0,1% số phần tử.

**J2. Theo repo.** "% có" là tỷ lệ instance có ít nhất 1 phần tử hữu ích trong pool. P@1 là tỷ lệ phần tử ở vị trí 1 là hữu ích. P@10 là tỷ lệ phần tử hữu ích trong pool, lấy trung bình theo instance. "Hữu ích TB" là số phần tử hữu ích trung bình của một pool. "% có nối gold" là tỷ lệ instance có phần tử vừa hữu ích vừa nối tới gold. Năm cột này tính trên instance có pool. ΔMRR và ΔTop@10 là +nguồn trừ AST, tính trên mọi instance của repo. ΔTop@10 tính bằng điểm %.

J2 với DOC.

| Repo | Số instance | Có pool | Độ phủ doc (%) | Gold có doc (%) | % có | P@1 | P@10 | Hữu ích TB | % có nối gold | ΔMRR | ΔTop@10 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| astropy | 89 | 89 | 5,4 | 29,2 | 25,8 | 0,101 | 0,035 | 0,35 | 9,0 | −0,101 | −13,5 |
| django | 821 | 821 | 17,7 | 25,7 | 50,4 | 0,248 | 0,093 | 0,93 | 12,5 | −0,127 | −14,6 |
| flask | 11 | 11 | 23,8 | 54,5 | 45,5 | 0,273 | 0,073 | 0,73 | 27,3 | −0,003 | 0,0 |
| matplotlib | 180 | 180 | 2,8 | 18,3 | 15,0 | 0,050 | 0,019 | 0,19 | 3,3 | −0,166 | −22,8 |
| pylint | 53 | 34 | 0,1 | 5,7 | 11,8 | 0,029 | 0,024 | 0,12 | 2,9 | −0,060 | −11,3 |
| pytest | 117 | 117 | 3,1 | 12,0 | 21,4 | 0,068 | 0,027 | 0,27 | 4,3 | −0,024 | −4,3 |
| requests | 43 | 43 | 4,9 | 11,6 | 27,9 | 0,163 | 0,037 | 0,37 | 7,0 | −0,083 | −4,7 |
| scikit-learn | 223 | 223 | 13,4 | 52,5 | 46,2 | 0,229 | 0,072 | 0,72 | 18,4 | −0,113 | −14,3 |
| seaborn | 22 | 22 | 7,8 | 22,7 | 9,1 | 0,000 | 0,009 | 0,09 | 0,0 | −0,157 | −13,6 |
| sphinx | 182 | 182 | 3,2 | 3,8 | 23,1 | 0,055 | 0,030 | 0,30 | 0,0 | −0,189 | −22,5 |
| sympy | 366 | 366 | 6,3 | 37,7 | 36,6 | 0,128 | 0,046 | 0,46 | 14,2 | −0,151 | −10,7 |
| xarray | 107 | 107 | 12,2 | 43,9 | 36,4 | 0,140 | 0,056 | 0,56 | 13,1 | −0,108 | −22,4 |
| Gộp mọi repo | 2.214 | 2.195 | 10,7 | 27,6 | 37,8 | 0,166 | 0,061 | 0,61 | 10,8 | −0,128 | −14,7 |

J2 với HIST.

| Repo | Số instance | Có pool | % có | P@1 | P@10 | Hữu ích TB | % có nối gold | ΔMRR | ΔTop@10 |
|---|---|---|---|---|---|---|---|---|---|
| astropy | 89 | 89 | 75,3 | 0,281 | 0,212 | 2,12 | 39,3 | +0,059 | +5,6 |
| django | 821 | 821 | 78,7 | 0,368 | 0,210 | 2,10 | 43,1 | +0,058 | +7,7 |
| flask | 11 | 11 | 90,9 | 0,727 | 0,236 | 2,36 | 36,4 | +0,039 | +9,1 |
| matplotlib | 180 | 180 | 61,1 | 0,300 | 0,160 | 1,60 | 32,8 | +0,057 | +5,0 |
| pylint | 53 | 53 | 77,4 | 0,208 | 0,164 | 1,64 | 34,0 | +0,094 | +3,8 |
| pytest | 117 | 117 | 65,0 | 0,248 | 0,175 | 1,75 | 17,1 | +0,018 | +7,7 |
| requests | 43 | 43 | 60,5 | 0,233 | 0,156 | 1,56 | 27,9 | +0,072 | +11,6 |
| scikit-learn | 223 | 223 | 60,5 | 0,211 | 0,132 | 1,32 | 30,9 | +0,006 | −2,7 |
| seaborn | 22 | 22 | 54,5 | 0,136 | 0,105 | 1,05 | 18,2 | +0,079 | +4,5 |
| sphinx | 182 | 182 | 54,4 | 0,236 | 0,132 | 1,32 | 26,4 | +0,039 | +4,9 |
| sympy | 366 | 366 | 63,9 | 0,246 | 0,154 | 1,54 | 29,0 | +0,027 | +5,2 |
| xarray | 107 | 107 | 59,8 | 0,308 | 0,149 | 1,49 | 25,2 | +0,035 | −4,7 |
| Gộp mọi repo | 2.214 | 2.214 | 68,7 | 0,296 | 0,175 | 1,75 | 34,1 | +0,044 | +5,1 |

J2 với ISSUE.

| Repo | Số instance | Có pool | % có | P@1 | P@10 | Hữu ích TB | % có nối gold | ΔMRR | ΔTop@10 |
|---|---|---|---|---|---|---|---|---|---|
| astropy | 89 | 89 | 58,4 | 0,270 | 0,097 | 0,97 | 21,3 | −0,171 | −22,5 |
| django | 821 | 821 | 81,9 | 0,381 | 0,169 | 1,69 | 39,3 | −0,059 | −8,0 |
| flask | 11 | 11 | 72,7 | 0,455 | 0,155 | 1,55 | 36,4 | −0,080 | −18,2 |
| matplotlib | 180 | 180 | 75,6 | 0,294 | 0,136 | 1,36 | 30,6 | −0,063 | −13,3 |
| pylint | 53 | 53 | 71,7 | 0,358 | 0,138 | 1,34 | 20,8 | −0,111 | −18,9 |
| pytest | 117 | 117 | 71,8 | 0,299 | 0,132 | 1,32 | 20,5 | +0,046 | +2,6 |
| requests | 43 | 43 | 60,5 | 0,233 | 0,112 | 1,12 | 25,6 | +0,112 | 0,0 |
| scikit-learn | 223 | 223 | 72,2 | 0,318 | 0,129 | 1,29 | 25,6 | −0,141 | −20,2 |
| seaborn | 22 | 22 | 77,3 | 0,273 | 0,132 | 1,32 | 27,3 | −0,082 | −9,1 |
| sphinx | 182 | 177 | 61,6 | 0,254 | 0,105 | 1,05 | 22,0 | −0,065 | −12,6 |
| sympy | 366 | 366 | 68,3 | 0,314 | 0,130 | 1,30 | 30,9 | −0,116 | −3,8 |
| xarray | 107 | 107 | 71,0 | 0,224 | 0,135 | 1,35 | 31,8 | −0,114 | −12,1 |
| Gộp mọi repo | 2.214 | 2.209 | 73,7 | 0,326 | 0,142 | 1,42 | 31,5 | −0,077 | −9,8 |

ρ của Spearman ở mức repo, trên 12 repo (Cronen-Townsend và cộng sự 2002, như C1). p tính bằng hoán vị nhãn repo, 10.000 lần, và là p thô.

| Nguồn | Biến 1 | Biến 2 | ρ | p |
|---|---|---|---|---|
| DOC | Độ phủ doc (%) | % có | 0,762 | 0,0049 |
| DOC | % có | ΔMRR | 0,140 | 0,6628 |
| DOC | % có | ΔTop@10 | 0,084 | 0,8061 |
| HIST | % có | ΔMRR | 0,119 | 0,7105 |
| HIST | % có | ΔTop@10 | 0,455 | 0,1412 |
| ISSUE | % có | ΔMRR | 0,252 | 0,4357 |
| ISSUE | % có | ΔTop@10 | 0,063 | 0,8488 |

Repo có độ phủ doc cao hơn thì có tỷ lệ DOC hữu ích cao hơn. Ở cả ba nguồn, tỷ lệ có phần tử hữu ích của repo không đi cùng ΔMRR hay ΔTop@10 của repo đó (p ≥ 0,14).

J2 theo việc issue có nêu sẵn tên gold hay không.

| Nguồn | Issue nêu tên gold | Số instance | % có | P@1 | P@10 | % có nối gold |
|---|---|---|---|---|---|---|
| DOC | không | 1.136 | 35,3 | 0,144 | 0,055 | 4,3 |
| DOC | có | 1.078 | 40,5 | 0,189 | 0,067 | 17,5 |
| HIST | không | 1.136 | 59,6 | 0,222 | 0,142 | 20,9 |
| HIST | có | 1.078 | 78,2 | 0,374 | 0,210 | 48,1 |
| ISSUE | không | 1.136 | 72,1 | 0,299 | 0,139 | 26,6 |
| ISSUE | có | 1.078 | 75,5 | 0,355 | 0,145 | 36,7 |

Khi issue nêu sẵn tên gold, mọi tỷ lệ đều cao hơn. Mức tăng rõ nhất ở HIST. Tỷ lệ có phần tử hữu ích tăng từ 59,6% lên 78,2%, và tỷ lệ có phần tử hữu ích nối gold tăng từ 20,9% lên 48,1%.

**J3. Theo vị trí trong pool.** Tỷ lệ (%) phần tử hữu ích ở từng vị trí. Thứ tự là thứ tự theo điểm gốc của nguồn (Järvelin và Kekäläinen 2002). Với DOC, vị trí 1 tới 5 có 2.195 phần tử, và vị trí 6 tới 10 có 2.161 phần tử, vì 34 pool chỉ có 5 chunk. Với HIST, mỗi vị trí có 2.214 phần tử. Với ISSUE, mỗi vị trí có từ 2.201 tới 2.209 phần tử.

| Vị trí | DOC | HIST | ISSUE |
|---|---|---|---|
| 1 | 16,6 | 29,6 | 32,6 |
| 2 | 10,4 | 23,6 | 21,9 |
| 3 | 7,5 | 19,6 | 17,5 |
| 4 | 5,6 | 17,2 | 12,9 |
| 5 | 4,6 | 15,4 | 11,5 |
| 6 | 4,2 | 15,1 | 11,5 |
| 7 | 3,7 | 15,8 | 9,6 |
| 8 | 2,7 | 13,7 | 8,4 |
| 9 | 2,9 | 12,7 | 8,9 |
| 10 | 3,0 | 12,1 | 7,1 |

Ở cả ba nguồn, phần tử càng xếp cao thì càng hay hữu ích. Tỷ lệ của DOC giảm nhanh nhất, từ 16,6% xuống 3,0%. Tỷ lệ của HIST giảm chậm nhất, từ 29,6% xuống 12,1%, nên ở HIST vẫn có phần tử hữu ích tới vị trí 10.

**J4. Bổ sung giữa các nguồn.** Bảng đếm instance theo tổ hợp các nguồn có ít nhất 1 phần tử hữu ích (Zou và cộng sự, TSE 2021). Instance không có pool của một nguồn được tính là không có phần tử hữu ích từ nguồn đó. Bảng tách theo việc AST có gold trong top 10 hay không.

| Nguồn có phần tử hữu ích | Tất cả | % | AST có gold trong top 10 | % | AST không có gold trong top 10 | % |
|---|---|---|---|---|---|---|
| DOC + HIST + ISSUE | 509 | 23,0 | 345 | 28,8 | 164 | 16,2 |
| DOC + HIST | 111 | 5,0 | 63 | 5,2 | 48 | 4,7 |
| DOC + ISSUE | 154 | 7,0 | 69 | 5,8 | 85 | 8,4 |
| HIST + ISSUE | 673 | 30,4 | 409 | 34,1 | 264 | 26,0 |
| Chỉ DOC | 56 | 2,5 | 18 | 1,5 | 38 | 3,7 |
| Chỉ HIST | 227 | 10,3 | 131 | 10,9 | 96 | 9,5 |
| Chỉ ISSUE | 293 | 13,2 | 104 | 8,7 | 189 | 18,6 |
| Không nguồn nào | 191 | 8,6 | 61 | 5,1 | 130 | 12,8 |
| Tổng | 2.214 | 100,0 | 1.200 | 100,0 | 1.014 | 100,0 |

91,4% instance có phần tử hữu ích từ ít nhất một nguồn. Trong 1.014 instance mà AST không có gold trong top 10, tỷ lệ này là 87,2%. ISSUE là nguồn duy nhất có phần tử hữu ích ở 13,2% instance. Trong nhóm AST không có gold trong top 10, tỷ lệ này là 18,6%.

**J5. Nhãn của judge và việc nối tới gold.** Bảng tính ở mức phần tử (Faggioli và cộng sự, ICTIR 2023; Thomas và cộng sự, SIGIR 2024).

| Nguồn | Số phần tử | Nối gold (%) | Hữu ích (%) | Hữu ích khi nối gold (%) | Hữu ích khi không nối (%) | Phần tử hữu ích có nối gold (%) |
|---|---|---|---|---|---|---|
| DOC | 21.780 | 4,9 | 6,1 | 28,9 | 5,0 | 22,9 |
| HIST | 22.140 | 11,7 | 17,5 | 56,3 | 12,3 | 37,7 |
| ISSUE | 22.041 | 7,1 | 14,2 | 65,6 | 10,3 | 32,9 |

Tỷ lệ phần tử nối tới gold theo điểm hữu ích.

| Điểm hữu ích | DOC nối gold (%) | DOC số phần tử | HIST nối gold (%) | HIST số phần tử | ISSUE nối gold (%) | ISSUE số phần tử |
|---|---|---|---|---|---|---|
| 0 | 0,6 | 12.489 | 1,3 | 7.784 | 0,4 | 9.432 |
| 1 | 8,5 | 7.955 | 9,8 | 10.485 | 5,3 | 9.477 |
| 2 | 22,9 | 1.267 | 33,3 | 2.989 | 27,4 | 2.611 |
| 3 | 23,2 | 69 | 52,6 | 882 | 60,1 | 521 |

Loại thông tin (%) của phần tử hữu ích, tách theo việc phần tử có nối tới gold hay không. Một phần tử có thể có nhiều loại.

| Nguồn, nhóm (số phần tử hữu ích) | Hành vi mong đợi | Cách dùng API | Lỗi tương tự | Nguyên nhân lỗi | Vị trí code | Lý do thiết kế | Thay đổi trước đây |
|---|---|---|---|---|---|---|---|
| DOC, nối gold (306) | 52,9 | 45,1 | 2,3 | 3,6 | 85,9 | 6,5 | 4,6 |
| DOC, không nối (1.030) | 49,0 | 57,4 | 4,4 | 6,5 | 50,7 | 14,8 | 4,7 |
| HIST, nối gold (1.460) | 5,4 | 14,9 | 1,0 | 28,4 | 98,4 | 4,0 | 63,2 |
| HIST, không nối (2.411) | 7,7 | 26,5 | 5,2 | 24,9 | 91,3 | 7,0 | 47,6 |
| ISSUE, nối gold (1.029) | 7,9 | 9,8 | 38,4 | 32,1 | 99,6 | 5,3 | 36,8 |
| ISSUE, không nối (2.103) | 8,5 | 14,5 | 51,3 | 34,4 | 85,5 | 6,5 | 19,6 |

- Ở cả ba nguồn, tỷ lệ phần tử nối tới gold tăng theo điểm hữu ích. Như vậy nhãn của judge đi cùng hướng với tín hiệu khách quan.
- Phần lớn phần tử hữu ích không nối tới gold. Tỷ lệ không nối là 77,1% với DOC, 62,3% với HIST và 67,1% với ISSUE.
- Phần tử hữu ích không nối gold mang loại thông tin khác. Với DOC, 57,4% có cách dùng API và 49,0% có hành vi mong đợi. Với ISSUE, 51,3% có lỗi tương tự. Với HIST, 47,6% có thay đổi trước đây.

**J6. Nhãn của judge và kết quả xếp hạng.** Instance được chia theo pool của từng nguồn thành ba nhóm (Salemi và Zamani, SIGIR 2024; Cuconasu và cộng sự, SIGIR 2024). Nhóm a có phần tử hữu ích nối tới gold. Nhóm b có phần tử hữu ích, nhưng không phần tử hữu ích nào nối tới gold. Nhóm c không có phần tử hữu ích, và gồm cả instance không có pool. Δ là +nguồn trừ AST. "Tốt hơn" và "kém hơn" tính theo hạng của gold tốt nhất.

| Nguồn | Nhóm | Số instance | MRR của AST | MRR của +nguồn | ΔMRR | ΔTop@10 | Tốt hơn (%) | Kém hơn (%) |
|---|---|---|---|---|---|---|---|---|
| DOC | a | 236 | 0,602 | 0,603 | +0,002 | +5,1 | 37,3 | 30,1 |
| DOC | b | 594 | 0,277 | 0,139 | −0,138 | −14,0 | 27,1 | 62,3 |
| DOC | c | 1.384 | 0,309 | 0,163 | −0,145 | −18,4 | 19,2 | 62,9 |
| DOC | a + b | 830 | 0,369 | 0,271 | −0,099 | −8,6 | 30,0 | 53,1 |
| DOC | Tất cả | 2.214 | 0,331 | 0,204 | −0,128 | −14,7 | 23,3 | 59,3 |
| HIST | a | 756 | 0,523 | 0,690 | +0,167 | +17,2 | 54,2 | 6,6 |
| HIST | b | 764 | 0,247 | 0,213 | −0,034 | −4,1 | 44,6 | 40,4 |
| HIST | c | 694 | 0,216 | 0,213 | −0,003 | +1,9 | 41,4 | 33,3 |
| HIST | a + b | 1.520 | 0,384 | 0,450 | +0,066 | +6,5 | 49,4 | 23,6 |
| HIST | Tất cả | 2.214 | 0,331 | 0,375 | +0,044 | +5,1 | 46,9 | 26,6 |
| ISSUE | a | 696 | 0,442 | 0,534 | +0,092 | +13,2 | 51,9 | 25,6 |
| ISSUE | b | 933 | 0,276 | 0,107 | −0,168 | −24,3 | 17,7 | 70,6 |
| ISSUE | c | 585 | 0,288 | 0,154 | −0,134 | −13,8 | 20,3 | 62,6 |
| ISSUE | a + b | 1.629 | 0,347 | 0,290 | −0,057 | −8,3 | 32,3 | 51,4 |
| ISSUE | Tất cả | 2.214 | 0,331 | 0,254 | −0,077 | −9,8 | 29,1 | 54,3 |

Kiểm định so sánh nhóm có phần tử hữu ích (a + b) với nhóm c. Hiệu là Δ của nhóm a + b trừ Δ của nhóm c. p tính bằng hoán vị nhãn nhóm trong từng repo, 10.000 lần, như C2. Holm áp dụng trên ba nguồn, trong từng độ đo.

| Nguồn | Hiệu ΔMRR | p | Holm p | Hiệu ΔTop@10 | p | Holm p |
|---|---|---|---|---|---|---|
| DOC | +0,047 | 0,0017 | 0,0017 | +9,8 | 0,0001 | 0,0003 |
| HIST | +0,069 | 0,0001 | 0,0003 | +4,6 | 0,0394 | 0,0684 |
| ISSUE | +0,077 | 0,0001 | 0,0003 | +5,6 | 0,0342 | 0,0684 |

**Đánh giá của phân tích judge.**
- Fusion chỉ cải thiện kết quả khi bằng chứng hữu ích nối tới gold (nhóm a). Với HIST, ΔMRR của nhóm a là +0,167. Với ISSUE, nó là +0,092. Danh sách của mỗi nguồn xếp các hàm/lớp mà bằng chứng dẫn tới. Khi bằng chứng không dẫn tới gold, danh sách đó đưa các hàm/lớp khác gold lên trên. Vì vậy nhóm b không tốt hơn nhóm c. Với ISSUE, nhóm b còn kém hơn nhóm c (ΔMRR −0,168 so với −0,134).
- Với DOC, nhóm a cũng gần như không tăng MRR (+0,002). Ở nhóm này, AST đã xếp gold khá cao (MRR 0,602).
- Nhóm có phần tử hữu ích có ΔMRR cao hơn có ý nghĩa so với nhóm không có, ở cả ba nguồn. Mức chênh này chủ yếu đến từ nhóm a, vì nhóm b không tốt hơn nhóm c.
- Phần lớn thông tin hữu ích của DOC và ISSUE là cách dùng API, hành vi mong đợi và lỗi tương tự. RRF chỉ trộn các danh sách hàm/lớp, nên không dùng được loại thông tin này. Các độ đo xếp hạng cũng không đo được giá trị của nó.
- Bằng chứng có phần tử hữu ích ở hầu hết instance, kể cả khi AST không có gold trong top 10 (J4). Cách trộn hiện tại chỉ khai thác được phần thông tin về vị trí code.
- Kết quả này giải thích thêm một điểm trong mục Đánh giá ở trên. Judge chấm ISSUE là hữu ích nhiều nhất, nhưng +ISSUE kém hơn AST (Q3). Ở ISSUE, 933 instance thuộc nhóm b, và 70,6% instance của nhóm này kém hơn AST.

**Giới hạn của phân tích judge.**
- Nhóm a được xác định bằng gold, nên đây là phân tích sau sự kiện. Một phương pháp thật không dùng được cách chia này lúc chạy.
- Judge thấy bản vá thật, nên nhãn hữu ích và việc nối gold không độc lập với nhau. J5 chỉ kiểm tra độ nhất quán của judge, không kiểm tra độ chính xác.
- Pool DOC là `doc_cand`. Danh sách DOC mà fusion dùng là `doc_kgc`. Danh sách này đi từ chunk của `doc_cand` qua graph, nên nó không trùng hẳn với pool.
- Hunk chỉ sửa code ở mức module có `ids` rỗng, nên loại hunk này không bao giờ được tính là nối gold.
- ρ ở J2 chỉ dựa trên 12 repo và là p thô.

**Phân tích bổ sung ở tầng xếp hạng (bước 1 của mục 6.18.8 trong `planning.md`).** Phần này được tính ngày 29/10/2026, ngoài notebook. Dữ liệu là `v4/scale_rows_v4.jsonl` và hai file judge của lượt này. Script dùng lại nguyên các hàm của cell `v4-config`, `v4-fusion` và `verify-v4`. Top@10 và MRR của 13 hệ thống khớp với Bảng 1 ở trên. Dữ liệu có 2.214 instance có gold, thuộc 276 snapshot. Mỗi snapshot có trung vị 4 instance, ít nhất 1 instance và nhiều nhất 46 instance.

Phần này gồm ba việc.
- **Kiểm định theo khối snapshot.** Các instance cùng snapshot dùng chung graph và history, nên chúng không độc lập với nhau. Định nghĩa "Bootstrap theo khối snapshot" ở mục 2 của `planning.md` cũng nêu lý do này. Với phép so cặp, mọi instance của một snapshot cùng đổi dấu chênh lệch, thay vì mỗi instance đổi dấu riêng. Thống kê vẫn là chênh lệch trung bình, với 10.000 hoán vị và seed 20261021. Đây là kiểm định ngẫu nhiên hóa theo cụm (Canay, Romano và Shaikh, Econometrica 2017, chưa đọc). Phép kiểm này được dùng cho mọi độ đo, thay cho cả McNemar lẫn hoán vị ghép cặp. Holm vẫn được tính trong từng họ Q và G. Với phép so nhóm (C2 và J6), nhãn nhóm được hoán vị trong từng snapshot, thay vì trong từng repo.
- **Trung bình theo repo.** Mỗi repo có trọng số bằng nhau. Lý do là Django và SymPy có 1.187 trên 2.214 instance có gold, tức 53,6%. Δ là trung bình của các Δ theo repo. p được tính bằng cách đổi dấu theo khối snapshot, với trọng số của mỗi instance là 1 chia cho 12 lần số instance của repo đó.
- **Bảng riêng cho 10 repo mới.** Phần này bỏ Django và SymPy, còn 1.027 instance có gold, thuộc 191 snapshot.

Trong các bảng dưới đây, "Holm" là p sau Holm của phép kiểm theo instance, như ở trên. "Holm khối" là p sau Holm của phép đổi dấu theo khối snapshot. Với phép đổi dấu, p nhỏ nhất có thể là 0,0001, nên Holm khối nhỏ nhất là 0,0007 ở họ Q và 0,0002 ở họ G. Δ của Top@k và Acc@k tính bằng điểm %.

**Kiểm định theo khối snapshot, gộp 12 repo, mức hàm/lớp.**

| Câu hỏi | ΔTop@1 | Holm | Holm khối | ΔTop@10 | Holm | Holm khối | ΔMRR | Holm | Holm khối |
|---|---|---|---|---|---|---|---|---|---|
| Q1: +DOC so với AST | −11,0 | < 0,0001 | 0,0007 | −14,7 | < 0,0001 | 0,0007 | −0,128 | 0,0007 | 0,0007 |
| Q2: +HIST so với AST | +4,0 | < 0,0001 | 0,0007 | +5,1 | < 0,0001 | 0,0007 | +0,044 | 0,0007 | 0,0007 |
| Q3: +ISSUE so với AST | −6,1 | < 0,0001 | 0,0007 | −9,8 | < 0,0001 | 0,0007 | −0,077 | 0,0007 | 0,0007 |
| Q4: +ALL so với AST | −3,9 | 0,0003 | 0,0018 | +1,4 | 0,2060 | 0,2639 | −0,025 | 0,0039 | 0,0162 |
| Q5: +ALL so với ALL−DOC | −1,6 | 0,0439 | 0,0884 | +1,1 | 0,1708 | 0,2278 | −0,007 | 0,2812 | 0,3648 |
| Q6: +ALL so với ALL−HIST | +4,1 | < 0,0001 | 0,0007 | +9,3 | < 0,0001 | 0,0007 | +0,057 | 0,0007 | 0,0007 |
| Q7: +ALL so với ALL−ISSUE | +0,6 | 0,4604 | 0,5199 | −1,9 | 0,0292 | 0,0357 | +0,003 | 0,5540 | 0,6145 |
| G1: +GRAPH so với AST | −5,2 | < 0,0001 | 0,0002 | −0,4 | 0,3284 | 0,3099 | −0,046 | 0,0002 | 0,0002 |
| G2: +ALL+GRAPH so với +ALL | +2,6 | < 0,0001 | 0,0002 | +4,5 | < 0,0001 | 0,0002 | +0,030 | 0,0002 | 0,0002 |

Mọi độ đo ở cả hai mức, trên 12 repo và trên 10 repo mới, đều đã được xét. Chỉ 8 kết luận đổi khi dùng khối snapshot, với ngưỡng 0,05 sau Holm. Cả 8 kết luận đều chuyển từ có ý nghĩa sang không có ý nghĩa.
- Gộp 12 repo, mức hàm/lớp: Q5 ở Top@1 (Holm 0,0439, Holm khối 0,0884).
- Gộp 12 repo, mức file: Q5 ở Acc@1 (0,0460 và 0,1130), Q7 ở Acc@3 (0,0262 và 0,0720), Q7 ở MRR (0,0497 và 0,0908).
- 10 repo mới, mức hàm/lớp: Q5 ở Top@1 (0,0500 và 0,1130), Q5 ở MRR (0,0178 và 0,0776), Q7 ở Top@10 (0,0282 và 0,0724).
- 10 repo mới, mức file: Q4 ở Acc@5 (0,0159 và 0,0608).

**Trung bình theo repo, mức hàm/lớp.**

| Hệ thống | Top@1 | Top@5 | Top@10 | Acc@5 | Acc@10 | MRR | MAP |
|---|---|---|---|---|---|---|---|
| AST | 20,0 | 40,6 | 52,9 | 19,5 | 26,5 | 0,307 | 0,222 |
| +DOC | 11,1 | 26,9 | 40,0 | 11,8 | 20,2 | 0,200 | 0,142 |
| +HIST | 24,7 | 47,3 | 57,7 | 22,8 | 30,7 | 0,356 | 0,256 |
| +ISSUE | 14,4 | 32,2 | 41,5 | 15,5 | 20,1 | 0,236 | 0,172 |
| +ALL | 17,4 | 41,1 | 52,4 | 19,8 | 27,2 | 0,289 | 0,215 |
| ALL−DOC | 18,3 | 41,0 | 52,4 | 18,8 | 26,7 | 0,298 | 0,217 |
| ALL−HIST | 14,1 | 32,4 | 43,5 | 14,5 | 22,1 | 0,239 | 0,173 |
| ALL−ISSUE | 17,1 | 43,3 | 56,9 | 20,8 | 30,4 | 0,291 | 0,213 |
| +GRAPH | 16,6 | 39,2 | 52,4 | 17,5 | 26,4 | 0,279 | 0,209 |
| +ALL+GRAPH | 19,8 | 45,6 | 56,9 | 22,2 | 31,8 | 0,319 | 0,239 |
| +HIST (NL) | 22,2 | 46,1 | 54,6 | 22,7 | 29,8 | 0,335 | 0,244 |
| +HIST (NL+CE) | 24,3 | 47,2 | 57,0 | 23,3 | 30,4 | 0,352 | 0,257 |
| +ISSUE (Refs) | 14,4 | 32,2 | 41,5 | 15,5 | 20,1 | 0,237 | 0,172 |

Kiểm định của trung bình theo repo dùng phép đổi dấu theo khối snapshot.

| Câu hỏi | ΔTop@1 | Holm khối | ΔTop@10 | Holm khối | ΔAcc@10 | Holm khối | ΔMRR | Holm khối |
|---|---|---|---|---|---|---|---|---|
| Q1: +DOC so với AST | −8,9 | 0,0007 | −12,9 | 0,0007 | −6,4 | 0,0007 | −0,107 | 0,0007 |
| Q2: +HIST so với AST | +4,7 | 0,0084 | +4,8 | 0,0507 | +4,2 | 0,0126 | +0,049 | 0,0007 |
| Q3: +ISSUE so với AST | −5,6 | 0,0040 | −11,4 | 0,0007 | −6,4 | 0,0007 | −0,070 | 0,0007 |
| Q4: +ALL so với AST | −2,6 | 0,5495 | −0,5 | 1,0000 | +0,7 | 1,0000 | −0,018 | 0,7370 |
| Q5: +ALL so với ALL−DOC | −0,9 | 1,0000 | +0,1 | 1,0000 | +0,5 | 1,0000 | −0,009 | 0,7611 |
| Q6: +ALL so với ALL−HIST | +3,3 | 0,0012 | +8,9 | 0,0007 | +5,1 | 0,0007 | +0,050 | 0,0007 |
| Q7: +ALL so với ALL−ISSUE | +0,3 | 1,0000 | −4,5 | 0,0184 | −3,2 | 0,0016 | −0,002 | 0,8228 |
| G1: +GRAPH so với AST | −3,4 | 0,0018 | −0,5 | 0,2283 | −0,1 | 0,6953 | −0,028 | 0,0010 |
| G2: +ALL+GRAPH so với +ALL | +2,4 | 0,0780 | +4,5 | 0,0002 | +4,6 | 0,0002 | +0,030 | 0,0010 |

**10 repo mới, mức hàm/lớp.** Các số dưới đây gộp theo instance trên 10 repo.

| Hệ thống | Top@1 | Top@5 | Top@10 | Acc@5 | Acc@10 | MRR | MAP |
|---|---|---|---|---|---|---|---|
| AST | 20,8 | 43,1 | 52,7 | 19,4 | 26,4 | 0,316 | 0,225 |
| +DOC | 11,3 | 26,3 | 36,5 | 10,8 | 16,9 | 0,196 | 0,136 |
| +HIST | 24,7 | 48,3 | 55,6 | 22,3 | 28,5 | 0,355 | 0,252 |
| +ISSUE | 15,7 | 30,3 | 39,4 | 11,9 | 15,9 | 0,238 | 0,162 |
| +ALL | 16,5 | 40,2 | 51,3 | 16,6 | 24,4 | 0,277 | 0,196 |
| ALL−DOC | 18,7 | 39,8 | 51,4 | 15,8 | 24,2 | 0,294 | 0,204 |
| ALL−HIST | 13,5 | 31,5 | 42,0 | 12,2 | 18,8 | 0,230 | 0,155 |
| ALL−ISSUE | 17,0 | 42,0 | 54,3 | 17,4 | 28,1 | 0,288 | 0,205 |
| +GRAPH | 16,4 | 40,4 | 52,5 | 17,6 | 26,1 | 0,279 | 0,210 |
| +ALL+GRAPH | 19,8 | 45,5 | 56,6 | 20,0 | 29,4 | 0,316 | 0,229 |
| +HIST (NL) | 22,9 | 46,0 | 53,9 | 21,8 | 28,0 | 0,336 | 0,243 |
| +HIST (NL+CE) | 24,8 | 47,7 | 55,9 | 22,3 | 29,0 | 0,356 | 0,256 |
| +ISSUE (Refs) | 15,7 | 30,3 | 39,4 | 11,9 | 15,9 | 0,238 | 0,162 |

| Câu hỏi | ΔTop@1 | Holm | Holm khối | ΔTop@10 | Holm | Holm khối | ΔAcc@10 | Holm | Holm khối | ΔMRR | Holm | Holm khối |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Q1: +DOC so với AST | −9,5 | < 0,0001 | 0,0007 | −16,2 | < 0,0001 | 0,0007 | −9,4 | < 0,0001 | 0,0007 | −0,120 | 0,0007 | 0,0007 |
| Q2: +HIST so với AST | +3,9 | 0,0073 | 0,0030 | +2,9 | 0,1384 | 0,2031 | +2,1 | 0,2834 | 0,3579 | +0,039 | 0,0007 | 0,0007 |
| Q3: +ISSUE so với AST | −5,2 | 0,0021 | 0,0124 | −13,2 | < 0,0001 | 0,0007 | −10,5 | < 0,0001 | 0,0007 | −0,078 | 0,0007 | 0,0007 |
| Q4: +ALL so với AST | −4,4 | 0,0073 | 0,0240 | −1,4 | 0,8106 | 0,9409 | −1,9 | 0,3084 | 0,3862 | −0,039 | 0,0027 | 0,0084 |
| Q5: +ALL so với ALL−DOC | −2,2 | 0,0500 | 0,1130 | −0,1 | 1,0000 | 1,0000 | +0,2 | 0,9007 | 0,9017 | −0,017 | 0,0178 | 0,0776 |
| Q6: +ALL so với ALL−HIST | +2,9 | 0,0022 | 0,0055 | +9,3 | < 0,0001 | 0,0007 | +5,6 | < 0,0001 | 0,0007 | +0,047 | 0,0007 | 0,0007 |
| Q7: +ALL so với ALL−ISSUE | −0,6 | 0,6792 | 0,6967 | −3,0 | 0,0282 | 0,0724 | −3,7 | 0,0004 | 0,0028 | −0,011 | 0,1935 | 0,2240 |
| G1: +GRAPH so với AST | −4,5 | 0,0001 | 0,0004 | −0,2 | 0,8238 | 0,8333 | −0,3 | 0,6072 | 0,6090 | −0,037 | 0,0002 | 0,0002 |
| G2: +ALL+GRAPH so với +ALL | +3,3 | 0,0001 | 0,0006 | +5,3 | < 0,0001 | 0,0002 | +5,0 | < 0,0001 | 0,0002 | +0,038 | 0,0002 | 0,0002 |

**Mức file.**
- Khi trung bình theo repo, AST có Top@1 46,2 và MRR 0,606. Q2 tăng MRR thêm 0,031 (Holm khối 0,0388), còn Top@1 tăng 4,0 điểm mà không có ý nghĩa (Holm khối 0,1743). Q4 giảm Top@1 7,1 điểm (Holm khối 0,0328) và giảm MRR 0,050 (Holm khối 0,0388). G2 tăng MRR thêm 0,040 (Holm khối 0,0003).
- Trên 10 repo mới, AST có Top@1 48,6 và MRR 0,617. Q2 không có ý nghĩa ở độ đo nào. Ví dụ, ΔMRR là +0,016, với p khối 0,1290. Q4 giảm Top@1 10,4 điểm và giảm MRR 0,073, cả hai có Holm khối 0,0007. Q7 giảm MRR 0,033 (Holm khối 0,0012). G2 tăng MRR thêm 0,055 (Holm khối 0,0002).

**C2 với hoán vị nhãn nhóm trong snapshot.** Cột hiệu là Δ của nhóm gold có doc trừ Δ của nhóm còn lại, như bảng C-B ở trên. Chỉ 138 trên 276 snapshot có đủ cả hai nhóm, và các snapshot này chứa 1.817 instance. Instance của các snapshot còn lại không đóng góp vào phép hoán vị trong snapshot.

| So sánh | Hiệu Top@1 | p trong repo | p trong snapshot | Hiệu Top@10 | p trong repo | p trong snapshot | Hiệu MRR | p trong repo | p trong snapshot |
|---|---|---|---|---|---|---|---|---|---|
| +DOC so với AST | +8,0 | 0,0001 | 0,0002 | +20,5 | 0,0001 | 0,0001 | +0,123 | 0,0001 | 0,0001 |
| +ALL so với ALL−DOC | +9,0 | 0,0001 | 0,0001 | +7,9 | 0,0001 | 0,0001 | +0,101 | 0,0001 | 0,0001 |
| +HIST so với AST | +0,8 | 0,6811 | 0,6604 | +1,1 | 0,6722 | 0,5446 | +0,009 | 0,5739 | 0,4984 |
| +GRAPH so với AST | −10,6 | 0,0001 | 0,0001 | −1,9 | 0,0201 | 0,1047 | −0,088 | 0,0001 | 0,0001 |

**J6 với hoán vị nhãn nhóm trong snapshot.** Phép kiểm giống bảng kiểm định J6 ở trên, chỉ khác ở chỗ nhãn nhóm được hoán vị trong từng snapshot.

| Nguồn | Hiệu ΔMRR | p | Holm p | Hiệu ΔTop@10 | p | Holm p |
|---|---|---|---|---|---|---|
| DOC | +0,047 | 0,0010 | 0,0010 | +9,8 | 0,0001 | 0,0003 |
| HIST | +0,069 | 0,0001 | 0,0003 | +4,6 | 0,0782 | 0,0782 |
| ISSUE | +0,077 | 0,0002 | 0,0004 | +5,6 | 0,0287 | 0,0574 |

**Đánh giá của phân tích bổ sung.**
- Khi tính tới sự phụ thuộc trong snapshot, p tăng nhẹ. Chỉ 8 kết luận ở sát ngưỡng đổi, và chúng đều thuộc Q4, Q5 hoặc Q7. Các kết luận của Q1, Q2, Q3, Q6, G1 và G2 ở MRR giữ nguyên.
- Kết luận "+ALL kém AST" ở mức hàm/lớp phụ thuộc vào cách gộp. Khi gộp theo instance, Q4 âm có ý nghĩa ở Top@1 và MRR, trên cả 12 repo lẫn 10 repo mới. Khi mỗi repo có trọng số bằng nhau, Q4 không có ý nghĩa ở độ đo nào. Ở mức file, Q4 âm có ý nghĩa ở Top@1 và MRR theo cả hai cách gộp.
- Ở mức hàm/lớp, Q2 tăng MRR có ý nghĩa theo mọi cách gộp. Mức tăng Top@10 không còn có ý nghĩa ở 10 repo mới (+2,9, Holm 0,1384) và khi trung bình theo repo (+4,8, Holm khối 0,0507). Django có mức tăng Top@10 lớn nhất (+7,7, bảng J2 với HIST). Trên 10 repo mới, Q2 ở mức file không có ý nghĩa ở độ đo nào.
- G2 có ý nghĩa theo mọi cách gộp, ở cả hai mức. Ngoại lệ duy nhất là Top@1 ở mức hàm/lớp khi trung bình theo repo (+2,4, Holm khối 0,0780). G1 âm có ý nghĩa ở Top@1 và MRR theo mọi cách gộp.
- Ở Q7, thêm ISSUE vào +ALL làm giảm Top@10 và Acc@10. Kết luận này vẫn có ý nghĩa khi trung bình theo repo (ΔTop@10 −4,5, Holm khối 0,0184).
- Kết luận của C2 và J6 không đổi khi hoán vị trong snapshot. Ở C2, đối chứng âm +GRAPH vẫn có hiệu nhóm có ý nghĩa ở Top@1 và MRR. Như vậy, việc chia instance theo gold_doc đi cùng một đặc điểm khác của instance, và đặc điểm đó cũng ảnh hưởng tới GRAPH. Vì vậy, hiệu nhóm của +DOC ở C2 có thể không chỉ do doc.

**Giới hạn của phân tích bổ sung.**
- Phép đổi dấu theo khối giả định các snapshot độc lập với nhau. Các snapshot của cùng một repo vẫn dùng chung phần lớn history, nên giả định này chưa chặt. Phép đổi dấu theo repo thì chỉ có 12 cụm, quá ít để kiểm định.
- Trung bình theo repo cho repo nhỏ trọng số lớn. Flask có 11 instance và seaborn có 22 instance, nhưng mỗi repo đều có trọng số 1/12.
- Bảng 10 repo mới là một cách cắt để mô tả trên cùng một thực nghiệm 12 repo. Đây không phải tập kiểm tra riêng.
- Ở C2, phép hoán vị trong snapshot chỉ dùng 138 snapshot có đủ cả hai nhóm.
- Mọi phép kiểm ở đây dùng file của v4-L8, tức HIST theo Locus. Từ ngày 29/10/2026, +HIST trong notebook là HIST theo phần lời (mục 6b của `pipeline_design.md`). Vì vậy Q2, Q4, Q6 và các hệ thống có HIST sẽ phải tính lại sau lượt chạy tới.

---

## 11. Độ lặp lại giữa các lượt

So hai lần dựng lại toàn bộ file kết quả trên Kaggle (L1 và L3), với cùng code AST và cùng cấu hình v3:

| Hệ thống | Top@1 | Top@5 | Top@10 | MRR | MAP | Acc@10 |
|---|---|---|---|---|---|---|
| AST | 23,9 → 23,8 | 45,6 → 45,7 | 55,5 → 55,5 | 0,345 → 0,344 | 0,266 → 0,265 | 33,6 → 33,6 |
| DOC+HIST (v3) | 23,9 → 23,8 | 51,2 → 51,3 | 61,2 → 61,2 | 0,356 → 0,355 | 0,276 → 0,275 | 38,4 → 38,3 |

- Mức lệch là khoảng 1 instance trên 1.187. Năm cặp số McNemar Top@10 giống hệt nhau.
- Nguyên nhân là hàm `_rrf` của AST. Hàm này gộp ứng viên bằng một `set`, nên thứ tự các node bằng điểm phụ thuộc hash seed của mỗi tiến trình.
- HIST theo Locus, ISSUE, cách chia phần, trọng số chọn được và kiểm định hoán vị đều lặp lại y hệt.
- Ngày 22/10/2026, `_rrf` được sửa để xếp node bằng điểm theo id. Bản sửa chỉ có tác dụng khi file kết quả được dựng lại.

---

## 12. Kiểm thử trên máy trước các lượt

Mỗi thay đổi đều được thử trên 12 instance ở `D:\tmp\rgdata` (6 instance Django ở snapshot `838e432e`, 6 instance SymPy ở snapshot `9bf73cc2`) trước khi ghi vào notebook. Harness chạy chính các cell của notebook. Client Gemini là bản giả.

| Thay đổi | Phép kiểm tra chính | Kết quả |
|---|---|---|
| Bước A | So cell gốc và cell đã sửa trên cùng máy, cùng hash seed | 1.224 trên 1.224 trường cũ giữ nguyên |
| Bước C | So `verify-v4` với `v3-recheck` | 72 ô của Bảng 1, 48 ô của Bảng 2 và 3 cặp McNemar trùng nhau |
| Bước D | Tính lại danh sách HIST | Tái tạo đúng 12 trên 12 instance |
| Bước B | Rò rỉ, cosine so với `TfidfVectorizer`, SimiScore tính bằng vòng lặp | Đạt |
| `issue-fetch` (con trỏ) | Tải thật 12 trang GitHub qua ranh giới trang 10 | 1.200 mục, trùng bản cào ngày 16/10 |
| Bước H | Mọi alias có nhãn, nhãn loại trừ, hash đổi đúng chỗ | Đạt |
| Trộn có trọng số | MAP tính bằng ma trận so với danh sách trộn thật | 1.320 cặp, không lệch |
| `hist-proc` bỏ commit lớn | Các trường HIST khác không đổi | Đạt, 30 trên 120 hunk bị thay |
| `_rrf` xếp hòa theo id | Hai lượt với hash seed khác nhau | Mọi trường giống hệt |
| `issue-index` có dấu cách tính | Đổi `ISSUE_CUTOFF` thì tự tính lại | Đạt |
| `depth-v4` (26/10) | Chạy trên 12 instance mẫu | Chạy được. Không instance nào không tới được gold |
| Dọn notebook (27/10) | So bản cũ và bản mới trên cùng 12 instance | Mọi cột mà pipeline đọc, trọng số trộn, các bảng của `verify-v4` và `depth-v4`, và 72 request của `judge-v4` trùng nhau |
| `v4-fusion` dùng RRF gốc (27/10) | So danh sách trộn của bản mới với RRF trọng số bằng nhau của bản cũ | Cả 11 hệ thống trùng từng id trên 12 instance |
| Khôi phục `cell-files` (27/10) | Chạy notebook mà harness không chèn thêm cell nào | `v4-run` tính xong 12 instance. Kết quả trùng lượt thử trước |
| Gộp 12 repo, bỏ `V4_PHASE` (27/10) | So bản cũ và bản mới trên cùng 12 instance, harness giới hạn `SCALE_REPOS` vào Django và SymPy | File kết quả, danh sách trộn, bảng của `verify-v4` và `depth-v4`, và 72 request của `judge-v4` trùng nhau. `fusion.json` và `manifest` chỉ khác ở trường `phase` đã bỏ |
| Xếp hạng sau hop theo KGCompass, `graph-proc` (28/10) | So bản cũ và bản mới trên cùng 12 instance. Tính lại l bằng phép nới lặp (Bellman-Ford) không dùng heap, và tính lại S bằng `Levenshtein.distance` cùng cosine tự tính | 504 trên 504 trường cũ giữ nguyên. Danh sách trộn của AST, +HIST, +ISSUE, ALL−DOC và ba hệ thống phụ trùng từng id. Bốn hệ thống có DOC đổi, đúng như dự kiến. 72 request của `judge-v4` trùng. Trên 24 danh sách, l của mọi phần tử và của mọi gold khớp, số ứng viên khớp, và S của 30 phần tử đầu lệch tối đa 5×10⁻⁷. Thứ tự đúng: 6 cặp liền nhau có điểm bằng nhau sau khi làm tròn 6 chữ số, nhưng điểm chưa làm tròn của phần tử đứng trước luôn lớn hơn. Họ G1, G2 có Holm riêng, cặp phụ không có Holm. Số ứng viên từ 2.829 tới 11.246, trung vị 5.980 (GRAPH) và 5.458 (DOC). `graph-proc` chạy 12 instance trong 8 giây. Số liệu Bảng 1 trên 12 instance không dùng để kết luận |
| Nối method của lớp với module trong `graph-proc` (28/10) | So với lượt thử trước trên cùng 12 instance. Thêm cạnh module tới method vào phép tính l độc lập | Chỉ các cột của `graph` và `doc_kgc` đổi. Danh sách của mọi hệ thống không có DOC hay GRAPH trùng từng id. Trên 24 danh sách, l, số ứng viên và S khớp phép tính độc lập. Method của lớp khác cùng file với node xuất phát có l ≤ 0,75, trừ 3 danh sách có node xuất phát là hàm lồng, nơi l = 1,0. Số ứng viên trung vị 6.290 (GRAPH) và 5.939 (DOC). `graph-proc` mất 10 giây |
| Phân tích độ phủ doc (28/10) | So với lượt thử trước trên cùng 12 instance. Tính lại `gold_doc` và `doc_cov` từ graph JSON. Thử khối phân tích trên dữ liệu giả 12 repo, có hiệu ứng cài sẵn ở +DOC | 684 trên 684 trường cũ giữ nguyên, chỉ thêm `gold_doc` và `doc_cov`. Danh sách trộn của cả 13 hệ thống và 72 request của judge trùng. `gold_doc` và `doc_cov` khớp trên 12 dòng. `doc_cov` là 17,7% (Django) và 8,2% (SymPy), khớp `coverage_report.md`. Với 2 repo, cell báo C1 cần ít nhất 3 repo. Trên dữ liệu giả, ρ của cell trùng `scipy.stats.spearmanr`. C1 và C2 của +DOC có ý nghĩa, còn đối chứng âm thì không |

---

## 13. Mẫu cho lượt tiếp theo

Thêm một hàng vào bảng ở mục 1, và một mục mới theo mẫu sau.

```
## N. Lượt v4-Lk (ngày, giờ UTC)

**Thay đổi so với lượt trước.** Cell nào đổi, vì sao, cơ sở bài báo.
**Cấu hình.** Tham số chính, cách trộn, trọng số, ngưỡng.
**Thời gian.** Thời gian của từng cell nặng.
**Kết quả.** Bảng 1 mức hàm/lớp và mức file, bảng kiểm định Q1 đến Q7, các bảng bằng chứng nếu có.
**Đánh giá.** Kết luận nào thay đổi so với lượt trước.
**Sự cố.** Lỗi, cách xử lý, việc cần làm ở lượt sau.
```
