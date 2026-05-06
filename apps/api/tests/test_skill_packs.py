"""
Tests for the three built-in skill packs:
- python_finance
- accounting
- personal_finance
"""
from __future__ import annotations

import pytest


# ─────────────────────────── Python Finance Pack ──────────────────────────────

class TestDataframes:
    def test_clean_financial_records_happy_path(self):
        from app.skills.python_finance.core.dataframes import clean_financial_records

        records = [
            {"date": "2024-01-15", "amount": "$1,200.00"},
            {"date": "2024-01-20", "amount": "500"},
        ]
        df = clean_financial_records(records)
        assert len(df) == 2
        assert list(df.columns).count("date") == 1

    def test_clean_financial_records_empty(self):
        from app.skills.python_finance.core.dataframes import clean_financial_records

        df = clean_financial_records([])
        assert df.empty

    def test_dataframe_to_records_replaces_nan(self):
        import numpy as np
        from app.skills.python_finance.core.dataframes import dataframe_to_records, to_dataframe

        records = [{"amount": float("nan")}, {"amount": 100.0}]
        df = to_dataframe(records)
        out = dataframe_to_records(df)
        assert out[0]["amount"] is None
        assert out[1]["amount"] == 100.0


class TestProfiling:
    def test_profile_records_basic(self):
        from app.skills.python_finance.analytics.profiling import profile_records

        records = [
            {"date": "2024-01-01", "amount": 100},
            {"date": "2024-01-02", "amount": 200},
        ]
        result = profile_records(records)
        assert result["row_count"] == 2
        assert "amount_distribution" in result
        assert result["amount_distribution"]["min"] == 100.0

    def test_profile_records_empty(self):
        from app.skills.python_finance.analytics.profiling import profile_records

        result = profile_records([])
        assert result["row_count"] == 0
        assert "No records." in result["warnings"]


class TestTimeSeries:
    def test_analyze_time_series_monthly(self):
        from app.skills.python_finance.analytics.time_series import analyze_time_series

        observations = [
            {"date": "2024-01-15", "value": 1000},
            {"date": "2024-02-10", "value": 1200},
            {"date": "2024-03-05", "value": 900},
        ]
        result = analyze_time_series(observations, frequency="ME")
        assert "series" in result
        assert "summary" in result
        assert result["summary"]["periods"] >= 1

    def test_analyze_time_series_empty(self):
        from app.skills.python_finance.analytics.time_series import analyze_time_series

        result = analyze_time_series([])
        assert result["series"] == []
        assert "No valid time series data." in result["warnings"]


class TestReturns:
    def test_calculate_returns_basic(self):
        from app.skills.python_finance.analytics.returns import calculate_returns

        observations = [
            {"date": "2024-01-01", "value": 1000},
            {"date": "2024-02-01", "value": 1100},
            {"date": "2024-03-01", "value": 1050},
        ]
        result = calculate_returns(observations)
        assert "summary" in result
        assert "cumulative_return" in result["summary"]
        assert abs(result["summary"]["cumulative_return"] - 0.05) < 0.001

    def test_calculate_returns_needs_two_observations(self):
        from app.skills.python_finance.analytics.returns import calculate_returns

        result = calculate_returns([{"date": "2024-01-01", "value": 1000}])
        assert "Need at least two observations." in result["warnings"]


class TestRollingStatistics:
    def test_rolling_statistics_basic(self):
        from app.skills.python_finance.analytics.rolling import calculate_rolling_statistics

        observations = [{"date": f"2024-01-{i:02d}", "value": float(i * 100)} for i in range(1, 15)]
        result = calculate_rolling_statistics(observations, window=5)
        assert "series" in result
        assert result["window"] == 5

    def test_rolling_statistics_empty(self):
        from app.skills.python_finance.analytics.rolling import calculate_rolling_statistics

        result = calculate_rolling_statistics([])
        assert result["series"] == []


class TestRiskMetrics:
    def test_risk_metrics_basic(self):
        from app.skills.python_finance.analytics.risk import calculate_risk_metrics

        returns = [0.01, -0.02, 0.03, -0.01, 0.02, 0.00, -0.03, 0.04, -0.015, 0.025]
        result = calculate_risk_metrics(returns)
        assert "mean_return" in result
        assert "max_drawdown" in result
        assert result["max_drawdown"] <= 0.0
        assert "limitations" in result

    def test_risk_metrics_empty(self):
        from app.skills.python_finance.analytics.risk import calculate_risk_metrics

        result = calculate_risk_metrics([])
        assert "warnings" in result


