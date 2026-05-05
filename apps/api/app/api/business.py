from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import DB, CurrentUserDep, RequestCtx, require_reader, require_writer
from app.models import Entity, EntityMember
from app.schemas.business import (
    AgingReportOut,
    BalanceSheetOut,
    BillCreate,
    BillOut,
    BillUpdate,
    BusinessDashboardOut,
    CashFlowOut,
    ClosingChecklistOut,
    ClosingPeriodCreate,
    ClosingPeriodOut,
    ConfirmPostRequest,
    CustomerCreate,
    CustomerOut,
    CustomerUpdate,
    IncomeStatementOut,
    InvoiceCreate,
    InvoiceOut,
    InvoiceUpdate,
    PaymentCreate,
    PaymentOut,
    TaxRateCreate,
    TaxRateOut,
    TaxReserveCreate,
    TaxReserveOut,
    VendorCreate,
    VendorOut,
    VendorUpdate,
)
from app.services.audit import write_audit
from app.services.business import (
    ap_aging,
    ar_aging,
    balance_sheet,
    business_dashboard,
    cash_flow_statement,
    closing_checklist,
    create_bill,
    create_closing_period,
    create_customer,
    create_invoice,
    create_tax_rate,
    create_tax_reserve,
    create_vendor,
    delete_customer,
    delete_vendor,
    get_bill,
    get_customer,
    get_invoice,
    get_vendor,
    income_statement,
    list_bills,
    list_closing_periods,
    list_customers,
    list_invoices,
    list_payments,
    list_tax_rates,
    list_tax_reserves,
    list_vendors,
    post_bill,
    post_invoice,
    record_payment,
    update_bill,
    update_customer,
    update_invoice,
    update_vendor,
)

router = APIRouter(prefix="/entities/{entity_id}/business", tags=["business"])


def _obj_dict(obj, fields: list[str]) -> dict:
    out = {}
    for field in fields:
        value = getattr(obj, field)
        out[field] = value.isoformat() if hasattr(value, "isoformat") else (str(value) if value is not None else None)
    return out


@router.get("/dashboard", response_model=BusinessDashboardOut)
async def dashboard_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
    as_of: date = Query(default_factory=date.today),
) -> BusinessDashboardOut:
    return await business_dashboard(db, entity_id=entity_id, as_of=as_of)


@router.get("/customers", response_model=list[CustomerOut])
async def list_customers_endpoint(
    entity_id: uuid.UUID, db: DB, scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)]
) -> list[CustomerOut]:
    return [CustomerOut.model_validate(item) for item in await list_customers(db, entity_id=entity_id)]


@router.post("/customers", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
async def create_customer_endpoint(
    entity_id: uuid.UUID,
    payload: CustomerCreate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> CustomerOut:
    row = await create_customer(db, entity_id=entity_id, payload=payload)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="create", object_type="customer", object_id=row.id, after=_obj_dict(row, ["name", "email", "is_active"]), ip=ctx.ip, user_agent=ctx.user_agent)
    return CustomerOut.model_validate(row)


@router.patch("/customers/{customer_id}", response_model=CustomerOut)
async def update_customer_endpoint(
    entity_id: uuid.UUID,
    customer_id: uuid.UUID,
    payload: CustomerUpdate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> CustomerOut:
    row = await get_customer(db, entity_id=entity_id, customer_id=customer_id)
    before = _obj_dict(row, ["name", "email", "is_active"])
    row = await update_customer(db, row, payload=payload)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="update", object_type="customer", object_id=row.id, before=before, after=_obj_dict(row, ["name", "email", "is_active"]), ip=ctx.ip, user_agent=ctx.user_agent)
    return CustomerOut.model_validate(row)


@router.delete("/customers/{customer_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_customer_endpoint(
    entity_id: uuid.UUID,
    customer_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> Response:
    row = await get_customer(db, entity_id=entity_id, customer_id=customer_id)
    before = _obj_dict(row, ["name", "email", "is_active"])
    await delete_customer(db, row)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="delete", object_type="customer", object_id=customer_id, before=before, ip=ctx.ip, user_agent=ctx.user_agent)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/vendors", response_model=list[VendorOut])
async def list_vendors_endpoint(
    entity_id: uuid.UUID, db: DB, scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)]
) -> list[VendorOut]:
    return [VendorOut.model_validate(item) for item in await list_vendors(db, entity_id=entity_id)]


