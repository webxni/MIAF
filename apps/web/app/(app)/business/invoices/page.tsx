"use client";

import { useEffect, useState } from "react";

import { SectionCard, StatCard } from "../../../_components/cards";
import {
  entities,
  findEntityByMode,
  listInvoices,
  type Entity,
  type Invoice,
} from "../../../_lib/api";

function statusBadge(status: string): string {
  switch (status) {
    case "draft":
      return "bg-[var(--panel)] text-[var(--muted)]";
    case "posted":
      return "bg-[var(--accent)] text-[var(--accent-ink)]";
    case "partial":
      return "bg-[var(--accent)]/40 text-[var(--ink)]";
    case "paid":
      return "bg-emerald-500/20 text-emerald-300";
    case "void":
      return "bg-[var(--danger-bg)] text-[var(--danger-ink)]";
    default:
      return "bg-[var(--panel)] text-[var(--muted)]";
  }
}

function sumDecimal(values: string[]): string {
  return values.reduce((acc, v) => acc + Number(v ?? 0), 0).toFixed(2);
}

export default function BusinessInvoicesPage() {
  const [entity, setEntity] = useState<Entity | null>(null);
  const [invoices, setInvoices] = useState<Invoice[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    entities()
      .then(async (items) => {
        if (!active) return;
        const next = findEntityByMode(items, "business");
        setEntity(next);
        if (!next) return;
        const list = await listInvoices(next.id);
        if (active) setInvoices(list);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "Failed to load invoices");
      });
    return () => {
      active = false;
    };
  }, []);

  const open = invoices?.filter((i) => Number(i.balance_due) > 0) ?? [];
  const outstanding = sumDecimal(open.map((i) => i.balance_due));

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--accent)]">Business</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">Invoices</h1>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Read-only view. Posting an invoice requires confirmation via{" "}
          <code>POST /api/entities/:id/business/invoices/:id/post</code>.
        </p>
      </div>

      {error ? (
        <div className="rounded-xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger-ink)]">
          {error}
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="Invoices on file" value={invoices ? String(invoices.length) : "—"} />
        <StatCard label="Open invoices" value={invoices ? String(open.length) : "—"} />
        <StatCard label="Outstanding AR" value={invoices ? outstanding : "—"} />
      </div>

      <SectionCard title="All invoices" description="Most recent first.">
        {!entity ? (
          <p className="text-sm text-[var(--muted)]">No business entity available.</p>
        ) : !invoices ? (
          <p className="text-sm text-[var(--muted)]">Loading…</p>
        ) : invoices.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">No invoices yet.</p>
        ) : (
          <div className="space-y-2">
            <div className="grid grid-cols-[8rem_1fr_repeat(4,minmax(0,6.5rem))] gap-2 px-2 text-xs uppercase tracking-[0.2em] text-[var(--muted)]">
              <span>Number</span>
              <span>Customer</span>
              <span className="text-right">Date</span>
              <span className="text-right">Due</span>
              <span className="text-right">Total</span>
              <span className="text-right">Balance</span>
            </div>
            {[...invoices]
              .sort((a, b) => (a.invoice_date < b.invoice_date ? 1 : -1))
              .map((invoice) => (
                <div
                  key={invoice.id}
                  className="grid grid-cols-[8rem_1fr_repeat(4,minmax(0,6.5rem))] items-center gap-2 rounded-xl bg-[var(--surface)] px-3 py-2 text-sm"
                >
                  <span className="font-medium">{invoice.number}</span>
                  <span className="flex items-center gap-2 text-[var(--muted)]">
                    <span className={`rounded-full px-2 py-0.5 text-xs uppercase tracking-[0.2em] ${statusBadge(invoice.status)}`}>
                      {invoice.status}
                    </span>
                    <span className="truncate">{invoice.memo ?? invoice.customer_id.slice(0, 8)}</span>
                  </span>
                  <span className="text-right">{invoice.invoice_date}</span>
                  <span className="text-right">{invoice.due_date}</span>
                  <span className="text-right">{invoice.total}</span>
                  <span className="text-right font-semibold">{invoice.balance_due}</span>
                </div>
              ))}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