class TestPortfolioAllocation:
    def test_portfolio_allocation_basic(self):
        from app.skills.python_finance.analytics.portfolio import calculate_portfolio_allocation

        holdings = [
            {"asset_class": "equity", "market_value": 6000},
            {"asset_class": "bonds", "market_value": 3000},
            {"asset_class": "cash", "market_value": 1000},
        ]
        result = calculate_portfolio_allocation(holdings)
        assert abs(result["total_market_value"] - 10000) < 0.01
        assert len(result["allocation"]) == 3
        assert "safety_note" in result

    def test_portfolio_allocation_with_target(self):
        from app.skills.python_finance.analytics.portfolio import calculate_portfolio_allocation

        holdings = [{"asset_class": "equity", "market_value": 8000}, {"asset_class": "bonds", "market_value": 2000}]
        target = {"equity": 0.7, "bonds": 0.3}
        result = calculate_portfolio_allocation(holdings, target_allocation=target)
        assert len(result["target_drift"]) == 2

    def test_portfolio_allocation_empty(self):
        from app.skills.python_finance.analytics.portfolio import calculate_portfolio_allocation

        result = calculate_portfolio_allocation([])
        assert result["allocation"] == []


class TestMonteCarlo:
    def test_monte_carlo_goal(self):
        from app.skills.python_finance.analytics.monte_carlo import simulate_goal_balance

        result = simulate_goal_balance(
            starting_balance=5000,
            monthly_contribution=200,
            months=12,
            goal_amount=7000,
        )
        assert "ending_balance_percentiles" in result
        assert "success_probability" in result
        assert 0.0 <= result["success_probability"] <= 1.0
        assert "limitations" in result

    def test_monte_carlo_invalid_months(self):
        from app.skills.python_finance.analytics.monte_carlo import simulate_goal_balance

        with pytest.raises(ValueError, match="months must be positive"):
            simulate_goal_balance(starting_balance=1000, monthly_contribution=100, months=0)


class TestAnomalyDetection:
    def test_anomaly_detection_flags_outlier(self):
        from app.skills.python_finance.analytics.anomalies import detect_amount_anomalies

        records = [
            {"category": "food", "amount": 50},
            {"category": "food", "amount": 52},
            {"category": "food", "amount": 51},
            {"category": "food", "amount": 49},
            {"category": "food", "amount": 53},
            {"category": "food", "amount": 50},
            {"category": "food", "amount": 2000},
        ]
        result = detect_amount_anomalies(records, z_threshold=2.0)
        assert len(result["anomalies"]) >= 1

    def test_anomaly_detection_empty(self):
        from app.skills.python_finance.analytics.anomalies import detect_amount_anomalies

        result = detect_amount_anomalies([])
        assert result["anomalies"] == []


class TestChartData:
    def test_line_chart(self):
        from app.skills.python_finance.visualization.chart_data import generate_chart

        rows = [{"period": "2024-01", "value": 1000}]
        chart = generate_chart("line", "Cashflow", rows)
        assert chart["type"] == "line"
        assert chart["title"] == "Cashflow"
        assert chart["data"] == rows

    def test_bar_chart(self):
        from app.skills.python_finance.visualization.chart_data import generate_chart

        rows = [{"period": "2024-01", "value": 500}]
        chart = generate_chart("bar", "Expenses", rows)
        assert chart["type"] == "bar"

    def test_pie_chart(self):
        from app.skills.python_finance.visualization.chart_data import generate_chart

        rows = [{"label": "Rent", "value": 1000}]
        chart = generate_chart("pie", "Spending", rows, label_key="label", value_key="value")
        assert chart["type"] == "pie"

    def test_unknown_chart_type_raises(self):
        from app.skills.python_finance.visualization.chart_data import generate_chart

        with pytest.raises(ValueError):
            generate_chart("radar", "Bad", [])


# ─────────────────────────── Accounting Pack ─────────────────────────────────