@router.post("/vendors", response_model=VendorOut, status_code=status.HTTP_201_CREATED)
async def create_vendor_endpoint(
    entity_id: uuid.UUID,
    payload: VendorCreate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> VendorOut:
    row = await create_vendor(db, entity_id=entity_id, payload=payload)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="create", object_type="vendor", object_id=row.id, after=_obj_dict(row, ["name", "email", "is_active"]), ip=ctx.ip, user_agent=ctx.user_agent)
    return VendorOut.model_validate(row)


@router.patch("/vendors/{vendor_id}", response_model=VendorOut)
async def update_vendor_endpoint(
    entity_id: uuid.UUID,
    vendor_id: uuid.UUID,
    payload: VendorUpdate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> VendorOut:
    row = await get_vendor(db, entity_id=entity_id, vendor_id=vendor_id)
    before = _obj_dict(row, ["name", "email", "is_active"])
    row = await update_vendor(db, row, payload=payload)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="update", object_type="vendor", object_id=row.id, before=before, after=_obj_dict(row, ["name", "email", "is_active"]), ip=ctx.ip, user_agent=ctx.user_agent)
    return VendorOut.model_validate(row)


@router.delete("/vendors/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_vendor_endpoint(
    entity_id: uuid.UUID,
    vendor_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> Response:
    row = await get_vendor(db, entity_id=entity_id, vendor_id=vendor_id)
    before = _obj_dict(row, ["name", "email", "is_active"])
    await delete_vendor(db, row)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="delete", object_type="vendor", object_id=vendor_id, before=before, ip=ctx.ip, user_agent=ctx.user_agent)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/invoices", response_model=list[InvoiceOut])
async def list_invoices_endpoint(
    entity_id: uuid.UUID, db: DB, scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)]
) -> list[InvoiceOut]:
    return [InvoiceOut.model_validate(item) for item in await list_invoices(db, entity_id=entity_id)]


@router.post("/invoices", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
async def create_invoice_endpoint(
    entity_id: uuid.UUID,
    payload: InvoiceCreate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> InvoiceOut:
    row = await create_invoice(db, entity_id=entity_id, payload=payload)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="create", object_type="invoice", object_id=row.id, after=_obj_dict(row, ["number", "invoice_date", "due_date", "status", "total", "balance_due"]), ip=ctx.ip, user_agent=ctx.user_agent)
    return InvoiceOut.model_validate(row)


@router.patch("/invoices/{invoice_id}", response_model=InvoiceOut)
async def update_invoice_endpoint(
    entity_id: uuid.UUID,
    invoice_id: uuid.UUID,
    payload: InvoiceUpdate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> InvoiceOut:
    row = await get_invoice(db, entity_id=entity_id, invoice_id=invoice_id)
    before = _obj_dict(row, ["number", "invoice_date", "due_date", "status", "total", "balance_due"])
    row = await update_invoice(db, row, payload=payload)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="update", object_type="invoice", object_id=row.id, before=before, after=_obj_dict(row, ["number", "invoice_date", "due_date", "status", "total", "balance_due"]), ip=ctx.ip, user_agent=ctx.user_agent)
    return InvoiceOut.model_validate(row)


@router.post("/invoices/{invoice_id}/post", response_model=InvoiceOut)
async def post_invoice_endpoint(
    entity_id: uuid.UUID,
    invoice_id: uuid.UUID,
    payload: ConfirmPostRequest,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> InvoiceOut:
    row = await get_invoice(db, entity_id=entity_id, invoice_id=invoice_id)
    before = _obj_dict(row, ["status", "balance_due"])
    row = await post_invoice(db, row, user_id=me.id, confirmed=payload.confirmed)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="post", object_type="invoice", object_id=row.id, before=before, after=_obj_dict(row, ["status", "balance_due", "posted_entry_id"]), ip=ctx.ip, user_agent=ctx.user_agent)
    return InvoiceOut.model_validate(row)


@router.get("/bills", response_model=list[BillOut])
async def list_bills_endpoint(
    entity_id: uuid.UUID, db: DB, scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)]
) -> list[BillOut]:
    return [BillOut.model_validate(item) for item in await list_bills(db, entity_id=entity_id)]


