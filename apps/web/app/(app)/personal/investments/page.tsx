"use client";

import { useEffect, useState } from "react";

import { SectionCard, StatCard } from "../../../_components/cards";
import {
  entities,
  findEntityByMode,
  listInvestments,
  type Entity,
  type InvestmentAccount,
} from "../../../_lib/api";
import { brand } from "../../../_lib/brand";

function holdingValue(shares: string, current: string | null): number {
  const px = current ? Number(current) : 0;
  return Number(shares) * px;
}

function accountValue(account: InvestmentAccount): number {
  return account.holdings.reduce(
    (acc, h) => acc + holdingValue(h.shares, h.current_price),
    0,
  );
}

export default function PersonalInvestmentsPage() {
  const [entity, setEntity] = useState<Entity | null>(null);
  const [accounts, setAccounts] = useState<InvestmentAccount[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    entities()
      .then(async (items) => {
        if (!active) return;
        const next = findEntityByMode(items, "personal");
        setEntity(next);
        if (!next) return;
        const list = await listInvestments(next.id);
        if (active) setAccounts(list);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "Failed to load investments");
      });
    return () => {
      active = false;
    };
  }, []);

  const totalValue = accounts
    ? accounts.reduce((acc, a) => acc + accountValue(a), 0).toFixed(2)
    : "—";
  const holdingsCount = accounts?.reduce((acc, a) => acc + a.holdings.length, 0) ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--accent)]">Personal</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">Investments</h1>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Read-only view of recorded investment accounts and holdings.
        </p>
      </div>

      <div className="rounded-xl border border-[var(--line)] bg-[var(--surface)] px-4 py-3 text-xs text-[var(--muted)]">
        Investment tracking is advisory only. {brand.shortName} does not execute trades or
        guarantee returns.
      </div>

      {error ? (
        <div className="rounded-xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger-ink)]">
          {error}
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="Accounts" value={accounts ? String(accounts.length) : "—"} />
        <StatCard label="Holdings" value={accounts ? String(holdingsCount) : "—"} />
        <StatCard label="Tracked value" value={accounts ? totalValue : "—"} note="Sum of shares × current price (where set)." />
      </div>

      <SectionCard
        title="Accounts and holdings"
        description="Holdings without a current_price contribute 0 to tracked value."
      >
        {!entity ? (
          <p className="text-sm text-[var(--muted)]">No personal entity available.</p>
        ) : !accounts ? (
          <p className="text-sm text-[var(--muted)]">Loading…</p>
        ) : accounts.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">No investment accounts recorded yet.</p>
        ) : (
          <div className="space-y-4">
            {accounts.map((account) => (
              <div key={account.id} className="rounded-xl bg-[var(--surface)] p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="font-semibold">{account.name}</p>
                    <p className="text-xs text-[var(--muted)]">
                      {account.broker ?? "—"} · {account.kind} · {account.currency}
                    </p>
                  </div>
                  <p className="text-sm font-semibold">{accountValue(account).toFixed(2)}</p>
                </div>
                {account.holdings.length === 0 ? (
                  <p className="mt-3 text-xs text-[var(--muted)]">No holdings recorded.</p>
                ) : (
                  <div className="mt-3 space-y-1">
                    <div className="grid grid-cols-[6rem_1fr_repeat(3,minmax(0,5rem))] gap-2 px-2 text-xs uppercase tracking-[0.2em] text-[var(--muted)]">
                      <span>Symbol</span>
                      <span>Name</span>
                      <span className="text-right">Shares</span>
                      <span className="text-right">Px</span>
                      <span className="text-right">Value</span>
                    </div>
                    {account.holdings.map((h) => (
                      <div
                        key={h.id}
                        className="grid grid-cols-[6rem_1fr_repeat(3,minmax(0,5rem))] gap-2 rounded-lg bg-[var(--panel)] px-3 py-2 text-xs"
                      >
                        <span className="font-medium">{h.symbol}</span>
                        <span className="truncate text-[var(--muted)]">{h.name ?? h.kind}</span>
                        <span className="text-right">{h.shares}</span>
                        <span className="text-right">{h.current_price ?? "—"}</span>
                        <span className="text-right font-semibold">
                          {holdingValue(h.shares, h.current_price).toFixed(2)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
