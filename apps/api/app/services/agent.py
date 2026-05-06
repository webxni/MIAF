from __future__ import annotations

import json
import logging
import os
import re
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

try:
    import anthropic
except ImportError:  # pragma: no cover - exercised only when dependency is absent
    anthropic = None

try:
    import openai as _openai_sdk
except ImportError:  # pragma: no cover
    _openai_sdk = None
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.config import get_settings
from app.core.brand import AGENT_INTRO, DISPLAY_NAME, SHORT_NAME, TAGLINE
from app.errors import MIAFError, NotFoundError, RateLimitError
from app.models import Account, AuditLog, Customer, Entity, EntityMember, EntityMode
from app.models.journal import JournalEntry, JournalEntryStatus, JournalLine
from app.models.account import AccountType
from app.models.base import utcnow
from app.schemas.agent import (
    AccountingQuestionArgs,
    AgentChatRequest,
    AgentChatResponse,
    AgentToolCallOut,
    AnalyzeSpendingArgs,
    ConversationMessage,
    CreateBillArgs,
    CreateBudgetAgentArgs,
    CreateDebtPlanAgentArgs,
    CreateGoalAgentArgs,
    RecordBillPaymentArgs,
    RecordInvoicePaymentArgs,
    AnomalyRecordsArgs,
    BudgetVarianceArgs,
    CashFlowArgs,
    ChartDataArgs,
    CheckFinancialHealthArgs,
    CreateInvoiceArgs,
    CreateJournalEntryDraftArgs,
    CreatePersonalExpenseArgs,
    ExplainTransactionArgs,
    JournalLinesArgs,
    MemoryArgs,
    MoneyMeetingContextArgs,
    PendingConfirmationOut,
    PostJournalEntryArgs,
    ReturnsListArgs,
    RoomForErrorArgs,
    SimulateGoalArgs,
    StatementArgs,
    SuggestEmergencyFundPlanArgs,
    SuggestInvestmentAllocationArgs,
    SummaryArgs,
    ToolConfirmationIn,
    TransactionsListArgs,
    ValidateJournalArgs,
)
from app.schemas.business import BillCreate, BillLineIn, CustomerCreate, InvoiceCreate, PaymentCreate, VendorCreate
from app.schemas.personal import BudgetCreate, DebtCreate, GoalCreate
from app.models.business import PaymentKind, Vendor as VendorModel
from app.schemas.journal import JournalEntryCreate, JournalEntryOut, JournalLineIn
from app.schemas.memory import MemoryCreate
from app.services.audit import write_audit
from app.services.business import (
    balance_sheet,
    business_dashboard,
    cash_flow_statement,
    create_bill,
    create_customer,
    create_invoice,
    create_vendor,
    get_bill,
    get_invoice,
    income_statement,
    record_payment,
    tax_reserve_report,
)
from app.services.entities import list_entities_for_user
from app.services.crypto import decrypt_secret
from app.services.journal import create_draft, get_entry_scoped, post_entry
from app.services.memory import create_memory, list_memories
from app.services.personal import create_budget, create_debt, create_goal, personal_dashboard
from app.services.user_settings import get_or_create as get_or_create_user_settings


_MONEY_RE = re.compile(r"\$?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)")
_SALE_RE = re.compile(
    r"(?:sold|vendi[oó]|vendio|vendi)\s+\$?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s+(?:to|a)\s+(.+)",
    re.IGNORECASE,
)
_DISCLAIMER_RE = re.compile(r"^\s*disclaimer\s*:\s*(.+)$", re.IGNORECASE)

log = logging.getLogger(__name__)

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
DEFAULT_OPENAI_MODEL = "gpt-4o"
_TOOL_DESCRIPTIONS: dict[str, str] = {
    "create_journal_entry_draft": "Create a draft journal entry from explicit double-entry lines.",
    "post_journal_entry": "Post an existing draft journal entry after confirmation.",
    "create_personal_expense": "Draft a balanced personal expense journal entry from a described spend.",
    "create_business_expense": "Reserved business expense drafting tool for a later phase.",
    "create_invoice": "Create a draft business invoice for a customer sale.",
    "record_invoice_payment": "Reserved invoice payment recording tool that requires confirmation.",
    "create_bill": "Reserved vendor bill creation tool for a later phase.",
    "record_bill_payment": "Reserved bill payment recording tool that requires confirmation.",
    "get_personal_summary": "Return deterministic personal dashboard summary figures.",
    "get_business_summary": "Return deterministic business dashboard summary figures.",
    "get_balance_sheet": "Return a deterministic business balance sheet snapshot.",
    "get_income_statement": "Return a deterministic business income statement for a date range.",
    "get_cash_flow": "Return a deterministic business cash flow statement for a date range.",
    "create_budget": "Reserved budget creation tool for a later phase.",
    "create_goal": "Reserved goal creation tool for a later phase.",
    "create_debt_plan": "Reserved debt planning tool for a later phase.",
    "suggest_emergency_fund_plan": "Suggest an emergency fund target from deterministic personal figures.",
    "suggest_investment_allocation": "Suggest an educational investment allocation without executing trades.",
    "classify_transaction": "Reserved transaction classification tool for a later phase.",
    "explain_transaction": "Explain a transaction using deterministic accounting context.",
    "search_memory": "Search consented user memories for relevant notes.",
    "add_memory": "Create a consented memory note from user-provided text.",
    "analyze_spending_habits": "Find top merchants and spending categories from recent personal transactions.",
    "check_financial_health": "Score the user's personal margin of safety and identify cashflow risks.",
    "simulate_financial_goal": "Run a Monte Carlo simulation for a savings or investment goal.",
    "validate_journal_entry_structure": "Validate that a journal entry draft is balanced and structurally correct.",
    "generate_income_statement_data": "Generate a deterministic income statement from raw journal lines and accounts.",
    "generate_balance_sheet_data": "Generate a deterministic balance sheet snapshot from raw journal lines and accounts.",
    "generate_trial_balance_data": "Generate a trial balance and verify debit/credit equality.",
    "analyze_personal_cashflow": "Calculate personal income, expenses, net cashflow, and savings rate from a transaction list.",
    "analyze_budget_variance": "Calculate budget vs actuals variance and flag overspent categories.",
    "check_room_for_error": "Score personal financial margin of safety: emergency fund, debt ratio, business dependency.",
    "analyze_portfolio_risk": "Calculate historical risk metrics (VaR, drawdown, volatility) for a return series.",
    "detect_financial_anomalies": "Detect unusually large or small amounts in financial records using z-score analysis.",
    "generate_chart_data": "Convert financial data rows into dashboard-ready chart JSON (line, bar, pie, multi-line).",
    "build_money_meeting_agenda": "Build a weekly money review agenda tailored to the user's active financial context.",
    "create_accounting_question": "Generate a structured accounting question for an ambiguous transaction.",
}


def _parse_amount(text: str) -> Decimal | None:
    match = _MONEY_RE.search(text)
    if not match:
        return None
    return Decimal(match.group(1).replace(",", ""))


def _month_bounds(as_of: date) -> tuple[date, date]:
    start = as_of.replace(day=1)
    next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    end = next_month - timedelta(days=1)
    return start, end


from app.services.classifier import _category_to_code  # re-exported for callers


@dataclass
class ToolContext:
    db: AsyncSession
    me: CurrentUser
    request: AgentChatRequest


@dataclass
class PlannedToolCall:
    tool_name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class Tool:
    name: str
    args_model: type
    handler: Any
    description: str
    visible: bool = True  # False = registered for execution but hidden from LLM schemas


class LLMProvider:
    name = "base"

    async def plan(
        self,
        request: AgentChatRequest,
        *,
        api_key: str | None = None,
        model: str | None = None,
        suggested_tools: list[str] | None = None,
    ) -> tuple[str, list[PlannedToolCall], list[str]]:
        raise NotImplementedError