@router.post("/bills", response_model=BillOut, status_code=status.HTTP_201_CREATED)
async def create_bill_endpoint(
    entity_id: uuid.UUID,
    payload: BillCreate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> BillOut:
    row = await create_bill(db, entity_id=entity_id, payload=payload)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="create", object_type="bill", object_id=row.id, after=_obj_dict(row, ["number", "bill_date", "due_date", "status", "total", "balance_due"]), ip=ctx.ip, user_agent=ctx.user_agent)
    return BillOut.model_validate(row)


@router.patch("/bills/{bill_id}", response_model=BillOut)
async def update_bill_endpoint(
    entity_id: uuid.UUID,
    bill_id: uuid.UUID,
    payload: BillUpdate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> BillOut:
    row = await get_bill(db, entity_id=entity_id, bill_id=bill_id)
    before = _obj_dict(row, ["number", "bill_date", "due_date", "status", "total", "balance_due"])
    row = await update_bill(db, row, payload=payload)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="update", object_type="bill", object_id=row.id, before=before, after=_obj_dict(row, ["number", "bill_date", "due_date", "status", "total", "balance_due"]), ip=ctx.ip, user_agent=ctx.user_agent)
    return BillOut.model_validate(row)


@router.post("/bills/{bill_id}/post", response_model=BillOut)
async def post_bill_endpoint(
    entity_id: uuid.UUID,
    bill_id: uuid.UUID,
    payload: ConfirmPostRequest,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> BillOut:
    row = await get_bill(db, entity_id=entity_id, bill_id=bill_id)
    before = _obj_dict(row, ["status", "balance_due"])
    row = await post_bill(db, row, user_id=me.id, confirmed=payload.confirmed)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="post", object_type="bill", object_id=row.id, before=before, after=_obj_dict(row, ["status", "balance_due", "posted_entry_id"]), ip=ctx.ip, user_agent=ctx.user_agent)
    return BillOut.model_validate(row)


@router.get("/payments", response_model=list[PaymentOut])
async def list_payments_endpoint(
    entity_id: uuid.UUID, db: DB, scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)]
) -> list[PaymentOut]:
    return [PaymentOut.model_validate(item) for item in await list_payments(db, entity_id=entity_id)]


@router.post("/payments", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
async def create_payment_endpoint(
    entity_id: uuid.UUID,
    payload: PaymentCreate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> PaymentOut:
    row = await record_payment(db, entity_id=entity_id, user_id=me.id, payload=payload)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="create", object_type="payment", object_id=row.id, after=_obj_dict(row, ["kind", "payment_date", "amount", "invoice_id", "bill_id", "posted_entry_id"]), ip=ctx.ip, user_agent=ctx.user_agent)
    return PaymentOut.model_validate(row)


@router.get("/reports/ar-aging", response_model=AgingReportOut)
async def ar_aging_endpoint(
    entity_id: uuid.UUID, db: DB, scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)], as_of: date = Query(default_factory=date.today)
) -> AgingReportOut:
    return await ar_aging(db, entity_id=entity_id, as_of=as_of)


@router.get("/reports/ap-aging", response_model=AgingReportOut)
async def ap_aging_endpoint(
    entity_id: uuid.UUID, db: DB, scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)], as_of: date = Query(default_factory=date.today)
) -> AgingReportOut:
    return await ap_aging(db, entity_id=entity_id, as_of=as_of)


