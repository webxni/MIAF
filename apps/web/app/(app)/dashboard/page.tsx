"use client";

import { useEffect, useMemo, useState } from "react";

import { SectionCard, StatCard } from "../../_components/cards";
import { apiFetch, entities, type Entity } from "../../_lib/api";

type PersonalDashboard = {
  net_worth: string;
  monthly_income: string;
  monthly_expenses: string;
  monthly_savings: string;
  savings_rate: string;
  emergency_fund_months: string;
  total_debt: string;
};

type BusinessDashboard = {
  cash_balance: string;
  accounts_receivable: string;
  accounts_payable: string;
  monthly_revenue: string;
  monthly_expenses: string;
  monthly_net_income: string;
  open_invoices: number;
  open_bills: number;
};

export default function DashboardPage() {
  const [items, setItems] = useState<Entity[]>([]);
  const [personal, setPersonal] = useState<PersonalDashboard | null>(null);
  const [business, setBusiness] = useState<BusinessDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    entities()
      .then(async (nextEntities) => {
        if (!active) return;
        setItems(nextEntities);
        const personalEntity = nextEntities.find((entity) => entity.mode === "personal");
        const businessEntity = nextEntities.find((entity) => entity.mode === "business");
        const tasks: Promise<void>[] = [];
        if (personalEntity) {
          tasks.push(
            apiFetch<PersonalDashboard>(`/entities/${personalEntity.id}/personal/dashboard`).then((result) => {
              if (active) setPersonal(result);
            }),
          );
        }
        if (businessEntity) {
          tasks.push(
            apiFetch<BusinessDashboard>(`/entities/${businessEntity.id}/business/dashboard`).then((result) => {
              if (active) setBusiness(result);
            }),
          );
        }
        await Promise.all(tasks);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load dashboard");
      });
    return () => {
      active = false;
    };
  }, []);

  const stats = useMemo(() => {
    return [
      { label: "Entities", value: String(items.length), note: "Personal and business contexts" },
      { label: "Personal net worth", value: personal?.net_worth ?? "—", note: "From ledger-backed KPI service" },
      { label: "Business cash", value: business?.cash_balance ?? "—", note: "Operating bank balance" },
      { label: "Business net income", value: business?.monthly_net_income ?? "—", note: "Current month" },
    ];
  }, [items.length, personal?.net_worth, business?.cash_balance, business?.monthly_net_income]);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--accent)]">Overview</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">Unified dashboard</h1>
        <p className="mt-3 max-w-3xl text-sm text-[var(--muted)]">
          This screen combines the personal and business dashboards already exposed by the API so
          you can move between both modes without losing the shared financial context.
        </p>
      </div>

      {error ? (
        <div className="rounded-2xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-5 py-4 text-sm text-[var(--danger-ink)]">
          {error}
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {stats.map((item) => (
          <StatCard key={item.label} label={item.label} value={item.value} note={item.note} />
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <SectionCard title="Personal mode" description="Deterministic KPIs from the personal dashboard endpoint.">
          {personal ? (
            <dl className="grid gap-3 text-sm md:grid-cols-2">
              <div><dt className="text-[var(--muted)]">Income</dt><dd className="text-lg font-semibold">{personal.monthly_income}</dd></div>
              <div><dt className="text-[var(--muted)]">Expenses</dt><dd className="text-lg font-semibold">{personal.monthly_expenses}</dd></div>
              <div><dt className="text-[var(--muted)]">Savings</dt><dd className="text-lg font-semibold">{personal.monthly_savings}</dd></div>
              <div><dt className="text-[var(--muted)]">Savings rate</dt><dd className="text-lg font-semibold">{personal.savings_rate}</dd></div>
              <div><dt className="text-[var(--muted)]">Emergency fund months</dt><dd className="text-lg font-semibold">{personal.emergency_fund_months}</dd></div>
              <div><dt className="text-[var(--muted)]">Debt</dt><dd className="text-lg font-semibold">{personal.total_debt}</dd></div>
            </dl>
          ) : (
            <p className="text-sm text-[var(--muted)]">Loading personal dashboard…</p>
          )}
        </SectionCard>

        <SectionCard title="Business mode" description="Business KPI summary from Phase 3 report endpoints.">
          {business ? (
            <dl className="grid gap-3 text-sm md:grid-cols-2">
              <div><dt className="text-[var(--muted)]">Revenue</dt><dd className="text-lg font-semibold">{business.monthly_revenue}</dd></div>
              <div><dt className="text-[var(--muted)]">Expenses</dt><dd className="text-lg font-semibold">{business.monthly_expenses}</dd></div>
              <div><dt className="text-[var(--muted)]">AR</dt><dd className="text-lg font-semibold">{business.accounts_receivable}</dd></div>
              <div><dt className="text-[var(--muted)]">AP</dt><dd className="text-lg font-semibold">{business.accounts_payable}</dd></div>
              <div><dt className="text-[var(--muted)]">Open invoices</dt><dd className="text-lg font-semibold">{business.open_invoices}</dd></div>
              <div><dt className="text-[var(--muted)]">Open bills</dt><dd className="text-lg font-semibold">{business.open_bills}</dd></div>
            </dl>
          ) : (
            <p className="text-sm text-[var(--muted)]">Loading business dashboard…</p>
          )}
        </SectionCard>
      </div>
    </div>
  );
}
