import logging

from fastapi import BackgroundTasks, FastAPI, Request

from bot import config as bot_config
from bot.triage import triage_issue

bot_config.validate()
BOT_USER_ID    = bot_config.BOT_USER_ID
WEBHOOK_SECRET = bot_config.WEBHOOK_SECRET

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger(__name__)

app = FastAPI()


@app.post("/webhook")
async def webhook(req: Request, bg: BackgroundTasks):
    if req.headers.get("X-Gitlab-Token") != WEBHOOK_SECRET:
        return {"ok": True}

    payload = await req.json()

    if payload.get("object_kind") != "issue":
        return {"ok": True}

    attrs = payload.get("object_attributes") or {}
    if attrs.get("action") != "open":
        return {"ok": True}

    user_id = (payload.get("user") or {}).get("id")
    if user_id == BOT_USER_ID:
        return {"ok": True}

    bg.add_task(triage_issue, payload)
    return {"ok": True}


@app.get("/health")
async def health():
    return {"ok": True}
