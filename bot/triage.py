import asyncio
import logging

from bot import gitlab_client
from pipeline import generator
from pipeline.retriever import GraphRetriever

log = logging.getLogger(__name__)

FOOTER = (
    "\n\n---\n"
    "_🤖 RepoGraph triage bot (Phase 1). React 👎 if incorrect._"
)


def _run_pipeline(text: str) -> dict:
    retriever = GraphRetriever()
    try:
        ctx = retriever.retrieve(text, depth=2)
    finally:
        retriever.close()
    return generator.generate(text, ctx.get("context", ""))


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
        log.info("triaged project=%s iid=%s", pid, iid)
    except Exception:
        log.exception("triage failed project=%s iid=%s", pid, iid)
        try:
            await gitlab_client.add_comment(
                pid, iid,
                "Bot lỗi tạm thời, vui lòng triage thủ công." + FOOTER,
            )
        except Exception:
            log.exception("fallback comment failed project=%s iid=%s", pid, iid)
