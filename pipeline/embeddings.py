# =============================================================================
# pipeline/embeddings.py - Embedding cho Function, Class và DocChunk
#
# Thiết kế: mục 2.1 pipeline_design.md.
#   - Model: config.EMBED_MODEL_ID (bge-small-en-v1.5), vector chuẩn hóa.
#   - Function/Class: config.EMBED_CODE_CHARS ký tự đầu của source
#     (source rỗng → "label name"). DocChunk: heading + "\n" + nội dung.
#   - Module và Document không có embedding.
#
# Cache theo nội dung: khóa là sha1(model + text). Khi repo đổi, chỉ node có
# văn bản đổi mới phải encode lại. Cache nằm ở {index_dir}/embed_cache.*.
#
# Output cho bước truy hồi: {index_dir}/node_vectors.npy (float32, N×dim) và
# {index_dir}/node_ids.json (id của từng hàng).
# =============================================================================

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path

import numpy as np

import config

logger = logging.getLogger(__name__)

EMBED_LABELS = ("Function", "Class", "DocChunk")

_MODEL = None  # (model, device, dtype) nạp một lần cho mỗi tiến trình


def embed_text(node: dict) -> str:
    """Văn bản đem đi embed của một node (format {"labels", "id", "properties"})."""
    label = node["labels"][0]
    p = node["properties"]
    if label == "DocChunk":
        return f"{p['heading']}\n{p['text']}" if p.get("heading") else p.get("text", "")
    src = p.get("source") or ""
    return src[:config.EMBED_CODE_CHARS] if src else f"{label} {p.get('name', '')}"


def _get_model():
    """Nạp model một lần. GPU có CUDA → float16 nếu EMBED_FP16, CPU → float32."""
    global _MODEL
    if _MODEL is None:
        import torch
        from sentence_transformers import SentenceTransformer
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = SentenceTransformer(config.EMBED_MODEL_ID, device=device)
        dtype = "float32"
        if device == "cuda" and config.EMBED_FP16:
            model = model.half()
            dtype = "float16"
        _MODEL = (model, device, dtype)
    return _MODEL


def _key(text: str) -> str:
    return hashlib.sha1(f"{config.EMBED_MODEL_ID}\n{text}".encode("utf-8")).hexdigest()


def _save_npy(path: Path, arr: np.ndarray) -> None:
    np.save(path, arr)


def _save_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


class EmbeddingCache:
    """Cache vector theo sha1(model + text), lưu trên đĩa ở index_dir."""

    def __init__(self, index_dir: Path):
        self.keys_path = index_dir / "embed_cache_keys.json"
        self.vecs_path = index_dir / "embed_cache.npy"
        self.meta_path = index_dir / "embed_cache_meta.json"
        self.keys: list[str] = []
        self.vecs = np.zeros((0, 0), dtype=np.float32)
        # Thiết bị/kiểu số đã từng encode vào cache, vd "cpu/float32". GPU float16 và CPU
        # float32 cho vector hơi khác nhau, nên cần biết cache được tạo bằng cách nào.
        self.encoders: set[str] = set()
        if self.keys_path.exists() and self.vecs_path.exists():
            self.keys = json.loads(self.keys_path.read_text(encoding="utf-8"))
            self.vecs = np.load(self.vecs_path)
            if len(self.keys) != len(self.vecs):  # hai file lệch nhau → bỏ cache
                logger.warning("Embedding cache is inconsistent, ignoring it.")
                self.keys, self.vecs = [], np.zeros((0, 0), dtype=np.float32)
            elif self.meta_path.exists():
                self.encoders = set(json.loads(self.meta_path.read_text(encoding="utf-8"))["encoders"])
        self.row = {k: i for i, k in enumerate(self.keys)}

    def encode(self, texts: list[str]) -> tuple[np.ndarray, int]:
        """Trả (ma trận vector theo thứ tự texts, số văn bản phải encode mới)."""
        keys = [_key(t) for t in texts]
        miss = list(dict.fromkeys(k for k in keys if k not in self.row))
        if miss:
            model, device, dtype = _get_model()
            self.encoders.add(f"{device}/{dtype}")
            text_of = dict(zip(keys, texts))
            new = model.encode([text_of[k] for k in miss], batch_size=config.EMBED_BATCH,
                               normalize_embeddings=True, convert_to_numpy=True,
                               show_progress_bar=len(miss) > 200).astype(np.float32)
            base = len(self.keys)
            if base and self.vecs.shape[1] != new.shape[1]:
                # Cache cũ của một model có số chiều khác: không dòng nào dùng lại được → bỏ
                logger.warning("Embedding cache has another vector size, rebuilding it.")
                self.keys, self.row, self.encoders = [], {}, {f"{device}/{dtype}"}
                base = 0
            self.vecs = new if base == 0 else np.vstack([self.vecs, new])
            self.keys += miss
            self.row.update({k: base + j for j, k in enumerate(miss)})
        out = self.vecs[[self.row[k] for k in keys]] if keys else np.zeros((0, 0), dtype=np.float32)
        return out, len(miss)

    def save(self) -> None:
        _save_npy(self.vecs_path, self.vecs)
        _save_json(self.keys_path, self.keys)
        _save_json(self.meta_path, {"encoders": sorted(self.encoders)})


def embed_nodes(nodes: list[dict], index_dir: str | Path) -> dict:
    """
    Embed mọi Function, Class và DocChunk trong nodes, ghi node_vectors.npy và node_ids.json.

    Returns:
        stats: model, encoders (thiết bị/kiểu số đã tạo các vector trong cache), dim,
        n (số node có embedding), encoded (số văn bản phải encode mới), reused, seconds.
    """
    index_dir = Path(index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    targets = [n for n in nodes if n["labels"][0] in EMBED_LABELS]
    cache = EmbeddingCache(index_dir)
    vecs, n_new = cache.encode([embed_text(n) for n in targets])
    cache.save()
    _save_npy(index_dir / "node_vectors.npy", vecs)
    _save_json(index_dir / "node_ids.json", [n["id"] for n in targets])

    return {
        "model": config.EMBED_MODEL_ID,
        "encoders": sorted(cache.encoders),
        "dim": int(vecs.shape[1]) if len(vecs) else 0,
        "n": len(targets),
        "encoded": n_new,
        "reused": len(targets) - n_new,
        "seconds": round(time.perf_counter() - t0, 1),
    }