class TestJournalEntryValidator:
    def test_balanced_entry_valid(self):
        from app.skills.accounting.core.validators import validate_journal_entry

        entry = {
            "lines": [
                {"account_id": "acc-1", "debit": 1000, "credit": 0},
                {"account_id": "acc-2", "debit": 0, "credit": 1000},
            ]
        }
        result = validate_journal_entry(entry)
        assert result["valid"] is True
        assert result["errors"] == []

    def test_unbalanced_entry_rejected(self):
        from app.skills.accounting.core.validators import validate_journal_entry

        entry = {
            "lines": [
                {"account_id": "acc-1", "debit": 1000, "credit": 0},
                {"account_id": "acc-2", "debit": 0, "credit": 900},
            ]
        }
        result = validate_journal_entry(entry)
        assert result["valid"] is False
        assert any("not balanced" in e for e in result["errors"])

    def test_debit_and_credit_same_line_rejected(self):
        from app.skills.accounting.core.validators import validate_journal_entry

        entry = {
            "lines": [
                {"account_id": "acc-1", "debit": 1000, "credit": 1000},
                {"account_id": "acc-2", "debit": 0, "credit": 0},
            ]
        }
        result = validate_journal_entry(entry)
        assert result["valid"] is False

    def test_single_line_rejected(self):
        from app.skills.accounting.core.validators import validate_journal_entry

        entry = {"lines": [{"account_id": "acc-1", "debit": 500, "credit": 0}]}
        result = validate_journal_entry(entry)
        assert result["valid"] is False


class TestNormalBalances:
    def test_asset_normal_debit(self):
        from app.skills.accounting.core.normal_balances import NORMAL_BALANCE

        assert NORMAL_BALANCE["asset"] == "debit"

    def test_liability_normal_credit(self):
        from app.skills.accounting.core.normal_balances import NORMAL_BALANCE

        assert NORMAL_BALANCE["liability"] == "credit"

    def test_account_effect_increase(self):
        from app.skills.accounting.core.normal_balances import account_effect

        assert account_effect("asset", 100, 0) == "increase"
        assert account_effect("liability", 0, 100) == "increase"

    def test_signed_balance(self):
        from app.skills.accounting.core.normal_balances import signed_balance

        assert signed_balance("asset", 1000, 0) == 1000.0
        assert signed_balance("liability", 0, 500) == 500.0


class TestTrialBalance:
    def test_trial_balance_balanced(self):
        from app.skills.accounting.ledger.trial_balance import generate_trial_balance

        journal_lines = [
            {"account_id": "a1", "debit": 1000.0, "credit": 0.0, "date": "2024-01-01"},
            {"account_id": "a2", "debit": 0.0, "credit": 1000.0, "date": "2024-01-01"},
        ]
        accounts = [
            {"id": "a1", "code": "1100", "name": "Cash", "type": "asset"},
            {"id": "a2", "code": "4000", "name": "Revenue", "type": "income"},
        ]
        result = generate_trial_balance(journal_lines, accounts)
        assert result["balanced"] is True
        assert result["total_debits"] == result["total_credits"]

    def test_trial_balance_empty(self):
        from app.skills.accounting.ledger.trial_balance import generate_trial_balance

        result = generate_trial_balance([], [])
        assert result["balanced"] is True
        assert result["total_debits"] == 0.0


class TestIncomeStatement:
    def test_income_statement_net_income(self):
        from app.skills.accounting.ledger.financial_statements import generate_income_statement

        journal_lines = [
            {"account_id": "a1", "debit": 0.0, "credit": 5000.0},
            {"account_id": "a2", "debit": 2000.0, "credit": 0.0},
        ]
        accounts = [
            {"id": "a1", "name": "Revenue", "type": "income"},
            {"id": "a2", "name": "Rent", "type": "expense"},
        ]
        result = generate_income_statement(journal_lines, accounts)
        assert result["revenue"] == 5000.0
        assert result["expenses"] == 2000.0
        assert result["net_income"] == 3000.0

    def test_income_statement_empty(self):
        from app.skills.accounting.ledger.financial_statements import generate_income_statement

        result = generate_income_statement([], [])
        assert result["net_income"] == 0.0


