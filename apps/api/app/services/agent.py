from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.errors import FinClawError, NotFoundError
from app.models import Account, Customer, Entity, EntityMember, EntityMode
from app.schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    AgentToolCallOut,
    CashFlowArgs,
    CreateInvoiceArgs,
    CreateJournalEntryDraftArgs,
    CreatePersonalExpenseArgs,
    ExplainTransactionArgs,
    MemoryArgs,
    PendingConfirmationOut,
    PostJournalEntryArgs,
    StatementArgs,
    SuggestEmergencyFundPlanArgs,
    SuggestInvestmentAllocationArgs,
    SummaryArgs,
    ToolConfirmationIn,
)
from app.schemas.business import CustomerCreate, InvoiceCreate
from app.schemas.journal import JournalEntryCreate, JournalEntryOut, JournalLineIn
from app.services.audit import write_audit
from app.services.business import (
    balance_sheet,
    business_dashboard,
    cash_flow_statement,
    create_customer,
    create_invoice,
    income_statement,
)
from app.services.entities import list_entities_for_user
from app.services.journal import create_draft, get_entry_scoped, post_entry
from app.services.personal import personal_dashboard


_MONEY_RE = re.compile(r"\$?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)")
_SALE_RE = re.compile(
    r"(?:sold|vendi[oó]|vendio|vendi)\s+\$?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s+(?:to|a)\s+(.+)",
    re.IGNORECASE,
)


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


def _category_to_code(text: str) -> str:
    normalized = text.lower()
    if any(token in normalized for token in ("gas", "gasolina", "uber", "lyft", "transport", "fuel")):
        return "5300"
    if any(token in normalized for token in ("food", "restaurant", "cafe", "coffee", "grocer", "dinner")):
        return "5200"
    if any(token in normalized for token in ("rent", "housing", "mortgage")):
        return "5100"
    if any(token in normalized for token in ("electric", "water", "utility", "internet")):
        return "5400"
    return "5900"


@dataclass
class ToolContext:
    db: AsyncSession
    me: CurrentUser
    request: AgentChatRequest


@dataclass
class PlannedToolCall:
    tool_name: str
    arguments: dict[str, Any]


class LLMProvider:
    name = "base"

    async def plan(self, request: AgentChatRequest) -> tuple[str, list[PlannedToolCall], list[str]]:
        raise NotImplementedError


class HeuristicProvider(LLMProvider):
    name = "heuristic"

    async def plan(self, request: AgentChatRequest) -> tuple[str, list[PlannedToolCall], list[str]]:
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


class OpenAIProvider(HeuristicProvider):
    name = "openai"


class AnthropicProvider(HeuristicProvider):
    name = "anthropic"


class GeminiProvider(HeuristicProvider):
    name = "gemini"


class PolicyEngine:
    def check(self, tool_name: str) -> None:
        if tool_name in {"move_money", "execute_trade", "place_trade"}:
            raise FinClawError(
                "FinClaw cannot move real money or execute trades",
                code="policy_blocked",
            )


class ConfirmationEngine:
    _sensitive = {"post_journal_entry", "record_invoice_payment", "record_bill_payment"}

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
        self._tools: dict[str, tuple[type, Any]] = {}

    def register(self, name: str, schema: type, handler) -> None:
        self._tools[name] = (schema, handler)

    async def execute(self, name: str, raw_arguments: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        if name not in self._tools:
            raise NotFoundError(f"Tool {name} not found", code="tool_not_found")
        schema, handler = self._tools[name]
        payload = schema.model_validate(raw_arguments)
        return await handler(ctx, payload)


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
        "risk_disclaimer": "Educational only. FinClaw does not execute trades or guarantee returns.",
    }


async def _tool_explain_transaction(ctx: ToolContext, args: ExplainTransactionArgs) -> dict[str, Any]:
    return {
        "explanation": (
            "Transactions are explained from deterministic accounting rules. "
            f"Description received: {args.description}"
        )
    }