class HeuristicProvider(LLMProvider):
    name = "heuristic"

    async def plan(
        self,
        request: AgentChatRequest,
        *,
        api_key: str | None = None,
        model: str | None = None,
        suggested_tools: list[str] | None = None,
    ) -> tuple[str, list[PlannedToolCall], list[str]]:
        text = request.message.strip()
        lower = text.lower()
        if not text:
            return "No action requested.", [], []

        if "balance sheet" in lower or "balance general" in lower:
            today = date.today()
            return (
                "I can explain the current balance sheet using the deterministic report engine.",
                [PlannedToolCall("get_balance_sheet", {"as_of": today.isoformat()})],
                [],
            )

        if "cash flow" in lower and ("compare" in lower or "compar" in lower):
            today = date.today()
            return (
                "I can compare your personal and business cash position from the backend summaries.",
                [
                    PlannedToolCall("get_personal_summary", {"as_of": today.isoformat()}),
                    PlannedToolCall("get_business_summary", {"as_of": today.isoformat()}),
                ],
                [],
            )

        sale = _SALE_RE.search(text)
        if sale and ("negocio" in lower or "business" in lower):
            amount = Decimal(sale.group(1).replace(",", ""))
            customer_name = sale.group(2).strip().rstrip(".")
            today = date.today()
            return (
                "I can draft that sale as a business invoice.",
                [
                    PlannedToolCall(
                        "create_invoice",
                        {
                            "customer_name": customer_name,
                            "amount": str(amount),
                            "description": "Agent-drafted sale",
                            "invoice_date": today.isoformat(),
                            "due_date": (today + timedelta(days=14)).isoformat(),
                        },
                    )
                ],
                [],
            )

        if any(token in lower for token in ("gasté", "gaste", "spent")) and any(
            token in lower for token in ("personal", "gasolina", "gas", "food", "grocer", "restaurant")
        ):
            amount = _parse_amount(text)
            if amount is None:
                return "I could not find an amount in that expense request.", [], []
            today = date.today()
            category_hint = None
            if "gasolina" in lower or "gas" in lower:
                category_hint = "transportation"
            elif "food" in lower or "restaurant" in lower or "grocer" in lower:
                category_hint = "food"
            return (
                "I can draft that as a personal expense entry and ask for confirmation before posting it.",
                [
                    PlannedToolCall(
                        "create_personal_expense",
                        {
                            "amount": str(amount),
                            "description": text,
                            "category_hint": category_hint,
                            "entry_date": today.isoformat(),
                        },
                    )
                ],
                [],
            )

        if "emergency fund" in lower:
            today = date.today()
            return (
                "I can suggest an emergency fund plan from your current personal KPIs.",
                [PlannedToolCall("suggest_emergency_fund_plan", {"as_of": today.isoformat()})],
                [],
            )

        if "investment" in lower or "portfolio" in lower:
            today = date.today()
            return (
                "I can suggest an educational allocation based on current personal context.",
                [PlannedToolCall("suggest_investment_allocation", {"as_of": today.isoformat()})],
                ["Educational only. This is not legal, tax, or investment advice."],
            )

        return "I could not map that request to a supported financial tool yet.", [], []


def _tool_to_openai_schema(tool: "Tool") -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.args_model.model_json_schema(),
        },
    }


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, *, tool_registry: "ToolRegistry | None" = None) -> None:
        self._env_api_key = os.getenv("OPENAI_API_KEY")
        self._fallback = HeuristicProvider()
        self._tool_registry = tool_registry or None  # set lazily in AgentService

    async def plan(
        self,
        request: AgentChatRequest,
        *,
        api_key: str | None = None,
        model: str | None = None,
        suggested_tools: list[str] | None = None,
    ) -> tuple[str, list[PlannedToolCall], list[str]]:
        key = api_key or self._env_api_key
        registry = self._tool_registry or build_tool_registry()

        if not key or _openai_sdk is None:
            if key and _openai_sdk is None:
                log.warning("openai SDK unavailable; falling back to heuristic provider")
            return await self._fallback.plan(request)

        tools = [_tool_to_openai_schema(tool) for tool in registry.list_tools(visible_only=True)]
        system_parts = [
            f"You are {DISPLAY_NAME}.",
            f"Introduce yourself as: {AGENT_INTRO}",
            f"Brand tagline: {TAGLINE}",
            "Use the provided tools to answer finance questions deterministically.",
            "Never invent numbers. Only tool outputs provide figures.",
        ]
        if suggested_tools:
            system_parts.append(
                f"Suggested tools for this request (in order): {', '.join(suggested_tools)}. "
                "Use them if appropriate — you are not required to."
            )
        system = " ".join(system_parts)
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        for prior in request.conversation_history:
            messages.append({"role": prior.role, "content": prior.content})
        messages.append({"role": "user", "content": request.message})
        try:
            client = _openai_sdk.OpenAI(api_key=key)
            response = client.chat.completions.create(
                model=model or DEFAULT_OPENAI_MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=1024,
            )
        except Exception:
            log.warning("OpenAI planning failed; falling back to heuristic provider", exc_info=True)
            return await self._fallback.plan(request)

        planned_calls: list[PlannedToolCall] = []
        text_parts: list[str] = []
        choice = response.choices[0] if response.choices else None
        if choice is None:
            return "", [], []

        msg = choice.message
        if msg.content:
            text_parts.append(msg.content.strip())

        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except json.JSONDecodeError:
                args = {}
            planned_calls.append(PlannedToolCall(tool_name=tc.function.name, arguments=args))

        return " ".join(text_parts).strip(), planned_calls, []


def _content_block_value(block: Any, field: str, default: Any = None) -> Any:
    if isinstance(block, dict):
        return block.get(field, default)
    return getattr(block, field, default)


def _tool_to_anthropic_schema(tool: Tool) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.args_model.model_json_schema(),
    }


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, *, tool_registry: "ToolRegistry | None" = None) -> None:
        self._env_api_key = os.getenv("ANTHROPIC_API_KEY")
        self._fallback = HeuristicProvider()
        self._tool_registry = tool_registry or build_tool_registry()

    async def plan(
        self,
        request: AgentChatRequest,
        *,
        api_key: str | None = None,
        model: str | None = None,
        suggested_tools: list[str] | None = None,
    ) -> tuple[str, list[PlannedToolCall], list[str]]:
        key = api_key or self._env_api_key
        if not key or anthropic is None:
            if key and anthropic is None:
                log.warning("Anthropic SDK is unavailable; falling back to heuristic provider")
            return await self._fallback.plan(request)

        visible_tools = self._tool_registry.list_tools(visible_only=True)
        tools = [_tool_to_anthropic_schema(tool) for tool in visible_tools]
        tool_lines = [
            f"- {tool.name}: {tool.description} Schema: {json.dumps(tool.args_model.model_json_schema(), sort_keys=True)}"
            for tool in visible_tools
        ]
        system_lines = [
            f"You are {DISPLAY_NAME}.",
            f"Introduce yourself as: {AGENT_INTRO}",
            f"Brand tagline: {TAGLINE}",
            "You may classify, draft journal entries, explain reports, and plan tool calls.",
            "You MUST NOT invent numbers. Only deterministic backend tool outputs are allowed to provide figures.",
            "Use typed tools when a request needs financial data, drafts, or calculations.",
            "Confirmation gates apply to posting and payment tools. Do not bypass them.",
            "Available tools:",
            *tool_lines,
        ]
        if suggested_tools:
            system_lines.append(
                f"Suggested tools for this request (in order): {', '.join(suggested_tools)}. "
                "Use them if appropriate — you are not required to."
            )
        system = "\n".join(system_lines)

        messages: list[dict[str, Any]] = []
        for prior in request.conversation_history:
            messages.append({"role": prior.role, "content": prior.content})
        messages.append({"role": "user", "content": request.message})

        try:
            client = anthropic.Anthropic(api_key=key)
            response = client.messages.create(
                model=model or DEFAULT_ANTHROPIC_MODEL,
                system=system,
                tools=tools,
                messages=messages,
                max_tokens=1024,
            )
        except Exception:
            log.warning("Anthropic planning failed; falling back to heuristic provider", exc_info=True)
            return await self._fallback.plan(request)

        planned_calls: list[PlannedToolCall] = []
        text_parts: list[str] = []
        disclaimers: list[str] = []
        for block in _content_block_value(response, "content", []) or []:
            block_type = _content_block_value(block, "type")
            if block_type == "tool_use":
                planned_calls.append(
                    PlannedToolCall(
                        tool_name=_content_block_value(block, "name", ""),
                        arguments=_content_block_value(block, "input", {}) or {},
                    )
                )
                continue
            if block_type == "text":
                text = (_content_block_value(block, "text", "") or "").strip()
                if not text:
                    continue
                text_parts.append(text)
                for line in text.splitlines():
                    match = _DISCLAIMER_RE.match(line)
                    if match:
                        disclaimers.append(match.group(1).strip())

        return " ".join(text_parts).strip(), planned_calls, list(dict.fromkeys(disclaimers))


