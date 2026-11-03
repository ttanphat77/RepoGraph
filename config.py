# =============================================================================
# config.py — Nguồn cấu hình duy nhất (Single Source of Truth)
#
# Secrets (API keys, passwords) được load từ .env — KHÔNG hardcode ở đây.
# Tạo file .env từ .env.example và điền giá trị thực.
# =============================================================================

import os

from dotenv import load_dotenv

load_dotenv()

# ── Dataset ───────────────────────────────────────────────────────────────────
# Tên dataset trên HuggingFace Hub — dùng để tải SWE-bench Lite
DATASET_NAME = "princeton-nlp/SWE-bench_Lite"

# Đường dẫn cache local để tránh tải lại dataset mỗi lần chạy
DATASET_CACHE = "cache/swebench_lite.json"

# ── Repo storage ──────────────────────────────────────────────────────────────
# Thư mục chứa các repo GitHub đã clone.
# Mỗi repo được lưu dưới tên: {org_repo}_{short_commit}/
REPOS_DIR = "repos"

# ── Graph schema ──────────────────────────────────────────────────────────────
# Chọn schema đồ thị bằng cách đặt giá trị này.
# Không cần sửa bất kỳ file nào khác trong pipeline.
#
#   "simple"   → Node: Module, Class, Function
#                Edge: Defines, Calls, Imports, Inherits
#                Phù hợp phân tích cấu trúc file-level, luồng gọi hàm.
#
#   "detailed" → Node: MODULE, CLASS, METHOD, FUNCTION, FIELD, GLOBAL_VARIABLE
#                Edge: CONTAINS, INHERITS, HAS_METHOD, HAS_FIELD, USES
#                Phân biệt method (trong class) vs function (module-level),
#                theo dõi class attributes và global variables.
ACTIVE_SCHEMA = "simple"

# ── AST parsing ───────────────────────────────────────────────────────────────
# Giới hạn số file được parse mỗi repo.
# 0 = không giới hạn (parse toàn bộ repo).
# Dùng giá trị nhỏ (vd: 50) để test nhanh trên repo lớn.
MAX_FILES_PARSED = 0

# Bật/tắt Louvain/Leiden community detection.
# Khi True, mỗi node được gán thuộc tính `community` (int) sau khi parse.
# Chậm trên repo có hàng nghìn node — tắt khi cần debug nhanh.
ENABLE_COMMUNITY_DETECTION = True

# Trọng số cạnh dùng cho thuật toán Leiden.
# Cạnh có trọng số cao hơn → tạo "lực kéo" mạnh hơn giữa hai node,
# khiến chúng có xu hướng nằm cùng community.
# Ví dụ: INHERITS (3.0) > Calls (2.0) > Imports (1.5) vì kế thừa
# thường thể hiện quan hệ kết hợp chặt hơn là gọi hàm hay import.
COMMUNITY_EDGE_WEIGHTS: dict[str, float] = {
    "INHERITS": 3.0,  # kế thừa — liên kết chặt nhất
    "Inherits": 3.0,
    "USES": 2.0,  # gọi hàm (schema detailed)
    "Calls": 2.0,  # gọi hàm (schema simple)
    "IMPORTS": 1.5,  # import module
    "Imports": 1.5,
    "HAS_METHOD": 1.0,  # class chứa method
    "Defines": 1.0,  # module/class định nghĩa entity
    "CONTAINS": 0.5,  # quan hệ bao hàm chung (lỏng nhất)
    "HAS_FIELD": 0.3,  # class chứa field (rất lỏng)
}

# ── Index đa nguồn ───────────────────────────────────────────────────────────
# Dữ liệu chấm điểm (embedding, history, issue) của mỗi repo nằm ở
# {INDEX_ROOT}/{tên thư mục repo}/. Graph (node, cạnh) nằm trong Neo4j.
# Đường dẫn tuyệt đối theo thư mục của file này, để lệnh chạy từ thư mục nào cũng tìm thấy index.
INDEX_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")

# ── Embedding (mục 2.1 pipeline_design.md) ────────────────────────────────────
# Function/Class: EMBED_CODE_CHARS ký tự đầu của source. DocChunk: heading + nội dung.
# Vector được chuẩn hóa, nên tích vô hướng là cosine.
EMBED_MODEL_ID   = "BAAI/bge-small-en-v1.5"
EMBED_CODE_CHARS = 2000
EMBED_BATCH      = 64
EMBED_FP16       = True   # chỉ có tác dụng khi có GPU (CUDA); CPU luôn chạy float32
EMBED_QUERY_CHARS = 2000  # query bỏ khối ``` rồi cắt ở đây (bge-small nhận tối đa 512 token)

