# =============================================================================
# pipeline/dataset_loader.py — Tải và cache SWE-bench Lite dataset
#
# SWE-bench Lite là bộ 300 GitHub issues từ các Python repo phổ biến,
# mỗi issue có kèm patch (solution) đã được verify.
#
# Module này xử lý:
#   1. Tải dataset từ HuggingFace Hub (princeton-nlp/SWE-bench_Lite)
#   2. Parse unified diff patch để trích xuất ground-truth files
#   3. Cache kết quả ra JSON để không phải tải lại mỗi lần chạy
#
# Format mỗi instance sau khi xử lý:
#   {
#     "instance_id":        "astropy__astropy-12345",
#     "repo":               "astropy/astropy",
#     "base_commit":        "abc123...",
#     "problem_statement":  "Bug: ...",
#     "gt_files":           ["astropy/table/column.py", ...]
#   }
# =============================================================================

import json
import logging
from pathlib import Path

from datasets import load_dataset
from unidiff import PatchSet

import config

logger = logging.getLogger(__name__)


def parse_patch_for_gt_files(patch_str: str) -> list[str]:
    """
    Parse unified diff patch string và trả về danh sách file được sửa đổi.

    Đây là "ground truth" — file mà developer thực sự đã sửa để fix bug.
    Được dùng để đánh giá Precision/Recall của hệ thống file localization.

    Lưu ý:
      - File mới hoàn toàn (is_added_file=True) bị bỏ qua vì chúng không
        tồn tại tại base_commit, nên không thể có trong Knowledge Graph.
      - Patch thường chứa cả file test lẫn file source — ta lấy tất cả.
      - Dùng set để loại bỏ duplicate (đôi khi patch sửa cùng file nhiều lần).
    """
    gt_files = []
    if not patch_str:
        return gt_files

    try:
        patch = PatchSet(patch_str)
        for patched_file in patch:
            if patched_file.is_added_file:
                # File này không tồn tại tại base_commit — skip
                logger.warning(
                    f"File {patched_file.path} is a new file in the patch. "
                    "Skipped (không có trong base_commit graph)."
                )
                continue

            # source_file có prefix "a/" theo format git diff — cần strip
            gt_files.append(patched_file.source_file.lstrip("a/"))

    except Exception as e:
        logger.error(f"Failed to parse patch: {e}")

    return list(set(gt_files))  # deduplicate


def load_swe_bench_lite() -> list[dict]:
    """
    Tải toàn bộ SWE-bench Lite dataset từ HuggingFace và xử lý.

    Quá trình này cần kết nối internet và mất vài phút lần đầu.
    Kết quả được cache bằng save_cache() để dùng lại.

    Returns:
        list[dict]: danh sách instance, mỗi instance có gt_files đã parse.
    """
    logger.info(f"Loading dataset: {config.DATASET_NAME}")
    # split="test" — SWE-bench Lite chỉ có split "test" (300 instances)
    dataset = load_dataset(config.DATASET_NAME, split="test")

    instances = []
    for instance in dataset:
        gt_files = parse_patch_for_gt_files(instance["patch"])
        instances.append({
            "instance_id":       instance["instance_id"],
            "repo":              instance["repo"],
            "base_commit":       instance["base_commit"],
            "problem_statement": instance["problem_statement"],
            "gt_files":          gt_files,
        })

    return instances


def save_cache(instances: list[dict], cache_path: str) -> None:
    """
    Lưu danh sách instances ra file JSON cache.

    Thư mục cha được tạo tự động nếu chưa tồn tại.
    Dùng indent=2 để file dễ đọc khi debug thủ công.
    """
    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(instances, f, indent=2)
    logger.info(f"Saved {len(instances)} instances to {cache_path}")


def load_cache(cache_path: str) -> list[dict]:
    """
    Đọc cache JSON. Raise FileNotFoundError nếu chưa có cache.

    Caller (build_graph.py) bắt exception này để quyết định có tải mới không.
    """
    with open(cache_path, "r", encoding="utf-8") as f:
        return json.load(f)
