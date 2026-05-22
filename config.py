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
