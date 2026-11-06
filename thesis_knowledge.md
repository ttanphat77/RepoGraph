# Tổng hợp tri thức đề tài RepoGraph

Cập nhật ngày 29/10/2026 (kết quả lượt v4-L8 trên 12 repo, phân tích chi tiết của judge, cơ sở của phân tích này). Lần cập nhật trước là ngày 28/10/2026 (xếp hạng node sau hop theo KGCompass, phân tích ảnh hưởng của độ phủ doc).

File này hệ thống hóa toàn bộ kiến thức của đề tài ở một chỗ: bài toán, lý thuyết nền, graph, pipeline, đánh giá, kết quả, quyết định và việc còn mở. File chỉ tóm tắt. Chi tiết nằm ở các file được trỏ tới. Khi file này và file chi tiết khác nhau, file chi tiết là nguồn đúng.

Cột "Đã đọc" ở mục 2 ghi mức đọc bài báo: **toàn văn**, **một phần**, **tóm tắt**, hoặc **chưa đọc** (mới chỉ nhắc theo hiểu biết chung, cần đọc trước khi dẫn).

---

## 0. Bản đồ tài liệu

| Tài liệu | Vai trò | Tình trạng |
|---|---|---|
| `research_context.md` | Bối cảnh, dữ liệu, phương pháp, kết quả v2 đến v4, quyết định 1 đến 60, định hướng ngày 18/10 (mục 12) | Mới nhất |
| `planning.md` | Lộ trình, thiết kế v4, thuật ngữ (mục 2), câu hỏi Q1 đến Q7, chi phí, rủi ro, quy tắc làm việc, trạng thái mục 14 (mục 14.12 đến 14.17) | Mới, có vài mục cũ chưa khớp quyết định mới |
| `pipeline_design.md` | Từng kỹ thuật: input, tham số, output, cơ sở, trạng thái; bảng tham số (mục 12) | Cập nhật 28/10/2026. Chưa có ngưỡng |
| `theoretical_foundation.md` | Hệ thống cơ sở lý thuyết theo 6 tầng của pipeline: công thức, bài báo cơ sở, mức đã đọc; thành phần chưa có cơ sở, mâu thuẫn giữa các file, lỗ hổng lập luận | Tạo ngày 03/11/2026 |
| `experiment_log.md` | Nhật ký các lượt chạy: cấu hình, thời gian, kết quả, đánh giá, sự cố; độ lặp lại giữa các lượt | Tạo ngày 22/10/2026. Cập nhật 29/10/2026, tới lượt v4-L8 và phân tích chi tiết của judge |
| Artifact "Tổng quan tài liệu RepoGraph" (https://claude.ai/artifact/DSWQi3W5KrFzSFPLKynKcL) | Báo cáo đọc 18 bài báo, bảng kết luận cho từng câu hỏi thiết kế | Cập nhật 14/10, thiếu các bài về ISSUE và RRF |
| `colab/build_graph_flask_colab.ipynb` | Notebook chạy thực nghiệm trên Kaggle, 46 cell. Từ 27/10/2026 chỉ còn code của pipeline v4 | Chứa output lượt v4-L8, cùng `GOOGLE_API_KEY` và `GITHUB_TOKEN` thật. Không commit khi còn key |
| `docs/graph-architecture-discussion.md` | Thảo luận kiến trúc graph tháng 5 | **Lỗi thời** (Neo4j, F1, bỏ Issue/Commit) |
| `README.md`, `doc_integration_plan.md` | Bản POC ban đầu | **Lỗi thời** |

---

## 1. Bài toán và phạm vi

**Tên đề tài.** Truy xuất ngữ cảnh đa nguồn dựa trên đồ thị hỗ trợ AI Agent trong phát triển phần mềm.

**Bài toán.** Input là một prompt trên một repository: issue, câu hỏi, hoặc yêu cầu tìm code hay doc. Hệ thống truy xuất tập ngữ cảnh đa nguồn K(p) gồm code, doc, history và issue cũ, ghép theo loại và lọc bằng ngưỡng. Đánh giá là K(p) có cung cấp đúng thông tin cần cho prompt hay không: với issue là có tìm được file và hàm cần sửa không, với hỏi đáp là có tìm đúng thông tin cần không. Phân tích issue chỉ là một use case. Hệ thống hỗ trợ AI agent, và agent sẽ được dùng sau để kiểm chứng.

**Phạm vi thực nghiệm.** Chỉ tập trung vào kiến trúc retrieval. Use case được đánh giá là issue trên SWE-bench. Agent, sinh patch và các use case khác nằm ngoài thực nghiệm hiện tại. Tài liệu và phân tích được thu thập cũng chỉ giới hạn ở quy trình retrieval.

**Đo được hiện tại.** Với use case issue, output gồm:
- AST node xếp theo khả năng phải sửa, đo bằng gold;
- các node bằng chứng (chunk doc, issue cũ, hunk), ghép theo loại, đánh giá bằng LLM judge.

**Bốn nguồn.**

| Nguồn | Nội dung | Thông tin mang lại |
|---|---|---|
| AST | Hàm, lớp, module và quan hệ code | Mốc chỉ dùng code |
| DOC | File tài liệu `.rst`, `.md`, `.txt`, chia thành DocChunk. Docstring không tính là doc | Hành vi mong đợi, cách dùng API |
| HIST | Commit cũ, xem cùng diff | Vùng code từng đổi ra sao và vì sao |
| ISSUE | Báo cáo lỗi cũ đã sửa | Lỗi tương tự, nơi đã sửa |

**Dữ liệu.** Split test của SWE-bench bản đầy đủ. Từ lượt v4-L8, v4 dùng cả 12 repo của split test. File kết quả có 2.294 instance, và 2.214 instance có gold được đánh giá. Cache có 279 graph snapshot. Các lượt v4 trước dùng Django và SymPy: 1.187 instance (821 và 366), 86 graph snapshot. V2 đã chạy trên 12 repo. Không tách dev và test từ v4.

**Khung lập luận** (mục 2 của `research_context.md`).
- Mọi kết quả so với AST. Mục tiêu chính không phải tìm nguồn mạnh nhất.
- Doc có tác động âm thì lỗi nằm ở phương pháp. Thông tin trùng với issue và code thì tác động bằng 0.
- Không bắt buộc issue nào cũng được doc giúp. Doc chỉ cần giúp khi xét chung.
- LLM không tham gia tạo xếp hạng.
- Commit luôn được đọc cùng diff.
- Mỗi quyết định kỹ thuật phải có bài báo làm cơ sở. Số đo của đề tài chỉ bổ sung.

**Giới hạn phạm vi.**
- Chưa đo bước sinh patch.
- Kết quả chỉ khẳng định cho use case issue. HIST theo Locus và ISSUE theo BugLocator có cơ sở bài báo cho báo cáo lỗi, chưa có cho loại prompt khác.
- Đề tài không chia dữ liệu thành tập dùng để chọn và tập dùng để xác nhận, vì không huấn luyện model (quyết định 58). Từ lượt v4-L8, kết quả gồm cả 12 repo của tập test trong cùng một thực nghiệm.
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

**Giới hạn của cách trộn của v3** (`fused_multi`, đã bỏ). Điểm là 1/(60 + hạng AST) + Σ p/(60 + vị trí trong nguồn), giữ h node đầu của AST. Với p = 0,25, node đứng đầu danh sách nguồn chỉ vào top 10 khi hạng AST nhỏ hơn khoảng 38. Với p = 1, không có giới hạn. Lưới p và h chưa có bài báo làm cơ sở.

**Cách trộn đã chốt (27/10/2026).** V4 dùng RRF gốc của Cormack và cộng sự, với mọi danh sách có trọng số 1 và k = 60. Không tham số nào được chọn trên dữ liệu của đề tài. Giới hạn là bài của Cormack không thử trộn một danh sách mạnh với các danh sách yếu hơn nhiều. Ở lượt v4-L7 và v4-L8, chính trường hợp này làm DOC và ISSUE kéo kết quả xuống. Phân tích judge của v4-L8 cho thấy cơ chế. Danh sách của một nguồn chỉ giúp khi bằng chứng của nguồn đó dẫn tới gold. Khi bằng chứng không dẫn tới gold, danh sách vẫn có lá phiếu ngang AST, và đẩy các hàm/lớp khác gold lên trên (mục 6).

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
  - Công thức đầy đủ (đọc bài và code công khai ngày 27/10/2026): S(f) = β^l(f) × (α × cos_norm + (1 − α) × lev), với β = 0,6, α = 0,3, cos_norm = (cos + 1) / 2, và lev = 1 − d / max(|a|, |b|) theo khoảng cách Levenshtein ký tự giữa issue và source của hàm. l(f) là tổng trọng số trên đường ngắn nhất (Dijkstra) từ issue tới f.
  - Bài không nêu trọng số cạnh. Code dùng ba mức: 0,25 cho quan hệ chứa và tham chiếu chắc chắn, 0,5 cho tham chiếu giải bằng tên, 1,0 cho lời gọi và thư mục. Ngân sách đường đi là 4. Cạnh gọi chỉ được tạo tới 500 method giống issue nhất.
  - β và α được tác giả chọn bằng cách thử trên SWE-bench. Hai bài được dẫn chỉ cho ý tưởng. Zhu và Iglesias (IEEE TKDE 2017) định nghĩa wpath = 1 / (1 + length × k^IC), không phải dạng mũ, và bỏ qua hướng cạnh. Ballatore và cộng sự (ISPRS IJGI 2015) cộng tuyến tính độ giống cấu trúc và độ giống văn bản, với α tốt nhất khoảng 0,5.
  - Đề tài dùng công thức này để xếp node sau hop (quyết định 59, mục 8b của `pipeline_design.md`).
  - Kết quả ở v4-L8 trên 12 repo. +GRAPH không đạt tiêu chí đặt trước (G1), vì kém AST có ý nghĩa ở Top@1, Top@5, Acc@5, MRR và MAP. DOC theo công thức này (`doc_kgc`) vẫn kém AST có ý nghĩa ở mọi độ đo (Q1). Thêm GRAPH vào +ALL thì tốt hơn có ý nghĩa ở mọi độ đo (G2).
- **Các hệ thống graph cho code** (khảo sát tháng 5, đọc code): RepoGraph của ozyyshr (NetworkX, ego graph), CodeFuse CGM (8 loại node, BFS 2 bước), Prometheus (Neo4j, TextNode), CodexGraph (Cypher), LocAgent (agent đi theo graph). Cả ba hệ đầu đều build graph cho từng instance và offline.

### 2.5 Ngưỡng và cắt danh sách

- **Quyết định.** Dùng ngưỡng thay cho số lượng cố định, ở ba chỗ: trước khi hop, trước khi vote và trước khi output.
- **Lý do.** Một instance có thể có 5 đến 10 issue cũ liên quan, hoặc không có issue nào. Đưa đủ 5 issue không liên quan làm loãng context. Theo ước lượng ở mục 9.2 của `research_context.md`, mức trần ISSUE sau khi lọc là 83,7% (Django) và 66,9% (SymPy).
- **Tiền lệ trong tài liệu đã đọc.** Phần lớn dùng top k (KGCompass 15 hàm, ExpeRepair 3 ví dụ, BugLocator không có ngưỡng). ROSE dùng ngưỡng support và confidence, nhưng cho khai thác luật.
- **Ngữ cảnh nhiễu làm hại LLM** (đọc 19/10/2026). The Power of Noise (Cuconasu và cộng sự, SIGIR 2024): một tài liệu giống câu hỏi nhưng không chứa đáp án làm độ chính xác giảm tới 0,24; 3 đến 5 tài liệu là tốt nhất trong thí nghiệm của bài. Gu và cộng sự (arXiv 2503.20589): thêm code tương tự làm Pass@1 giảm từ 37,75 xuống 29,86 (RepoExec, GPT).
- **Cắt danh sách theo từng query, không giám sát** (đọc 19/10/2026).
  - Adaptive-k (Taguchi và cộng sự, EMNLP 2025): cắt tại khoảng rơi lớn nhất của cosine, cộng B = 5. Không trả rỗng được.
  - Phân bố điểm (Arampatzis, Kamps, Robertson, SIGIR 2009): hỗn hợp chuẩn và mũ, chọn điểm cắt tối ưu F1, có xét phương án không lấy gì.
  - Surprise (Bahri và cộng sự, arXiv 2010.09797): điểm bất ngờ theo GPD; không có độ đo đích thì gợi ý ngưỡng 2,3 đến 4,6 (p từ 0,1 đến 0,01).
- **Phương pháp có giám sát** (Choppy, SIGIR 2020; Meng và cộng sự, SIGIR 2024) chỉ hơn fixed-k một ít, cần nhãn, và hiếm khi dự đoán "không cần gì". Fixed-k là mốc phải so.
- **Ngưỡng trên đồ thị** (đọc 19/10/2026). Push PageRank (Andersen, Chung, Lang, FOCS 2006): chỉ lan tiếp từ node có phần dư r(u) ≥ ε·d(u), có cận trên cho số node được chạm tới. G-Retriever: hạt giống top k theo cosine, PCST với chi phí cạnh C_e điều khiển kích thước.
- **Ngưỡng cosine tuyệt đối:** chưa có bài nào trong các bài đã đọc dùng làm phương pháp chính.
- **Cách chọn ngưỡng:** chưa chốt. Chi tiết và bảng theo ba vị trí nằm ở mục "Ngưỡng và cắt danh sách" của artifact tài liệu.

### 2.6 Đánh giá

**Theo gold.**
- Gold là các hàm/lớp mà bản vá thật đã sửa, tính bằng oracle `get_oracle` tại base commit. Oracle đã sửa ba lỗi (dòng thêm mới, đổi tên file, decorator). Gold, HIST và ISSUE dùng chung oracle, và điều này được ghi là mối đe dọa.
- Độ đo:
  - Top@1, Top@5, Top@10 (any-gold) và MAP theo Locus và AmaLgam (toàn văn); MRR theo Locus;
  - Acc@10 (mọi gold trong top 10) theo LocAgent và SweRank (tóm tắt). MULocBench (toàn văn phần độ đo) cũng dùng Acc@k.
- Hạng tính tới 500.
- Kiểm định: `verify-v4` dùng McNemar chính xác cho độ đo đúng/sai, kiểm định hoán vị ghép cặp cho MRR và MAP, và Holm trong từng độ đo, riêng cho từng họ câu hỏi (mục 2.7). V2 và v3 có dùng TRisk (Dinçer và cộng sự, tóm tắt). `verify-v4` không dùng khoảng tin cậy hay TRisk.
- **Ảnh hưởng của độ phủ doc (28/10/2026).** Độ phủ doc được phân tích như một biến, không như ngưỡng lọc repo.
  - Ở mức repo, ρ của Spearman đặt độ phủ cạnh mức đóng góp của DOC. Cronen-Townsend, Zhou và Croft (SIGIR 2002, đọc đoạn phương pháp) dùng kiểm định này cho quan hệ giữa một đặc tính và độ chính xác truy hồi.
  - Ở mức instance, cell so hiệu giữa nhóm có gold được document và nhóm không có. Cách làm theo Kochhar và cộng sự (ASE 2014), và Gelman và Stern (2006).
  - +HIST và +GRAPH là đối chứng âm (Lipsitch và cộng sự, Epidemiology 2010).
  - Không cắt độ phủ thành hai nhóm, theo Altman và Royston (BMJ 2006).
  - Chi tiết ở mục 13.6 của `research_context.md`.
  - Kết quả ở v4-L8. C1 không có ý nghĩa ở độ đo nào. C2 có ý nghĩa ở mọi độ đo. Đối chứng âm +HIST không khác giữa hai nhóm, đúng như dự kiến. Số liệu ở mục 6.

**Theo LLM judge.**
- eRAG (Salemi, Zamani, SIGIR 2024, toàn văn): nhãn "liên quan" do LLM chấm gần như không tương quan với kết quả cuối (Kendall τ từ −0,04 đến 0,19).
- Utility judgments (Zhang và cộng sự, SIGIR 2024, toàn văn phần chính): hỏi "hữu ích" tốt hơn hỏi "liên quan" (F1 +30,98% trên NQ). Chấm theo danh sách tốt hơn. LLM nhạy với vị trí.
- Thomas và cộng sự (SIGIR 2024, tóm tắt): nhãn LLM chính xác khi prompt được chọn theo phản hồi thật.
- Judge v3 chấm mức liên quan. Nhãn commit của v3 không dùng được vì judge chỉ thấy message.
- Judge v4 chấm hai điểm (liên quan và hữu ích), có xem bản vá, xáo thứ tự, và ghi thêm loại thông tin. Danh sách loại gồm bảy loại theo Ko và cộng sự cộng hai nhãn loại trừ (quyết định 40). Từ ngày 26/10/2026, judge chỉ chấm bằng chứng, không viết lý do, và dùng thinking MINIMAL.

**Phân tích chi tiết của judge (29/10/2026).** Phân tích chạy ngoài notebook, trên nhãn của lượt v4-L8. Kết quả ở mục 6.
- **Kiểm tra nhãn của judge bằng một tín hiệu khách quan.** Một phần tử bằng chứng nối tới gold khi nó dẫn tới một hàm/lớp mà bản vá thật đã sửa. Với DOC, đó là cạnh `Documents` của chunk. Với HIST, đó là các hàm/lớp mà chính hunk đó sửa. Với ISSUE, đó là các hàm/lớp mà bản sửa của báo cáo cũ đã sửa. Tín hiệu này chỉ dựa vào cấu trúc code. Nhãn hữu ích của judge được so với tín hiệu đó, theo hướng của Faggioli và cộng sự (ICTIR 2023, chưa đọc) và Thomas và cộng sự (SIGIR 2024, tóm tắt). Judge thấy bản vá thật, nên hai tín hiệu không độc lập. Vì vậy phép so này chỉ kiểm tra độ nhất quán của judge.
- **Nối nhãn của từng phần tử với kết quả cuối.** Instance được chia theo việc pool của nguồn có phần tử hữu ích nối gold, có phần tử hữu ích không nối gold, hay không có phần tử hữu ích. Mỗi nhóm được đặt cạnh Δ của +nguồn so với AST. Cách làm theo eRAG (Salemi, Zamani, SIGIR 2024, toàn văn) và The Power of Noise (Cuconasu và cộng sự, SIGIR 2024, đọc 19/10/2026). Hiệu giữa nhóm có và không có phần tử hữu ích được kiểm định bằng hoán vị nhãn nhóm trong từng repo, như C2. Cách chia theo gold chỉ dùng được sau sự kiện, nên không phải là một phương pháp.
- **Bổ sung giữa các nguồn.** Bảng đếm instance theo tổ hợp nguồn có phần tử hữu ích, tách theo việc AST có gold trong top 10 hay không. Cách làm theo phân tích tổ hợp các họ kỹ thuật định vị lỗi của Zou và cộng sự (TSE 2021, chưa đọc).
- **Tỷ lệ hữu ích theo vị trí trong pool.** Cách xét theo vị trí theo Järvelin và Kekäläinen (TOIS 2002, chưa đọc).

**Theo agent (sau này).** Agent dùng output để kiểm chứng hiệu quả từ bên ngoài. CodeRAG-Bench (NAACL 2025, đã phân tích trong cuộc trò chuyện trước) là tiền lệ cho việc đánh giá truy hồi bằng tác vụ phía sau.

### 2.7 Bộ độ đo đã chốt (21/10/2026)

- **Phần AST, hai mức.** Hàm/lớp là mức chính, file là mức phụ. Xếp hạng file lấy điểm cao nhất của hàm/lớp trong file, theo [SweRank](https://arxiv.org/html/2505.07849v2). Độ đo: Top@1, Top@5, Top@10, MRR, MAP, và Acc@k (k = 5, 10 ở mức hàm/lớp; k = 1, 3, 5 ở mức file, như LocAgent và SweRank).
- **Phần bằng chứng.** Judge chấm một pool 10 phần tử đầu mỗi loại một lần. Hữu ích khi điểm hữu ích từ 2. Mỗi cách lọc có Precision, Recall, F1 (độ đo chuẩn của cắt danh sách), tỷ lệ trả rỗng đúng và sai, số token. Mốc so sánh là hạn ngạch cố định.
- **Loại thông tin.** Một danh sách chung, nhiều nhãn: hành vi mong đợi, cách dùng API, triệu chứng tương tự, nguyên nhân, vị trí code liên quan, lý do thiết kế, thay đổi trước đây; cộng hai nhãn loại trừ "không có thông tin mới" và "không liên quan". Cơ sở: [Ko, DeLine, Venolia (ICSE 2007)](https://faculty.washington.edu/ajko/papers/Ko2007InformationNeeds.pdf) và [Bettenburg và cộng sự](https://www.st.cs.uni-saarland.de/publications/files/bettenburg-tr-2007.pdf).
- **Đủ thông tin cho cả tập.** Nhãn nhị phân theo [Sufficient Context (ICLR 2025)](https://arxiv.org/pdf/2411.06037.pdf), chỉ cho Q4, đo chi phí trên 50 instance trước.
- **Kiểm định.** McNemar cho độ đo đúng/sai; hoán vị ghép cặp cho độ đo liên tục ([Smucker và cộng sự, CIKM 2007](https://ciir-publications.cs.umass.edu/pub/web/getpdf.php?id=744); [Urbano và cộng sự, SIGIR 2019](https://arxiv.org/pdf/1905.11096)); Holm trong từng độ đo.
- Chi tiết ở mục 13 của `research_context.md`.

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
| 4 | AST | BM25 (mọi node, kể cả Module) cộng embedding (Function/Class), RRF, giữ 500. Từ 22/10, hòa điểm xếp theo id | Đã chạy |
| 5 | DOC (`vote_ast`) | 5 chunk có cạnh `Documents` bỏ phiếu, lan một bước theo cạnh AST (0,5, trần 20 hàng xóm). Khi trộn, xếp theo điểm phiếu. Từ 28/10/2026, danh sách DOC khi trộn là `doc_kgc` (bước 7b) | Đã chạy. `doc_kgc` đã chạy ở v4-L8 |
| 6 | HIST v4 | Locus ở mức hàm/lớp trên hunk của các đơn vị là tổ tiên của snapshot | Đã chạy và đã trộn |
| 7 | ISSUE | SimiScore của BugLocator, TF-IDF cosine, lọc thời gian và tổ tiên, chỉ liên kết "Fixed #N" | Đã chạy và đã trộn |
| 7b | Xếp hạng node sau hop (`graph-proc`) | Công thức KGCompass trên cạnh `Defines`, `Calls`, `Inherits` và `Documents`, ngân sách 4. GRAPH đi từ 10 node đầu của AST. DOC đi từ đích cạnh của 10 chunk trong `doc_cand` | Đã chạy (v4-L8) |
| 8 | Trộn | RRF gốc của Cormack và cộng sự, mọi danh sách có trọng số 1, k = 60 (từ 27/10/2026). Trước đó dùng RRF có trọng số theo nguồn, chọn bằng kiểm định chéo | Đã chạy (v4-L7, v4-L8) |
| 9 | Ngưỡng | Trước hop, trước vote, trước output | Chưa chốt cách chọn |
| 10 | Judge v4 | Chỉ chấm bằng chứng (`#ev-doc`, `#ev-hist`, `#ev-issue`) và chấm lặp một mẫu. Từ 26/10: không viết lý do, thinking MINIMAL, không chấm node code | Bằng chứng, node code và chấm lặp đã chạy (v4-L5). Cài đặt mới đã chạy (v4-L6). Đã chạy trên 12 repo (v4-L8) |
| 11 | Đánh giá `verify-v4` | Bảng 1 hai mức, Bảng 2, kiểm định McNemar, hoán vị và Holm; khối ảnh hưởng của độ phủ doc; bảng bằng chứng | Đã chạy (v4-L8) |
| 12 | Độ đo theo cấu trúc `depth-v4` | Số node phải đọc trước khi gặp gold (k = 1, 5, 10) và độ sâu tới gold, trên graph Function/Class với cạnh `Calls`, `Inherits`, `Defines`. Thay cho nDCG@10 theo judge | Đã chạy (v4-L6 đến v4-L8) |

Chi tiết từng bước ở `pipeline_design.md`.

---

## 5. Câu hỏi và bản đồ liên kết

Câu hỏi giữ nguyên Q1 đến Q7 (mục 6.2 của `planning.md`). Khung so sánh với AST được giữ toàn bộ, gồm các mức hop và các cách kết hợp nguồn.

| Câu hỏi | So sánh | Thành phần | Cơ sở chính | Kết quả hiện có |
|---|---|---|---|---|
| Q1 | +DOC so với AST | Graph doc. Từ 28/10/2026, danh sách DOC là `doc_kgc` của `graph-proc`. Trước đó là `vote_ast` | KGCompass cho `doc_kgc`. Cách bỏ phiếu cũ chưa có bài | v4-L8 (12 repo): kém hơn có ý nghĩa ở mọi độ đo. Top@10 54,2 xuống 39,5, MRR 0,331 xuống 0,204, MAP 0,247 xuống 0,148 |
| Q2 | +HIST so với AST | HIST v4 theo Locus | Locus, AmaLgam | v4-L8: tốt hơn có ý nghĩa ở mọi độ đo. Top@10 54,2 lên 59,3, MRR 0,331 lên 0,375, MAP 0,247 lên 0,283. ΔMRR dương ở cả 12 repo |
| Q3 | +ISSUE so với AST | ISSUE | BugLocator, Lingxi, KGCompass | v4-L8: kém hơn có ý nghĩa ở mọi độ đo. Top@10 54,2 xuống 44,4, MRR 0,331 xuống 0,254, MAP 0,247 xuống 0,181 |
| Q4 | +ALL so với AST (câu chính) | Mọi nguồn, trộn | Cormack RRF | v4-L8: Top@10 54,2 lên 55,6, không có ý nghĩa. Top@1 22,4 xuống 18,5, MRR 0,331 xuống 0,306 và MAP 0,247 xuống 0,228, đều có ý nghĩa. Kết quả "Top@10 tốt hơn có ý nghĩa" của v4-L7 trên hai repo không còn đúng |
| Q5 đến Q7 | +ALL so với bỏ bớt từng nguồn | Trộn | | v4-L8: bỏ HIST làm kết quả giảm có ý nghĩa ở mọi độ đo (Q6). Thêm DOC làm Top@1 giảm 1,6 điểm có ý nghĩa, và không đổi có ý nghĩa ở độ đo khác (Q5). Thêm ISSUE làm Top@10 giảm 1,9 điểm và Acc@10 giảm 3,1 điểm, có ý nghĩa (Q7) |
| C1, C2 | Độ phủ doc so với mức đóng góp của DOC: ρ của Spearman ở mức repo (C1), hiệu giữa instance có và không có gold được document (C2) (họ Holm riêng) | `gold_doc`, `doc_cov`, khối độ phủ của `verify-v4` | Cronen-Townsend và cộng sự 2002, Kochhar và cộng sự 2014, Gelman và Stern 2006, Lipsitch và cộng sự 2010 | v4-L8: C1 không có ý nghĩa ở độ đo nào (Holm nhỏ nhất 0,5469). C2 có ý nghĩa ở mọi độ đo (Holm 0,0002). Hiệu ΔMRR giữa nhóm có và không có gold có doc là +0,123. Đối chứng âm +HIST không khác giữa hai nhóm (p = 0,57) |
| G1, G2 | +GRAPH so với AST; +ALL+GRAPH so với +ALL (họ Holm riêng) | Graph code, `graph-proc` | KGCompass | Tiêu chí đặt trước: tốt hơn có ý nghĩa ở ít nhất một độ đo của Bảng 1 mức hàm/lớp và không kém hơn có ý nghĩa ở độ đo nào. v4-L8: G1 không đạt tiêu chí. +GRAPH kém AST có ý nghĩa ở Top@1, Top@5, Acc@5, MRR và MAP. G2 tốt hơn có ý nghĩa ở mọi độ đo, và +ALL+GRAPH có Top@10 cao nhất (60,0) |

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

History giúp nhiều nhất khi issue không nêu tên gold: Top@10 từ 39,8% lên 45,9%. HIST theo Locus khi đứng riêng: thành phần Fix làm Django giảm còn 43,1%.

**V4 lượt đầy đủ (v4-L4, 22/10/2026, 1.187 instance).** Bốn nguồn được trộn bằng RRF có trọng số theo nguồn, chọn bằng kiểm định chéo 5 phần. Cách trộn này bị bỏ ngày 27/10/2026.

| Hệ thống | Top@1 | Top@10 | MRR | MAP |
|---|---|---|---|---|
| AST | 23,8 | 55,5 | 0,344 | 0,265 |
| +DOC | 22,4 | 56,4 | 0,340 | 0,259 |
| +HIST | 27,5 | 62,1 | 0,390 | 0,306 |
| +ISSUE | 24,3 | 56,7 | 0,355 | 0,272 |
| +ALL | 27,7 | 62,2 | 0,392 | 0,308 |

- +ALL tốt hơn AST ở mọi độ đo chính, có ý nghĩa sau Holm. Ở mức file, Top@1 tăng từ 47,3% lên 51,6%.
- Gần như toàn bộ phần tăng đến từ HIST. Trong HIST, CE (khớp tên code) đóng góp nhiều nhất. Fix không thêm gì sau khi trộn.
- DOC và ISSUE không thêm giá trị xếp hạng khi đã có HIST. Trọng số của DOC luôn ở mức nhỏ nhất của lưới. Giá trị của hai nguồn này như nội dung cho agent chưa được đánh giá.
- Fix kéo hàm bị sửa nhiều lần lên đầu danh sách ở Django. Đây là lý do HIST đứng riêng giảm ở Django.
- Chi tiết của mọi lượt nằm ở `experiment_log.md`.

**V4 với RRF gốc (v4-L7, 27/10/2026, 1.187 instance).** Bốn nguồn được trộn bằng RRF gốc, trọng số bằng nhau, k = 60. Không tham số nào được chọn trên dữ liệu của đề tài.

| Hệ thống | Top@1 | Top@10 | Acc@10 | MRR | MAP |
|---|---|---|---|---|---|
| AST | 23,8 | 55,5 | 33,6 | 0,345 | 0,265 |
| +DOC | 11,7 | 43,6 | 25,0 | 0,215 | 0,161 |
| +HIST | 27,9 | 62,4 | 39,1 | 0,393 | 0,309 |
| +ISSUE | 16,9 | 48,8 | 26,2 | 0,268 | 0,198 |
| +ALL | 19,1 | 59,6 | 36,4 | 0,318 | 0,241 |

- +HIST tốt hơn AST ở mọi độ đo, có ý nghĩa sau Holm. Đây là hệ thống tốt nhất ở Top@1, MRR và MAP.
- +ALL tốt hơn AST ở Top@10 và Acc@10, nhưng kém hơn ở Top@1 và MAP, đều có ý nghĩa. Ở mức file, +ALL không khác AST có ý nghĩa.
- +DOC và +ISSUE kém hơn AST có ý nghĩa ở mọi độ đo. Danh sách của hai nguồn này yếu hơn AST nhiều, nhưng có lá phiếu ngang AST.
- Trong HIST, CE vẫn đóng góp nhiều nhất, và Fix không thêm gì.

**V4 trên 12 repo (v4-L8, 28/10/2026, 2.214 instance).** Thực nghiệm gồm cả 12 repo của tập test. Cách trộn giống v4-L7. Danh sách DOC là `doc_kgc`, và có thêm nguồn GRAPH, cả hai theo KGCompass. Chi tiết ở mục 10 của `experiment_log.md`.

| Hệ thống | Top@1 | Top@10 | Acc@10 | MRR | MAP |
|---|---|---|---|---|---|
| AST | 22,4 | 54,2 | 30,3 | 0,331 | 0,247 |
| +DOC | 11,4 | 39,5 | 20,3 | 0,204 | 0,148 |
| +HIST | 26,4 | 59,3 | 34,2 | 0,375 | 0,283 |
| +ISSUE | 16,4 | 44,4 | 21,4 | 0,254 | 0,181 |
| +ALL | 18,5 | 55,6 | 30,4 | 0,306 | 0,228 |
| +GRAPH | 17,2 | 53,8 | 29,9 | 0,285 | 0,221 |
| +ALL+GRAPH | 21,1 | 60,0 | 35,0 | 0,336 | 0,258 |

- +HIST tốt hơn AST ở mọi độ đo, có ý nghĩa sau Holm. ΔMRR của +HIST dương ở cả 12 repo. +HIST là hệ thống tốt nhất ở Top@1 và MRR.
- +ALL không còn tốt hơn AST ở Top@10. Mức tăng 1,4 điểm không có ý nghĩa. Top@1, MRR và MAP kém hơn có ý nghĩa. Ở mức file, +ALL kém AST có ý nghĩa ở Top@1, Acc@1, Acc@3, MRR và MAP.
- +DOC và +ISSUE kém hơn AST có ý nghĩa ở mọi độ đo. DOC theo KGCompass không làm Q1 tốt hơn.
- +GRAPH không đạt tiêu chí đặt trước (G1). Thêm GRAPH vào +ALL tốt hơn có ý nghĩa ở mọi độ đo (G2). +ALL+GRAPH có Top@10 và Acc@10 cao nhất, nhưng vẫn kém +HIST ở Top@1, MRR và MAP.
- Độ phủ doc của repo không liên quan tới hiệu quả của +DOC (C1). Ở mức instance, việc gold có cạnh `Documents` quyết định hiệu quả của DOC (C2). Khi gold có doc, MRR của +DOC giảm 0,039 so với AST. Khi gold không có doc, MRR giảm 0,162. Chỉ 27,6% instance có gold có doc.
- Ở Django và SymPy, số liệu theo repo của AST và +HIST trùng v4-L7 ở từng ô.

**Bằng chứng theo judge (v4-L6, cài đặt judge mới).** Tỷ lệ instance có ít nhất một phần tử hữu ích trong 10 phần tử đầu là 46,2% với DOC, 74,1% với HIST và 77,7% với ISSUE. DOC chủ yếu cho hành vi mong đợi và cách dùng API. HIST cho vị trí code và thay đổi trước đây. ISSUE cho lỗi tương tự và nguyên nhân lỗi. κ của nhãn hữu ích khi gộp ba nguồn là 0,627. Như vậy DOC và ISSUE không giúp xếp hạng, nhưng vẫn cung cấp loại thông tin mà HIST hiếm khi có.

**Bằng chứng theo judge (v4-L8, 12 repo).** Tỷ lệ instance có ít nhất một phần tử hữu ích trong pool là 37,8% với DOC, 68,7% với HIST và 73,7% với ISSUE. Thứ tự giữa ba nguồn giống v4-L6. κ của nhãn hữu ích khi gộp ba nguồn là 0,646, trên mẫu chấm lặp 130 instance. Phân tích chi tiết của judge (cuối mục 10 của `experiment_log.md`) cho năm kết quả.
- Nhãn của judge nhất quán với tín hiệu khách quan. Tỷ lệ phần tử nối tới gold tăng theo điểm hữu ích. Ở điểm 0, tỷ lệ này không quá 1,3%. Ở điểm 3, tỷ lệ này là 23,2% với DOC, 52,6% với HIST và 60,1% với ISSUE.
- Phần lớn phần tử hữu ích không nối tới gold. Tỷ lệ không nối là 77,1% với DOC, 62,3% với HIST và 67,1% với ISSUE. Các phần tử này mang loại thông tin khác. Với DOC, 57,4% có cách dùng API và 49,0% có hành vi mong đợi. Với ISSUE, 51,3% có lỗi tương tự.
- Trộn chỉ giúp khi bằng chứng hữu ích nối tới gold. Ở nhóm instance này, ΔMRR so với AST là +0,167 với HIST, +0,092 với ISSUE và +0,002 với DOC. Khi bằng chứng hữu ích không nối tới gold, ΔMRR là −0,034 với HIST, −0,168 với ISSUE và −0,138 với DOC. Nhóm này không tốt hơn nhóm không có phần tử hữu ích nào.
- 91,4% instance có phần tử hữu ích từ ít nhất một nguồn. Trong các instance mà AST không có gold trong top 10, tỷ lệ này là 87,2%. ISSUE là nguồn duy nhất có phần tử hữu ích ở 13,2% instance.
- Ở cả ba nguồn, phần tử xếp càng cao càng hay hữu ích. Ở vị trí 1, tỷ lệ hữu ích là 16,6% với DOC, 29,6% với HIST và 32,6% với ISSUE. Ở vị trí 10, các tỷ lệ này là 3,0%, 12,1% và 7,1%.

Như vậy bằng chứng mang thông tin hữu ích ở hầu hết instance, kể cả khi AST trượt. Tuy vậy, cách trộn hiện tại chỉ dùng được phần thông tin về vị trí code. Điều này giải thích vì sao judge chấm ISSUE là hữu ích nhiều nhất, trong khi +ISSUE kém AST (Q3).

**Vai trò của graph.** Từ v4-L8, DOC và GRAPH đi trên cạnh của graph theo KGCompass. GRAPH đứng riêng kém AST (G1). Thêm GRAPH vào +ALL thì tốt hơn (G2). Có một giả thuyết chưa được kiểm tra cho G2. GRAPH đi từ 10 node đầu của AST, nên thêm GRAPH có thể chỉ trả lại phần lá phiếu của AST mà DOC và ISSUE đã làm loãng. DOC chỉ giữ được Top@10 của AST khi gold có cạnh `Documents` (C2). HIST và ISSUE vẫn là tìm kiếm văn bản rồi nối kết quả với hàm/lớp theo id, nên không đi trên graph. Commit và issue cũ vẫn nằm ở file riêng, chưa thành node của graph. Vì vậy phần tăng chắc chắn của đa nguồn vẫn đến từ tìm kiếm trên history.

**Kết luận về xếp hạng (v4-L8).** Trên 12 repo, thêm history giúp định vị tốt hơn chỉ dùng code ở mọi độ đo. Câu "đa nguồn nói chung tốt hơn chỉ dùng code" chưa được chứng minh. Với cách trộn đã chốt, đủ nguồn không tốt hơn AST ở Top@10, và kém hơn ở Top@1, MRR và MAP. DOC và ISSUE kéo kết quả xuống khi được trộn ngang hàng với AST. Theo phân tích judge, bằng chứng của DOC và ISSUE vẫn có thông tin hữu ích ở phần lớn instance. Phần lớn thông tin đó không phải vị trí code, nên RRF không dùng được, và độ đo xếp hạng không đo được. Sai lệch của snapshot chưa được đo.

---

## 7. Quyết định quan trọng

Danh sách đầy đủ ở mục 11 của `research_context.md` (quyết định 1 đến 60). Các quyết định định hướng:
- LLM không tham gia tạo xếp hạng.
- Mọi quyết định kỹ thuật phải có bài báo làm cơ sở.
- Không chia dữ liệu thành dev và test, train và test, hay đợt chính và đợt xác nhận, vì đề tài không huấn luyện model (27/10/2026).
- HIST xếp hạng theo Locus. Thiết kế `hist-llm` đã bỏ.
- Chủ đề là truy xuất ngữ cảnh. Agent dùng để kiểm chứng sau. Judge chấm các node output.
- Node doc, issue cũ và hunk là output, ghép theo loại.
- Dùng ngưỡng thay cho số lượng cố định.
- Giữ toàn bộ khung so sánh với AST và Q1 đến Q7.
- Cách trộn từng là RRF có trọng số theo nguồn, chọn bằng kiểm định chéo (22/10/2026). Từ 27/10/2026, cách trộn là RRF gốc với trọng số bằng nhau, và không tham số nào được chọn trên dữ liệu của đề tài.
- Liên kết Django chỉ dùng "Fixed #N". Mốc cắt của ISSUE là thời điểm tạo báo cáo của chính instance.
- Kết quả lặp lại được: hòa điểm xếp theo id, và các cell tự tính lại khi cấu hình hoặc cách tính đổi.
- Judge chỉ chấm bằng chứng, không viết lý do, và dùng thinking MINIMAL. Node code được đánh giá bằng gold và độ đo theo cấu trúc (26/10/2026).
- 10 repo còn lại của tập test là thêm dữ liệu cho cùng thực nghiệm (26/10 và 27/10/2026).
- Bảng độ phủ của `coverage_report.md` dùng để đo độ phủ doc ảnh hưởng thế nào tới hiệu quả. Repo có độ phủ thấp được giữ, và độ phủ được phân tích như một biến ở mức repo và mức instance. Nhóm repo có độ phủ từ 5% bị bỏ (28/10/2026).
- Notebook chỉ chứa code của pipeline. Phân tích một lần chạy ngoài notebook. Code của v3 đã bị bỏ (27/10/2026).
- Node sau hop được xếp theo công thức của KGCompass, với tham số lấy nguyên từ bài và code công khai. Nguồn GRAPH đi từ 10 node đầu của AST, và DOC dùng cùng công thức thay cho cách bỏ phiếu cũ (28/10/2026).

---

## 8. Việc còn mở

Danh sách ưu tiên đầy đủ nằm ở mục 14.15 và 14.16 của `planning.md`. Lượt Kaggle trên 12 repo, phép đo lại độ ổn định của judge trên mẫu 130 instance, lượt chạy `graph-proc` và phân tích độ phủ doc đã xong ở v4-L8.

1. Cách chọn ngưỡng ở ba vị trí. Cần tìm bài báo hoặc kỹ thuật liên quan.
2. Sửa cách nối doc với code. Tiêu chí cần chốt lại cho RRF gốc trước khi sửa.
3. Quyết định về thành phần Fix của HIST (có đổi A2, A3 hay không).
4. Quy tắc A7 bỏ sót tên lớp chỉ viết hoa chữ đầu.
5. Việc 1.3: kiểm tra snapshot trên 100 instance.
6. Request "đủ thông tin" (`#suff`).
7. Bỏ việc phụ thuộc vào `In` ở `manifest` và ở dấu cách tính của `issue-index`.
8. Viết lại dàn ý Chương 2 theo mục 2 của file này.
9. Đầu cao của khoảng độ phủ doc rất mỏng. Trên 12 repo, chỉ flask có độ phủ trên 20%, và flask có 11 instance. Có thể cần thêm repo phần train có độ phủ cao.
10. Phân tích ngoài notebook ở việc 8 của mục 14.16 trong `planning.md` chưa làm. Phân tích này báo l của gold đầu tiên trong GRAPH, và tỷ lệ instance có gold là ứng viên của GRAPH nhưng nằm ngoài 500 node đầu của AST.
11. Giả thuyết về G2 chưa được kiểm tra. GRAPH đi từ 10 node đầu của AST, nên thêm GRAPH có thể chỉ trả lại phần lá phiếu của AST mà DOC và ISSUE đã làm loãng.
12. Bảng kiểm định của `verify-v4` có hơn 20 cột, nên pandas ẩn các cột ở giữa. Notebook chưa được sửa ở chỗ này.
13. Đọc ba bài Faggioli và cộng sự (ICTIR 2023), Zou và cộng sự (TSE 2021), Järvelin và Kekäläinen (TOIS 2002) trước khi dẫn trong luận văn.

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
- KGCompass: https://arxiv.org/abs/2503.21710; code: https://github.com/GLEAM-Lab/KGCompass
- Zhu và Iglesias, IEEE TKDE 29(1), 2017: https://oa.upm.es/43462/1/TKDE2610428.pdf
- Ballatore, Bertolotto, Wilson, ISPRS IJGI 4(2), 2015: https://doi.org/10.3390/ijgi4020471
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
- Bruch, Gai, Ingber, An Analysis of Fusion Functions for Hybrid Retrieval, ACM TOIS 2023: https://arxiv.org/abs/2210.11934 (đọc phần chính qua bản HTML ngày 22/10/2026, chi tiết ở artifact tài liệu)
- Cuconasu và cộng sự, The Power of Noise: Redefining Retrieval for RAG Systems, SIGIR 2024 (chưa có link trong tài liệu hiện có)
- Faggioli và cộng sự, Perspectives on Large Language Models for Relevance Judgment, ICTIR 2023 (chưa đọc, chưa có link)
- Zou, Ghanbari, Xie, Zhang, An Empirical Study of Fault Localization Families and Their Combinations, IEEE TSE 2021 (chưa đọc, chưa có link)
- Järvelin và Kekäläinen, Cumulated Gain-Based Evaluation of IR Techniques, ACM TOIS 2002 (chưa đọc, chưa có link)
