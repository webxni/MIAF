from __future__ import annotations


def generate_accounting_question(record: dict, reason_codes: list[str]) -> dict:
    amount = record.get("amount")
    description = record.get("description") or record.get("merchant") or "this item"

    question = f"How should I classify {description} for {amount}?"

    if "personal_business_ambiguous" in reason_codes:
        question = f"Is {description} personal or business?"
    elif "owner_draw_possible" in reason_codes:
        question = (
            f"Is {description} an owner draw, payroll, reimbursement, loan, or something else?"
        )
    elif "asset_vs_expense" in reason_codes:
        question = f"Should {description} be expensed now or recorded as an asset?"

    return {
        "record_id": record.get("id"),
        "question": question,
        "reason_codes": reason_codes,
        "status": "open",
    }
