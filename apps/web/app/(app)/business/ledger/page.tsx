"use client";

import { useEffect, useMemo, useState } from "react";

import { SectionCard, StatCard } from "../../../_components/cards";
import {
  entities,
  findEntityByMode,
  listAccounts,
  listJournalEntries,
  type Account,
  type Entity,
  type JournalEntry,
} from "../../../_lib/api";

function statusBadge(status: string): string {
  switch (status) {
    case "draft":
      return "bg-[var(--panel)] text-[var(--muted)]";
    case "posted":
      return "bg-[var(--accent)] text-[var(--accent-ink)]";
    case "voided":
      return "bg-[var(--danger-bg)] text-[var(--danger-ink)]";
    default:
      return "bg-[var(--panel)] text-[var(--muted)]";
  }
}

function lineSummary(entry: JournalEntry, accounts: Map<string, Account>): string {
  const parts = entry.lines.slice(0, 3).map((line) => {
    const account = accounts.get(line.account_id);
    const code = account?.code ?? line.account_id.slice(0, 6);
    const amount = Number(line.debit) > 0 ? `Dr ${line.debit}` : `Cr ${line.credit}`;
    return `${code} ${amount}`;
  });
  if (entry.lines.length > 3) parts.push(`(+${entry.lines.length - 3} more)`);
  return parts.join(" · ");
}

export default function BusinessLedgerPage() {
  const [entity, setEntity] = useState<Entity | null>(null);
  const [entries, setEntries] = useState<JournalEntry[] | null>(null);
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
        const [es, accs] = await Promise.all([listJournalEntries(next.id), listAccounts(next.id)]);
        if (!active) return;
        setEntries(es);
        setAccounts(accs);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "Failed to load ledger");
      });
    return () => {
      active = false;
    };
  }, []);

  const accountMap = useMemo(() => {
    const map = new Map<string, Account>();
    for (const a of accounts ?? []) map.set(a.id, a);
    return map;
  }, [accounts]);

  const counts = useMemo(() => {
    const out = { draft: 0, posted: 0, voided: 0 };
    for (const e of entries ?? []) out[e.status] += 1;
    return out;
  }, [entries]);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--accent)]">Business</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">Ledger</h1>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Recent journal entries (most recent first). Posted entries are
          immutable; corrections happen via reversal entries.
        </p>
      </div>

      {error ? (
        <div className="rounded-xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger-ink)]">
          {error}
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="Drafts" value={entries ? String(counts.draft) : "—"} />
        <StatCard label="Posted" value={entries ? String(counts.posted) : "—"} />
        <StatCard label="Voided" value={entries ? String(counts.voided) : "—"} />
      </div>

      <SectionCard title="Journal entries" description="Up to 100 most recent entries returned by the API.">
        {!entity ? (
          <p className="text-sm text-[var(--muted)]">No business entity available.</p>
        ) : !entries ? (
          <p className="text-sm text-[var(--muted)]">Loading…</p>
        ) : entries.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">No entries yet.</p>
        ) : (
          <div className="space-y-2">
            <div className="grid grid-cols-[6.5rem_1fr_8rem] gap-3 px-2 text-xs uppercase tracking-[0.2em] text-[var(--muted)]">
              <span>Date</span>
              <span>Memo · lines</span>
              <span className="text-right">Status</span>
            </div>
            {entries.map((entry) => (
              <div
                key={entry.id}
                className={`grid grid-cols-[6.5rem_1fr_8rem] gap-3 rounded-xl bg-[var(--surface)] px-3 py-2 text-sm ${
                  entry.status === "voided" ? "opacity-70" : ""
                }`}
              >
                <span>{entry.entry_date}</span>
                <span className="min-w-0">
                  <p className="truncate font-medium">
                    {entry.memo ?? entry.reference ?? `Entry ${entry.id.slice(0, 8)}`}
                  </p>
                  <p className="truncate text-xs text-[var(--muted)]">
                    {lineSummary(entry, accountMap)}
                  </p>
                </span>
                <span className="text-right">
                  <span className={`rounded-full px-2 py-0.5 text-xs uppercase tracking-[0.2em] ${statusBadge(entry.status)}`}>
                    {entry.status}
                  </span>
                </span>
              </div>
            ))}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
