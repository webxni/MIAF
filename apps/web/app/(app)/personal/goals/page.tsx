"use client";

import { useEffect, useState } from "react";

import { SectionCard, StatCard } from "../../../_components/cards";
import {
  entities,
  findEntityByMode,
  listGoals,
  type Entity,
  type Goal,
} from "../../../_lib/api";

function progressRatio(g: Goal): number {
  const target = Number(g.target_amount);
  const current = Number(g.current_amount);
  if (!target) return 0;
  return Math.min(1, Math.max(0, current / target));
}

function statusBadge(status: string): string {
  switch (status) {
    case "active":
      return "bg-[var(--accent)] text-[var(--accent-ink)]";
    case "achieved":
      return "bg-emerald-500/20 text-emerald-300";
    case "paused":
      return "bg-[var(--panel)] text-[var(--muted)]";
    case "abandoned":
      return "bg-[var(--danger-bg)] text-[var(--danger-ink)]";
    default:
      return "bg-[var(--panel)] text-[var(--muted)]";
  }
}

export default function PersonalGoalsPage() {
  const [entity, setEntity] = useState<Entity | null>(null);
  const [goals, setGoals] = useState<Goal[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    entities()
      .then(async (items) => {
        if (!active) return;
        const next = findEntityByMode(items, "personal");
        setEntity(next);
        if (!next) return;
        const list = await listGoals(next.id);
        if (active) setGoals(list);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "Failed to load goals");
      });
    return () => {
      active = false;
    };
  }, []);

  const activeGoals = goals?.filter((g) => g.status === "active") ?? [];
  const achieved = goals?.filter((g) => g.status === "achieved").length ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--accent)]">Personal</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">Goals</h1>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Read-only view. Linked goals draw their balance from the linked
          account; the rest use stored `current_amount`.
        </p>
      </div>

      {error ? (
        <div className="rounded-xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger-ink)]">
          {error}
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="Goals total" value={goals ? String(goals.length) : "—"} />
        <StatCard label="Active" value={goals ? String(activeGoals.length) : "—"} />
        <StatCard label="Achieved" value={goals ? String(achieved) : "—"} />
      </div>

      <SectionCard title="All goals" description="Sorted by status (active first), then by target date.">
        {!entity ? (
          <p className="text-sm text-[var(--muted)]">No personal entity available.</p>
        ) : !goals ? (
          <p className="text-sm text-[var(--muted)]">Loading…</p>
        ) : goals.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">No goals defined yet.</p>
        ) : (
          <div className="space-y-3">
            {[...goals]
              .sort((a, b) => {
                const order = { active: 0, paused: 1, achieved: 2, abandoned: 3 } as Record<string, number>;
                const da = order[a.status] ?? 9;
                const db = order[b.status] ?? 9;
                if (da !== db) return da - db;
                if (!a.target_date && !b.target_date) return a.name.localeCompare(b.name);
                if (!a.target_date) return 1;
                if (!b.target_date) return -1;
                return a.target_date < b.target_date ? -1 : 1;
              })
              .map((goal) => {
                const ratio = progressRatio(goal);
                return (
                  <div key={goal.id} className="rounded-xl bg-[var(--surface)] px-4 py-3 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-semibold">{goal.name}</p>
                        <p className="text-[var(--muted)]">
                          {goal.kind} · {goal.current_amount} of {goal.target_amount}
                          {goal.target_date ? ` · target ${goal.target_date}` : ""}
                        </p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs uppercase tracking-[0.2em] ${statusBadge(goal.status)}`}>
                        {goal.status}
                      </span>
                    </div>
                    <div className="mt-3 h-2 overflow-hidden rounded-full bg-[var(--panel)]">
                      <div
                        className="h-full bg-[var(--accent)]"
                        style={{ width: `${(ratio * 100).toFixed(1)}%` }}
                      />
                    </div>
                    <p className="mt-2 text-xs text-[var(--muted)]">{(ratio * 100).toFixed(1)}% of target</p>
                  </div>
                );
              })}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
