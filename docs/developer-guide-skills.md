# Developer Guide: Skills Engine

## Overview

Skills are typed, permission-gated analytical modules that extend the FinClaw agent. Each skill lives in a `skills/<name>/` directory with three required files:

```
skills/<name>/
  SKILL.yaml     # manifest: name, version, permissions, triggers
  handler.py     # pure-function entry point
  README.md      # usage notes
```

At startup the API loads skill manifests from both `skills/` (repo root, for local development) and `apps/api/skills/` (container bind-mount path). Built-in skills are mirrored to both locations.

## Skill manifest (`SKILL.yaml`)

```yaml
name: my_skill
version: "1.0.0"
description: "One-line description"
enabled_by_default: true        # false for third-party skills
permissions:
  - read_transactions
  - read_reports
triggers:
  - manual
  - heartbeat_weekly
entry_point: handler.handle
```

### Declared permissions

| Permission | What it grants |
|---|---|
| `read_transactions` | Read ledger/journal data |
| `write_drafts` | Create draft journal entries |
| `post_entries` | Post (finalize) entries — requires `ConfirmationEngine` gate |
| `read_documents` | Read attachments and extractions |
| `write_documents` | Write/update document records |
| `read_memory` | Read user memories |
| `write_memory` | Create/update memories |
| `read_reports` | Read generated reports |
| `send_messages` | Send outbound messages (Telegram, etc.) |

Permissions are validated at load time and enforced by the `SkillService` before calling the handler.

## Writing a skill handler

The handler must be a **pure function** (no database, no secrets, no shell):

```python
# skills/my_skill/handler.py

def handle(input_payload: dict) -> dict:
    records = input_payload.get("records", [])
    # ... pure computation ...
    return {"result": ..., "summary": ...}
```

Return a `dict` — it is stored as the skill run output and surfaced in `/skills/runs`.

### Built-in skill packs

Three built-in packs live under `apps/api/app/skills/`:

| Pack | Path | What it provides |
|---|---|---|
| `python_finance` | `app/skills/python_finance/` | Time series, Monte Carlo, VaR, portfolio allocation, anomaly detection, chart data |
| `accounting` | `app/skills/accounting/` | Journal validators, trial balance, income statement, balance sheet, AR/AP aging, depreciation, bank reconciliation |
| `personal_finance` | `app/skills/personal_finance/` | Budget variance, cashflow, emergency fund, debt strategy, room-for-error score, spending habits, weekly money meeting |

Import these functions from agent tool handlers using **lazy imports** (inside the function body) to avoid startup errors if numpy/pandas are unavailable:

```python
async def _tool_check_room_for_error(ctx, args):
    from app.skills.personal_finance.calculations.room_for_error import calculate_room_for_error_score
    return calculate_room_for_error_score(args.profile)
```

## Registering a skill as an agent tool

1. Add a Pydantic `Args` class to `app/schemas/agent.py`.
2. Add the tool description to `_TOOL_DESCRIPTIONS` in `app/services/agent.py`.
3. Write an async handler function `_tool_<name>(ctx, args) -> dict`.
4. Register in `build_tool_registry()`.
5. If the tool is read-only, it does NOT need a `ConfirmationEngine` entry.
6. If the tool writes ledger data, add its name to `ConfirmationEngine._sensitive`.

## SkillPlanner

`SkillPlanner` in `app/services/agent.py` maps intent keywords to ordered tool suggestions. It injects hints into the LLM system prompt before planning — the LLM decides whether to use them.

To add a new intent mapping:

```python
class SkillPlanner:
    INTENT_PLANS = {
        ...
        "depreciation": ["calculate_depreciation", "generate_balance_sheet_data"],
    }
```

## Testing

All skill pack functions have tests in `apps/api/tests/test_skill_packs.py`. Agent tool registration and planner behavior are tested in `apps/api/tests/test_agent_tools.py`.

Run tests:
```bash
make test
# or targeted:
docker compose exec api pytest tests/test_skill_packs.py tests/test_agent_tools.py -v
```

## Skill run logs

Every skill execution (manual or heartbeat-triggered) is persisted in `skill_run_logs` with:
- `skill_name`, `version`, `permissions_used`
- `input_payload`, `output_payload`
- `status` (`success` / `error`)
- `entity_id`, `user_id`, `tenant_id`

Query via `GET /api/skills/runs`.
