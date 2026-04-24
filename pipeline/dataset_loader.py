import json
import logging
from pathlib import Path
from datasets import load_dataset
from unidiff import PatchSet
import config

logger = logging.getLogger(__name__)

def parse_patch_for_gt_files(patch_str: str) -> list[str]:
    """Parse the unidiff patch string to find modified files (ground truth)."""
    gt_files = []
    if not patch_str:
        return gt_files
        
    try:
        patch = PatchSet(patch_str)
        for patched_file in patch:
            # We care about files that are modified, not test files typically,
            # but usually SWE-Bench patch includes the test and the solution.
            # Usually we just take the target file we want to modify.
            # If it's a new file, it wasn't in the base commit.
            if patched_file.is_added_file:
                logger.warning(f"File {patched_file.path} is a new file in the patch. It will be skipped for base_commit matching.")
                continue
            
            # Record the source file path (the file that was modified)
            gt_files.append(patched_file.source_file.lstrip('a/'))
            
    except Exception as e:
        logger.error(f"Failed to parse patch: {e}")
        
    return list(set(gt_files))

def load_swe_bench_lite() -> list[dict]:
    """Load SWE-bench Lite dataset and extract ground truth files."""
    logger.info(f"Loading dataset: {config.DATASET_NAME}")
    dataset = load_dataset(config.DATASET_NAME, split="test")

    instances = []
    for instance in dataset:
        gt_files = parse_patch_for_gt_files(instance["patch"])
        instances.append({
            "instance_id": instance["instance_id"],
            "repo": instance["repo"],
            "base_commit": instance["base_commit"],
            "problem_statement": instance["problem_statement"],
            "gt_files": gt_files
        })

    return instances

def save_cache(instances: list[dict], cache_path: str):
    """Save the loaded instances to JSON cache."""
    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(instances, f, indent=2)
    logger.info(f"Saved {len(instances)} instances to {cache_path}")

def load_cache(cache_path: str) -> list[dict]:
    """Load instances from JSON cache."""
    with open(cache_path, "r", encoding="utf-8") as f:
        return json.load(f)
