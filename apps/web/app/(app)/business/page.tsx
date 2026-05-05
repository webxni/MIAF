"use client";

import { useEffect, useState } from "react";

import { SectionCard, StatCard } from "../../_components/cards";
import { apiFetch, entities, type Entity } from "../../_lib/api";

type BusinessDashboard = {
  cash_balance: string;
  accounts_receivable: string;
  accounts_payable: string;
  monthly_revenue: string;
  monthly_expenses: string;
  monthly_net_income: string;
  open_invoices: number;
  open_bills: number;
  tax_estimate_note: string;
};

export default function BusinessPage() {
  const [entity, setEntity] = useState<Entity | null>(null);
  const [dashboard, setDashboard] = useState<BusinessDashboard | null>(null);

  useEffect(() => {
    let active = true;
    entities()
      .then(async (items) => {
        const nextEntity = items.find((item) => item.mode === "business") ?? null;
        if (!active || !nextEntity) return;
        setEntity(nextEntity);
        const result = await apiFetch<BusinessDashboard>(`/entities/${nextEntity.id}/business/dashboard`);
        if (active) setDashboard(result);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--accent)]">Business</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">{entity?.name ?? "Business dashboard"}</h1>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Cash" value={dashboard?.cash_balance ?? "—"} />
        <StatCard label="Revenue" value={dashboard?.monthly_revenue ?? "—"} />
        <StatCard label="Expenses" value={dashboard?.monthly_expenses ?? "—"} />
        <StatCard label="Net income" value={dashboard?.monthly_net_income ?? "—"} />
      </div>
      <SectionCard title="Working capital">
        {dashboard ? (
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-xl bg-[var(--surface)] px-4 py-3 text-sm">
              <p className="text-[var(--muted)]">Accounts receivable</p>
              <p className="mt-2 text-2xl font-semibold">{dashboard.accounts_receivable}</p>
            </div>
            <div className="rounded-xl bg-[var(--surface)] px-4 py-3 text-sm">
              <p className="text-[var(--muted)]">Accounts payable</p>
              <p className="mt-2 text-2xl font-semibold">{dashboard.accounts_payable}</p>
            </div>
            <div className="rounded-xl bg-[var(--surface)] px-4 py-3 text-sm">
              <p className="text-[var(--muted)]">Open invoices</p>
              <p className="mt-2 text-2xl font-semibold">{dashboard.open_invoices}</p>
            </div>
            <div className="rounded-xl bg-[var(--surface)] px-4 py-3 text-sm">
              <p className="text-[var(--muted)]">Open bills</p>
              <p className="mt-2 text-2xl font-semibold">{dashboard.open_bills}</p>
            </div>
          </div>
        ) : (
          <p className="text-sm text-[var(--muted)]">Loading…</p>
        )}
        {dashboard?.tax_estimate_note ? (
          <div className="mt-4 rounded-xl border border-[var(--warn-line)] bg-[var(--warn-bg)] px-4 py-3 text-sm text-[var(--warn-ink)]">
            {dashboard.tax_estimate_note}
          </div>
        ) : null}
      </SectionCard>
    </div>
  );
}
