import httpx

from bot.config import BOT_PAT, GITLAB_API_URL

_HEADERS = {"PRIVATE-TOKEN": BOT_PAT}


async def add_comment(project_id: int, iid: int, body: str) -> None:
    url = f"{GITLAB_API_URL}/projects/{project_id}/issues/{iid}/notes"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=_HEADERS, json={"body": body})
        r.raise_for_status()
