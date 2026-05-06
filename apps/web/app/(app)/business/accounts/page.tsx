"use client";

import { useEffect, useMemo, useState } from "react";

import { SectionCard, StatCard } from "../../../_components/cards";
import {
  entities,
  findEntityByMode,
  listAccounts,
  type Account,
  type Entity,
} from "../../../_lib/api";

const TYPE_ORDER: Account["type"][] = ["asset", "liability", "equity", "income", "expense"];

const TYPE_LABEL: Record<Account["type"], string> = {
  asset: "Assets",
  liability: "Liabilities",
  equity: "Equity",
  income: "Income",
  expense: "Expenses",
};

export default function BusinessAccountsPage() {
  const [entity, setEntity] = useState<Entity | null>(null);
  const [accounts, setAccounts] = useState<Account[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    entities()
      .then(async (items) => {
        if (!active) return;
        const next = findEntityByMode(items, "business");
        setEntity(next);
        if (!next) return;
        const list = await listAccounts(next.id);
        if (active) setAccounts(list);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "Failed to load accounts");
      });
    return () => {
      active = false;
    };
  }, []);

  const grouped = useMemo(() => {
    if (!accounts) return null;
    const buckets: Record<Account["type"], Account[]> = {
      asset: [], liability: [], equity: [], income: [], expense: [],
    };
    for (const a of accounts) buckets[a.type].push(a);
    for (const k of TYPE_ORDER) buckets[k].sort((x, y) => x.code.localeCompare(y.code));
    return buckets;
  }, [accounts]);

  const inactive = accounts?.filter((a) => !a.is_active).length ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--accent)]">Business</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">Chart of accounts</h1>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Read-only view of the account tree, grouped by type. Use the API
          (`/api/entities/:id/accounts`) for create/update/delete.
        </p>
      </div>

      {error ? (
        <div className="rounded-xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger-ink)]">
          {error}
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="Accounts" value={accounts ? String(accounts.length) : "—"} />
        <StatCard label="Active" value={accounts ? String(accounts.length - inactive) : "—"} />
        <StatCard label="Inactive" value={accounts ? String(inactive) : "—"} />
      </div>

      {!entity ? (
        <SectionCard title="Accounts">
          <p className="text-sm text-[var(--muted)]">No business entity available.</p>
        </SectionCard>
      ) : !grouped ? (
        <SectionCard title="Accounts">
          <p className="text-sm text-[var(--muted)]">Loading…</p>
        </SectionCard>
      ) : (
        <div className="grid gap-6 xl:grid-cols-2">
          {TYPE_ORDER.map((kind) => (
            <SectionCard
              key={kind}
              title={TYPE_LABEL[kind]}
              description={`Normal side: ${grouped[kind][0]?.normal_side ?? "—"}`}
            >
              {grouped[kind].length === 0 ? (
                <p className="text-sm text-[var(--muted)]">None.</p>
              ) : (
                <div className="space-y-1">
                  {grouped[kind].map((a) => (
                    <div
                      key={a.id}
                      className={`flex items-center justify-between rounded-lg bg-[var(--surface)] px-3 py-2 text-sm ${
                        a.is_active ? "" : "opacity-60"
                      }`}
                    >
                      <span>
                        <span className="font-medium">{a.code}</span>{" "}
                        <span className="text-[var(--muted)]">{a.name}</span>
                      </span>
                      <span className="text-xs uppercase tracking-[0.2em] text-[var(--muted)]">
                        {a.normal_side}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </SectionCard>
          ))}
        </div>
      )}
    </div>
  );
}
