"""CLI adapter: the agent runs one command per WhatsApp turn and reads
the JSON envelope from stdout (docs/ADAPTER.md).

Usage:
  python -m finance.cli --chat-id <id> --message-id <id> \
      [--sent-at <iso>] <command> --payload '<json>'

Commands: create | list | update | delete | restore | report
Payload JSON per command:
  create  -> CreateExpensesRequest (source_message_id must equal
             --message-id; add "derived_key": true for post-clarification)
  list    -> ListExpensesFilter
  update  -> {"expense_id": "...", "patch": {...}}
  delete/restore -> {"expense_id": "..."}
  report  -> ReportRequest
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from . import service
from .config import load_settings
from .gateway import SupabaseGateway
from .models import (
    CreateExpensesRequest,
    ListExpensesFilter,
    ReportRequest,
    TrustedEnvelope,
    ExpensePatch,
)
from .repository import SupabaseRepository

WIB = ZoneInfo("Asia/Jakarta")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="finance.cli")
    parser.add_argument("--chat-id", required=True)
    parser.add_argument("--message-id", required=True)
    parser.add_argument("--sent-at", default=None)
    parser.add_argument("--modality", default="text")
    parser.add_argument("--source-type", default="text")
    parser.add_argument("command")
    parser.add_argument("--payload", default="{}")
    args = parser.parse_args(argv)

    settings = load_settings()
    sent_at = (
        datetime.fromisoformat(args.sent_at)
        if args.sent_at
        else datetime.now(WIB)
    )
    envelope = TrustedEnvelope(
        chat_id=args.chat_id,
        message_id=args.message_id,
        sent_at=sent_at,
        modality=args.modality,
        source_type=args.source_type,
    )
    gateway = SupabaseGateway(settings.supabase_url)
    repo = SupabaseRepository(gateway, settings.owner_user_id)
    payload = json.loads(args.payload)

    if args.command == "create":
        derived = bool(payload.pop("derived_key", False))
        result = service.create_expenses(
            settings, repo, envelope,
            CreateExpensesRequest(**payload), derived_key=derived,
        )
    elif args.command == "list":
        result = service.list_expenses(
            settings, repo, envelope, ListExpensesFilter(**payload)
        )
    elif args.command == "update":
        result = service.update_expense(
            settings, repo, envelope,
            payload["expense_id"], ExpensePatch(**payload["patch"]),
        )
    elif args.command == "delete":
        result = service.delete_expense(
            settings, repo, envelope, payload["expense_id"]
        )
    elif args.command == "restore":
        result = service.restore_expense(
            settings, repo, envelope, payload["expense_id"]
        )
    elif args.command == "report":
        result = service.get_report(
            settings, repo, envelope, ReportRequest(**payload)
        )
    else:
        result = {
            "ok": False, "status": "validation_error", "data": {},
            "error": {"code": "validation_error",
                      "message": f"unknown command {args.command}",
                      "retryable": False},
        }
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
