"use client";

import { useEffect, useState } from "react";

import { SectionCard, StatCard } from "../../../_components/cards";
import {
  entities,
  findEntityByMode,
  getApAging,
  getArAging,
  getBalanceSheet,
  getIncomeStatement,
  monthStartIso,
  todayIso,
  type AgingReport,
  type BalanceSheet,
  type Entity,
  type IncomeStatement,
  type StatementRow,
} from "../../../_lib/api";

function StatementBlock({ title, rows, total }: { title: string; rows: StatementRow[]; total?: string }) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--muted)]">{title}</p>
      {rows.length === 0 ? (
        <p className="text-sm text-[var(--muted)]">No entries.</p>
      ) : (
        rows.map((row) => (
          <div key={row.account_id} className="flex items-center justify-between rounded-lg bg-[var(--surface)] px-3 py-2 text-sm">
            <span>
              <span className="font-medium">{row.code}</span>{" "}
              <span className="text-[var(--muted)]">{row.name}</span>
            </span>
            <span className="font-semibold">{row.amount}</span>
          </div>
        ))
      )}
      {total !== undefined ? (
        <div className="flex items-center justify-between border-t border-[var(--line)] px-3 py-2 text-sm">
          <span className="font-semibold">Total</span>
          <span className="font-semibold">{total}</span>
        </div>
      ) : null}
    </div>
  );
}

export default function BusinessReportsPage() {
  const [entity, setEntity] = useState<Entity | null>(null);
  const [balance, setBalance] = useState<BalanceSheet | null>(null);
  const [income, setIncome] = useState<IncomeStatement | null>(null);
  const [arAging, setArAging] = useState<AgingReport | null>(null);
  const [apAging, setApAging] = useState<AgingReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const asOf = todayIso();
    const monthStart = monthStartIso(asOf);
    entities()
      .then(async (items) => {
        if (!active) return;
        const next = findEntityByMode(items, "business");
        setEntity(next);
        if (!next) return;
        const [bs, is, ar, ap] = await Promise.all([
          getBalanceSheet(next.id, asOf),
          getIncomeStatement(next.id, monthStart, asOf),
          getArAging(next.id, asOf),
          getApAging(next.id, asOf),
        ]);
        if (!active) return;
        setBalance(bs);
        setIncome(is);
        setArAging(ar);
        setApAging(ap);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "Failed to load reports");
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--accent)]">Business</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">Reports</h1>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Deterministic statements computed from posted ledger balances.
          Numbers come from the backend services in `app/services/business.py` —
          this page only displays them.
        </p>
      </div>

      {error ? (
        <div className="rounded-xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger-ink)]">
          {error}
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="Total assets" value={balance?.total_assets ?? "—"} />
        <StatCard label="Total liabilities" value={balance?.total_liabilities ?? "—"} />
        <StatCard label="Total equity" value={balance?.total_equity ?? "—"} note={balance ? `Balanced: ${balance.is_balanced ? "yes" : "NO"}` : undefined} />
        <StatCard label="Net income (MTD)" value={income?.net_income ?? "—"} note={income ? `${income.date_from} → ${income.date_to}` : undefined} />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <SectionCard
          title="Balance sheet"
          description={balance ? `As of ${balance.as_of}` : undefined}
        >
          {!entity ? (
            <p className="text-sm text-[var(--muted)]">No business entity available.</p>
          ) : !balance ? (
            <p className="text-sm text-[var(--muted)]">Loading…</p>
          ) : (
            <div className="space-y-5">
              <StatementBlock title="Assets" rows={balance.assets} total={balance.total_assets} />
              <StatementBlock title="Liabilities" rows={balance.liabilities} total={balance.total_liabilities} />
              <StatementBlock title="Equity" rows={balance.equity} total={balance.total_equity} />
              <p className="text-xs text-[var(--muted)]">
                Current period earnings: {balance.current_earnings}
              </p>
            </div>
          )}
        </SectionCard>

        <SectionCard
          title="Income statement"
          description={income ? `${income.date_from} → ${income.date_to}` : undefined}
        >
          {!income ? (
            <p className="text-sm text-[var(--muted)]">Loading…</p>
          ) : (
            <div className="space-y-5">
              <StatementBlock title="Income" rows={income.income} total={income.total_income} />
              <StatementBlock title="Expenses" rows={income.expenses} total={income.total_expenses} />
              <div className="flex items-center justify-between border-t border-[var(--line)] px-3 py-2 text-sm">
                <span className="font-semibold">Net income</span>
                <span className="font-semibold">{income.net_income}</span>
              </div>
            </div>
          )}
        </SectionCard>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <SectionCard title="AR aging" description={arAging ? `As of ${arAging.as_of}` : undefined}>
          {!arAging ? (
            <p className="text-sm text-[var(--muted)]">Loading…</p>
          ) : arAging.rows.length === 0 ? (
            <p className="text-sm text-[var(--muted)]">No open invoices.</p>
          ) : (
            <div className="space-y-2">
              <div className="grid grid-cols-[1fr_repeat(2,minmax(0,7rem))] gap-2 px-2 text-xs uppercase tracking-[0.2em] text-[var(--muted)]">
                <span>Customer</span>
                <span className="text-right">Due</span>
                <span className="text-right">Balance</span>
              </div>
              {arAging.rows.map((row) => (
                <div key={row.object_id} className="grid grid-cols-[1fr_repeat(2,minmax(0,7rem))] gap-2 rounded-lg bg-[var(--surface)] px-3 py-2 text-sm">
                  <span>
                    <span className="font-medium">{row.number}</span>{" "}
                    <span className="text-[var(--muted)]">{row.counterparty_name}</span>
                  </span>
                  <span className="text-right">{row.due_date}</span>
                  <span className="text-right font-semibold">{row.balance_due}</span>
                </div>
              ))}
              <div className="flex items-center justify-between border-t border-[var(--line)] px-3 py-2 text-sm">
                <span className="font-semibold">Total open</span>
                <span className="font-semibold">{arAging.total_balance_due}</span>
              </div>
            </div>
          )}
        </SectionCard>

        <SectionCard title="AP aging" description={apAging ? `As of ${apAging.as_of}` : undefined}>
          {!apAging ? (
            <p className="text-sm text-[var(--muted)]">Loading…</p>
          ) : apAging.rows.length === 0 ? (
            <p className="text-sm text-[var(--muted)]">No open bills.</p>
          ) : (
            <div className="space-y-2">
              <div className="grid grid-cols-[1fr_repeat(2,minmax(0,7rem))] gap-2 px-2 text-xs uppercase tracking-[0.2em] text-[var(--muted)]">
                <span>Vendor</span>
                <span className="text-right">Due</span>
                <span className="text-right">Balance</span>
              </div>
              {apAging.rows.map((row) => (
                <div key={row.object_id} className="grid grid-cols-[1fr_repeat(2,minmax(0,7rem))] gap-2 rounded-lg bg-[var(--surface)] px-3 py-2 text-sm">
                  <span>
                    <span className="font-medium">{row.number}</span>{" "}
                    <span className="text-[var(--muted)]">{row.counterparty_name}</span>
                  </span>
                  <span className="text-right">{row.due_date}</span>
                  <span className="text-right font-semibold">{row.balance_due}</span>
                </div>
              ))}
              <div className="flex items-center justify-between border-t border-[var(--line)] px-3 py-2 text-sm">
                <span className="font-semibold">Total open</span>
                <span className="font-semibold">{apAging.total_balance_due}</span>
              </div>
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  );
}