class TestBalanceSheet:
    def test_balance_sheet_equation(self):
        from app.skills.accounting.ledger.financial_statements import generate_balance_sheet

        journal_lines = [
            {"account_id": "a1", "debit": 10000.0, "credit": 0.0},
            {"account_id": "a2", "debit": 0.0, "credit": 6000.0},
            {"account_id": "a3", "debit": 0.0, "credit": 4000.0},
        ]
        accounts = [
            {"id": "a1", "name": "Cash", "type": "asset"},
            {"id": "a2", "name": "Loan", "type": "liability"},
            {"id": "a3", "name": "Owner Equity", "type": "equity"},
        ]
        result = generate_balance_sheet(journal_lines, accounts)
        assert result["balanced"] is True
        assert result["difference"] == 0.0


class TestArAging:
    def test_ar_aging_buckets(self):
        from app.skills.accounting.workflows.ar import calculate_ar_aging

        invoices = [
            {"due_date": "2024-03-01", "open_amount": 1000},
            {"due_date": "2024-01-01", "open_amount": 500},
        ]
        result = calculate_ar_aging(invoices, "2024-03-31")
        assert "buckets" in result
        assert len(result["rows"]) == 2

    def test_ar_aging_empty(self):
        from app.skills.accounting.workflows.ar import calculate_ar_aging

        result = calculate_ar_aging([], "2024-03-31")
        assert result["buckets"] == {}


class TestApAging:
    def test_ap_aging_buckets(self):
        from app.skills.accounting.workflows.ap import calculate_ap_aging

        bills = [{"due_date": "2024-02-15", "open_amount": 800}]
        result = calculate_ap_aging(bills, "2024-03-31")
        assert "1_30" in result["buckets"] or "31_60" in result["buckets"] or "61_90" in result["buckets"]


class TestBankReconciliation:
    def test_bank_reconciliation_matches(self):
        from app.skills.accounting.workflows.bank_reconciliation import reconcile_bank_to_ledger

        bank = [{"id": "b1", "amount": 500.0}]
        ledger = [{"id": "l1", "amount": 500.0}]
        result = reconcile_bank_to_ledger(bank, ledger)
        assert len(result["matched"]) == 1
        assert result["unmatched_bank"] == []

    def test_bank_reconciliation_unmatched(self):
        from app.skills.accounting.workflows.bank_reconciliation import reconcile_bank_to_ledger

        bank = [{"id": "b1", "amount": 500.0}]
        ledger = [{"id": "l1", "amount": 600.0}]
        result = reconcile_bank_to_ledger(bank, ledger)
        assert len(result["matched"]) == 0


class TestDepreciation:
    def test_straight_line_depreciation(self):
        from app.skills.accounting.workflows.depreciation import straight_line_depreciation

        result = straight_line_depreciation(cost=12000, salvage_value=0, useful_life_months=60)
        assert result["monthly_depreciation"] == 200.0
        assert result["annual_depreciation"] == 2400.0

    def test_depreciation_with_salvage(self):
        from app.skills.accounting.workflows.depreciation import straight_line_depreciation

        result = straight_line_depreciation(cost=6000, salvage_value=600, useful_life_months=12)
        assert abs(result["monthly_depreciation"] - 450.0) < 0.01

    def test_depreciation_invalid_months(self):
        from app.skills.accounting.workflows.depreciation import straight_line_depreciation

        with pytest.raises(ValueError):
            straight_line_depreciation(cost=1000, salvage_value=0, useful_life_months=0)


class TestJournalBuilder:
    def test_owner_draw_entry(self):
        from app.skills.accounting.ledger.journal import build_owner_draw_entry

        entry = build_owner_draw_entry("ent-1", "2024-01-15", "3100", "1110", 2000.0)
        assert entry["status"] == "draft"
        debits = sum(l["debit"] for l in entry["lines"])
        credits = sum(l["credit"] for l in entry["lines"])
        assert debits == credits == 2000.0

    def test_invoice_entry_balanced(self):
        from app.skills.accounting.ledger.journal import build_invoice_issued_entry

        entry = build_invoice_issued_entry("ent-1", "2024-01-20", "1200", "4000", 5000.0, "inv-1")
        assert entry["source_type"] == "invoice"
        debits = sum(l["debit"] for l in entry["lines"])
        credits = sum(l["credit"] for l in entry["lines"])
        assert debits == credits == 5000.0


