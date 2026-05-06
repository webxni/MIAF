# MIAF — Mayordomo IA Financiero User Guide

MIAF es tu Mayordomo IA Financiero. Administra con sabiduría.

MIAF helps you manage personal finances, small business accounting, and owner finances with AI-assisted bookkeeping and financial guidance. The AI agent can explain reports, draft journal entries, and run deterministic analyses, but the ledger, not the AI, is always the source of truth for numbers.

## Getting started

1. Navigate to `/onboarding` to create your owner account and workspace.
2. Your workspace has two entities: **Personal** and **Business**. Use the entity switcher in the sidebar to switch context.
3. Upload receipts or import CSV transactions from the **Documents** page to start building your ledger.
4. Configure your AI provider in `/settings` before expecting external-model responses from the agent.

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

## Reports

MIAF currently has two report surfaces:

- `/business/reports`
- `/alerts` plus the heartbeat report API

### Business reports (`/business/reports`)

This page reads deterministic numbers from the posted ledger and shows:

- balance sheet
- income statement for the current month-to-date window
- AR aging
- AP aging

Use this page when you want formal accounting output from posted entries rather than AI interpretation.

### Heartbeat-generated reports

Heartbeat runs can also create generated reports in the backend. The app currently exposes heartbeat alerts directly in the UI and recent alert summaries on the dashboard. The underlying report list is available from `/api/heartbeat/reports`.

Today, the end-user workflow is:

1. Review alerts in `/alerts`.
2. Open `/business/reports` for formal business statement output.
3. Use `/agent` to ask for explanation or comparison of the current numbers.

## Memory

The agent can remember contextual notes about your finances (spending patterns, goals, preferences). Memory is consent-gated — the agent will always ask before saving anything.

### Memory workspace (`/memory`)

Use `/memory` to:

- create a new memory with explicit consent
- search active memories
- review a memory as accepted, needs update, or archived
- expire a memory
- delete a memory

The memory list also shows system-learned merchant rules when MIAF learns from your draft-entry corrections after CSV imports.

Sensitive credentials such as passwords and API keys are blocked from memory storage.

## Telegram (`/telegram`)

MIAF includes a Telegram integration backend and a simple management screen in `/telegram`.

Use it to:

- link a Telegram user and chat ID to your workspace
- route personal mode to one entity and business mode to another
- choose the currently active mode
- inspect recent inbound and outbound Telegram message logs

Current command support:

- `/start`
- `/personal`
- `/business`
- `/summary`
- `/budget`
- `/cash`
- `/help`

Current limitations:

- there is no full bot provisioning wizard in the app
- you still need a Telegram bot or webhook sender outside the UI to deliver inbound messages to the backend webhook
- voice note handling is still placeholder behavior

## Disclaimer

Investment features are **educational only**. MIAF does not execute trades, move real money, or guarantee returns. All investment-related outputs carry an explicit disclaimer.
