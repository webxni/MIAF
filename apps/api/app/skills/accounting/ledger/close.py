from __future__ import annotations


def build_monthly_close_checklist(context: dict) -> dict:
    checks = [
        "all_bank_imports_reviewed",
        "all_receipts_attached",
        "low_confidence_entries_resolved",
        "trial_balance_balanced",
        "ar_reviewed",
        "ap_reviewed",
        "bank_reconciliation_completed",
        "adjusting_entries_reviewed",
        "income_statement_generated",
        "balance_sheet_generated",
        "owner_draws_reviewed",
        "tax_reserve_reviewed",
        "reports_approved",
    ]

    items = [
        {"check": check, "status": "done" if context.get(check) else "pending"}
        for check in checks
    ]

    can_close = all(item["status"] == "done" for item in items)
    return {"items": items, "can_close": can_close}
