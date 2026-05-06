"use client";

import { useEffect, useState } from "react";

import { SectionCard, StatCard } from "../../../_components/cards";
import {
  entities,
  findEntityByMode,
  getBudgetActuals,
  listBudgets,
  type Budget,
  type BudgetActuals,
  type Entity,
} from "../../../_lib/api";

export default function PersonalBudgetPage() {
  const [entity, setEntity] = useState<Entity | null>(null);
  const [budgets, setBudgets] = useState<Budget[] | null>(null);
  const [activeBudget, setActiveBudget] = useState<Budget | null>(null);
  const [actuals, setActuals] = useState<BudgetActuals | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    entities()
      .then(async (items) => {
        if (!active) return;
        const next = findEntityByMode(items, "personal");
        setEntity(next);
        if (!next) return;
        const list = await listBudgets(next.id);
        if (!active) return;
        setBudgets(list);
        const latest = [...list].sort((a, b) =>
          a.period_end < b.period_end ? 1 : -1,
        )[0];
        if (latest) {
          setActiveBudget(latest);
          const data = await getBudgetActuals(next.id, latest.id);
          if (active) setActuals(data);
        }
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "Failed to load budgets");
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--accent)]">Personal</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">Budget workspace</h1>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Read-only view of budgets and current period actuals. Use the API
          (`/api/entities/:id/personal/budgets`) for create/update/delete.
        </p>
      </div>

      {error ? (
        <div className="rounded-xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger-ink)]">
          {error}
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="Budgets defined" value={budgets ? String(budgets.length) : "—"} />
        <StatCard
          label="Active period"
          value={activeBudget ? `${activeBudget.period_start} → ${activeBudget.period_end}` : "—"}
          note={activeBudget?.name}
        />
        <StatCard
          label="Variance (planned − actual)"
          value={actuals?.total_variance ?? "—"}
          note={
            actuals
              ? `Planned ${actuals.total_planned} · actual ${actuals.total_actual}`
              : undefined
          }
        />
      </div>

      <SectionCard
        title={activeBudget ? `Actuals · ${activeBudget.name}` : "Actuals"}
        description="Lines come from posted journal entries against expense accounts within the period."
      >
        {!entity ? (
          <p className="text-sm text-[var(--muted)]">No personal entity available.</p>
        ) : !actuals ? (
          <p className="text-sm text-[var(--muted)]">
            {budgets && budgets.length === 0 ? "No budgets defined yet." : "Loading…"}
          </p>
        ) : (
          <div className="space-y-2">
            <div className="grid grid-cols-[1fr_repeat(3,minmax(0,7rem))] gap-2 px-2 text-xs uppercase tracking-[0.2em] text-[var(--muted)]">
              <span>Account</span>
              <span className="text-right">Planned</span>
              <span className="text-right">Actual</span>
              <span className="text-right">Variance</span>
            </div>
            {actuals.lines.map((row) => (
              <div
                key={row.account_id}
                className={`grid grid-cols-[1fr_repeat(3,minmax(0,7rem))] gap-2 rounded-xl bg-[var(--surface)] px-3 py-2 text-sm ${
                  row.overspent ? "border border-[var(--danger-line)]" : ""
                }`}
              >
                <span>
                  <span className="font-medium">{row.account_code}</span>{" "}
                  <span className="text-[var(--muted)]">{row.account_name}</span>
                </span>
                <span className="text-right">{row.planned_amount}</span>
                <span className="text-right">{row.actual_amount}</span>
                <span
                  className={`text-right font-semibold ${
                    row.overspent ? "text-[var(--danger-ink)]" : ""
                  }`}
                >
                  {row.variance_amount}
                </span>
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      <SectionCard title="All budgets" description="Most recent first.">
        {!budgets ? (
          <p className="text-sm text-[var(--muted)]">Loading…</p>
        ) : budgets.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">No budgets defined yet.</p>
        ) : (
          <div className="space-y-2">
            {[...budgets]
              .sort((a, b) => (a.period_end < b.period_end ? 1 : -1))
              .map((budget) => (
                <div
                  key={budget.id}
                  className="flex items-center justify-between rounded-xl bg-[var(--surface)] px-4 py-3 text-sm"
                >
                  <div>
                    <p className="font-semibold">{budget.name}</p>
                    <p className="text-[var(--muted)]">
                      {budget.period_start} → {budget.period_end} · {budget.lines.length} line
                      {budget.lines.length === 1 ? "" : "s"}
                    </p>
                  </div>
                  <span className="rounded-full bg-[var(--panel)] px-3 py-1 text-xs uppercase tracking-[0.2em] text-[var(--muted)]">
                    {budget.id === activeBudget?.id ? "Active" : "Past"}
                  </span>
                </div>
              ))}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
