"""Bot config — reads from root config.py (single .env source)."""

import config as _root

WEBHOOK_SECRET = _root.GITLAB_WEBHOOK_SECRET
BOT_PAT        = _root.GITLAB_BOT_PAT
BOT_USER_ID    = _root.GITLAB_BOT_USER_ID
GITLAB_API_URL = _root.GITLAB_API_URL


def validate() -> None:
    missing = [
        name for name, val in [
            ("GITLAB_WEBHOOK_SECRET", WEBHOOK_SECRET),
            ("GITLAB_BOT_PAT",        BOT_PAT),
            ("GITLAB_BOT_USER_ID",    BOT_USER_ID),
        ] if not val
    ]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")