# ── Xếp hạng (mục 4, 8 pipeline_design.md) ───────────────────────────────────
# RRF của Cormack, Clarke, Büttcher (SIGIR 2009): score = Σ 1/(RRF_K + hạng).
RRF_K      = 60
AST_DEPTH  = 500   # độ dài danh sách BM25, embedding và danh sách AST sau khi gộp

# ── History (mục 6, 6b pipeline_design.md) ───────────────────────────────────
HIST_YEARS     = 5     # commit nhánh chính trong HIST_YEARS năm trước HEAD
HIST_MAX_TOUCH = 50    # commit sửa quá nhiều hàm/lớp bị bỏ khỏi bằng chứng HIST (ROSE bỏ transaction > 30 thực thể)
LOCUS_LAMBDA   = 5     # Locus: α = min(1, λ·#tên code / #token của query)
LOCUS_BETA1    = 0.1   # Locus: trọng số của thành phần Fix
# Danh sách HIST trộn với AST ở phần Code: "locus" (đã đo ở v4-L8) hoặc "hist_msg"
# (thiết kế judge v5, chưa chạy trên Kaggle). Bằng chứng HIST luôn là commit của hist_msg.
HIST_RANK_SOURCE = "locus"
EVID_POOL_N    = 10    # số phần tử của pool mỗi loại bằng chứng (V4_EVID_N)

# ── ISSUE (mục 7 pipeline_design.md) ─────────────────────────────────────────
# Issue và PR đã đóng tải từ GitHub REST API. Có token: 5.000 lượt gọi mỗi giờ.
# Không có token: 60 lượt mỗi giờ; hết lượt thì dừng, lần build sau tải tiếp.
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# ── K(p): phần Thực thể được nhắc, caller/callee ─────────────────────────────
ENTITY_LIMIT   = 30   # số node trùng tên/đường dẫn trong prompt được giữ (như LIMIT của _find_seeds)
NEIGHBOR_LIMIT = 10   # số caller và số callee một bước kèm mỗi item Code

# ── K(p) đưa cho LLM ─────────────────────────────────────────────────────────
# Hạn ngạch cố định (mốc fixed-k của verify-v4, V4_EV_QUOTA) cho tới khi chọn được ngưỡng.
# Pool của mỗi loại vẫn giữ EVID_POOL_N phần tử trong bản ghi lần chạy.
CODE_N          = 10  # hàm/lớp đầu của danh sách trộn
FILE_N          = 5
ENTITY_SOURCE_N = 5   # thực thể (Function/Class) chưa có ở phần Code được kèm source
DOC_QUOTA       = 5
HIST_QUOTA      = 10
ISSUE_QUOTA     = 5

# ── Sinh câu trả lời ─────────────────────────────────────────────────────────
RUNS_DIRNAME = "runs"   # bản ghi lần chạy: {INDEX_ROOT}/{repo}/runs/

# ── BM25 fulltext search ──────────────────────────────────────────────────────
# Neo4j fulltext index (Lucene + BM25) dùng để tìm seed nodes từ issue text.
# Bao gồm label của cả hai schema (simple + detailed) — label không tồn tại
# trong DB sẽ bị bỏ qua tự động khi index.
FULLTEXT_INDEX_NAME = "node_text_bm25"

# Số node tối đa trả về từ BM25 query — đủ để bổ sung regex seeds,
# không nên quá lớn để tránh loãng context BFS.
BM25_SEED_LIMIT = 15

# ── LLM ──────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-3.5-flash"

# ── Neo4j ─────────────────────────────────────────────────────────────────────
# Kết nối Neo4j Community Edition chạy qua Docker (xem docker-compose.yml).
# Thay đổi nếu dùng Neo4j AuraDB hoặc instance khác.
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "graphrag123")

# Số node/edge ghi vào Neo4j mỗi batch MERGE.
# Tăng lên nếu mạng tốt và RAM đủ; giảm xuống nếu gặp timeout.
NEO4J_BATCH_SIZE = 500

# ── GitLab Triage Bot ────────────────────────────────────────────────────────
GITLAB_WEBHOOK_SECRET = os.getenv("GITLAB_WEBHOOK_SECRET", "")
GITLAB_BOT_PAT        = os.getenv("GITLAB_BOT_PAT", "")
GITLAB_BOT_USER_ID    = int(os.getenv("GITLAB_BOT_USER_ID", "0"))
GITLAB_API_URL        = os.getenv("GITLAB_API_URL", "https://gitlab.com/api/v4").rstrip("/")

# ── Validation ────────────────────────────────────────────────────────────────
# Kiểm tra ngay khi import config — fail fast nếu ACTIVE_SCHEMA sai chính tả.
# Không cần chờ đến lúc chạy pipeline mới phát hiện lỗi.
from pipeline.schemas import load_schema as _load_schema

_load_schema(ACTIVE_SCHEMA)
