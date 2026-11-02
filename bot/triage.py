import asyncio
import logging

from bot import gitlab_client
from pipeline.evaluator import run_prompt

log = logging.getLogger(__name__)

FOOTER = (
    "\n\n---\n"
    "_🤖 RepoGraph triage bot (Phase 1). React 👎 if incorrect._"
)


def _run_pipeline(text: str) -> dict:
    """Một lần prompting trên K(p) của index build gần nhất; bản ghi lần chạy nằm ở runs/."""
    rec, run_dir = run_prompt(text)
    llm = rec.get("llm") or {}
    return {"answer": (run_dir / "answer.md").read_text(encoding="utf-8"),
            "finish_reason": llm.get("finish_reason"), "run_id": rec["run"]["run_id"]}


async def triage_issue(payload: dict) -> None:
    attrs = payload["object_attributes"]
    pid   = payload["project"]["id"]
    iid   = attrs["iid"]
    title = attrs.get("title") or ""
    desc  = attrs.get("description") or ""
    text  = f"{title}\n\n{desc}".strip()

    try:
        result = await asyncio.to_thread(_run_pipeline, text)
        answer = result.get("answer", "")
        if not answer or result.get("finish_reason") == "ERROR":
            raise RuntimeError(f"LLM finish_reason={result.get('finish_reason')}")
        await gitlab_client.add_comment(pid, iid, answer + FOOTER)
        log.info("triaged project=%s iid=%s run=%s", pid, iid, result.get("run_id"))
    except Exception:
        log.exception("triage failed project=%s iid=%s", pid, iid)
        try:
            await gitlab_client.add_comment(
                pid, iid,
                "Bot lỗi tạm thời, vui lòng triage thủ công." + FOOTER,
            )
        except Exception:
            log.exception("fallback comment failed project=%s iid=%s", pid, iid)
