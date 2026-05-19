# =============================================================================
# pipeline/repo_manager.py — Clone và quản lý GitHub repositories
#
# Module này xử lý:
#   1. Tính toán đường dẫn local cho repo tại một commit cụ thể
#   2. Clone repo từ GitHub (bỏ qua nếu đã tồn tại — idempotent)
#   3. Checkout đúng commit để đồng bộ với SWE-bench base_commit
#   4. Liệt kê tất cả file .py trong repo (bỏ qua .git/)
#
# Idempotency:
#   clone_and_checkout() kiểm tra thư mục trước khi clone.
#   Nếu repo đã tồn tại và là git repo hợp lệ → bỏ qua clone.
#   Điều này cho phép chạy lại pipeline mà không tốn thời gian clone lại.
# =============================================================================

import os
import shutil
import logging
from pathlib import Path

from git import Repo

import config

logger = logging.getLogger(__name__)


def get_repo_path(repo_name: str, base_commit: str) -> str:
    """
    Tính đường dẫn local cho một repo tại một commit cụ thể.

    Format thư mục: {REPOS_DIR}/{org}_{repo}_{short_commit}/
    Ví dụ: repos/astropy_astropy_abc12345/

    Lý do dùng 8 ký tự đầu của commit: đủ unique, tên thư mục không quá dài.
    "latest" được giữ nguyên khi clone HEAD của default branch.
    """
    # Thay '/' bằng '_' để tránh tạo nested directory vô ý
    safe_repo_name = repo_name.replace("/", "_")
    short_commit = (
        base_commit[:8]
        if base_commit and base_commit != "latest"
        else "latest"
    )
    return os.path.join(config.REPOS_DIR, f"{safe_repo_name}_{short_commit}")


def clone_and_checkout(repo_name: str, base_commit: str) -> str:
    """
    Clone repo từ GitHub và checkout đúng commit. Idempotent.

    Args:
        repo_name:   Tên repo dạng "org/repo" (vd: "astropy/astropy")
        base_commit: Commit hash đầy đủ hoặc "latest" (HEAD)

    Returns:
        Đường dẫn tuyệt đối đến thư mục repo đã clone.

    Raises:
        Exception: Nếu clone hoặc checkout thất bại (thư mục lỗi bị xóa).
    """
    repo_path = get_repo_path(repo_name, base_commit)
    path = Path(repo_path)

    # ── Kiểm tra xem repo đã tồn tại chưa ────────────────────────────────────
    if path.exists() and path.is_dir():
        if (path / ".git").exists():
            # Repo hợp lệ đã có — bỏ qua clone để tiết kiệm thời gian
            logger.info(f"Repository already exists at {repo_path}. Skipping clone.")
            return repo_path
        else:
            # Thư mục tồn tại nhưng không phải git repo → xóa và clone lại
            logger.warning(f"Path {repo_path} exists but is not a valid git repo. Recreating...")
            shutil.rmtree(path)

    # ── Clone từ GitHub ───────────────────────────────────────────────────────
    url = f"https://github.com/{repo_name}.git"
    logger.info(f"Cloning {url} into {repo_path}...")
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if base_commit and base_commit != "latest":
            # no_checkout=True: clone nhanh hơn, tránh checkout HEAD rồi
            # phải checkout lại commit cụ thể (tiết kiệm thời gian với repo lớn).
            repo = Repo.clone_from(url, repo_path, no_checkout=True)
            logger.info(f"Checking out commit {base_commit}...")
            repo.git.checkout(base_commit)
            logger.info(f"Successfully cloned and checked out {repo_name} at {base_commit}")
        else:
            # Clone HEAD của default branch (main/master)
            repo = Repo.clone_from(url, repo_path)
            logger.info(f"Successfully cloned {repo_name} (latest branch)")

    except Exception as e:
        logger.error(f"Failed to clone or checkout repository: {e}")
        # Xóa thư mục dở dang để lần chạy sau không bị nhầm là hợp lệ
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
        raise

    return repo_path


def get_python_files(repo_path: str) -> list[str]:
    """
    Liệt kê tất cả file .py trong repo, trả về đường dẫn tương đối.

    Bỏ qua thư mục .git/ để không parse metadata của git.
    Đường dẫn dùng '/' thay '\\' ngay cả trên Windows để nhất quán
    với module_id format trong pipeline.

    Returns:
        list[str]: đường dẫn relative, vd: ["django/db/models.py", ...]
    """
    py_files = []
    base_path = Path(repo_path)

    for root, _, files in os.walk(base_path):
        # Bỏ qua thư mục .git — chứa binary objects, không phải source code
        if ".git" in root:
            continue

        for file in files:
            if file.endswith(".py"):
                full_path = Path(root) / file
                # Chuyển về relative path so với root repo
                rel_path = full_path.relative_to(base_path)
                # Normalize separator để nhất quán trên mọi OS
                py_files.append(str(rel_path).replace("\\", "/"))

    return py_files