class TestAccountingQuestions:
    def test_personal_business_ambiguous(self):
        from app.skills.accounting.workflows.questions import generate_accounting_question

        record = {"id": "tx-1", "description": "Dinner at Nobu", "amount": 250}
        result = generate_accounting_question(record, ["personal_business_ambiguous"])
        assert "personal" in result["question"].lower() or "business" in result["question"].lower()
        assert result["status"] == "open"

    def test_owner_draw_question(self):
        from app.skills.accounting.workflows.questions import generate_accounting_question

        record = {"description": "transfer to personal", "amount": 1000}
        result = generate_accounting_question(record, ["owner_draw_possible"])
        assert "owner draw" in result["question"].lower()


class TestMonthlyClose:
    def test_close_checklist_blocks_open_items(self):
        from app.skills.accounting.ledger.close import build_monthly_close_checklist

        context = {"trial_balance_balanced": True}
        result = build_monthly_close_checklist(context)
        assert result["can_close"] is False
        pending = [item for item in result["items"] if item["status"] == "pending"]
        assert len(pending) > 0

    def test_close_checklist_all_done(self):
        from app.skills.accounting.ledger.close import build_monthly_close_checklist

        context = {
            "all_bank_imports_reviewed": True,
            "all_receipts_attached": True,
            "low_confidence_entries_resolved": True,
            "trial_balance_balanced": True,
            "ar_reviewed": True,
            "ap_reviewed": True,
            "bank_reconciliation_completed": True,
            "adjusting_entries_reviewed": True,
            "income_statement_generated": True,
            "balance_sheet_generated": True,
            "owner_draws_reviewed": True,
            "tax_reserve_reviewed": True,
            "reports_approved": True,
        }
        result = build_monthly_close_checklist(context)
        assert result["can_close"] is True


# ────────────────────────── Personal Finance Pack ────────────────────────────

class TestCashflow:
    def test_cashflow_savings_rate(self):
        from app.skills.personal_finance.calculations.cashflow import calculate_personal_cashflow

        transactions = [
            {"amount": 5000, "type": "income"},
            {"amount": 3000, "type": "expense"},
            {"amount": 500, "type": "expense"},
        ]
        result = calculate_personal_cashflow(transactions)
        assert result["income"] == 5000.0
        assert result["expenses"] == 3500.0
        assert abs(result["savings_rate"] - 0.3) < 0.001

    def test_cashflow_empty(self):
        from app.skills.personal_finance.calculations.cashflow import calculate_personal_cashflow

        result = calculate_personal_cashflow([])
        assert result["savings_rate"] == 0.0
        assert "No transactions available." in result["warnings"]


class TestBudget:
    def test_budget_summary_balanced(self):
        from app.skills.personal_finance.calculations.budget import calculate_budget_summary

        lines = [
            {"type": "housing", "amount": 1500},
            {"type": "food", "amount": 500},
        ]
        result = calculate_budget_summary(2000, lines)
        assert result["balanced"] is True
        assert result["remaining"] == 0.0

    def test_budget_summary_exceeded(self):
        from app.skills.personal_finance.calculations.budget import calculate_budget_summary

        lines = [{"type": "housing", "amount": 2500}]
        result = calculate_budget_summary(2000, lines)
        assert result["balanced"] is False
        assert "Budget exceeds income." in result["warnings"]

    def test_budget_variance(self):
        from app.skills.personal_finance.calculations.budget import budget_variance

        lines = [{"category": "food", "amount": 600}]
        actuals = {"food": 750}
        result = budget_variance(lines, actuals)
        assert result["overspent"][0]["category"] == "food"
        assert result["overspent"][0]["status"] == "overspent"


class TestEmergencyFund:
    def test_emergency_fund_plan(self):
        from app.skills.personal_finance.calculations.emergency_fund import emergency_fund_plan

        result = emergency_fund_plan(
            monthly_essential_expenses=3000,
            current_fund=6000,
            target_months=6,
            monthly_contribution=500,
        )
        assert result["target"] == 18000.0
        assert result["gap"] == 12000.0
        assert result["months_covered"] == pytest.approx(2.0, abs=0.01)
        assert result["months_to_goal"] == pytest.approx(24.0, abs=0.01)

    def test_emergency_fund_already_funded(self):
        from app.skills.personal_finance.calculations.emergency_fund import emergency_fund_plan

        result = emergency_fund_plan(
            monthly_essential_expenses=2000,
            current_fund=15000,
            target_months=6,
        )
        assert result["gap"] == 0.0