async def _tool_not_implemented(_: ToolContext, __) -> dict[str, Any]:
    return {"status": "not_implemented", "message": "This tool is reserved for a later phase."}


def build_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register("create_journal_entry_draft", CreateJournalEntryDraftArgs, _tool_create_journal_entry_draft)
    registry.register("post_journal_entry", PostJournalEntryArgs, _tool_post_journal_entry)
    registry.register("create_personal_expense", CreatePersonalExpenseArgs, _tool_create_personal_expense)
    registry.register("create_business_expense", CreatePersonalExpenseArgs, _tool_not_implemented)
    registry.register("create_invoice", CreateInvoiceArgs, _tool_create_invoice)
    registry.register("record_invoice_payment", PostJournalEntryArgs, _tool_not_implemented)
    registry.register("create_bill", CreateInvoiceArgs, _tool_not_implemented)
    registry.register("record_bill_payment", PostJournalEntryArgs, _tool_not_implemented)
    registry.register("get_personal_summary", SummaryArgs, _tool_get_personal_summary)
    registry.register("get_business_summary", SummaryArgs, _tool_get_business_summary)
    registry.register("get_balance_sheet", StatementArgs, _tool_get_balance_sheet)
    registry.register("get_income_statement", CashFlowArgs, _tool_get_income_statement)
    registry.register("get_cash_flow", CashFlowArgs, _tool_get_cash_flow)
    registry.register("create_budget", MemoryArgs, _tool_not_implemented)
    registry.register("create_goal", MemoryArgs, _tool_not_implemented)
    registry.register("create_debt_plan", MemoryArgs, _tool_not_implemented)
    registry.register("suggest_emergency_fund_plan", SuggestEmergencyFundPlanArgs, _tool_suggest_emergency_fund_plan)
    registry.register("suggest_investment_allocation", SuggestInvestmentAllocationArgs, _tool_suggest_investment_allocation)
    registry.register("classify_transaction", ExplainTransactionArgs, _tool_not_implemented)
    registry.register("explain_transaction", ExplainTransactionArgs, _tool_explain_transaction)
    registry.register("search_memory", MemoryArgs, _tool_not_implemented)
    registry.register("add_memory", MemoryArgs, _tool_not_implemented)
    return registry


class AgentService:
    def __init__(
        self,
        *,
        tool_registry: ToolRegistry | None = None,
        policy_engine: PolicyEngine | None = None,
        confirmation_engine: ConfirmationEngine | None = None,
        audit_logger: AgentAuditLogger | None = None,
    ) -> None:
        self.tool_registry = tool_registry or build_tool_registry()
        self.policy_engine = policy_engine or PolicyEngine()
        self.confirmation_engine = confirmation_engine or ConfirmationEngine()
        self.audit_logger = audit_logger or AgentAuditLogger()
        self.providers: dict[str, LLMProvider] = {
            "heuristic": HeuristicProvider(),
            "openai": OpenAIProvider(),
            "anthropic": AnthropicProvider(),
            "gemini": GeminiProvider(),
        }

    async def chat(self, db: AsyncSession, *, me: CurrentUser, payload: AgentChatRequest) -> AgentChatResponse:
        ctx = ToolContext(db=db, me=me, request=payload)
        await self.audit_logger.log_prompt(ctx)

        provider = self.providers.get(payload.provider or "heuristic", self.providers["heuristic"])
        tool_calls: list[AgentToolCallOut] = []
        pending_confirmations: list[PendingConfirmationOut] = []
        disclaimers: list[str] = []

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

        provider_message, planned, provider_disclaimers = await provider.plan(payload)
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
        except FinClawError as exc:
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
        if pending_confirmations:
            return provider_message + " I prepared the draft action and left the sensitive step pending confirmation."
        if tool_calls:
            completed = [call.tool_name for call in tool_calls if call.status == "completed"]
            if completed:
                return provider_message + f" Completed: {', '.join(completed)}."
        return provider_message

