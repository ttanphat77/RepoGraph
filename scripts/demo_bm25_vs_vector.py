import os
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# 1. Tập dữ liệu giả lập (3 hàm)
# Hàm 1: Đoạn code BẨN, thực tế chứa bug. Có mã lỗi "ERR_VIP_TX_INVALID".
CODE_1_DIRTY = """
def process(*args, **kwargs):
    req = args[0]
    if req.get("typ") == "vip":
        tx = req["tx_id"]
        # complex logic...
        if not db.verify(tx):
            raise Exception("ERR_VIP_TX_INVALID")
    return True
"""

# Hàm 2: Đoạn code SẠCH, đẹp, có docstring, CÙNG NGỮ NGHĨA với query nhưng KHÔNG CHỨA BUG.
CODE_2_CLEAN = """
def cancel_vip_subscription(user_id: int) -> bool:
    '''
    Cancels a VIP subscription order for the user.
    Use this if there is a bug or error in the VIP processing system.
    '''
    user = db.get_user(user_id)
    user.is_vip = False
    user.save()
    return True
"""

# Hàm 3: Hàm bình thường không liên quan.
CODE_3_RANDOM = """
def calculate_tax(amount: float) -> float:
    return amount * 0.08
"""

documents = [CODE_1_DIRTY, CODE_2_CLEAN, CODE_3_RANDOM]
doc_names = ["Hàm 1 (Code Bẩn - Chứa Bug thật)", "Hàm 2 (Code Sạch - Mồi nhử ngữ nghĩa)", "Hàm 3 (Hàm rác)"]

# 2. Câu hỏi của User (Từ 1 issue trên Github)
# Nó mô tả ngữ nghĩa (Semantic) lẫn từ khóa (Keyword)
QUERY = "There is a bug when processing VIP orders. It throws ERR_VIP_TX_INVALID."

print("==================================================")
print(f"User Query (Issue): '{QUERY}'")
print("==================================================\n")

# --- LUỒNG 1: BM25 (KEYWORD SEARCH) ---
print("--- KẾT QUẢ BM25 (TÌM KIẾM TỪ KHÓA) ---")
# Tokenize đơn giản (cắt theo khoảng trắng)
tokenized_corpus = [doc.lower().split() for doc in documents]
bm25 = BM25Okapi(tokenized_corpus)
tokenized_query = QUERY.lower().split()
bm25_scores = bm25.get_scores(tokenized_query)

for i, score in enumerate(bm25_scores):
    print(f"{doc_names[i]}: Điểm = {score:.4f}")
print("=> BM25 đã đưa Hàm 1 lên Top 1 vì nó bắt dính mã lỗi 'ERR_VIP_TX_INVALID'.\n")

# --- LUỒNG 2: VECTOR SEARCH (SEMANTIC SEARCH) ---
print("--- KẾT QUẢ VECTOR SEARCH (sentence-transformers) ---")
print("Đang load model (all-MiniLM-L6-v2)...")
# Tắt cảnh báo symlinks trên windows
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
model = SentenceTransformer('all-MiniLM-L6-v2')

# Nhúng dữ liệu
doc_embeddings = model.encode(documents)
query_embedding = model.encode([QUERY])

# Tính Cosine Similarity
cosine_scores = cosine_similarity(query_embedding, doc_embeddings)[0]

for i, score in enumerate(cosine_scores):
    print(f"{doc_names[i]}: Độ tương đồng = {score:.4f}")

print("\n=> VECTOR SEARCH đã BỊ LỪA! Nó chấm Hàm 2 (Code Sạch) cao hơn Hàm 1 (Code Bẩn)!")
print("   Lý do: Hàm 2 có docstring tự nhiên chứa các từ khóa 'VIP', 'bug', 'error', 'processing' rất giống với câu Query.")
print("   Trong khi đó, Hàm 1 viết quá tắt (req.get('typ') == 'vip'), Vector Model không hiểu được ý nghĩa ngữ nghĩa của nó.")
print("==================================================")