class GeminiProvider(HeuristicProvider):
    name = "gemini"


class PolicyEngine:
    def check(self, tool_name: str) -> None:
        if tool_name in {"move_money", "execute_trade", "place_trade"}:
            raise MIAFError(
                f"{SHORT_NAME} cannot move real money or execute trades",
                code="policy_blocked",
            )


class ConfirmationEngine:
    _sensitive = {
        "post_journal_entry",
        "create_invoice",
        "record_invoice_payment",
        "record_bill_payment",
    }

    def requires_confirmation(self, tool_name: str) -> bool:
        return tool_name in self._sensitive


class AgentAuditLogger:
    async def log_prompt(self, ctx: ToolContext) -> None:
        await write_audit(
            ctx.db,
            tenant_id=ctx.me.tenant_id,
            user_id=ctx.me.id,
            entity_id=ctx.request.entity_id,
            action="prompt",
            object_type="agent",
            object_id=None,
            after={"message": ctx.request.message, "provider": ctx.request.provider},
        )

    async def log_tool_call(
        self,
        ctx: ToolContext,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        await write_audit(
            ctx.db,
            tenant_id=ctx.me.tenant_id,
            user_id=ctx.me.id,
            entity_id=ctx.request.entity_id,
            action="tool_call",
            object_type=tool_name,
            object_id=None,
            before={"arguments": arguments},
            after={"result": result, "error": error},
        )


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, name: str, schema: type, handler, description: str | None = None, *, visible: bool = True) -> None:
        self._tools[name] = Tool(
            name=name,
            args_model=schema,
            handler=handler,
            description=description or _TOOL_DESCRIPTIONS.get(name, name.replace("_", " ")),
            visible=visible,
        )

    def list_tools(self, *, visible_only: bool = False) -> list[Tool]:
        tools = list(self._tools.values())
        if visible_only:
            return [t for t in tools if t.visible]
        return tools

    async def execute(self, name: str, raw_arguments: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        if name not in self._tools:
            raise NotFoundError(f"Tool {name} not found", code="tool_not_found")
        tool = self._tools[name]
        payload = tool.args_model.model_validate(raw_arguments)
        return await tool.handler(ctx, payload)


async def _entity_for_mode(ctx: ToolContext, mode: EntityMode) -> Entity:
    entities = await list_entities_for_user(ctx.db, user_id=ctx.me.id)
    for entity in entities:
        if entity.tenant_id == ctx.me.tenant_id and entity.mode == mode:
            return entity
    raise NotFoundError(f"{mode.value.title()} entity not found", code="entity_not_found")


async def _account_by_code(db: AsyncSession, entity_id: uuid.UUID, code: str) -> Account:
    account = (
        await db.execute(
            select(Account).where(Account.entity_id == entity_id, Account.code == code)
        )
    ).scalar_one_or_none()
    if account is None:
        raise NotFoundError(f"Account {code} not found", code="account_not_found")
    return account


async def _customer_by_name(db: AsyncSession, entity_id: uuid.UUID, name: str) -> Customer | None:
    return (
        await db.execute(
            select(Customer).where(Customer.entity_id == entity_id, Customer.name == name)
        )
    ).scalar_one_or_none()


async def _tool_create_journal_entry_draft(ctx: ToolContext, args: CreateJournalEntryDraftArgs) -> dict[str, Any]:
    payload = JournalEntryCreate(
        entry_date=args.entry_date,
        memo=args.memo,
        reference=args.reference,
        lines=[JournalLineIn.model_validate(line) for line in args.lines],
    )
    entry = await create_draft(
        ctx.db,
        entity_id=args.entity_id,
        user_id=ctx.me.id,
        payload=payload,
    )
    return {"entry_id": str(entry.id), "status": entry.status.value}


async def _tool_post_journal_entry(ctx: ToolContext, args: PostJournalEntryArgs) -> dict[str, Any]:
    entry = await get_entry_scoped(ctx.db, entity_id=args.entity_id, entry_id=args.entry_id)
    posted = await post_entry(ctx.db, entry, posted_by_id=ctx.me.id)
    return {"entry_id": str(posted.id), "status": posted.status.value}


async def _tool_create_personal_expense(ctx: ToolContext, args: CreatePersonalExpenseArgs) -> dict[str, Any]:
    entity = await _entity_for_mode(ctx, EntityMode.personal)
    cash_account = await _account_by_code(ctx.db, entity.id, "1110")
    expense_account = await _account_by_code(
        ctx.db, entity.id, _category_to_code(args.category_hint or args.description)
    )
    entry = await create_draft(
        ctx.db,
        entity_id=entity.id,
        user_id=ctx.me.id,
        payload=JournalEntryCreate(
            entry_date=args.entry_date,
            memo=args.description,
            reference="agent:personal-expense",
            lines=[
                JournalLineIn(
                    account_id=expense_account.id,
                    debit=args.amount,
                    credit=Decimal("0"),
                    description=args.description,
                ),
                JournalLineIn(
                    account_id=cash_account.id,
                    debit=Decimal("0"),
                    credit=args.amount,
                    description="Cash paid",
                ),
            ],
        ),
    )
    return {
        "entity_id": str(entity.id),
        "draft_entry_id": str(entry.id),
        "status": entry.status.value,
        "post_confirmation": {
            "tool_name": "post_journal_entry",
            "reason": "Posting a journal entry is sensitive and requires confirmation.",
            "arguments": {"entity_id": str(entity.id), "entry_id": str(entry.id)},
        },
    }


async def _tool_create_invoice(ctx: ToolContext, args: CreateInvoiceArgs) -> dict[str, Any]:
    entity = await _entity_for_mode(ctx, EntityMode.business)
    customer = await _customer_by_name(ctx.db, entity.id, args.customer_name)
    if customer is None:
        customer = await create_customer(
            ctx.db,
            entity_id=entity.id,
            payload=CustomerCreate(name=args.customer_name),
        )
    revenue = await _account_by_code(ctx.db, entity.id, "4200")
    invoice = await create_invoice(
        ctx.db,
        entity_id=entity.id,
        payload=InvoiceCreate(
            customer_id=customer.id,
            number=f"AGENT-{date.today().strftime('%Y%m%d')}-{str(customer.id)[:6]}",
            invoice_date=args.invoice_date,
            due_date=args.due_date,
            memo="Agent-drafted invoice",
            lines=[
                {
                    "description": args.description,
                    "quantity": "1",
                    "unit_price": str(args.amount),
                    "revenue_account_id": revenue.id,
                }
            ],
        ),
    )
    return {
        "entity_id": str(entity.id),
        "invoice_id": str(invoice.id),
        "customer_id": str(customer.id),
        "status": invoice.status.value,
        "total": str(invoice.total),
    }


async def _tool_get_personal_summary(ctx: ToolContext, args: SummaryArgs) -> dict[str, Any]:
    entity = await _entity_for_mode(ctx, EntityMode.personal)
    summary = await personal_dashboard(ctx.db, entity_id=entity.id, as_of=args.as_of)
    return {
        "entity_id": str(entity.id),
        "net_worth": str(summary.net_worth),
        "monthly_income": str(summary.monthly_income),
        "monthly_expenses": str(summary.monthly_expenses),
        "monthly_savings": str(summary.monthly_savings),
        "savings_rate": str(summary.savings_rate),
    }


async def _tool_get_business_summary(ctx: ToolContext, args: SummaryArgs) -> dict[str, Any]:
    entity = await _entity_for_mode(ctx, EntityMode.business)
    summary = await business_dashboard(ctx.db, entity_id=entity.id, as_of=args.as_of)
    return {
        "entity_id": str(entity.id),
        "cash_balance": str(summary.cash_balance),
        "monthly_revenue": str(summary.monthly_revenue),
        "monthly_expenses": str(summary.monthly_expenses),
        "monthly_net_income": str(summary.monthly_net_income),
        "accounts_receivable": str(summary.accounts_receivable),
        "accounts_payable": str(summary.accounts_payable),
    }


async def _tool_get_balance_sheet(ctx: ToolContext, args: StatementArgs) -> dict[str, Any]:
    entity = await _entity_for_mode(ctx, EntityMode.business)
    report = await balance_sheet(ctx.db, entity_id=entity.id, as_of=args.as_of)
    return {
        "entity_id": str(entity.id),
        "as_of": args.as_of.isoformat(),
        "total_assets": str(report.total_assets),
        "total_liabilities": str(report.total_liabilities),
        "total_equity": str(report.total_equity),
        "is_balanced": report.is_balanced,
    }


async def _tool_get_income_statement(ctx: ToolContext, args: CashFlowArgs) -> dict[str, Any]:
    entity = await _entity_for_mode(ctx, EntityMode.business)
    report = await income_statement(
        ctx.db,
        entity_id=entity.id,
        date_from=args.date_from,
        date_to=args.date_to,
    )
    return {
        "entity_id": str(entity.id),
        "date_from": args.date_from.isoformat(),
        "date_to": args.date_to.isoformat(),
        "total_income": str(report.total_income),
        "total_expenses": str(report.total_expenses),
        "net_income": str(report.net_income),
    }


async def _tool_get_cash_flow(ctx: ToolContext, args: CashFlowArgs) -> dict[str, Any]:
    entity = await _entity_for_mode(ctx, EntityMode.business)
    report = await cash_flow_statement(
        ctx.db,
        entity_id=entity.id,
        date_from=args.date_from,
        date_to=args.date_to,
    )
    return {
        "entity_id": str(entity.id),
        "date_from": args.date_from.isoformat(),
        "date_to": args.date_to.isoformat(),
        "total_cash_change": str(report.total_cash_change),
        "operating_cash_flow": str(report.operating_cash_flow),
        "financing_cash_flow": str(report.financing_cash_flow),
    }


async def _tool_suggest_emergency_fund_plan(
    ctx: ToolContext, args: SuggestEmergencyFundPlanArgs
) -> dict[str, Any]:
    entity = await _entity_for_mode(ctx, EntityMode.personal)
    summary = await personal_dashboard(ctx.db, entity_id=entity.id, as_of=args.as_of)
    monthly_expenses = summary.monthly_expenses
    target_min = monthly_expenses * Decimal("3")
    target_max = monthly_expenses * Decimal("6")
    return {
        "entity_id": str(entity.id),
        "current_months": str(summary.emergency_fund_months),
        "target_min": str(target_min),
        "target_max": str(target_max),
        "message": "Build 3-6 months of essential expenses in your emergency fund before taking additional risk.",
    }


async def _tool_suggest_investment_allocation(
    ctx: ToolContext, args: SuggestInvestmentAllocationArgs
) -> dict[str, Any]:
    entity = await _entity_for_mode(ctx, EntityMode.personal)
    summary = await personal_dashboard(ctx.db, entity_id=entity.id, as_of=args.as_of)
    if summary.emergency_fund_months < Decimal("3"):
        allocation = "100% cash / short-term reserves until emergency fund reaches at least 3 months."
    else:
        allocation = "Example educational split: 70% diversified equity funds, 20% bonds, 10% cash."
    return {
        "entity_id": str(entity.id),
        "allocation_note": allocation,
        "risk_disclaimer": f"Educational only. {SHORT_NAME} does not execute trades or guarantee returns.",
    }


async def _tool_explain_transaction(ctx: ToolContext, args: ExplainTransactionArgs) -> dict[str, Any]:
    keyword = args.description.lower()
    stmt = (
        select(JournalEntry)
        .join(Entity, JournalEntry.entity_id == Entity.id)
        .where(
            Entity.tenant_id == ctx.me.tenant_id,
            JournalEntry.status == JournalEntryStatus.posted,
            JournalEntry.memo.ilike(f"%{keyword[:80]}%"),
        )
        .order_by(JournalEntry.entry_date.desc())
        .limit(3)
    )
    rows = (await ctx.db.execute(stmt)).scalars().all()
    if not rows:
        return {
            "explanation": (
                f"No posted journal entries matched '{args.description}'. "
                "In double-entry accounting every transaction posts balanced debit and credit lines. "
                "You can search by exact memo text or entry ID."
            ),
            "entries_found": 0,
        }

    entries_out = []
    for entry in rows:
        lines_stmt = (
            select(JournalLine, Account)
            .join(Account, JournalLine.account_id == Account.id)
            .where(JournalLine.entry_id == entry.id)
        )
        line_rows = (await ctx.db.execute(lines_stmt)).all()
        entries_out.append({
            "entry_id": str(entry.id),
            "entry_date": str(entry.entry_date),
            "memo": entry.memo,
            "status": entry.status.value,
            "lines": [
                {
                    "account_code": acc.code,
                    "account_name": acc.name,
                    "account_type": acc.type.value,
                    "debit": float(line.debit),
                    "credit": float(line.credit),
                    "description": line.description,
                }
                for line, acc in line_rows
            ],
        })

    return {
        "explanation": (
            f"Found {len(entries_out)} posted journal entr{'y' if len(entries_out)==1 else 'ies'} "
            f"matching '{args.description}'. Each entry has balanced debit and credit lines."
        ),
        "entries_found": len(entries_out),
        "entries": entries_out,
    }


async def _tool_create_business_expense(ctx: ToolContext, args: CreatePersonalExpenseArgs) -> dict[str, Any]:
    entity = await _entity_for_mode(ctx, EntityMode.business)
    cash_account = await _account_by_code(ctx.db, entity.id, "1110")
    expense_account = await _account_by_code(
        ctx.db, entity.id, _category_to_code(args.category_hint or args.description)
    )
    entry = await create_draft(
        ctx.db,
        entity_id=entity.id,
        user_id=ctx.me.id,
        payload=JournalEntryCreate(
            entry_date=args.entry_date,
            memo=args.description,
            reference="agent:business-expense",
            lines=[
                JournalLineIn(
                    account_id=expense_account.id,
                    debit=args.amount,
                    credit=Decimal("0"),
                    description=args.description,
                ),
                JournalLineIn(
                    account_id=cash_account.id,
                    debit=Decimal("0"),
                    credit=args.amount,
                    description="Cash paid",
                ),
            ],
        ),
    )
    return {
        "entity_id": str(entity.id),
        "draft_entry_id": str(entry.id),
        "status": entry.status.value,
        "post_confirmation": {
            "tool_name": "post_journal_entry",
            "reason": "Posting a business journal entry is sensitive and requires confirmation.",
            "arguments": {"entity_id": str(entity.id), "entry_id": str(entry.id)},
        },
    }


async def _tool_classify_transaction(ctx: ToolContext, args: ExplainTransactionArgs) -> dict[str, Any]:
    code = _category_to_code(args.description)
    reason = (
        "keyword match"
        if code != "5900"
        else "default (no keyword matched; review suggested)"
    )
    return {
        "description": args.description,
        "suggested_account_code": code,
        "reason": reason,
        "note": "Classification is keyword-based. Override the account before posting.",
    }


async def _tool_not_implemented(_: ToolContext, __) -> dict[str, Any]:
    return {"status": "not_implemented", "message": "This tool is reserved for a later phase."}


async def _vendor_by_name(db: AsyncSession, entity_id: uuid.UUID, name: str) -> VendorModel | None:
    return (
        await db.execute(
            select(VendorModel).where(VendorModel.entity_id == entity_id, VendorModel.name == name)
        )
    ).scalar_one_or_none()


async def _tool_record_invoice_payment(ctx: ToolContext, args: RecordInvoicePaymentArgs) -> dict[str, Any]:
    entity = await _entity_for_mode(ctx, EntityMode.business)
    invoice = await get_invoice(ctx.db, entity_id=entity.id, invoice_id=args.invoice_id)
    payment = await record_payment(
        ctx.db,
        entity_id=entity.id,
        user_id=ctx.me.id,
        payload=PaymentCreate(
            confirmed=True,
            kind=PaymentKind.customer_receipt,
            payment_date=args.payment_date,
            amount=args.amount,
            reference=args.reference,
            invoice_id=invoice.id,
        ),
    )
    return {
        "entity_id": str(entity.id),
        "payment_id": str(payment.id),
        "invoice_id": str(invoice.id),
        "amount": str(payment.amount),
        "status": "posted",
    }


async def _tool_create_bill(ctx: ToolContext, args: CreateBillArgs) -> dict[str, Any]:
    entity = await _entity_for_mode(ctx, EntityMode.business)
    vendor = await _vendor_by_name(ctx.db, entity.id, args.vendor_name)
    if vendor is None:
        vendor = await create_vendor(
            ctx.db,
            entity_id=entity.id,
            payload=VendorCreate(name=args.vendor_name),
        )
    expense_account = await _account_by_code(
        ctx.db, entity.id, _category_to_code(args.description)
    )
    bill = await create_bill(
        ctx.db,
        entity_id=entity.id,
        payload=BillCreate(
            vendor_id=vendor.id,
            number=f"AGENT-{date.today().strftime('%Y%m%d')}-{str(vendor.id)[:6]}",
            bill_date=args.bill_date,
            due_date=args.due_date,
            memo="Agent-drafted bill",
            lines=[
                BillLineIn(
                    description=args.description,
                    quantity=Decimal("1"),
                    unit_price=args.amount,
                    expense_account_id=expense_account.id,
                )
            ],
        ),
    )
    return {
        "entity_id": str(entity.id),
        "bill_id": str(bill.id),
        "vendor_id": str(vendor.id),
        "status": bill.status.value,
        "total": str(bill.total),
    }


async def _tool_record_bill_payment(ctx: ToolContext, args: RecordBillPaymentArgs) -> dict[str, Any]:
    entity = await _entity_for_mode(ctx, EntityMode.business)
    bill = await get_bill(ctx.db, entity_id=entity.id, bill_id=args.bill_id)
    payment = await record_payment(
        ctx.db,
        entity_id=entity.id,
        user_id=ctx.me.id,
        payload=PaymentCreate(
            confirmed=True,
            kind=PaymentKind.vendor_payment,
            payment_date=args.payment_date,
            amount=args.amount,
            reference=args.reference,
            bill_id=bill.id,
        ),
    )
    return {
        "entity_id": str(entity.id),
        "payment_id": str(payment.id),
        "bill_id": str(bill.id),
        "amount": str(payment.amount),
        "status": "posted",
    }


async def _tool_create_budget(ctx: ToolContext, args: CreateBudgetAgentArgs) -> dict[str, Any]:
    entity = await _entity_for_mode(ctx, EntityMode.personal)
    budget = await create_budget(
        ctx.db,
        entity_id=entity.id,
        payload=BudgetCreate(
            name=args.name,
            period_start=args.period_start,
            period_end=args.period_end,
            notes=args.notes,
            lines=[],
        ),
    )
    return {
        "entity_id": str(entity.id),
        "budget_id": str(budget.id),
        "name": budget.name,
        "period_start": str(budget.period_start),
        "period_end": str(budget.period_end),
        "note": "Budget created with no lines. Add budget lines from the web UI or via the budget API.",
    }


async def _tool_create_goal(ctx: ToolContext, args: CreateGoalAgentArgs) -> dict[str, Any]:
    from app.models.goal import GoalKind, GoalStatus
    entity = await _entity_for_mode(ctx, EntityMode.personal)
    goal = await create_goal(
        ctx.db,
        entity_id=entity.id,
        payload=GoalCreate(
            name=args.name,
            kind=GoalKind.savings,
            target_amount=args.target_amount,
            target_date=args.target_date,
            notes=args.notes,
        ),
    )
    return {
        "entity_id": str(entity.id),
        "goal_id": str(goal.id),
        "name": goal.name,
        "target_amount": str(goal.target_amount),
        "target_date": str(goal.target_date) if goal.target_date else None,
        "status": goal.status.value,
    }


async def _tool_create_debt_plan(ctx: ToolContext, args: CreateDebtPlanAgentArgs) -> dict[str, Any]:
    from app.models.debt import DebtKind
    entity = await _entity_for_mode(ctx, EntityMode.personal)
    debt = await create_debt(
        ctx.db,
        entity_id=entity.id,
        payload=DebtCreate(
            confirmed=True,
            name=args.name,
            kind=DebtKind.other,
            current_balance=args.current_balance,
            interest_rate_apr=args.interest_rate_apr,
            minimum_payment=args.minimum_payment,
            notes=args.notes,
        ),
    )
    return {
        "entity_id": str(entity.id),
        "debt_id": str(debt.id),
        "name": debt.name,
        "current_balance": str(debt.current_balance),
        "interest_rate_apr": str(debt.interest_rate_apr) if debt.interest_rate_apr else None,
        "minimum_payment": str(debt.minimum_payment) if debt.minimum_payment else None,
        "status": debt.status.value,
    }


async def _tool_search_memory(ctx: ToolContext, args: MemoryArgs) -> dict[str, Any]:
    rows = await list_memories(ctx.db, tenant_id=ctx.me.tenant_id, query=args.query, limit=5)
    return {
        "matches": [
            {
                "memory_id": str(row.id),
                "title": row.title,
                "memory_type": row.memory_type.value,
                "summary": row.summary,
            }
            for row in rows
        ]
    }


def _infer_memory_type(text: str) -> str:
    lower = text.lower()
    if any(k in lower for k in ("merchant", "vendor", "store", "categorize", "account code")):
        return "merchant_rule"
    if any(k in lower for k in ("goal", "saving for", "target", "fund")):
        return "goal_context"
    if any(k in lower for k in ("tax", "deductible", "iva", "impuesto")):
        return "tax_context"
    if any(k in lower for k in ("risk", "invest", "portfolio", "conservative", "aggressive")):
        return "risk_preference"
    if any(k in lower for k in ("prefer", "always", "never", "rule", "policy")):
        return "financial_rule"
    if any(k in lower for k in ("business", "company", "negocio", "empresa")):
        return "business_profile"
    if any(k in lower for k in ("personal", "myself", "my income", "my expense")):
        return "personal_preference"
    return "advisor_note"


async def _tool_add_memory(ctx: ToolContext, args: MemoryArgs) -> dict[str, Any]:
    memory_type = _infer_memory_type(args.query)
    memory = await create_memory(
        ctx.db,
        tenant_id=ctx.me.tenant_id,
        user_id=ctx.me.id,
        payload=MemoryCreate(
            memory_type=memory_type,
            title=args.query[:80],
            content=args.query,
            summary=args.query[:200],
            consent_granted=True,
            source="agent",
        ),
    )
    return {"memory_id": str(memory.id), "title": memory.title, "memory_type": memory.memory_type.value}


async def _tool_analyze_spending_habits(ctx: ToolContext, args: AnalyzeSpendingArgs) -> dict[str, Any]:
    from app.skills.personal_finance.behavior.habits import analyze_spending_habits

    entities = await list_entities_for_user(ctx.db, user_id=ctx.me.id)
    personal = next(
        (e for e in entities if e.tenant_id == ctx.me.tenant_id and e.mode == EntityMode.personal),
        None,
    )
    if personal is None:
        return {"warnings": ["No personal entity found."]}

    date_from = args.as_of - timedelta(days=args.limit)
    line_stmt = (
        select(JournalLine, Account, JournalEntry)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .join(Account, JournalLine.account_id == Account.id)
        .where(
            JournalEntry.entity_id == personal.id,
            JournalEntry.status == JournalEntryStatus.posted,
            Account.type == AccountType.expense,
            JournalEntry.entry_date >= date_from,
            JournalEntry.entry_date <= args.as_of,
            JournalLine.debit > 0,
        )
        .order_by(JournalEntry.entry_date.desc())
        .limit(500)
    )
    line_rows = (await ctx.db.execute(line_stmt)).all()

    transactions = [
        {
            "amount": float(line.debit),
            "type": "expense",
            "category": acc.name,
            "description": line.description or entry.memo or acc.name,
            "date": str(entry.entry_date),
        }
        for line, acc, entry in line_rows
    ]

    dashboard = await personal_dashboard(ctx.db, entity_id=personal.id, as_of=args.as_of)
    if not transactions:
        transactions = [
            {"amount": float(dashboard.monthly_expenses), "type": "expense", "category": "total_expenses"},
        ]

    result = analyze_spending_habits(transactions)
    result["summary"] = {
        "monthly_income": float(dashboard.monthly_income),
        "monthly_expenses": float(dashboard.monthly_expenses),
        "savings_rate": float(dashboard.savings_rate),
        "transactions_analyzed": len(transactions),
        "period_days": args.limit,
    }
    return result


async def _tool_check_financial_health(ctx: ToolContext, args: CheckFinancialHealthArgs) -> dict[str, Any]:
    from app.skills.personal_finance.calculations.room_for_error import calculate_room_for_error_score

    entities = await list_entities_for_user(ctx.db, user_id=ctx.me.id)
    personal = next(
        (e for e in entities if e.tenant_id == ctx.me.tenant_id and e.mode == EntityMode.personal),
        None,
    )
    if personal is None:
        return {"warnings": ["No personal entity found."]}

    dashboard = await personal_dashboard(ctx.db, entity_id=personal.id, as_of=args.as_of)
    income = float(dashboard.monthly_income)
    expenses = float(dashboard.monthly_expenses)

    # Derive business income dependency from personal dashboard's business_dependency data
    business_dependency_ratio = float(dashboard.business_dependency.business_dependency_ratio)

    # Derive tax reserve gap from the business entity if one exists
    tax_reserve_gap = 0.0
    business_entity = next(
        (e for e in entities if e.tenant_id == ctx.me.tenant_id and e.mode == EntityMode.business),
        None,
    )
    if business_entity is not None:
        try:
            tax_report = await tax_reserve_report(ctx.db, entity_id=business_entity.id, as_of=args.as_of)
            gap = float(tax_report.reserve_gap)
            tax_reserve_gap = max(0.0, gap)
        except Exception:
            pass

    profile = {
        "emergency_fund_months": float(dashboard.emergency_fund_months),
        "debt_to_income_ratio": expenses / income if income > 0 else 0.0,
        "business_income_dependency": business_dependency_ratio,
        "tax_reserve_gap": tax_reserve_gap,
    }
    score = calculate_room_for_error_score(profile)
    return {
        **score,
        "monthly_income": income,
        "monthly_expenses": expenses,
        "savings_rate": float(dashboard.savings_rate),
        "emergency_fund_months": float(dashboard.emergency_fund_months),
        "business_income_dependency": business_dependency_ratio,
        "tax_reserve_gap": tax_reserve_gap,
    }


async def _tool_simulate_financial_goal(ctx: ToolContext, args: SimulateGoalArgs) -> dict[str, Any]:
    from app.skills.python_finance.analytics.monte_carlo import simulate_goal_balance
    return simulate_goal_balance(
        starting_balance=args.starting_balance,
        monthly_contribution=args.monthly_contribution,
        months=args.months,
        expected_monthly_return=args.expected_monthly_return,
        monthly_volatility=args.monthly_volatility,
        goal_amount=args.goal_amount,
    )


async def _tool_validate_journal_entry_structure(ctx: ToolContext, args: ValidateJournalArgs) -> dict[str, Any]:
    from app.skills.accounting.core.validators import validate_journal_entry
    return validate_journal_entry({"lines": args.lines})


# ── 11 skill-backed analytics tools (read-only, no confirmation needed) ──────

async def _tool_generate_income_statement_data(ctx: ToolContext, args: JournalLinesArgs) -> dict[str, Any]:
    from app.skills.accounting.ledger.financial_statements import generate_income_statement
    return generate_income_statement(args.journal_lines, args.accounts)


async def _tool_generate_balance_sheet_data(ctx: ToolContext, args: JournalLinesArgs) -> dict[str, Any]:
    from app.skills.accounting.ledger.financial_statements import generate_balance_sheet
    return generate_balance_sheet(args.journal_lines, args.accounts)


async def _tool_generate_trial_balance_data(ctx: ToolContext, args: JournalLinesArgs) -> dict[str, Any]:
    from app.skills.accounting.ledger.trial_balance import generate_trial_balance
    return generate_trial_balance(args.journal_lines, args.accounts)


async def _tool_analyze_personal_cashflow(ctx: ToolContext, args: TransactionsListArgs) -> dict[str, Any]:
    from app.skills.personal_finance.calculations.cashflow import calculate_personal_cashflow
    return calculate_personal_cashflow(args.transactions)


async def _tool_analyze_budget_variance(ctx: ToolContext, args: BudgetVarianceArgs) -> dict[str, Any]:
    from app.skills.personal_finance.calculations.budget import budget_variance
    return budget_variance(args.budget_lines, args.actual_by_category)


async def _tool_check_room_for_error(ctx: ToolContext, args: RoomForErrorArgs) -> dict[str, Any]:
    from app.skills.personal_finance.calculations.room_for_error import calculate_room_for_error_score
    result = calculate_room_for_error_score(args.profile)
    if result.get("risk_level") in {"medium", "high"}:
        result["memory_suggestion"] = {
            "type": "behavioral_observation",
            "content": f"Room-for-error score: {result['score']}/100 ({result['risk_level']} risk). Issues: {'; '.join(result.get('issues', []))}",
        }
    return result


async def _tool_analyze_portfolio_risk(ctx: ToolContext, args: ReturnsListArgs) -> dict[str, Any]:
    from app.skills.python_finance.analytics.risk import calculate_risk_metrics
    result = calculate_risk_metrics(args.returns, confidence_level=args.confidence_level)
    result.setdefault("disclaimer", "Educational risk analysis only. Not investment advice.")
    return result


async def _tool_detect_financial_anomalies(ctx: ToolContext, args: AnomalyRecordsArgs) -> dict[str, Any]:
    from app.skills.python_finance.analytics.anomalies import detect_amount_anomalies
    result = detect_amount_anomalies(args.records, group_col=args.group_col, z_threshold=args.z_threshold)
    if result.get("anomalies"):
        result["memory_suggestion"] = {
            "type": "behavioral_observation",
            "content": f"Detected {len(result['anomalies'])} anomalous transaction(s). Review suggested.",
        }
    return result


async def _tool_generate_chart_data(ctx: ToolContext, args: ChartDataArgs) -> dict[str, Any]:
    from app.skills.python_finance.visualization.chart_data import generate_chart
    return generate_chart(
        chart_type=args.chart_type,
        title=args.title,
        rows=args.rows,
        x_key=args.x_key,
        y_key=args.y_key,
        label_key=args.label_key,
        value_key=args.value_key,
    )


async def _tool_build_money_meeting_agenda(ctx: ToolContext, args: MoneyMeetingContextArgs) -> dict[str, Any]:
    from app.skills.personal_finance.meetings.weekly_money_meeting import build_weekly_money_meeting_agenda
    return build_weekly_money_meeting_agenda(args.context)


async def _tool_create_accounting_question(ctx: ToolContext, args: AccountingQuestionArgs) -> dict[str, Any]:
    from app.skills.accounting.workflows.questions import generate_accounting_question
    return generate_accounting_question(args.record, args.reason_codes)


class SkillPlanner:
    """Maps high-level message intent to an ordered list of suggested tool names.

    The planner injects hints into the system prompt so the LLM can decide
    whether to use them; it does NOT auto-execute tools.
    """

    INTENT_PLANS: dict[str, list[str]] = {
        "income statement": ["generate_income_statement_data", "get_income_statement"],
        "balance sheet": ["generate_balance_sheet_data", "get_balance_sheet"],
        "trial balance": ["generate_trial_balance_data"],
        "cash flow": ["analyze_personal_cashflow", "get_cash_flow"],
        "budget": ["analyze_budget_variance", "get_personal_summary"],
        "anomaly": ["detect_financial_anomalies"],
        "anomalies": ["detect_financial_anomalies"],
        "unusual": ["detect_financial_anomalies"],
        "emergency fund": ["suggest_emergency_fund_plan", "check_room_for_error"],
        "room for error": ["check_room_for_error"],
        "safety score": ["check_room_for_error"],
        "portfolio": ["analyze_portfolio_risk", "suggest_investment_allocation"],
        "investment": ["analyze_portfolio_risk", "suggest_investment_allocation"],
        "risk": ["analyze_portfolio_risk", "check_room_for_error"],
        "simulate": ["simulate_financial_goal"],
        "goal": ["simulate_financial_goal"],
        "spending": ["analyze_spending_habits", "detect_financial_anomalies"],
        "habits": ["analyze_spending_habits"],
        "chart": ["generate_chart_data"],
        "graph": ["generate_chart_data"],
        "money meeting": ["build_money_meeting_agenda", "get_personal_summary", "get_business_summary"],
        "weekly review": ["build_money_meeting_agenda"],
        "health": ["check_financial_health", "check_room_for_error"],
        "validate": ["validate_journal_entry_structure"],
        "journal": ["validate_journal_entry_structure", "create_journal_entry_draft"],
    }

    def suggest(self, message: str) -> list[str]:
        lower = message.lower()
        seen: set[str] = set()
        ordered: list[str] = []
        for keyword, tools in self.INTENT_PLANS.items():
            if keyword in lower:
                for t in tools:
                    if t not in seen:
                        seen.add(t)
                        ordered.append(t)
        return ordered


def build_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register("create_journal_entry_draft", CreateJournalEntryDraftArgs, _tool_create_journal_entry_draft)
    registry.register("post_journal_entry", PostJournalEntryArgs, _tool_post_journal_entry)
    registry.register("create_personal_expense", CreatePersonalExpenseArgs, _tool_create_personal_expense)
    registry.register("create_business_expense", CreatePersonalExpenseArgs, _tool_create_business_expense)
    registry.register("create_invoice", CreateInvoiceArgs, _tool_create_invoice)
    registry.register("record_invoice_payment", RecordInvoicePaymentArgs, _tool_record_invoice_payment, visible=False)
    registry.register("create_bill", CreateBillArgs, _tool_create_bill, visible=False)
    registry.register("record_bill_payment", RecordBillPaymentArgs, _tool_record_bill_payment, visible=False)
    registry.register("get_personal_summary", SummaryArgs, _tool_get_personal_summary)
    registry.register("get_business_summary", SummaryArgs, _tool_get_business_summary)
    registry.register("get_balance_sheet", StatementArgs, _tool_get_balance_sheet)
    registry.register("get_income_statement", CashFlowArgs, _tool_get_income_statement)
    registry.register("get_cash_flow", CashFlowArgs, _tool_get_cash_flow)
    registry.register("create_budget", CreateBudgetAgentArgs, _tool_create_budget, visible=False)
    registry.register("create_goal", CreateGoalAgentArgs, _tool_create_goal, visible=False)
    registry.register("create_debt_plan", CreateDebtPlanAgentArgs, _tool_create_debt_plan, visible=False)
    registry.register("suggest_emergency_fund_plan", SuggestEmergencyFundPlanArgs, _tool_suggest_emergency_fund_plan)
    registry.register("suggest_investment_allocation", SuggestInvestmentAllocationArgs, _tool_suggest_investment_allocation)
    registry.register("classify_transaction", ExplainTransactionArgs, _tool_classify_transaction)
    registry.register("explain_transaction", ExplainTransactionArgs, _tool_explain_transaction)
    registry.register("search_memory", MemoryArgs, _tool_search_memory)
    registry.register("add_memory", MemoryArgs, _tool_add_memory)
    registry.register("analyze_spending_habits", AnalyzeSpendingArgs, _tool_analyze_spending_habits)
    registry.register("check_financial_health", CheckFinancialHealthArgs, _tool_check_financial_health)
    registry.register("simulate_financial_goal", SimulateGoalArgs, _tool_simulate_financial_goal)
    registry.register("validate_journal_entry_structure", ValidateJournalArgs, _tool_validate_journal_entry_structure)
    # skill-backed analytics (read-only)
    registry.register("generate_income_statement_data", JournalLinesArgs, _tool_generate_income_statement_data)
    registry.register("generate_balance_sheet_data", JournalLinesArgs, _tool_generate_balance_sheet_data)
    registry.register("generate_trial_balance_data", JournalLinesArgs, _tool_generate_trial_balance_data)
    registry.register("analyze_personal_cashflow", TransactionsListArgs, _tool_analyze_personal_cashflow)
    registry.register("analyze_budget_variance", BudgetVarianceArgs, _tool_analyze_budget_variance)
    registry.register("check_room_for_error", RoomForErrorArgs, _tool_check_room_for_error)
    registry.register("analyze_portfolio_risk", ReturnsListArgs, _tool_analyze_portfolio_risk)
    registry.register("detect_financial_anomalies", AnomalyRecordsArgs, _tool_detect_financial_anomalies)
    registry.register("generate_chart_data", ChartDataArgs, _tool_generate_chart_data)
    registry.register("build_money_meeting_agenda", MoneyMeetingContextArgs, _tool_build_money_meeting_agenda)
    registry.register("create_accounting_question", AccountingQuestionArgs, _tool_create_accounting_question)
    return registry


async def _check_agent_rate_limit(db: AsyncSession, *, user_id: uuid.UUID) -> None:
    """Reject agent calls when a user exceeds the configured per-window quota.

    Counts existing prompt audit rows for this user — those are written by the
    agent on every call, so reusing them avoids a dedicated rate-limit table.
    """
    settings = get_settings()
    since = utcnow() - timedelta(seconds=settings.agent_rate_limit_window_seconds)
    recent = (
        await db.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.user_id == user_id,
                AuditLog.action == "prompt",
                AuditLog.object_type == "agent",
                AuditLog.created_at >= since,
            )
        )
    ).scalar_one()
    if recent >= settings.agent_rate_limit_attempts:
        raise RateLimitError(
            "Too many agent requests. Try again shortly.",
            code="agent_rate_limited",
            details={
                "window_seconds": settings.agent_rate_limit_window_seconds,
                "limit": settings.agent_rate_limit_attempts,
            },
        )


