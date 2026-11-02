"""
scripts/ask.py — Hỏi một lần trên repo đã build (giai đoạn 1 của app)

    .venv\\Scripts\\python.exe scripts/ask.py "url_for raises BuildError when ..."
    .venv\\Scripts\\python.exe scripts/ask.py "..." --index cache/flask --json

Luồng: truy hồi K(p) (code, doc, history, issue) → một lần gọi Gemini → in câu trả lời,
bảng item RAG của từng phần, một dòng số liệu và đường dẫn tới bản ghi lần chạy.
--json in toàn bộ bản ghi thay cho phần hiển thị.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass

from rich.console import Console
from rich.markdown import Markdown

from pipeline.evaluator import run_prompt
from tui.kp_render import kp_tables, metrics_line


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    for noisy in ("httpx", "huggingface_hub", "sentence_transformers", "google_genai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    p = argparse.ArgumentParser(description="Ask one question over a built repository index")
    p.add_argument("prompt", help="Issue, question, or request about the repository")
    p.add_argument("--index", default=None, help="Index directory (default: the most recently built one)")
    p.add_argument("--json", action="store_true", help="Print the full run record as JSON")
    args = p.parse_args()

    console = Console()
    if args.json:
        rec, run_dir = run_prompt(args.prompt, index_dir=args.index)
        print(json.dumps(rec, ensure_ascii=False, indent=1, default=str))
        return
    with console.status("Retrieving context and generating the answer..."):
        rec, run_dir = run_prompt(args.prompt, index_dir=args.index)
    console.rule("Answer")
    console.print(Markdown((run_dir / "answer.md").read_text(encoding="utf-8") or "_(no answer)_"))
    console.rule("Retrieved context K(p)")
    for t in kp_tables(rec.get("retrieval") or {}):
        console.print(t)
    for w in rec["warnings"]:
        console.print(f"[yellow]warning:[/] {w}")
    console.rule()
    console.print(metrics_line(rec, run_dir), markup=False, highlight=False)


if __name__ == "__main__":
    main()
