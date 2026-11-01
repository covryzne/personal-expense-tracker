import sys
from datetime import datetime
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from finance.config import Settings  # noqa: E402
from finance.models import TrustedEnvelope  # noqa: E402

WIB = ZoneInfo("Asia/Jakarta")
OWNER = UUID("11111111-2222-3333-4444-555555555555")
CHAT_ID = "chat-allowed-1"


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        supabase_url="https://example.supabase.co",
        owner_user_id=OWNER,
        allowed_chat_id=CHAT_ID,
        report_max_range_days=366,
    )


def make_envelope(message_id="msg-1", sent_at=None, chat_id=CHAT_ID,
                  source_type="text") -> TrustedEnvelope:
    return TrustedEnvelope(
        chat_id=chat_id,
        message_id=message_id,
        sent_at=sent_at or datetime(2026, 11, 2, 9, 0, tzinfo=WIB),
        source_type=source_type,
    )
