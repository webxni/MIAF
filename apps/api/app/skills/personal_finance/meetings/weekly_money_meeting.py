from __future__ import annotations


def build_weekly_money_meeting_agenda(context: dict) -> dict:
    agenda = [
        "Review income and expenses",
        "Review transactions needing classification",
        "Review budget progress",
        "Review savings and emergency fund",
        "Review upcoming bills",
        "Choose one improvement for next week",
    ]

    if context.get("has_business"):
        agenda.insert(2, "Review business cashflow and owner draws")

    if context.get("has_debt"):
        agenda.append("Review debt payoff progress")

    if context.get("has_open_questions"):
        agenda.insert(0, "Resolve open accounting questions")

    return {"agenda": agenda}
