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
    """
    return get_source_files(repo_path, (".py",))


def get_source_files(repo_path: str, extensions: tuple[str, ...]) -> list[str]:
    """
    Liệt kê file có extension trong extensions, trả về đường dẫn tương đối.

    Dùng `git ls-files` nếu repo_path là git repo (tự động lọc theo .gitignore).
    Fallback về os.walk (bỏ qua .git/) nếu không phải git repo.
    """
    import subprocess
    base_path = Path(repo_path)

    try:
        out = subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=str(base_path),
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return [
            line
            for line in out.splitlines()
            if any(line.endswith(ext) for ext in extensions)
        ]
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # fallback: không phải git repo
    result = []
    for root, _, files in os.walk(base_path):
        if ".git" in root:
            continue
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                full_path = Path(root) / file
                result.append(str(full_path.relative_to(base_path)).replace("\\", "/"))
    return result


def _inject_token(url: str, token: str) -> str:
    """Inject oauth2 token vào HTTPS URL để clone private repo."""
    if url.startswith("https://"):
        return url.replace("https://", f"https://oauth2:{token}@", 1)
    return url


def clone_from_url(url: str, branch: str | None = None, token: str | None = None) -> str:
    """
    Clone repo từ bất kỳ git URL nào. Idempotent.

    Args:
        url:    Git URL (https hoặc ssh), vd: https://github.com/org/repo.git
        branch: Tên branch cụ thể, hoặc None để dùng default branch
        token:  Access token cho private repo (HTTPS only)

    Returns:
        Đường dẫn tuyệt đối đến thư mục repo đã clone.
    """
    # Tạo tên thư mục từ URL — bỏ .git suffix, thay ký tự đặc biệt bằng _
    repo_slug = url.rstrip("/").rstrip(".git").split("/")[-1]
    branch_suffix = f"_{branch}" if branch else ""
    repo_path = os.path.join(config.REPOS_DIR, f"{repo_slug}{branch_suffix}")
    path = Path(repo_path)

    if path.exists() and (path / ".git").exists():
        logger.info(f"Repository already exists at {repo_path}. Skipping clone.")
        return repo_path

    if path.exists():
        shutil.rmtree(path)

    clone_url = _inject_token(url, token) if token else url
    logger.info(f"Cloning {url} into {repo_path}...")
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        kwargs = {}
        if branch:
            kwargs["branch"] = branch
        Repo.clone_from(clone_url, repo_path, **kwargs)
        logger.info(f"Successfully cloned {url}")
    except Exception as e:
        logger.error(f"Failed to clone {url}: {e}")
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
        raise

    return repo_path
