"""Supabase repository: the only module that talks to the database API.

Every query is filtered by the server-derived owner user_id (DATA_MODEL
§6: the secret key bypasses RLS, so these filters are the real guard).
No free-form SQL exists here; report aggregation is the static RPC from
migration 0003.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from .errors import NotFound, OutcomeUnknown, TemporarilyUnavailable
from .gateway import SupabaseGateway

REST = "/rest/v1"
COLUMNS = (
    "id,user_id,occurred_at,amount_idr,category_code,description,merchant,"
    "payment_method,source_type,source_platform,source_message_id,"
    "source_item_index,timestamp_basis,receipt_reference,created_at,"
    "updated_at,deleted_at"
)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_row(row: dict) -> dict:
    out = dict(row)
    for key in ("occurred_at", "created_at", "updated_at", "deleted_at"):
        val = out.get(key)
        if isinstance(val, str):
            out[key] = datetime.fromisoformat(val.replace("Z", "+00:00"))
    return out


class SupabaseRepository:
    def __init__(self, gateway: SupabaseGateway, owner_user_id: UUID):
        self._gw = gateway
        self._owner = str(owner_user_id)

    # -- create ---------------------------------------------------------
    def insert_expense(self, row: dict) -> tuple[dict, bool]:
        """Return (stored_row, created). Unique-key replay returns the
        previously stored row with created=False (TOOL_CONTRACT §5)."""
        payload = dict(row)
        payload["user_id"] = self._owner
        payload["occurred_at"] = _iso(payload["occurred_at"])
        status, data = self._gw.request(
            "POST", f"{REST}/expenses",
            json_body=payload,
            headers={"Prefer": "return=representation"},
            write=True,
        )
        if status in (200, 201) and isinstance(data, list) and data:
            return _parse_row(data[0]), True
        if status == 409:
            existing = self.fetch_by_source_key(
                payload["source_platform"],
                payload["source_message_id"],
                payload["source_item_index"],
            )
            if existing is not None:
                return existing, False
            raise OutcomeUnknown("conflict reported but row not found")
        if status >= 500:
            raise OutcomeUnknown(f"insert returned HTTP {status}")
        raise TemporarilyUnavailable(f"insert returned HTTP {status}: {data}")

    def fetch_by_source_key(
        self, platform: str, message_id: str, item_index: int
    ) -> dict | None:
        status, data = self._gw.request(
            "GET", f"{REST}/expenses",
            params={
                "select": COLUMNS,
                "user_id": f"eq.{self._owner}",
                "source_platform": f"eq.{platform}",
                "source_message_id": f"eq.{message_id}",
                "source_item_index": f"eq.{item_index}",
                "limit": "1",
            },
        )
        if status == 200 and isinstance(data, list) and data:
            return _parse_row(data[0])
        if status >= 400:
            raise TemporarilyUnavailable(f"lookup returned HTTP {status}")
        return None

    # -- read -----------------------------------------------------------
    def list_expenses(
        self,
        *,
        start_utc: datetime | None = None,
        end_utc: datetime | None = None,
        category_code: str | None = None,
        merchant_contains: str | None = None,
        limit: int = 10,
        include_deleted: bool = False,
    ) -> list[dict]:
        params = {
            "select": COLUMNS,
            "user_id": f"eq.{self._owner}",
            "order": "occurred_at.desc,id.desc",
            "limit": str(limit),
        }
        if not include_deleted:
            params["deleted_at"] = "is.null"
        occurred_filters = []
        if start_utc is not None:
            occurred_filters.append(f"gte.{_iso(start_utc)}")
        if end_utc is not None:
            occurred_filters.append(f"lt.{_iso(end_utc)}")
        if occurred_filters:
            # httpx repeats the key for list values; PostgREST ANDs them.
            params["occurred_at"] = occurred_filters
        if category_code:
            params["category_code"] = f"eq.{category_code}"
        if merchant_contains:
            params["merchant"] = f"ilike.*{merchant_contains}*"
        status, data = self._gw.request("GET", f"{REST}/expenses", params=params)
        if status != 200 or not isinstance(data, list):
            raise TemporarilyUnavailable(f"list returned HTTP {status}")
        return [_parse_row(r) for r in data]

    def get_expense(self, expense_id: str) -> dict | None:
        status, data = self._gw.request(
            "GET", f"{REST}/expenses",
            params={
                "select": COLUMNS,
                "user_id": f"eq.{self._owner}",
                "id": f"eq.{expense_id}",
                "limit": "1",
            },
        )
        if status == 200 and isinstance(data, list) and data:
            return _parse_row(data[0])
        if status >= 400:
            raise TemporarilyUnavailable(f"get returned HTTP {status}")
        return None

    # -- mutate ---------------------------------------------------------
    def update_expense(self, expense_id: str, patch: dict) -> dict:
        payload = dict(patch)
        if "occurred_at" in payload and isinstance(
            payload["occurred_at"], datetime
        ):
            payload["occurred_at"] = _iso(payload["occurred_at"])
        status, data = self._gw.request(
            "PATCH", f"{REST}/expenses",
            params={
                "user_id": f"eq.{self._owner}",
                "id": f"eq.{expense_id}",
                "deleted_at": "is.null",
            },
            json_body=payload,
            headers={"Prefer": "return=representation"},
            write=True,
        )
        if status == 200 and isinstance(data, list) and data:
            return _parse_row(data[0])
        if status == 200:
            raise NotFound("expense not found or already deleted")
        if status >= 500:
            raise OutcomeUnknown(f"update returned HTTP {status}")
        raise TemporarilyUnavailable(f"update returned HTTP {status}")

    def set_deleted(self, expense_id: str, deleted: bool) -> str:
        """Return 'changed' or 'already_in_state'; raise NotFound."""
        now = datetime.now(timezone.utc)
        if deleted:
            params = {"deleted_at": "is.null"}
            payload = {"deleted_at": _iso(now)}
        else:
            params = {"deleted_at": "not.is.null"}
            payload = {"deleted_at": None}
        params.update({"user_id": f"eq.{self._owner}", "id": f"eq.{expense_id}"})
        status, data = self._gw.request(
            "PATCH", f"{REST}/expenses",
            params=params, json_body=payload,
            headers={"Prefer": "return=representation"},
            write=True,
        )
        if status == 200 and isinstance(data, list) and data:
            return "changed"
        if status == 200:
            existing = self.get_expense(expense_id)
            if existing is None:
                raise NotFound("expense not found")
            if (existing.get("deleted_at") is not None) == deleted:
                return "already_in_state"
            raise OutcomeUnknown("delete/restore state unclear")
        if status >= 500:
            raise OutcomeUnknown(f"set_deleted returned HTTP {status}")
        raise TemporarilyUnavailable(f"set_deleted returned HTTP {status}")

    # -- report ---------------------------------------------------------
    def report(
        self,
        start_utc: datetime,
        end_utc: datetime,
        category_code: str | None = None,
    ) -> dict:
        status, data = self._gw.request(
            "POST", f"{REST}/rpc/expense_report",
            json_body={
                "p_user_id": self._owner,
                "p_start_utc": _iso(start_utc),
                "p_end_utc": _iso(end_utc),
                "p_category_code": category_code,
            },
        )
        if status == 200 and isinstance(data, dict):
            return data
        raise TemporarilyUnavailable(f"report RPC returned HTTP {status}")
