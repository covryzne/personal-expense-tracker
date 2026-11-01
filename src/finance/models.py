"""Typed tool-call models (TOOL_CONTRACT §2, §4-§9).

Security invariant: no model here accepts a `user_id`. Ownership is
injected by the service from server-side configuration only. All models
forbid unknown fields so model output cannot smuggle extra keys.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .categories import CATEGORIES, PAYMENT_METHODS, TIMESTAMP_BASES

PaymentMethod = Literal[
    "cash", "qris", "bank_transfer", "debit_card",
    "credit_card", "e_wallet", "unknown",
]
TimestampBasis = Literal["receipt", "user_explicit", "message_time"]
SourceType = Literal["text", "voice", "receipt", "dashboard"]
Period = Literal[
    "today", "yesterday", "this_week", "last_week",
    "this_month", "last_month", "custom",
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TrustedEnvelope(_Strict):
    """Transport facts built by the adapter, never by the LLM."""

    chat_id: str = Field(min_length=1, max_length=128)
    message_id: str = Field(min_length=1, max_length=255)
    sent_at: datetime
    modality: Literal["text", "voice", "image"] = "text"
    source_type: SourceType = "text"

    @field_validator("sent_at")
    @classmethod
    def _aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("sent_at must be timezone-aware")
        return v


class ExpenseCandidate(_Strict):
    source_item_index: int = Field(ge=0)
    amount_idr: int = Field(gt=0)
    category_code: str
    description: str = Field(min_length=1, max_length=500)
    merchant: Optional[str] = Field(default=None, max_length=200)
    payment_method: PaymentMethod = "unknown"
    occurred_at: datetime
    timestamp_basis: TimestampBasis = "message_time"
    receipt_reference: Optional[str] = Field(default=None, max_length=200)

    @field_validator("category_code")
    @classmethod
    def _category(cls, v: str) -> str:
        if v not in CATEGORIES:
            raise ValueError(f"unknown category_code: {v}")
        return v

    @field_validator("occurred_at")
    @classmethod
    def _aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        return v


class CreateExpensesRequest(_Strict):
    source_platform: Literal["whatsapp", "dashboard"] = "whatsapp"
    source_message_id: str = Field(min_length=1, max_length=255)
    expenses: list[ExpenseCandidate] = Field(min_length=1, max_length=50)

    @field_validator("expenses")
    @classmethod
    def _unique_indexes(cls, v: list[ExpenseCandidate]):
        idx = [e.source_item_index for e in v]
        if len(idx) != len(set(idx)):
            raise ValueError("source_item_index values must be unique")
        return v


class ExpensePatch(_Strict):
    """Allowlisted mutable fields (TOOL_CONTRACT §7)."""

    amount_idr: Optional[int] = Field(default=None, gt=0)
    category_code: Optional[str] = None
    description: Optional[str] = Field(default=None, min_length=1, max_length=500)
    merchant: Optional[str] = Field(default=None, max_length=200)
    payment_method: Optional[PaymentMethod] = None
    occurred_at: Optional[datetime] = None
    timestamp_basis: Optional[TimestampBasis] = None

    @field_validator("category_code")
    @classmethod
    def _category(cls, v):
        if v is not None and v not in CATEGORIES:
            raise ValueError(f"unknown category_code: {v}")
        return v

    def to_update_dict(self) -> dict:
        return self.model_dump(exclude_none=True, mode="json")


class ListExpensesFilter(_Strict):
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    category_code: Optional[str] = None
    merchant_contains: Optional[str] = Field(default=None, max_length=200)
    limit: int = Field(default=10, ge=1, le=50)

    @field_validator("category_code")
    @classmethod
    def _category(cls, v):
        if v is not None and v not in CATEGORIES:
            raise ValueError(f"unknown category_code: {v}")
        return v


class ReportRequest(_Strict):
    period: Period = "this_month"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    category_code: Optional[str] = None

    @field_validator("category_code")
    @classmethod
    def _category(cls, v):
        if v is not None and v not in CATEGORIES:
            raise ValueError(f"unknown category_code: {v}")
        return v
