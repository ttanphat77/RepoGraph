# Tổng hợp tri thức đề tài RepoGraph

Cập nhật ngày 19/10/2026.

File này hệ thống hóa toàn bộ kiến thức của đề tài ở một chỗ: bài toán, lý thuyết nền, graph, pipeline, đánh giá, kết quả, quyết định và việc còn mở. File chỉ tóm tắt. Chi tiết nằm ở các file được trỏ tới. Khi file này và file chi tiết khác nhau, file chi tiết là nguồn đúng.

Cột "Đã đọc" ở mục 2 ghi mức đọc bài báo: **toàn văn**, **một phần**, **tóm tắt**, hoặc **chưa đọc** (mới chỉ nhắc theo hiểu biết chung, cần đọc trước khi dẫn).

---

## 0. Bản đồ tài liệu

| Tài liệu | Vai trò | Tình trạng |
|---|---|---|
| `research_context.md` | Bối cảnh, dữ liệu, phương pháp, kết quả v2 đến v4, quyết định 1 đến 35, định hướng ngày 18/10 (mục 12) | Mới nhất |
| `planning.md` | Lộ trình, thiết kế v4, thuật ngữ (mục 2), câu hỏi Q1 đến Q7, chi phí, rủi ro, quy tắc làm việc | Mới, có vài mục chưa khớp quyết định mới |
| `pipeline_design.md` | Từng kỹ thuật: input, tham số, output, cơ sở, trạng thái; bảng tham số (mục 12) | Chưa có ngưỡng, output theo loại, loại thông tin của judge |
| Artifact "Tổng quan tài liệu RepoGraph" (https://claude.ai/artifact/DSWQi3W5KrFzSFPLKynKcL) | Báo cáo đọc 18 bài báo, bảng kết luận cho từng câu hỏi thiết kế | Cập nhật 14/10, thiếu các bài về ISSUE và RRF |
| `colab/build_graph_flask_colab.ipynb` | Notebook chạy thực nghiệm trên Kaggle, 54 cell | Chứa output lượt 1 của v4 |
| `docs/graph-architecture-discussion.md` | Thảo luận kiến trúc graph tháng 5 | **Lỗi thời** (Neo4j, F1, bỏ Issue/Commit) |
| `README.md`, `doc_integration_plan.md` | Bản POC ban đầu | **Lỗi thời** |

---

## 1. Bài toán và phạm vi

**Tên đề tài.** Truy xuất ngữ cảnh đa nguồn dựa trên đồ thị hỗ trợ AI Agent trong phát triển phần mềm.

**Chủ đề.** Đề tài nghiên cứu truy xuất ngữ cảnh. Mục tiêu là hỗ trợ AI agent, nên agent sẽ được dùng để kiểm chứng hiệu quả. Thực nghiệm hiện tại chưa dùng agent. LLM judge đánh giá các node output, tức các node sau này sẽ được đưa cho agent.

**Bài toán đo được.** Input là một issue của SWE-bench và repository gần thời điểm issue. Output gồm:
- danh sách hàm/lớp xếp theo khả năng phải sửa (định vị code), đo bằng gold;
- các node bằng chứng (chunk doc, issue cũ, hunk), ghép theo loại, đánh giá bằng judge.

**Bốn nguồn.**

| Nguồn | Nội dung | Thông tin mang lại |
|---|---|---|
| AST | Hàm, lớp, module và quan hệ code | Mốc chỉ dùng code |
| DOC | File tài liệu `.rst`, `.md`, `.txt`, chia thành DocChunk. Docstring không tính là doc | Hành vi mong đợi, cách dùng API |
| HIST | Commit cũ, xem cùng diff | Vùng code từng đổi ra sao và vì sao |
| ISSUE | Báo cáo lỗi cũ đã sửa | Lỗi tương tự, nơi đã sửa |

**Dữ liệu.** Split test của SWE-bench bản đầy đủ. V4 dùng Django và SymPy: 1.187 instance (821 và 366), 86 graph snapshot. V2 đã chạy trên 12 repo. Không tách dev và test từ v4.

**Khung lập luận** (mục 2 của `research_context.md`).
- Mọi kết quả so với AST. Mục tiêu chính không phải tìm nguồn mạnh nhất.
- Doc có tác động âm thì lỗi nằm ở phương pháp. Thông tin trùng với issue và code thì tác động bằng 0.
- Không bắt buộc issue nào cũng được doc giúp. Doc chỉ cần giúp khi xét chung.
- LLM không tham gia tạo xếp hạng.
- Commit luôn được đọc cùng diff.
- Mỗi quyết định kỹ thuật phải có bài báo làm cơ sở. Số đo của đề tài chỉ bổ sung.

**Giới hạn phạm vi.**
- Chưa đo bước sinh patch.
- V3 và v4 trên Django và SymPy là thực nghiệm khám phá. Phần khẳng định nằm ở giai đoạn 3, trên repo giữ lại lấy từ split train của SWE-bench.
- Snapshot là phép xấp xỉ, có thể sớm hơn base commit tới 60 ngày.

---

## 2. Lý thuyết nền

### 2.1 Truy hồi thông tin

| Khái niệm | Nội dung | Dùng ở đâu | Cơ sở | Đã đọc |
|---|---|---|---|---|
| Mô hình không gian vector TF-IDF | Văn bản là vector thưa. Trọng số w = (log f + 1) × log(N / n_t). Độ tương đồng là cosine | HIST v4 (NL, CE), ISSUE | Locus; rVSM của BugLocator | Locus toàn văn; BugLocator qua nguồn thứ cấp |
| BM25 | Mô hình xác suất. `BM25Okapi`, k1 = 1,5, b = 0,75 | AST, DOC, HIST v3 | Mặc định của `rank_bm25` | Chưa có bài trong tài liệu đã đọc |
| Dense retrieval | Embedding `BAAI/bge-small-en-v1.5`, vector chuẩn hóa, cosine | AST (Function/Class), DOC | Chưa có bài | |
| Thang điểm | Cosine có thang cố định nên đặt được ngưỡng tuyệt đối. BM25 không có trần. RRF chỉ phản ánh thứ hạng | Ngưỡng (mục 2.5) | | |
| Reciprocal Rank Fusion | Điểm = Σ 1/(k + r), k = 60, trọng số bằng nhau | Gộp BM25 và embedding; trộn nguồn với AST | Cormack, Clarke, Büttcher (SIGIR 2009) | Chưa có trong artifact |

**Giới hạn của cách trộn hiện tại** (`fused_multi`). Điểm là 1/(60 + hạng AST) + Σ p/(60 + vị trí trong nguồn), giữ h node đầu của AST. Với p = 0,25, node đứng đầu danh sách nguồn chỉ vào top 10 khi hạng AST nhỏ hơn khoảng 38. Với p = 1, không có giới hạn. Lưới p và h chưa có bài báo làm cơ sở. Cách trộn chưa chốt.

### 2.2 Định vị lỗi dựa trên truy hồi thông tin

| Bài | Ý chính | Liên quan tới đề tài | Đã đọc |
|---|---|---|---|
| BugLocator (Zhou, Zhang, Lo, ICSE 2012) | SimiScore(f) = Σ sim(b, b′) / \|Fix(b′)\| qua mọi báo cáo cũ đã sửa ở f. Không có ngưỡng tương đồng. Trọng số tốt nhất 0,2 đến 0,3 | Công thức của ISSUE | Nguồn thứ cấp |
| AmaLgam (Wang, Lo, ICPC 2014) | Gộp version history, báo cáo tương tự và cấu trúc. History chỉ cộng khi điểm văn bản lớn hơn 0. Cửa sổ 15 ngày | Quy tắc `fix\|bug`; tiền lệ gộp có điều kiện | Toàn văn |
| Locus (Wen, Wu, Cheung, ASE 2016) | Mỗi hunk là một tài liệu. score = max{NL + α·CE} + β₁·Fix. λ = 5, β₁ = 0,1. Hunk tốt hơn cả file (SWT MAP 0,382 lên 0,630). CE +23,6% MAP | Công thức của HIST v4, với 7 chỗ chuyển đổi sang mức hàm/lớp | Toàn văn |
| Sisman và Kak (MSR 2012) | Xác suất tiên nghiệm từ history, giảm theo hàm mũ thời gian | Không dùng cửa sổ cứng | Một phần, qua patent |
| Kochhar, Tian, Lo (ASE 2014) và bản làm lại của Widyasari và cộng sự | Báo cáo lỗi nêu sẵn vị trí làm định vị dễ hơn | Tách kết quả theo issue có nêu tên gold | Tóm tắt |

### 2.3 Lịch sử phiên bản và liên kết issue với commit

- **Đơn vị commit.** Mỗi commit trên nhánh chính (`git log --first-parent`). Với SymPy, phần lớn là merge commit của một PR.
- **Liên kết issue với commit.** Django dùng "Fixed #N" trong message (ticket Trac). SymPy dùng từ khóa đóng issue trong body của PR. Đề xuất chỉ dùng "Fixed #N" cho Django chưa được xác nhận.
- **ROSE** (Zimmermann và cộng sự, ICSE 2004, toàn văn). Co-change theo support và confidence. Bỏ transaction chạm hơn 30 thực thể. Precision mức hàm khoảng 26%, 3 gợi ý đầu đúng ở 64%.
- **HAFix** (toàn văn phần chính) và **HAFixAgent** (toàn văn phần chính). Chọn commit bằng blame trên dòng nghi ngờ. Tên các hàm sửa cùng là tín hiệu ổn định. Diff thô thường làm kém với model nhỏ, nhưng là loại đơn lẻ tốt nhất ở 2 trên 3 model lớn. Gộp nhiều loại history là tốt nhất.
- **Rò rỉ theo thời gian.**
  - Bản tái lập ABLoTS (2026, toàn văn phần chính): dùng đúng ngày tạo báo cáo, MAP giảm từ 0,488 xuống 0,055.
  - KGCompass (toàn văn): chỉ giữ artifact có trước `created_at`, loại 24% artifact.
  - Lingxi: lọc kho issue cũ theo thời gian tạo.
  - SWE-bench issue #465: agent đọc được bản sửa tương lai qua `git log --all`.
  - Đề tài dùng điều kiện tổ tiên của snapshot, chặt hơn lọc theo thời gian.

### 2.4 Đồ thị của repository và lan truyền trên đồ thị

- **Vai trò của đồ thị trong đề tài.** Đồ thị liên kết các node. Khi search không với tới node cần thiết, quan hệ giữa các node đưa node đó vào kết quả. Node bằng chứng có liên kết với AST node đã truy hồi được ưu tiên hơn. AST node cũng hop ra các node khác.
- **Cơ sở cho graph History.** Abedu, Khatoonabadi, Shihab (ACM TOSEM, toàn văn): graph Neo4j với User, Commit, Issue, File; cạnh Fixed, Changed (mang patch), Impacted. KGCompass: nối issue và PR tới file, lớp, hàm.
- **HippoRAG** (NeurIPS 2024, toàn văn phần chính). Mở rộng hàng xóm đơn thuần kém hơn chỉ dùng node gốc (R@2 42,2 so với 50,7). PPR với restart 0,5 đạt 57,4. Specificity s = 1/|P_i| giúp thêm.
- **KGCompass.** Điểm giảm theo độ dài đường đi (β = 0,6). Giữ top 15 hàm vì phủ 97,3% gold mà graph tìm được.
- **Các hệ thống graph cho code** (khảo sát tháng 5, đọc code): RepoGraph của ozyyshr (NetworkX, ego graph), CodeFuse CGM (8 loại node, BFS 2 bước), Prometheus (Neo4j, TextNode), CodexGraph (Cypher), LocAgent (agent đi theo graph). Cả ba hệ đầu đều build graph cho từng instance và offline.

### 2.5 Ngưỡng và cắt danh sách

- **Quyết định.** Dùng ngưỡng thay cho số lượng cố định, ở ba chỗ: trước khi hop, trước khi vote và trước khi output.
- **Lý do.** Một instance có thể có 5 đến 10 issue cũ liên quan, hoặc không có issue nào. Đưa đủ 5 issue không liên quan làm loãng context. Theo ước lượng ở mục 9.2 của `research_context.md`, mức trần ISSUE sau khi lọc là 83,7% (Django) và 66,9% (SymPy).
- **Tiền lệ trong tài liệu đã đọc.** Phần lớn dùng top k (KGCompass 15 hàm, ExpeRepair 3 ví dụ, BugLocator không có ngưỡng). ROSE dùng ngưỡng support và confidence, nhưng cho khai thác luật.
- **Hướng tìm hiểu, chưa đọc:** cắt danh sách xếp hạng (ranked list truncation), ví dụ Arampatzis và cộng sự (SIGIR 2009), Choppy (Bahri và cộng sự, SIGIR 2020); ảnh hưởng của tài liệu nhiễu tới LLM, ví dụ Cuconasu và cộng sự (2024).
- **Cách chọn ngưỡng:** chưa chốt.

### 2.6 Đánh giá

**Theo gold.**
- Gold là các hàm/lớp mà bản vá thật đã sửa, tính bằng oracle `get_oracle` tại base commit. Oracle đã sửa ba lỗi (dòng thêm mới, đổi tên file, decorator). Gold, HIST và ISSUE dùng chung oracle, và điều này được ghi là mối đe dọa.
- Độ đo:
  - Top@1, Top@5, Top@10 (any-gold) và MAP theo Locus và AmaLgam (toàn văn); MRR theo Locus;
  - Acc@10 (mọi gold trong top 10) theo LocAgent và SweRank (tóm tắt). MULocBench (toàn văn phần độ đo) cũng dùng Acc@k.
- Hạng tính tới 500.
- Kiểm định: McNemar cho Top@10. V2 và v3 có dùng TRisk (Dinçer và cộng sự, tóm tắt). `verify-v4` giữ đơn giản, không có khoảng tin cậy, TRisk hay hiệu chỉnh nhiều kiểm định.

**Theo LLM judge.**
- eRAG (Salemi, Zamani, SIGIR 2024, toàn văn): nhãn "liên quan" do LLM chấm gần như không tương quan với kết quả cuối (Kendall τ từ −0,04 đến 0,19).
- Utility judgments (Zhang và cộng sự, SIGIR 2024, toàn văn phần chính): hỏi "hữu ích" tốt hơn hỏi "liên quan" (F1 +30,98% trên NQ). Chấm theo danh sách tốt hơn. LLM nhạy với vị trí.
- Thomas và cộng sự (SIGIR 2024, tóm tắt): nhãn LLM chính xác khi prompt được chọn theo phản hồi thật.
- Judge v3 chấm mức liên quan. Nhãn commit của v3 không dùng được vì judge chỉ thấy message.
- Judge v4 chấm hai điểm (liên quan và hữu ích), có xem bản vá, viết lý do trước điểm, xáo thứ tự, và ghi thêm loại thông tin. Danh sách loại chưa chốt.

**Theo agent (sau này).** Agent dùng output để kiểm chứng hiệu quả từ bên ngoài. CodeRAG-Bench (NAACL 2025, đã phân tích trong cuộc trò chuyện trước) là tiền lệ cho việc đánh giá truy hồi bằng tác vụ phía sau.

---

## 3. Graph

| Nhóm | Node | Cạnh | Cách tạo |
|---|---|---|---|
| Code | Module, Class, Function. Id `{snap8}:{đường dẫn}:{tên lồng nhau}` | `Defines`, `Imports`, `Calls` (heuristic), `Inherits` | tree-sitter. Bỏ thư mục test, docs, examples, benchmarks |
| Doc | Document, DocChunk (theo heading RST, cắt ở 1.600 ký tự) | `HasChunk`; `Documents` (role và directive Sphinx, nối theo module ngữ cảnh, bỏ khi mơ hồ); `References` (role `:doc:`) | Đọc thư mục doc đầu tiên tồn tại |
| History | Commit; Issue (`issue:<repo>:<số>`, title, toàn văn, thời điểm tạo) | `Modifies` (Commit tới hàm/lớp, mang diff của hunk); `Fixes` (Commit tới Issue) | `hist-build`, `hist-proc`; cào Trac CSV và GitHub API |

Issue đang cần định vị chỉ là query, không phải node. Nhóm History được lưu một lần cho mỗi repo, rồi đổi id sang id của từng snapshot.

**Vấn đề đã biết.**
- Chunk thường chỉ nối tới class thay vì method. Có chunk nhắc tên gold nhưng không có cạnh.
- Chỉ 18% (Django) và 8% (SymPy) hàm/lớp có chunk nối tới.

---

## 4. Pipeline

| Bước | Việc | Cách làm | Trạng thái |
|---|---|---|---|
| 1 | Snapshot | Khoảng 60 ngày, build tại base commit sớm nhất trong khoảng | Đã chạy |
| 2 | Graph code và doc | Mục 3 | Đã chạy |
| 3 | Gold | Oracle mới | Đã chạy ở lượt 1 của v4 |
| 4 | AST | BM25 (mọi node, kể cả Module) cộng embedding (Function/Class), RRF, giữ 500 | Đã chạy |
| 5 | DOC (`vote_ast`) | 5 chunk có cạnh `Documents` bỏ phiếu, lan một bước theo cạnh AST (0,5, trần 20 hàng xóm), sắp theo hạng AST | Đã chạy |
| 6 | HIST v4 | Locus ở mức hàm/lớp trên hunk của các đơn vị là tổ tiên của snapshot | Danh sách đã có, chưa trộn |
| 7 | ISSUE | SimiScore của BugLocator, TF-IDF cosine, lọc thời gian và tổ tiên | Có dữ liệu cào, chưa cài |
| 8 | Trộn | Chưa chốt. Yêu cầu: không tự đặt trần | Chưa chốt |
| 9 | Ngưỡng | Trước hop, trước vote, trước output | Chưa chốt cách chọn |
| 10 | Judge v4 | Node code `#code2` và bằng chứng | Đã chốt, chưa cài |
| 11 | Đánh giá `verify-v4` | Bảng 1, Bảng 2, ba phân tích bổ sung | Đã chốt, chưa cài |

Chi tiết từng bước ở `pipeline_design.md`.

---

## 5. Câu hỏi và bản đồ liên kết

Câu hỏi giữ nguyên Q1 đến Q7 (mục 6.2 của `planning.md`). Khung so sánh với AST được giữ toàn bộ, gồm các mức hop và các cách kết hợp nguồn.

| Câu hỏi | So sánh | Thành phần | Cơ sở chính | Kết quả hiện có |
|---|---|---|---|---|
| Q1 | +DOC so với AST | Graph doc, `vote_ast` | Chưa có bài cho cách bỏ phiếu | V3 với oracle mới: Top@10 55,5 lên 57,4 (McNemar 26 và 4, p = 0,0001) |
| Q2 | +HIST so với AST | HIST v4 theo Locus | Locus, AmaLgam | HIST v3: 55,5 lên 59,7 (71 và 21). HIST v4 chưa trộn |
| Q3 | +ISSUE so với AST | ISSUE | BugLocator, Lingxi, KGCompass | Chưa có |
| Q4 | +ALL so với AST (câu chính) | Mọi nguồn, trộn | Cormack RRF | DOC+HIST v3: 55,5 lên 61,2 (87 và 19) |
| Q5 đến Q7 | +ALL so với bỏ bớt từng nguồn | Trộn | | DOC+HIST so với HIST v3: 21 và 3 (p = 0,0003) |

---

## 6. Kết quả chính

**V2 (12 repo, test 1.924 instance).** DOC tốt hơn AST ở 27 instance và kém hơn ở 10 (p = 0,008). Django chiếm phần lớn. Kết quả theo judge của v2 không còn đáng tin vì judge sai yêu cầu.

**V3 (Django và SymPy, test 1.006 instance, thực nghiệm khám phá).** Hit@10 any-gold tăng từ 57,3% (AST) lên 62,4% (DOC+HIST). Hai nguồn bổ sung cho nhau: trong các instance AST trượt, 2,8% chỉ được doc cứu, 11,2% chỉ được history cứu, 2,6% được cả hai cứu. Không hệ thống nào đưa được gold ngoài hạng 100 vào top 10.

**V4 lượt 1 (16/10/2026, 1.187 instance, oracle mới).**

| Hệ thống | Top@1 | Top@5 | Top@10 | MRR | MAP | Acc@10 |
|---|---|---|---|---|---|---|
| AST | 23,9 | 45,6 | 55,5 | 0,345 | 0,266 | 33,6 |
| DOC | 23,9 | 46,7 | 57,4 | 0,349 | 0,268 | 35,8 |
| HIST (v3) | 23,9 | 50,7 | 59,7 | 0,354 | 0,274 | 36,9 |
| DOC+HIST (v3) | 23,9 | 51,2 | 61,2 | 0,356 | 0,276 | 38,4 |

History giúp nhiều nhất khi issue không nêu tên gold: Top@10 từ 39,8% lên 45,9%. HIST theo Locus khi đứng riêng: thành phần Fix làm Django giảm còn 43,1%, nguyên nhân chưa kiểm chứng.

**Kết luận hẹp.** Có cơ sở trên hai repo. **Kết luận rộng** ("đa nguồn nói chung tốt hơn chỉ dùng code") chưa chứng minh, vì còn thiếu repo giữ lại, nhiều repo hơn, kiểm tra snapshot và nguồn ISSUE.

---

## 7. Quyết định quan trọng

Danh sách đầy đủ ở mục 11 của `research_context.md` (quyết định 1 đến 35). Các quyết định định hướng:
- LLM không tham gia tạo xếp hạng.
- Mọi quyết định kỹ thuật phải có bài báo làm cơ sở.
- Không tách dev và test. V4 là thực nghiệm khám phá. Giai đoạn 3 chạy với luồng xử lý đã đóng băng.
- HIST xếp hạng theo Locus. Thiết kế `hist-llm` đã bỏ.
- Chủ đề là truy xuất ngữ cảnh. Agent dùng để kiểm chứng sau. Judge chấm các node output.
- Node doc, issue cũ và hunk là output, ghép theo loại.
- Dùng ngưỡng thay cho số lượng cố định.
- Giữ toàn bộ khung so sánh với AST và Q1 đến Q7.

---

## 8. Việc còn mở

1. Cách trộn các nguồn với AST.
2. Cách chọn ngưỡng ở ba vị trí. Cần tìm bài báo hoặc kỹ thuật liên quan.
3. Danh sách loại thông tin cho judge bằng chứng.
4. Cài nguồn ISSUE. Xác nhận chỉ dùng "Fixed #N" cho Django, và mốc thời gian theo thời điểm tạo báo cáo của instance.
5. Nguyên nhân thành phần Fix làm HIST giảm ở Django.
6. Sửa cách nối doc với code (phải xong trước khi đóng băng).
7. Quy tắc A7 bỏ sót tên lớp chỉ viết hoa chữ đầu.
8. Việc 1.3: kiểm tra snapshot trên 100 instance.
9. Các cell `v4-config`, `v4-fusion`, `judge-v4`, `verify-v4`, `manifest`.
10. Giai đoạn 3: xác nhận trên repo giữ lại.
11. Cập nhật `pipeline_design.md` và artifact tài liệu theo định hướng ngày 18/10.
12. Viết lại dàn ý Chương 2 theo mục 2 của file này.

---

## 9. Tài liệu tham khảo

- Locus, ASE 2016: https://cse.hkust.edu.hk/faculty/scc/publ/ase16-Locus-preprint.pdf
- AmaLgam, ICPC 2014: http://www.mysmu.edu/faculty/davidlo/papers/icpc14-localization.pdf
- BugLocator, bản ghi ở SMU: https://ink.library.smu.edu.sg/sis_research/1531
- Tái lập ABLoTS: https://arxiv.org/html/2605.11790v1
- Sisman và Kak, patent US10108526B2: https://patents.google.com/patent/US10108526B2/en
- ROSE, ICSE 2004: https://thomas-zimmermann.com/publications/files/zimmermann-icse-2004.pdf
- HAFix: https://arxiv.org/abs/2501.09135
- HAFixAgent: https://arxiv.org/html/2511.01047
- KGCompass: https://arxiv.org/abs/2503.21710
- Synergizing LLMs and Knowledge Graphs (Abedu và cộng sự): https://arxiv.org/abs/2412.03815
- HippoRAG: https://arxiv.org/abs/2405.14831
- Lingxi: https://arxiv.org/abs/2510.11838
- ExpeRepair: https://arxiv.org/abs/2506.10484
- OM-RAG: https://arxiv.org/abs/2607.21911
- LocAgent: https://arxiv.org/html/2503.09089v1
- SweRank: https://arxiv.org/html/2505.07849v2
- MULocBench: https://arxiv.org/html/2509.25242v1
- eRAG: https://arxiv.org/abs/2404.13781
- Utility judgments: https://arxiv.org/abs/2403.19216
- Thomas và cộng sự: https://arxiv.org/abs/2309.10621
- GeoRisk, SIGIR 2016: https://www.semanticscholar.org/paper/Risk-Sensitive-Evaluation-and-Learning-to-Rank-Din%C3%A7er-MacDonald/ec06182b8810bb70ddb3c0aa0f5d2981cbe2d602
- Cormack, Clarke, Büttcher, Reciprocal Rank Fusion, SIGIR 2009 (chưa có link trong tài liệu hiện có)
