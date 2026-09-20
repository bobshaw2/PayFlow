from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation

import numpy as np

REQUIRED_COLUMNS = ("transaction_id", "amount", "currency", "date")
COLUMNS = ["transaction_id", "merchant_amount", "provider_amount", "currency", "date", "status", "note"]


class ReconciliationError(ValueError):
    """Raised when incoming transaction data cannot be reconciled."""


def _validate(rows: list[dict[str, str]], source: str) -> list[dict[str, str]]:
    clean_rows = []
    for row_number, row in enumerate(rows, start=2):
        transaction_id = (row.get("transaction_id") or "").strip()
        if not transaction_id:
            raise ReconciliationError(f"{source} row {row_number}: transaction_id cannot be blank.")
        try:
            amount = Decimal((row.get("amount") or "").strip())
        except (InvalidOperation, ValueError):
            raise ReconciliationError(f"{source} row {row_number}: amount must be a number.")
        currency = (row.get("currency") or "").strip().upper()
        date = (row.get("date") or "").strip()
        if not currency or not date:
            raise ReconciliationError(f"{source} row {row_number}: currency and date are required.")
        clean_rows.append({"transaction_id": transaction_id, "amount": amount, "currency": currency, "date": date})
    return clean_rows


def _money(value: Decimal | None) -> str:
    return "" if value is None else f"{value:.2f}"


def reconcile(merchant_rows: list[dict[str, str]], provider_rows: list[dict[str, str]]) -> dict:
    """Compare two CSV row collections by transaction ID using simulated data only."""
    merchant = _validate(merchant_rows, "Merchant")
    provider = _validate(provider_rows, "Payment-provider")
    merchant_counts = Counter(row["transaction_id"] for row in merchant)
    provider_counts = Counter(row["transaction_id"] for row in provider)
    merchant_by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    provider_by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in merchant:
        merchant_by_id[row["transaction_id"]].append(row)
    for row in provider:
        provider_by_id[row["transaction_id"]].append(row)

    report = []
    all_ids = sorted(set(merchant_by_id) | set(provider_by_id))
    for transaction_id in all_ids:
        merchant_matches = merchant_by_id.get(transaction_id, [])
        provider_matches = provider_by_id.get(transaction_id, [])
        m = merchant_matches[0] if merchant_matches else None
        p = provider_matches[0] if provider_matches else None
        if merchant_counts[transaction_id] > 1 or provider_counts[transaction_id] > 1:
            status, note = "Duplicate", "ID appears more than once in one or both files"
        elif not m:
            status, note = "Missing merchant", "Found only in payment-provider file"
        elif not p:
            status, note = "Missing provider", "Found only in merchant file"
        elif m["amount"] != p["amount"]:
            status, note = "Amount mismatch", "Amounts differ between files"
        elif m["currency"] != p["currency"]:
            status, note = "Currency mismatch", "Currencies differ between files"
        else:
            status, note = "Matched", "Transaction reconciled"
        base = m or p
        report.append({
            "transaction_id": transaction_id,
            "merchant_amount": _money(m["amount"] if m else None),
            "provider_amount": _money(p["amount"] if p else None),
            "currency": base["currency"], "date": base["date"], "status": status, "note": note,
        })

    statuses = [row["status"] for row in report]
    amounts = np.array([float(row["amount"]) for row in merchant], dtype=float)
    summary = {
        "merchant_count": len(merchant), "provider_count": len(provider), "matched": statuses.count("Matched"),
        "issues": len(report) - statuses.count("Matched"), "duplicates": statuses.count("Duplicate"),
        "merchant_total": float(np.sum(amounts)),
    }
    return {"transactions": report, "summary": summary, "columns": COLUMNS}
