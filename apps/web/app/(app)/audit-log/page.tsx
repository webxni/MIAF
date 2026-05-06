"use client";

import { useEffect, useMemo, useState } from "react";

import { SectionCard } from "../../_components/cards";
import { ApiRequestError, listAuditLogs, type AuditLog } from "../../_lib/api";

const PAGE_SIZE = 50;

function shortId(value: string | null): string {
  if (!value) return "—";
  return value.length <= 12 ? value : `${value.slice(0, 8)}…${value.slice(-4)}`;
}

function toSinceIso(value: string): string | undefined {
  return value ? `${value}T00:00:00.000Z` : undefined;
}

function toUntilIso(value: string): string | undefined {
  return value ? `${value}T23:59:59.999Z` : undefined;
}

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString();
}

export default function AuditLogPage() {
  const [rows, setRows] = useState<AuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [actionInput, setActionInput] = useState("");
  const [objectTypeInput, setObjectTypeInput] = useState("");
  const [sinceInput, setSinceInput] = useState("");
  const [untilInput, setUntilInput] = useState("");
  const [filters, setFilters] = useState({
    action: "",
    objectType: "",
    since: "",
    until: "",
  });
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [expandedIds, setExpandedIds] = useState<string[]>([]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    setForbidden(false);

    listAuditLogs({
      action: filters.action || undefined,
      object_type: filters.objectType || undefined,
      since: toSinceIso(filters.since),
      until: toUntilIso(filters.until),
      limit: PAGE_SIZE,
      offset,
    })
      .then((response) => {
        if (!active) return;
        setRows(response.rows);
        setTotal(response.total);
      })
      .catch((err) => {
        if (!active) return;
        if (err instanceof ApiRequestError && err.status === 403) {
          setForbidden(true);
          setRows([]);
          setTotal(0);
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load audit log");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [filters, offset]);

  const actionSuggestions = useMemo(
    () => Array.from(new Set(rows.map((row) => row.action))).sort(),
    [rows],
  );

  function applyFilters() {
    setOffset(0);
    setExpandedIds([]);
    setFilters({
      action: actionInput.trim(),
      objectType: objectTypeInput.trim(),
      since: sinceInput,
      until: untilInput,
    });
  }

  function toggleExpanded(id: string) {
    setExpandedIds((current) =>
      current.includes(id) ? current.filter((value) => value !== id) : [...current, id],
    );
  }

  const shownCount = Math.min(total, offset + rows.length);
  const canGoPrevious = offset > 0;
  const canGoNext = offset + rows.length < total;

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--accent)]">Audit log</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">Sensitive activity trail</h1>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Read-only tenant-scoped audit records for trust, debugging, and compliance review.
        </p>
      </div>

      {forbidden ? (
        <div className="rounded-2xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-5 py-4 text-sm text-[var(--danger-ink)]">
          Audit log requires owner or admin role
        </div>
      ) : null}

      {error ? (
        <div className="rounded-2xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-5 py-4 text-sm text-[var(--danger-ink)]">
          {error}
        </div>
      ) : null}

      <SectionCard title="Filters" description="All results are tenant-scoped and sorted by newest first.">
        <div className="grid gap-4 md:grid-cols-4">
          <label className="text-sm font-medium">
            Action
            <input
              className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
              value={actionInput}
              onChange={(event) => setActionInput(event.target.value)}
              list="audit-action-suggestions"
              placeholder="create"
              disabled={loading}
            />
            <datalist id="audit-action-suggestions">
              {actionSuggestions.map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
          </label>

          <label className="text-sm font-medium">
            Object type
            <input
              className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
              value={objectTypeInput}
              onChange={(event) => setObjectTypeInput(event.target.value)}
              placeholder="journal_entry"
              disabled={loading}
            />
          </label>

          <label className="text-sm font-medium">
            Since
            <input
              className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
              type="date"
              value={sinceInput}
              onChange={(event) => setSinceInput(event.target.value)}
              disabled={loading}
            />
          </label>

          <label className="text-sm font-medium">
            Until
            <input
              className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
              type="date"
              value={untilInput}
              onChange={(event) => setUntilInput(event.target.value)}
              disabled={loading}
            />
          </label>
        </div>

        <div className="mt-4">
          <button
            type="button"
            className="rounded-xl bg-[var(--accent)] px-4 py-2 text-sm font-medium text-[var(--accent-ink)] disabled:opacity-60"
            onClick={applyFilters}
            disabled={loading}
          >
            Apply
          </button>
        </div>
      </SectionCard>

      <SectionCard title="Rows" description="Append-only records only. No edit or delete actions exist on this page.">
        {loading ? (
          <p className="text-sm text-[var(--muted)]">Loading…</p>
        ) : forbidden ? null : rows.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">No audit rows match the current filters.</p>
        ) : (
          <div className="overflow-x-auto">
            <div className="min-w-[52rem] space-y-3">
              <div className="grid grid-cols-[11rem_6rem_7rem_1fr_1fr_7rem] gap-3 px-2 text-xs uppercase tracking-[0.2em] text-[var(--muted)]">
                <span>Created</span>
                <span>Action</span>
                <span>Type</span>
                <span>Object</span>
                <span>User</span>
                <span className="text-right">Details</span>
              </div>
              {rows.map((row) => {
                const expanded = expandedIds.includes(row.id);
                return (
                  <div key={row.id} className="rounded-2xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3">
                    <div className="grid grid-cols-[11rem_6rem_7rem_1fr_1fr_7rem] gap-3 text-sm">
                      <span>{formatTimestamp(row.created_at)}</span>
                      <span className="font-medium">{row.action}</span>
                      <span>{row.object_type}</span>
                      <span className="font-mono text-xs">{shortId(row.object_id)}</span>
                      <span className="font-mono text-xs">{shortId(row.user_id)}</span>
                      <span className="text-right">
                        <button
                          type="button"
                          className="text-xs font-medium text-[var(--accent)]"
                          onClick={() => toggleExpanded(row.id)}
                        >
                          {expanded ? "Hide details" : "Show details"}
                        </button>
                      </span>
                    </div>
                    <p className="mt-2 text-xs text-[var(--muted)]">
                      IP {row.ip ?? "—"} · UA {row.user_agent ?? "—"}
                    </p>
                    {expanded ? (
                      <div className="mt-3 grid gap-3 md:grid-cols-2">
                        <div>
                          <p className="mb-1 text-xs uppercase tracking-[0.2em] text-[var(--muted)]">Before</p>
                          <pre className="overflow-x-auto rounded-xl bg-[var(--panel)] p-3 text-xs">
                            {JSON.stringify(row.before, null, 2)}
                          </pre>
                        </div>
                        <div>
                          <p className="mb-1 text-xs uppercase tracking-[0.2em] text-[var(--muted)]">After</p>
                          <pre className="overflow-x-auto rounded-xl bg-[var(--panel)] p-3 text-xs">
                            {JSON.stringify(row.after, null, 2)}
                          </pre>
                        </div>
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {!forbidden ? (
          <div className="mt-5 flex items-center justify-between gap-3 border-t border-[var(--line)] pt-4 text-sm">
            <span className="text-[var(--muted)]">
              Showing {shownCount} of {total}
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                className="rounded-xl border border-[var(--line)] px-4 py-2 disabled:opacity-50"
                onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
                disabled={!canGoPrevious || loading}
              >
                Previous
              </button>
              <button
                type="button"
                className="rounded-xl border border-[var(--line)] px-4 py-2 disabled:opacity-50"
                onClick={() => setOffset((current) => current + PAGE_SIZE)}
                disabled={!canGoNext || loading}
              >
                Next
              </button>
            </div>
          </div>
        ) : null}
      </SectionCard>
    </div>
  );
}
