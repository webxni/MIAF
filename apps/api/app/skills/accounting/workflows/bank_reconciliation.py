from __future__ import annotations

import pandas as pd


def reconcile_bank_to_ledger(
    bank_transactions: list[dict],
    ledger_cash_entries: list[dict],
    tolerance: float = 0.01,
) -> dict:
    bank = pd.DataFrame(bank_transactions)
    ledger = pd.DataFrame(ledger_cash_entries)

    if bank.empty:
        return {"matched": [], "unmatched_bank": [], "unmatched_ledger": ledger_cash_entries}
    if ledger.empty:
        return {"matched": [], "unmatched_bank": bank_transactions, "unmatched_ledger": []}

    bank["amount"] = pd.to_numeric(bank["amount"], errors="coerce").fillna(0.0)
    ledger["amount"] = pd.to_numeric(ledger["amount"], errors="coerce").fillna(0.0)

    matched = []
    used_ledger: set[int] = set()

    for _, bank_row in bank.iterrows():
        candidates = ledger[
            (~ledger.index.isin(used_ledger))
            & ((ledger["amount"] - bank_row["amount"]).abs() <= tolerance)
        ]
        if not candidates.empty:
            ledger_idx = candidates.index[0]
            used_ledger.add(ledger_idx)
            matched.append({
                "bank_transaction": bank_row.to_dict(),
                "ledger_entry": ledger.loc[ledger_idx].to_dict(),
            })

    matched_bank_ids = [m["bank_transaction"].get("id") for m in matched]
    if "id" in bank.columns:
        unmatched_bank = bank[~bank["id"].isin(matched_bank_ids)].to_dict("records")
    else:
        unmatched_bank = []

    unmatched_ledger = ledger[~ledger.index.isin(used_ledger)].to_dict("records")

    return {
        "matched": matched,
        "unmatched_bank": unmatched_bank,
        "unmatched_ledger": unmatched_ledger,
    }
