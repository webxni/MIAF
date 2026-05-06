"use client";

import { useEffect, useState } from "react";

import { SectionCard, StatCard } from "../../../_components/cards";
import {
  entities,
  findEntityByMode,
  listBills,
  type Bill,
  type Entity,
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

export default function BusinessBillsPage() {
  const [entity, setEntity] = useState<Entity | null>(null);
  const [bills, setBills] = useState<Bill[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    entities()
      .then(async (items) => {
        if (!active) return;
        const next = findEntityByMode(items, "business");
        setEntity(next);
        if (!next) return;
        const list = await listBills(next.id);
        if (active) setBills(list);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "Failed to load bills");
      });
    return () => {
      active = false;
    };
  }, []);

  const open = bills?.filter((b) => Number(b.balance_due) > 0) ?? [];
  const outstanding = sumDecimal(open.map((b) => b.balance_due));
  const today = new Date().toISOString().slice(0, 10);
  const overdue = bills?.filter((b) => b.due_date < today && Number(b.balance_due) > 0).length ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--accent)]">Business</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">Bills</h1>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Read-only view. Posting a bill requires confirmation via{" "}
          <code>POST /api/entities/:id/business/bills/:id/post</code>.
        </p>
      </div>

      {error ? (
        <div className="rounded-xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger-ink)]">
          {error}
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="Bills on file" value={bills ? String(bills.length) : "—"} />
        <StatCard label="Outstanding AP" value={bills ? outstanding : "—"} />
        <StatCard
          label="Overdue"
          value={bills ? String(overdue) : "—"}
          note={bills && overdue > 0 ? "Past due date with balance" : undefined}
        />
      </div>

      <SectionCard title="All bills" description="Most recent first.">
        {!entity ? (
          <p className="text-sm text-[var(--muted)]">No business entity available.</p>
        ) : !bills ? (
          <p className="text-sm text-[var(--muted)]">Loading…</p>
        ) : bills.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">No bills yet.</p>
        ) : (
          <div className="space-y-2">
            <div className="grid grid-cols-[8rem_1fr_repeat(4,minmax(0,6.5rem))] gap-2 px-2 text-xs uppercase tracking-[0.2em] text-[var(--muted)]">
              <span>Number</span>
              <span>Vendor</span>
              <span className="text-right">Date</span>
              <span className="text-right">Due</span>
              <span className="text-right">Total</span>
              <span className="text-right">Balance</span>
            </div>
            {[...bills]
              .sort((a, b) => (a.bill_date < b.bill_date ? 1 : -1))
              .map((bill) => {
                const past = bill.due_date < today && Number(bill.balance_due) > 0;
                return (
                  <div
                    key={bill.id}
                    className={`grid grid-cols-[8rem_1fr_repeat(4,minmax(0,6.5rem))] items-center gap-2 rounded-xl bg-[var(--surface)] px-3 py-2 text-sm ${
                      past ? "border border-[var(--danger-line)]" : ""
                    }`}
                  >
                    <span className="font-medium">{bill.number}</span>
                    <span className="flex items-center gap-2 text-[var(--muted)]">
                      <span className={`rounded-full px-2 py-0.5 text-xs uppercase tracking-[0.2em] ${statusBadge(bill.status)}`}>
                        {bill.status}
                      </span>
                      <span className="truncate">{bill.memo ?? bill.vendor_id.slice(0, 8)}</span>
                    </span>
                    <span className="text-right">{bill.bill_date}</span>
                    <span className={`text-right ${past ? "text-[var(--danger-ink)] font-semibold" : ""}`}>
                      {bill.due_date}
                    </span>
                    <span className="text-right">{bill.total}</span>
                    <span className="text-right font-semibold">{bill.balance_due}</span>
                  </div>
                );
              })}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
