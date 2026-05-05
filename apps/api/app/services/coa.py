"""Default charts of accounts for personal and business modes.

Hierarchy is expressed via parent codes. Codes follow the standard 1xxx
(assets), 2xxx (liabilities), 3xxx (equity), 4xxx (income/revenue),
5xxx/6xxx (expenses) convention.

Editable per entity after seeding — these are starting points, not contracts.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models import AccountType, EntityMode


@dataclass(frozen=True)
class CoaNode:
    code: str
    name: str
    type: AccountType
    parent_code: str | None = None
    description: str | None = None


PERSONAL_COA: tuple[CoaNode, ...] = (
    # Assets
    CoaNode("1000", "Assets", AccountType.asset),
    CoaNode("1100", "Cash & Equivalents", AccountType.asset, parent_code="1000"),
    CoaNode("1110", "Checking", AccountType.asset, parent_code="1100"),
    CoaNode("1120", "Savings", AccountType.asset, parent_code="1100"),
    CoaNode("1130", "Emergency Fund", AccountType.asset, parent_code="1100"),
    CoaNode("1200", "Investments", AccountType.asset, parent_code="1000"),
    CoaNode("1300", "Other Assets", AccountType.asset, parent_code="1000"),
    # Liabilities
    CoaNode("2000", "Liabilities", AccountType.liability),
    CoaNode("2100", "Credit Cards", AccountType.liability, parent_code="2000"),
    CoaNode("2200", "Loans", AccountType.liability, parent_code="2000"),
    # Equity
    CoaNode("3000", "Equity", AccountType.equity),
    CoaNode("3100", "Net Worth (Opening)", AccountType.equity, parent_code="3000"),
    # Income
    CoaNode("4000", "Income", AccountType.income),
    CoaNode("4100", "Salary", AccountType.income, parent_code="4000"),
    CoaNode("4200", "Owner Draws Received", AccountType.income, parent_code="4000",
            description="Distributions from your business shown as personal income."),
    CoaNode("4300", "Investment Income", AccountType.income, parent_code="4000"),
    CoaNode("4900", "Other Income", AccountType.income, parent_code="4000"),
    # Expenses
    CoaNode("5000", "Expenses", AccountType.expense),
    CoaNode("5100", "Housing", AccountType.expense, parent_code="5000"),
    CoaNode("5200", "Food & Dining", AccountType.expense, parent_code="5000"),
    CoaNode("5300", "Transportation", AccountType.expense, parent_code="5000"),
    CoaNode("5400", "Utilities", AccountType.expense, parent_code="5000"),
    CoaNode("5500", "Health", AccountType.expense, parent_code="5000"),
    CoaNode("5600", "Entertainment", AccountType.expense, parent_code="5000"),
    CoaNode("5700", "Personal Care", AccountType.expense, parent_code="5000"),
    CoaNode("5900", "Other Expenses", AccountType.expense, parent_code="5000"),
)

BUSINESS_COA: tuple[CoaNode, ...] = (
    # Assets
    CoaNode("1000", "Assets", AccountType.asset),
    CoaNode("1100", "Cash", AccountType.asset, parent_code="1000"),
    CoaNode("1110", "Operating Bank", AccountType.asset, parent_code="1100"),
    CoaNode("1200", "Accounts Receivable", AccountType.asset, parent_code="1000"),
    CoaNode("1300", "Inventory", AccountType.asset, parent_code="1000"),
    CoaNode("1400", "Fixed Assets", AccountType.asset, parent_code="1000"),
    # Liabilities
    CoaNode("2000", "Liabilities", AccountType.liability),
    CoaNode("2100", "Accounts Payable", AccountType.liability, parent_code="2000"),
    CoaNode("2200", "Tax Reserve", AccountType.liability, parent_code="2000",
            description="Set aside for taxes; jurisdiction-aware."),
    CoaNode("2300", "Loans Payable", AccountType.liability, parent_code="2000"),
    # Equity
    CoaNode("3000", "Equity", AccountType.equity),
    CoaNode("3100", "Owner Equity", AccountType.equity, parent_code="3000"),
    CoaNode("3200", "Owner Contributions", AccountType.equity, parent_code="3000"),
    CoaNode("3300", "Owner Draws", AccountType.equity, parent_code="3000",
            description="Contra-equity. Posted via owner-draw flow."),
    CoaNode("3400", "Retained Earnings", AccountType.equity, parent_code="3000"),
    # Revenue
    CoaNode("4000", "Revenue", AccountType.income),
    CoaNode("4100", "Sales", AccountType.income, parent_code="4000"),
    CoaNode("4200", "Service Revenue", AccountType.income, parent_code="4000"),
    CoaNode("4900", "Other Revenue", AccountType.income, parent_code="4000"),
    # COGS
    CoaNode("5000", "Cost of Goods Sold", AccountType.expense),
    CoaNode("5100", "COGS", AccountType.expense, parent_code="5000"),
    # Operating Expenses
    CoaNode("6000", "Operating Expenses", AccountType.expense),
    CoaNode("6100", "Rent", AccountType.expense, parent_code="6000"),
    CoaNode("6200", "Utilities", AccountType.expense, parent_code="6000"),
    CoaNode("6300", "Internet & Phone", AccountType.expense, parent_code="6000"),
    CoaNode("6400", "Salaries & Wages", AccountType.expense, parent_code="6000"),
    CoaNode("6500", "Office Supplies", AccountType.expense, parent_code="6000"),
    CoaNode("6600", "Professional Services", AccountType.expense, parent_code="6000"),
    CoaNode("6700", "Bank Fees", AccountType.expense, parent_code="6000"),
    CoaNode("6900", "Other Expenses", AccountType.expense, parent_code="6000"),
)


def coa_for_mode(mode: EntityMode) -> tuple[CoaNode, ...]:
    return PERSONAL_COA if mode == EntityMode.personal else BUSINESS_COA
