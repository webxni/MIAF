"use client";

import { useEffect, useState } from "react";

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
  investment_value: string;
  spending_by_category: Array<{ account_name: string; amount: string }>;
  goal_progress: Array<{ name: string; progress_ratio: string; current_amount: string; target_amount: string }>;
};

export default function PersonalPage() {
  const [entity, setEntity] = useState<Entity | null>(null);
  const [dashboard, setDashboard] = useState<PersonalDashboard | null>(null);

  useEffect(() => {
    let active = true;
    entities()
      .then(async (items) => {
        const nextEntity = items.find((item) => item.mode === "personal") ?? null;
        if (!active || !nextEntity) return;
        setEntity(nextEntity);
        const result = await apiFetch<PersonalDashboard>(`/entities/${nextEntity.id}/personal/dashboard`);
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
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--accent)]">Personal</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">{entity?.name ?? "Personal dashboard"}</h1>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Net worth" value={dashboard?.net_worth ?? "—"} />
        <StatCard label="Savings rate" value={dashboard?.savings_rate ?? "—"} />
        <StatCard label="Emergency fund months" value={dashboard?.emergency_fund_months ?? "—"} />
        <StatCard label="Investment value" value={dashboard?.investment_value ?? "—"} />
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <SectionCard title="Spending by category">
          <div className="space-y-3">
            {dashboard?.spending_by_category?.map((row) => (
              <div key={row.account_name} className="flex items-center justify-between rounded-xl bg-[var(--surface)] px-4 py-3 text-sm">
                <span>{row.account_name}</span>
                <span className="font-semibold">{row.amount}</span>
              </div>
            )) ?? <p className="text-sm text-[var(--muted)]">Loading…</p>}
          </div>
        </SectionCard>
        <SectionCard title="Goal progress">
          <div className="space-y-3">
            {dashboard?.goal_progress?.map((row) => (
              <div key={row.name} className="rounded-xl bg-[var(--surface)] px-4 py-3 text-sm">
                <div className="flex items-center justify-between">
                  <span>{row.name}</span>
                  <span className="font-semibold">{row.progress_ratio}</span>
                </div>
                <p className="mt-1 text-[var(--muted)]">
                  {row.current_amount} of {row.target_amount}
                </p>
              </div>
            )) ?? <p className="text-sm text-[var(--muted)]">Loading…</p>}
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
