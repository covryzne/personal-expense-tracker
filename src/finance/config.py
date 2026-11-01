"""Server-side configuration. Non-secret values come from the project
.env (or process environment). The Supabase secret key is NEVER read
here: authenticated calls go through the Muse Secure Vault connector
(custom.supabase) via gateway.py.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from .errors import FinanceError

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    owner_user_id: UUID
    allowed_chat_id: str
    timezone: str = "Asia/Jakarta"
    report_max_range_days: int = 366

    @property
    def supabase_host(self) -> str:
        return self.supabase_url.replace("https://", "").rstrip("/")


def load_settings(env_path: Path | None = None) -> Settings:
    file_values = _load_env_file(env_path or (PROJECT_ROOT / ".env"))

    def get(key: str) -> str:
        return os.environ.get(key) or file_values.get(key, "")

    url = get("SUPABASE_URL")
    owner = get("FINANCE_OWNER_USER_ID")
    chat_id = get("ALLOWED_WHATSAPP_CHAT_ID")
    missing = [
        name for name, val in (
            ("SUPABASE_URL", url),
            ("FINANCE_OWNER_USER_ID", owner),
            ("ALLOWED_WHATSAPP_CHAT_ID", chat_id),
        ) if not val
    ]
    if missing:
        raise FinanceError(f"missing configuration: {', '.join(missing)}")
    try:
        owner_uuid = UUID(owner)
    except ValueError as exc:
        raise FinanceError("FINANCE_OWNER_USER_ID is not a UUID") from exc
    return Settings(
        supabase_url=url,
        owner_user_id=owner_uuid,
        allowed_chat_id=chat_id,
        timezone=get("APP_TIMEZONE") or "Asia/Jakarta",
        report_max_range_days=int(get("REPORT_MAX_RANGE_DAYS") or 366),
    )
