"use client";

import { useEffect, useState } from "react";

import { SectionCard, StatCard } from "../../../_components/cards";
import {
  entities,
  findEntityByMode,
  listDebts,
  type Debt,
  type Entity,
} from "../../../_lib/api";

function sumDecimal(values: (string | null | undefined)[]): string {
  const total = values.reduce((acc, v) => acc + Number(v ?? 0), 0);
  return total.toFixed(2);
}

export default function PersonalDebtsPage() {
  const [entity, setEntity] = useState<Entity | null>(null);
  const [debts, setDebts] = useState<Debt[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    entities()
      .then(async (items) => {
        if (!active) return;
        const next = findEntityByMode(items, "personal");
        setEntity(next);
        if (!next) return;
        const list = await listDebts(next.id);
        if (active) setDebts(list);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "Failed to load debts");
      });
    return () => {
      active = false;
    };
  }, []);

  const totalBalance = debts ? sumDecimal(debts.map((d) => d.current_balance)) : "—";
  const totalMinimum = debts
    ? sumDecimal(debts.map((d) => d.minimum_payment ?? "0"))
    : "—";
  const dueSoon = debts
    ? debts.filter((d) => {
        if (!d.next_due_date) return false;
        const dueDate = new Date(d.next_due_date);
        const now = new Date();
        const diffMs = dueDate.getTime() - now.getTime();
        return diffMs <= 7 * 24 * 60 * 60 * 1000 && diffMs >= -1 * 24 * 60 * 60 * 1000;
      }).length
    : 0;

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--accent)]">Personal</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">Debt tracker</h1>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Read-only view of recorded debts. Creation requires explicit
          confirmation; use the API (`POST /api/entities/:id/personal/debts`).
        </p>
      </div>

      {error ? (
        <div className="rounded-xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger-ink)]">
          {error}
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="Debts tracked" value={debts ? String(debts.length) : "—"} />
        <StatCard label="Total balance" value={totalBalance} />
        <StatCard
          label="Minimum monthly"
          value={totalMinimum}
          note={dueSoon > 0 ? `${dueSoon} due in next 7 days` : undefined}
        />
      </div>

      <SectionCard title="All debts" description="Sorted by current balance, descending.">
        {!entity ? (
          <p className="text-sm text-[var(--muted)]">No personal entity available.</p>
        ) : !debts ? (
          <p className="text-sm text-[var(--muted)]">Loading…</p>
        ) : debts.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">No debts recorded yet.</p>
        ) : (
          <div className="space-y-2">
            <div className="grid grid-cols-[1fr_repeat(4,minmax(0,7rem))] gap-2 px-2 text-xs uppercase tracking-[0.2em] text-[var(--muted)]">
              <span>Debt</span>
              <span className="text-right">Balance</span>
              <span className="text-right">APR</span>
              <span className="text-right">Min payment</span>
              <span className="text-right">Next due</span>
            </div>
            {[...debts]
              .sort((a, b) => Number(b.current_balance) - Number(a.current_balance))
              .map((debt) => (
                <div
                  key={debt.id}
                  className="grid grid-cols-[1fr_repeat(4,minmax(0,7rem))] items-center gap-2 rounded-xl bg-[var(--surface)] px-3 py-2 text-sm"
                >
                  <span>
                    <span className="font-medium">{debt.name}</span>
                    <span className="ml-2 rounded-full bg-[var(--panel)] px-2 py-0.5 text-xs uppercase tracking-[0.2em] text-[var(--muted)]">
                      {debt.kind}
                    </span>
                  </span>
                  <span className="text-right font-semibold">{debt.current_balance}</span>
                  <span className="text-right">{debt.interest_rate_apr ?? "—"}</span>
                  <span className="text-right">{debt.minimum_payment ?? "—"}</span>
                  <span className="text-right">{debt.next_due_date ?? "—"}</span>
                </div>
              ))}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
