# FinClaw User Guide

FinClaw is an accounting-first financial assistant covering personal finance, small business (PyME) finance, and the shared dependency between them. The AI agent can explain reports, draft journal entries, and run deterministic analyses — but the ledger, not the AI, is always the source of truth for numbers.

## Getting started

1. Navigate to `/onboarding` to create your owner account and workspace.
2. Your workspace has two entities: **Personal** and **Business**. Use the entity switcher in the sidebar to switch context.
3. Upload receipts or import CSV transactions from the **Documents** page to start building your ledger.

## Agent chat (`/agent`)

Ask the agent natural language questions. It will:
- Identify the right deterministic tool (balance sheet, cash flow, budget analysis, etc.)
- Show you a **plan** of tool calls before executing them
- Gate sensitive actions (posting journal entries, creating invoices) behind an explicit **confirmation step**

### Example prompts

| Prompt | What the agent does |
|---|---|
| "Show me the balance sheet" | Runs `get_balance_sheet` from live ledger data |
| "Check my emergency fund" | Runs `suggest_emergency_fund_plan` and `check_room_for_error` |
| "Analyze spending anomalies" | Runs `detect_financial_anomalies` on recent transactions |
| "Run a Monte Carlo simulation for my savings goal" | Runs `simulate_financial_goal` with your parameters |
| "Build a weekly money meeting agenda" | Runs `build_money_meeting_agenda` using your current context |
| "I sold $500 to Acme Corp" | Drafts an invoice (confirmation required before posting) |

### Confirmation flow

When the agent proposes a sensitive action (posting an entry, creating an invoice), the response shows a **pending confirmation** card. Review the details and click **Confirm** to proceed.

## Skills (`/skills`)

Skills extend the agent with specialized analytical modules. Each skill declares typed permissions and is isolated from secrets and shell access.

Built-in skills are enabled by default. You can disable any skill from the Skills page. Third-party skills are disabled by default.

## Heartbeat alerts (`/alerts`)

The heartbeat scheduler runs daily, weekly, and monthly checks on your finances and generates alerts when:
- Emergency fund falls below 3 months of expenses
- Cash runway drops under 60 days
- A budget category is overspent
- AR/AP aging thresholds are exceeded

Dismiss alerts you have acted on, or resolve them when the underlying issue is fixed.

## Memory

The agent can remember contextual notes about your finances (spending patterns, goals, preferences). Memory is consent-gated — the agent will always ask before saving anything. You can review, expire, or delete any memory from the API.

## Disclaimer

Investment features are **educational only**. FinClaw does not execute trades, move real money, or guarantee returns. All investment-related outputs carry an explicit disclaimer.
