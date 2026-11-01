"""Controlled category codes (DATA_MODEL §5). Codes are immutable."""

CATEGORIES: dict[str, str] = {
    "food_drink": "Makanan & Minuman",
    "transport": "Transportasi",
    "groceries": "Belanja Kebutuhan",
    "bills": "Tagihan",
    "shopping": "Belanja Lainnya",
    "health": "Kesehatan",
    "entertainment": "Hiburan",
    "education": "Pendidikan",
    "other": "Lainnya",
}

PAYMENT_METHODS = (
    "cash", "qris", "bank_transfer", "debit_card",
    "credit_card", "e_wallet", "unknown",
)

TIMESTAMP_BASES = ("receipt", "user_explicit", "message_time")
SOURCE_TYPES = ("text", "voice", "receipt", "dashboard")


def is_valid_category(code: str) -> bool:
    return code in CATEGORIES


def label_for(code: str) -> str:
    return CATEGORIES.get(code, code)