class TestRoomForError:
    def test_room_for_error_score_low_risk(self):
        from app.skills.personal_finance.calculations.room_for_error import calculate_room_for_error_score

        profile = {"emergency_fund_months": 6, "debt_to_income_ratio": 0.2, "business_income_dependency": 0.3, "tax_reserve_gap": 0}
        result = calculate_room_for_error_score(profile)
        assert result["score"] == 100
        assert result["risk_level"] == "low"

    def test_room_for_error_score_high_risk(self):
        from app.skills.personal_finance.calculations.room_for_error import calculate_room_for_error_score

        profile = {"emergency_fund_months": 0, "debt_to_income_ratio": 0.8, "business_income_dependency": 0.9, "tax_reserve_gap": 1000}
        result = calculate_room_for_error_score(profile)
        assert result["score"] < 50
        assert result["risk_level"] in {"medium", "high"}

    def test_room_for_error_score_minimum_zero(self):
        from app.skills.personal_finance.calculations.room_for_error import calculate_room_for_error_score

        profile = {"emergency_fund_months": 0, "debt_to_income_ratio": 1.0, "business_income_dependency": 1.0, "tax_reserve_gap": 10000}
        result = calculate_room_for_error_score(profile)
        assert result["score"] >= 0


class TestDebtStrategy:
    def test_debt_strategy_motivation_snowball(self):
        from app.skills.personal_finance.calculations.debt import choose_debt_strategy

        debts = [
            {"name": "credit card", "balance": 3000, "interest_rate": 0.22, "minimum_payment": 60},
            {"name": "student loan", "balance": 15000, "interest_rate": 0.06, "minimum_payment": 200},
        ]
        result = choose_debt_strategy("motivation", debts)
        assert result["strategy"] == "snowball"
        assert result["ordered_debts"][0]["name"] == "credit card"

    def test_debt_strategy_interest_avalanche(self):
        from app.skills.personal_finance.calculations.debt import choose_debt_strategy

        debts = [
            {"name": "credit card", "balance": 3000, "interest_rate": 0.22, "minimum_payment": 60},
            {"name": "student loan", "balance": 15000, "interest_rate": 0.06, "minimum_payment": 200},
        ]
        result = choose_debt_strategy("interest", debts)
        assert result["strategy"] == "avalanche"
        assert result["ordered_debts"][0]["name"] == "credit card"


class TestSpendingHabits:
    def test_spending_habit_analyzer(self):
        from app.skills.personal_finance.behavior.habits import analyze_spending_habits

        transactions = [
            {"merchant": "Starbucks", "category": "food", "amount": 5},
            {"merchant": "Starbucks", "category": "food", "amount": 5},
            {"merchant": "Amazon", "category": "shopping", "amount": 100},
        ]
        result = analyze_spending_habits(transactions)
        assert "top_merchants" in result
        assert len(result["top_merchants"]) > 0

    def test_spending_habit_analyzer_empty(self):
        from app.skills.personal_finance.behavior.habits import analyze_spending_habits

        result = analyze_spending_habits([])
        assert result["patterns"] == []


class TestSubscriptions:
    def test_subscription_candidates_detected(self):
        from app.skills.personal_finance.behavior.subscriptions import identify_subscription_candidates

        transactions = [
            {"merchant": "Netflix", "amount": 15.99, "date": "2024-01-01"},
            {"merchant": "Netflix", "amount": 15.99, "date": "2024-02-01"},
            {"merchant": "Netflix", "amount": 15.99, "date": "2024-03-01"},
        ]
        result = identify_subscription_candidates(transactions)
        assert len(result["subscriptions"]) == 1
        assert result["subscriptions"][0]["merchant"] == "Netflix"

    def test_subscription_candidates_empty(self):
        from app.skills.personal_finance.behavior.subscriptions import identify_subscription_candidates

        result = identify_subscription_candidates([])
        assert result["subscriptions"] == []


