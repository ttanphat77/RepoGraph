import os
import shutil
import logging
from pathlib import Path
from git import Repo
import config

logger = logging.getLogger(__name__)

def get_repo_path(repo_name: str, base_commit: str) -> str:
    """Get the local path for a cloned repository at a specific commit."""
    safe_repo_name = repo_name.replace("/", "_")
    short_commit = base_commit[:8] if base_commit and base_commit != "latest" else "latest"
    return os.path.join(config.REPOS_DIR, f"{safe_repo_name}_{short_commit}")

def clone_and_checkout(repo_name: str, base_commit: str) -> str:
    """
    Clone a GitHub repository and checkout a specific commit.
    Skips if the directory already exists.
    Returns the path to the cloned repository.
    """
    repo_path = get_repo_path(repo_name, base_commit)
    path = Path(repo_path)
    
    if path.exists() and path.is_dir():
        # Quick validation that it's a git repo
        if (path / ".git").exists():
            logger.info(f"Repository already exists at {repo_path}. Skipping clone.")
            return repo_path
        else:
            logger.warning(f"Path {repo_path} exists but is not a valid git repository. Recreating...")
            shutil.rmtree(path)
            
    # Need to clone
    url = f"https://github.com/{repo_name}.git"
    logger.info(f"Cloning {url} into {repo_path}...")
    
    path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        if base_commit and base_commit != "latest":
            # Clone with no checkout, then checkout the exact commit
            repo = Repo.clone_from(url, repo_path, no_checkout=True)
            logger.info(f"Checking out commit {base_commit}...")
            repo.git.checkout(base_commit)
            logger.info(f"Successfully cloned and checked out {repo_name} at {base_commit}")
        else:
            # Clone normally (latest master/main)
            repo = Repo.clone_from(url, repo_path)
            logger.info(f"Successfully cloned {repo_name} (latest branch)")
    except Exception as e:
        logger.error(f"Failed to clone or checkout repository: {e}")
        # Clean up failed clone
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
        raise
        
    return repo_path

def get_python_files(repo_path: str) -> list[str]:
    """Get a list of all .py files in the repository."""
    py_files = []
    base_path = Path(repo_path)
    # Walk through all files in the directory
    for root, _, files in os.walk(base_path):
        # Skip hidden directories like .git
        if '.git' in root:
            continue
            
        for file in files:
            if file.endswith('.py'):
                # Get path relative to the repo root
                full_path = Path(root) / file
                rel_path = full_path.relative_to(base_path)
                py_files.append(str(rel_path).replace("\\", "/"))
                
    return py_files
