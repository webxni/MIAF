from __future__ import annotations


def build_simple_journal_entry(
    entity_id: str,
    date: str,
    description: str,
    debit_account_id: str,
    credit_account_id: str,
    amount: float,
    source_type: str | None = None,
    source_id: str | None = None,
) -> dict:
    return {
        "entity_id": entity_id,
        "date": date,
        "description": description,
        "source_type": source_type,
        "source_id": source_id,
        "status": "draft",
        "lines": [
            {"account_id": debit_account_id, "debit": amount, "credit": 0.0},
            {"account_id": credit_account_id, "debit": 0.0, "credit": amount},
        ],
    }


def build_invoice_issued_entry(
    entity_id: str,
    date: str,
    ar_account: str,
    revenue_account: str,
    amount: float,
    source_id: str,
) -> dict:
    return build_simple_journal_entry(
        entity_id, date, "Invoice issued", ar_account, revenue_account,
        amount, "invoice", source_id,
    )


def build_customer_payment_entry(
    entity_id: str,
    date: str,
    cash_account: str,
    ar_account: str,
    amount: float,
    source_id: str,
) -> dict:
    return build_simple_journal_entry(
        entity_id, date, "Customer payment received", cash_account, ar_account,
        amount, "payment", source_id,
    )


def build_owner_draw_entry(
    entity_id: str,
    date: str,
    owner_draw_account: str,
    cash_account: str,
    amount: float,
    source_id: str | None = None,
) -> dict:
    return build_simple_journal_entry(
        entity_id, date, "Owner draw", owner_draw_account, cash_account,
        amount, "owner_draw", source_id,
    )
