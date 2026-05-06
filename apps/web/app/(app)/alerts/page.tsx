"use client";

import { useEffect, useState } from "react";

import { SectionCard } from "../../_components/cards";
import { ApiRequestError, dismissAlert, listAlerts, resolveAlert, type Alert } from "../../_lib/api";

type AlertRowState = {
  action: "dismiss" | "resolve" | null;
  error: string | null;
};

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString();
}

function shortId(value: string | null): string {
  if (!value) return "—";
  return value.length <= 12 ? value : `${value.slice(0, 8)}…${value.slice(-4)}`;
}

function severityClasses(severity: Alert["severity"]): string {
  if (severity === "critical") {
    return "bg-[var(--danger-bg)] text-[var(--danger-ink)]";
  }
  if (severity === "warning") {
    return "bg-amber-100 text-amber-900";
  }
  return "bg-[var(--surface)] text-[var(--muted)]";
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) return error.message;
  return error instanceof Error ? error.message : fallback;
}

export default function AlertsPage() {
  const [onlyOpen, setOnlyOpen] = useState(true);
  const [rows, setRows] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rowState, setRowState] = useState<Record<string, AlertRowState>>({});

  async function loadAlerts(activeRef?: { current: boolean }) {
    try {
      setError(null);
      setLoading(true);
      const nextRows = await listAlerts({ only_open: onlyOpen, limit: 100 });
      if (activeRef && !activeRef.current) return;
      setRows(nextRows);
      setRowState((current) => {
        const next: Record<string, AlertRowState> = {};
        for (const row of nextRows) {
          next[row.id] = current[row.id] ?? { action: null, error: null };
        }
        return next;
      });
    } catch (loadError) {
      if (!activeRef || activeRef.current) {
        setError(errorMessage(loadError, "Failed to load alerts"));
        setRows([]);
      }
    } finally {
      if (!activeRef || activeRef.current) setLoading(false);
    }
  }

  useEffect(() => {
    const activeRef = { current: true };
    void loadAlerts(activeRef);
    return () => {
      activeRef.current = false;
    };
  }, [onlyOpen]);

  function setAlertRowState(alertId: string, patch: Partial<AlertRowState>) {
    setRowState((current) => ({
      ...current,
      [alertId]: {
        action: current[alertId]?.action ?? null,
        error: current[alertId]?.error ?? null,
        ...patch,
      },
    }));
  }

  async function runAction(alertId: string, action: "dismiss" | "resolve") {
    setAlertRowState(alertId, { action, error: null });
    try {
      if (action === "dismiss") {
        await dismissAlert(alertId);
      } else {
        await resolveAlert(alertId);
      }
      await loadAlerts();
    } catch (actionError) {
      setAlertRowState(alertId, {
        action: null,
        error: errorMessage(actionError, `Failed to ${action} alert`),
      });
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--accent)]">Alerts</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">Heartbeat alerts center</h1>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Review tenant alerts created by heartbeat runs and mark each one dismissed or resolved.
        </p>
      </div>

      {error ? (
        <div className="rounded-2xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-5 py-4 text-sm text-[var(--danger-ink)]">
          {error}
        </div>
      ) : null}

      <SectionCard title="Filters" description="Newest first. Open alerts are shown by default.">
        <div className="inline-flex rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-1">
          <button
            type="button"
            onClick={() => setOnlyOpen(true)}
            className={`rounded-xl px-4 py-2 text-sm font-medium ${
              onlyOpen ? "bg-[var(--accent)] text-[var(--accent-ink)]" : "text-[var(--muted)]"
            }`}
          >
            Only open
          </button>
          <button
            type="button"
            onClick={() => setOnlyOpen(false)}
            className={`rounded-xl px-4 py-2 text-sm font-medium ${
              !onlyOpen ? "bg-[var(--accent)] text-[var(--accent-ink)]" : "text-[var(--muted)]"
            }`}
          >
            All
          </button>
        </div>
      </SectionCard>

      <SectionCard title="Alert list" description="Actions are available only while the alert is open.">
        {loading ? (
          <p className="text-sm text-[var(--muted)]">Loading…</p>
        ) : rows.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">No alerts match the current filter.</p>
        ) : (
          <div className="overflow-x-auto">
            <div className="min-w-[72rem] space-y-3">
              <div className="grid grid-cols-[7rem_12rem_minmax(0,1.8fr)_10rem_11rem_15rem] gap-3 px-2 text-xs uppercase tracking-[0.2em] text-[var(--muted)]">
                <span>Severity</span>
                <span>Type</span>
                <span>Message</span>
                <span>Entity</span>
                <span>Created</span>
                <span className="text-right">Actions</span>
              </div>

              {rows.map((row) => {
                const state = rowState[row.id] ?? { action: null, error: null };
                const disabled = row.status !== "open" || state.action !== null;
                return (
                  <div key={row.id} className="rounded-2xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3">
                    <div className="grid grid-cols-[7rem_12rem_minmax(0,1.8fr)_10rem_11rem_15rem] gap-3 text-sm">
                      <div>
                        <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${severityClasses(row.severity)}`}>
                          {row.severity}
                        </span>
                        <p className="mt-2 text-xs text-[var(--muted)]">{row.status}</p>
                      </div>
                      <div className="font-medium">{row.alert_type}</div>
                      <div className="min-w-0">
                        <p className="truncate">{row.message}</p>
                      </div>
                      <div className="font-mono text-xs">{shortId(row.entity_id)}</div>
                      <div className="text-xs">{formatTimestamp(row.created_at)}</div>
                      <div className="flex items-start justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => void runAction(row.id, "dismiss")}
                          disabled={disabled}
                          className="rounded-xl border border-[var(--line)] px-3 py-2 text-xs font-semibold disabled:opacity-60"
                        >
                          {state.action === "dismiss" ? "Working…" : "Dismiss"}
                        </button>
                        <button
                          type="button"
                          onClick={() => void runAction(row.id, "resolve")}
                          disabled={disabled}
                          className="rounded-xl bg-[var(--accent)] px-3 py-2 text-xs font-semibold text-[var(--accent-ink)] disabled:opacity-60"
                        >
                          {state.action === "resolve" ? "Working…" : "Resolve"}
                        </button>
                      </div>
                    </div>
                    {state.error ? (
                      <p className="mt-3 text-xs text-[var(--danger-ink)]">{state.error}</p>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </SectionCard>
    </div>
  );
}