@router.get("/reports/balance-sheet", response_model=BalanceSheetOut)
async def balance_sheet_endpoint(
    entity_id: uuid.UUID, db: DB, scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)], as_of: date = Query(default_factory=date.today)
) -> BalanceSheetOut:
    return await balance_sheet(db, entity_id=entity_id, as_of=as_of)


@router.get("/reports/income-statement", response_model=IncomeStatementOut)
async def income_statement_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
    date_from: date,
    date_to: date,
) -> IncomeStatementOut:
    return await income_statement(db, entity_id=entity_id, date_from=date_from, date_to=date_to)


@router.get("/reports/cash-flow", response_model=CashFlowOut)
async def cash_flow_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
    date_from: date,
    date_to: date,
) -> CashFlowOut:
    return await cash_flow_statement(db, entity_id=entity_id, date_from=date_from, date_to=date_to)


@router.get("/reports/closing-checklist", response_model=ClosingChecklistOut)
async def closing_checklist_endpoint(
    entity_id: uuid.UUID, db: DB, scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)], as_of: date = Query(default_factory=date.today)
) -> ClosingChecklistOut:
    return await closing_checklist(db, entity_id=entity_id, as_of=as_of)


@router.get("/tax-rates", response_model=list[TaxRateOut])
async def list_tax_rates_endpoint(
    entity_id: uuid.UUID, db: DB, scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)]
) -> list[TaxRateOut]:
    return [TaxRateOut.model_validate(item) for item in await list_tax_rates(db, entity_id=entity_id)]


@router.post("/tax-rates", response_model=TaxRateOut, status_code=status.HTTP_201_CREATED)
async def create_tax_rate_endpoint(
    entity_id: uuid.UUID,
    payload: TaxRateCreate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> TaxRateOut:
    row = await create_tax_rate(db, entity_id=entity_id, payload=payload)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="create", object_type="tax_rate", object_id=row.id, after=_obj_dict(row, ["name", "jurisdiction", "rate", "is_active"]), ip=ctx.ip, user_agent=ctx.user_agent)
    return TaxRateOut.model_validate(row)


@router.get("/tax-reserves", response_model=list[TaxReserveOut])
async def list_tax_reserves_endpoint(
    entity_id: uuid.UUID, db: DB, scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)]
) -> list[TaxReserveOut]:
    return [TaxReserveOut.model_validate(item) for item in await list_tax_reserves(db, entity_id=entity_id)]


@router.post("/tax-reserves", response_model=TaxReserveOut, status_code=status.HTTP_201_CREATED)
async def create_tax_reserve_endpoint(
    entity_id: uuid.UUID,
    payload: TaxReserveCreate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> TaxReserveOut:
    row = await create_tax_reserve(db, entity_id=entity_id, payload=payload)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="create", object_type="tax_reserve", object_id=row.id, after=_obj_dict(row, ["as_of", "estimated_tax", "reserved_amount"]), ip=ctx.ip, user_agent=ctx.user_agent)
    return TaxReserveOut.model_validate(row)


@router.get("/closing-periods", response_model=list[ClosingPeriodOut])
async def list_closing_periods_endpoint(
    entity_id: uuid.UUID, db: DB, scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)]
) -> list[ClosingPeriodOut]:
    return [ClosingPeriodOut.model_validate(item) for item in await list_closing_periods(db, entity_id=entity_id)]


@router.post("/closing-periods", response_model=ClosingPeriodOut, status_code=status.HTTP_201_CREATED)
async def create_closing_period_endpoint(
    entity_id: uuid.UUID,
    payload: ClosingPeriodCreate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> ClosingPeriodOut:
    row = await create_closing_period(db, entity_id=entity_id, payload=payload)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="create", object_type="closing_period", object_id=row.id, after=_obj_dict(row, ["period_start", "period_end", "status"]), ip=ctx.ip, user_agent=ctx.user_agent)
    return ClosingPeriodOut.model_validate(row)