class TestLifestyleCreep:
    def test_lifestyle_creep_detected(self):
        from app.skills.personal_finance.behavior.lifestyle_creep import detect_lifestyle_creep

        monthly = [
            {"income": 5000, "expenses": 3000, "savings_rate": 0.40},
            {"income": 5500, "expenses": 4000, "savings_rate": 0.27},
            {"income": 6000, "expenses": 5000, "savings_rate": 0.17},
        ]
        result = detect_lifestyle_creep(monthly)
        assert result["detected"] is True

    def test_lifestyle_creep_not_detected(self):
        from app.skills.personal_finance.behavior.lifestyle_creep import detect_lifestyle_creep

        monthly = [
            {"income": 5000, "expenses": 3000, "savings_rate": 0.40},
            {"income": 6000, "expenses": 3500, "savings_rate": 0.42},
            {"income": 7000, "expenses": 4000, "savings_rate": 0.43},
        ]
        result = detect_lifestyle_creep(monthly)
        assert result["detected"] is False

    def test_lifestyle_creep_insufficient_data(self):
        from app.skills.personal_finance.behavior.lifestyle_creep import detect_lifestyle_creep

        result = detect_lifestyle_creep([{"income": 5000, "expenses": 3000, "savings_rate": 0.40}])
        assert result["detected"] is False
        assert "Need at least 3 months." in result["warnings"]


class TestWeeklyMoneyMeeting:
    def test_weekly_money_meeting_agenda_basic(self):
        from app.skills.personal_finance.meetings.weekly_money_meeting import build_weekly_money_meeting_agenda

        result = build_weekly_money_meeting_agenda({})
        assert "agenda" in result
        assert len(result["agenda"]) >= 5

    def test_weekly_money_meeting_agenda_with_business(self):
        from app.skills.personal_finance.meetings.weekly_money_meeting import build_weekly_money_meeting_agenda

        result = build_weekly_money_meeting_agenda({"has_business": True})
        assert any("business" in item.lower() for item in result["agenda"])

    def test_weekly_money_meeting_agenda_with_debt(self):
        from app.skills.personal_finance.meetings.weekly_money_meeting import build_weekly_money_meeting_agenda

        result = build_weekly_money_meeting_agenda({"has_debt": True})
        assert any("debt" in item.lower() for item in result["agenda"])

    def test_weekly_money_meeting_agenda_open_questions_first(self):
        from app.skills.personal_finance.meetings.weekly_money_meeting import build_weekly_money_meeting_agenda

        result = build_weekly_money_meeting_agenda({"has_open_questions": True})
        assert "open" in result["agenda"][0].lower() or "question" in result["agenda"][0].lower()


# ─────────────────────── Skill Registry Integration ──────────────────────────

class TestSkillRegistry:
    def test_registry_loads_new_skills(self):
        from app.services.skills import load_skill_manifests

        manifests = load_skill_manifests()
        names = {s.manifest.name for s in manifests}
        assert "financial_time_series_analyzer" in names
        assert "journal_entry_validator" in names
        assert "budget_coach" in names
        assert "monte_carlo_goal_simulator" in names
        assert "spending_habit_analyzer" in names

    def test_all_new_skill_permissions_valid(self):
        from app.services.skills import load_skill_manifests, _ALLOWED_PERMISSIONS

        manifests = load_skill_manifests()
        new_skills = {
            "financial_time_series_analyzer", "returns_calculator", "risk_metrics_calculator",
            "portfolio_allocation_analyzer", "monte_carlo_goal_simulator", "chart_data_generator",
            "finance_dataframe_profiler", "rolling_statistics_calculator",
            "journal_entry_validator", "trial_balance_generator", "income_statement_generator",
            "bank_reconciliation_assistant", "accounting_question_generator",
            "fixed_asset_depreciation_assistant",
            "cashflow_and_savings_rate", "budget_coach", "room_for_error_checker",
            "spending_habit_analyzer", "subscription_review_assistant",
            "lifestyle_creep_detector", "weekly_money_meeting_assistant",
        }
        for skill in manifests:
            if skill.manifest.name in new_skills:
                for perm in skill.manifest.permissions:
                    assert perm in _ALLOWED_PERMISSIONS, f"Invalid permission {perm} in {skill.manifest.name}"

    def test_no_broker_execution_in_skills(self):
        import inspect
        import app.skills.python_finance.analytics.portfolio as portfolio_mod
        import app.skills.python_finance.analytics.monte_carlo as mc_mod

        src_portfolio = inspect.getsource(portfolio_mod)
        src_mc = inspect.getsource(mc_mod)
        for forbidden in ("execute_trade", "place_order", "broker", "buy(", "sell("):
            assert forbidden not in src_portfolio, f"Forbidden call '{forbidden}' in portfolio.py"
            assert forbidden not in src_mc, f"Forbidden call '{forbidden}' in monte_carlo.py"