class AgentService:
    def __init__(
        self,
        *,
        tool_registry: ToolRegistry | None = None,
        policy_engine: PolicyEngine | None = None,
        confirmation_engine: ConfirmationEngine | None = None,
        audit_logger: AgentAuditLogger | None = None,
        skill_planner: SkillPlanner | None = None,
    ) -> None:
        self.tool_registry = tool_registry or build_tool_registry()
        self.policy_engine = policy_engine or PolicyEngine()
        self.confirmation_engine = confirmation_engine or ConfirmationEngine()
        self.audit_logger = audit_logger or AgentAuditLogger()
        self.skill_planner = skill_planner or SkillPlanner()
        _openai_provider = OpenAIProvider(tool_registry=self.tool_registry)
        self.providers: dict[str, LLMProvider] = {
            "heuristic": HeuristicProvider(),
            "openai": _openai_provider,
            "anthropic": AnthropicProvider(tool_registry=self.tool_registry),
            "gemini": GeminiProvider(),
        }

    async def chat(self, db: AsyncSession, *, me: CurrentUser, payload: AgentChatRequest) -> AgentChatResponse:
        ctx = ToolContext(db=db, me=me, request=payload)
        await _check_agent_rate_limit(db, user_id=me.id)
        await self.audit_logger.log_prompt(ctx)

        settings_row = await get_or_create_user_settings(db, user=me.user)
        configured_provider = settings_row.ai_provider or payload.provider
        configured_model = settings_row.ai_model or None
        configured_api_key = self._decrypt_user_api_key(settings_row.ai_api_key_encrypted)

        provider_name = configured_provider
        if provider_name == "openai" or (provider_name is None and os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY")):
            provider_name = "openai"
        elif provider_name == "anthropic" or (provider_name is None and os.getenv("ANTHROPIC_API_KEY")):
            provider_name = "anthropic"
        elif provider_name not in self.providers:
            provider_name = "heuristic"

        provider = self.providers.get(provider_name, self.providers["heuristic"])
        tool_calls: list[AgentToolCallOut] = []
        pending_confirmations: list[PendingConfirmationOut] = []
        disclaimers: list[str] = []

        if provider_name == "gemini":
            disclaimers.append(
                "Gemini provider is not yet fully integrated. Responses use the heuristic fallback."
            )

        # Inject relevant memories into conversation context before planning
        try:
            relevant_memories = await list_memories(
                db, tenant_id=me.tenant_id, query=payload.message, limit=4
            )
            if relevant_memories:
                memory_lines = "\n".join(
                    f"- [{m.memory_type.value}] {m.title}: {m.summary or m.content[:200]}"
                    for m in relevant_memories
                )
                memory_context = ConversationMessage(
                    role="assistant",
                    content=f"[Relevant memories from your profile]\n{memory_lines}",
                )
                payload = payload.model_copy(
                    update={"conversation_history": [memory_context, *payload.conversation_history]}
                )
        except Exception:
            log.debug("Memory injection skipped", exc_info=True)

        for confirmation in payload.confirmations:
            tool_calls.append(
                await self._execute_tool(
                    ctx,
                    tool_name=confirmation.tool_name,
                    arguments=confirmation.arguments,
                    confirmation_mode=True,
                    pending_confirmations=pending_confirmations,
                )
            )

        suggested_tools = self.skill_planner.suggest(payload.message)
        if suggested_tools:
            log.debug("SkillPlanner suggests: %s", suggested_tools)

        provider_message, planned, provider_disclaimers = await provider.plan(
            payload,
            api_key=configured_api_key,
            model=configured_model,
            suggested_tools=suggested_tools,
        )
        disclaimers.extend(provider_disclaimers)
        for planned_call in planned:
            tool_calls.append(
                await self._execute_tool(
                    ctx,
                    tool_name=planned_call.tool_name,
                    arguments=planned_call.arguments,
                    confirmation_mode=False,
                    pending_confirmations=pending_confirmations,
                )
            )

        message = self._compose_message(provider_message, tool_calls, pending_confirmations)
        if any(call.tool_name == "suggest_investment_allocation" for call in tool_calls):
            disclaimers.append("Educational only. This is not legal, tax, or investment advice.")

        return AgentChatResponse(
            message=message,
            provider=provider.name,
            tool_calls=tool_calls,
            pending_confirmations=pending_confirmations,
            disclaimers=list(dict.fromkeys(disclaimers)),
        )

    @staticmethod
    def _decrypt_user_api_key(ciphertext: bytes | None) -> str | None:
        if ciphertext is None:
            return None
        try:
            return decrypt_secret(ciphertext)
        except Exception:
            log.warning("Unable to decrypt stored AI provider API key; ignoring configured key", exc_info=True)
            return None

    async def _execute_tool(
        self,
        ctx: ToolContext,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        confirmation_mode: bool,
        pending_confirmations: list[PendingConfirmationOut],
    ) -> AgentToolCallOut:
        try:
            self.policy_engine.check(tool_name)
            if self.confirmation_engine.requires_confirmation(tool_name) and not confirmation_mode:
                call = AgentToolCallOut(
                    tool_name=tool_name,
                    status="confirmation_required",
                    arguments=arguments,
                    result=None,
                    error=None,
                )
                pending_confirmations.append(
                    PendingConfirmationOut(
                        tool_name=tool_name,
                        reason=f"{tool_name} is sensitive and requires confirmation.",
                        arguments=arguments,
                    )
                )
                await self.audit_logger.log_tool_call(
                    ctx,
                    tool_name=tool_name,
                    arguments=arguments,
                    result={"status": "confirmation_required"},
                )
                return call

            result = await self.tool_registry.execute(tool_name, arguments, ctx)
            status = "completed"
            if result.get("status") == "not_implemented":
                status = "not_implemented"
            if post_confirmation := result.get("post_confirmation"):
                pending_confirmations.append(PendingConfirmationOut.model_validate(post_confirmation))
            await self.audit_logger.log_tool_call(
                ctx,
                tool_name=tool_name,
                arguments=arguments,
                result=result,
            )
            return AgentToolCallOut(
                tool_name=tool_name,
                status=status,
                arguments=arguments,
                result=result,
                error=None,
            )
        except MIAFError as exc:
            await self.audit_logger.log_tool_call(
                ctx,
                tool_name=tool_name,
                arguments=arguments,
                error=exc.message,
            )
            return AgentToolCallOut(
                tool_name=tool_name,
                status="blocked",
                arguments=arguments,
                result=None,
                error=exc.message,
            )

    def _compose_message(
        self,
        provider_message: str,
        tool_calls: list[AgentToolCallOut],
        pending_confirmations: list[PendingConfirmationOut],
    ) -> str:
        base = provider_message.strip()
        if base:
            base = f"{AGENT_INTRO} {base}"
        else:
            base = AGENT_INTRO
        if pending_confirmations:
            return base + " I prepared the draft action and left the sensitive step pending confirmation."
        if tool_calls:
            completed = [call.tool_name for call in tool_calls if call.status == "completed"]
            if completed:
                return base + f" Completed: {', '.join(completed)}."
        return base
