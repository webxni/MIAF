from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def money(value: float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def validate_journal_entry(entry: dict) -> dict:
    lines = entry.get("lines", [])
    errors: list[str] = []
    warnings: list[str] = []

    if len(lines) < 2:
        errors.append("A journal entry must have at least two lines.")

    total_debits = Decimal("0.00")
    total_credits = Decimal("0.00")

    for index, line in enumerate(lines):
        debit = money(line.get("debit", 0))
        credit = money(line.get("credit", 0))

        total_debits += debit
        total_credits += credit

        if not line.get("account_id"):
            errors.append(f"Line {index + 1} is missing account_id.")
        if debit < 0 or credit < 0:
            errors.append(f"Line {index + 1} cannot have negative debit or credit.")
        if debit > 0 and credit > 0:
            errors.append(f"Line {index + 1} cannot have both debit and credit.")
        if debit == 0 and credit == 0:
            errors.append(f"Line {index + 1} must have debit or credit.")

    if total_debits != total_credits:
        errors.append(
            f"Entry is not balanced. Debits {total_debits} do not equal credits {total_credits}."
        )

    return {
        "valid": not errors,
        "total_debits": float(total_debits),
        "total_credits": float(total_credits),
        "errors": errors,
        "warnings": warnings,
    }
