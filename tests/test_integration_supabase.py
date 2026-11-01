"""Live Supabase integration tests. Skipped unless FINANCE_INTEGRATION=1
AND migrations 0001-0003 have been applied to the project (Phase 1 gate).
"""
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("FINANCE_INTEGRATION") != "1",
    reason="live integration disabled (set FINANCE_INTEGRATION=1)",
)


def test_categories_seeded():
    from finance.config import load_settings
    from finance.gateway import SupabaseGateway

    settings = load_settings()
    gw = SupabaseGateway(settings.supabase_url)
    status, data = gw.request(
        "GET", "/rest/v1/expense_categories",
        params={"select": "code", "order": "code"},
    )
    assert status == 200
    assert len(data) == 9
