"use client";

import { ChangeEvent, useEffect, useMemo, useState } from "react";

import { SectionCard } from "../../_components/cards";
import {
  ApiRequestError,
  deleteJournalEntry,
  entities,
  findEntityByMode,
  listAccounts,
  listPendingDrafts,
  postJournalEntry,
  updateJournalEntry,
  type Account,
  type Entity,
  type JournalLineInput,
  type PendingDraft,
} from "../../_lib/api";

type UploadResult = {
  attachment: { filename: string; id: string };
  extraction?: { confidence_score?: string | null; extracted_data?: Record<string, { value: string | null; confidence: string }> };
  batch?: { rows_imported: number; rows_total: number };
};

type DraftEntityState = {
  entity: Entity;
  accounts: Account[];
  drafts: PendingDraft[];
};

type DraftRowState = {
  selectedAccountId: string;
  saving: boolean;
  error: string | null;
};

function displayMoney(amount: string | null, currency: string | null): string {
  if (!amount) return "—";
  const value = Number(amount);
  if (Number.isNaN(value)) return currency ? `${amount} ${currency}` : amount;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency || "USD",
  }).format(value);
}

function displaySourceSummary(draft: PendingDraft): string {
  const parts = [draft.source.merchant, draft.source.memo].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : draft.memo ?? "Draft journal entry";
}

function draftDebitAccountId(draft: PendingDraft): string {
  return draft.lines.find((line) => Number(line.debit) > 0)?.account_id ?? draft.lines[0]?.account_id ?? "";
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) return error.message;
  return error instanceof Error ? error.message : fallback;
}

export default function DocumentsPage() {
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pendingSections, setPendingSections] = useState<DraftEntityState[] | null>(null);
  const [pendingError, setPendingError] = useState<string | null>(null);
  const [rowState, setRowState] = useState<Record<string, DraftRowState>>({});

  async function loadPendingDrafts(activeRef?: { current: boolean }) {
    try {
      setPendingError(null);
      const allEntities = await entities();
      if (activeRef && !activeRef.current) return;
      const targets = [findEntityByMode(allEntities, "personal"), findEntityByMode(allEntities, "business")].filter(
        (entity): entity is Entity => entity !== null,
      );
      const sections = await Promise.all(
        targets.map(async (entity) => {
          const [accounts, drafts] = await Promise.all([listAccounts(entity.id), listPendingDrafts(entity.id)]);
          return {
            entity,
            accounts: accounts
              .filter((account) => account.type === "expense" && account.is_active)
              .sort((left, right) => left.code.localeCompare(right.code)),
            drafts,
          };
        }),
      );
      if (activeRef && !activeRef.current) return;
      setPendingSections(sections);
      setRowState((current) => {
        const next: Record<string, DraftRowState> = {};
        for (const section of sections) {
          for (const draft of section.drafts) {
            const selectedAccountId = current[draft.id]?.selectedAccountId ?? draftDebitAccountId(draft);
            next[draft.id] = {
              selectedAccountId,
              saving: current[draft.id]?.saving ?? false,
              error: current[draft.id]?.error ?? null,
            };
          }
        }
        return next;
      });
    } catch (error) {
      if (!activeRef || activeRef.current) {
        setPendingError(errorMessage(error, "Failed to load pending drafts"));
        setPendingSections([]);
      }
    }
  }

  useEffect(() => {
    const activeRef = { current: true };
    void loadPendingDrafts(activeRef);
    return () => {
      activeRef.current = false;
    };
  }, []);

  const pendingCount = useMemo(
    () => pendingSections?.reduce((total, section) => total + section.drafts.length, 0) ?? 0,
    [pendingSections],
  );

  async function upload(kind: "receipts" | "csv-imports", file: File) {
    setBusy(true);
    setMessage(null);
    try {
      const allEntities = await entities();
      const entity = allEntities[0];
      if (!entity) {
        throw new Error("No entity available");
      }
      const form = new FormData();
      form.append("file", file);
      const response = await fetch(`/api/entities/${entity.id}/documents/${kind}`, {
        method: "POST",
        credentials: "include",
        body: form,
      });
      const body = (await response.json()) as UploadResult | { error?: { message?: string } };
      if (!response.ok) {
        throw new Error("error" in body ? body.error?.message ?? "Upload failed" : "Upload failed");
      }
      if (kind === "receipts" && "attachment" in body) {
        setMessage(`Receipt ${body.attachment.filename} uploaded and parsed.`);
      } else if (kind === "csv-imports" && "batch" in body) {
        setMessage(`Imported ${body.batch?.rows_imported ?? 0} of ${body.batch?.rows_total ?? 0} rows.`);
        await loadPendingDrafts();
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  function onReceiptChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) void upload("receipts", file);
  }

  function onCsvChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) void upload("csv-imports", file);
  }

  function setDraftState(draftId: string, patch: Partial<DraftRowState>) {
    setRowState((current) => {
      const base = current[draftId] ?? {
        selectedAccountId: "",
        saving: false,
        error: null,
      };
      return {
        ...current,
        [draftId]: {
          ...base,
          ...patch,
        },
      };
    });
  }

  function removeDraft(entityId: string, draftId: string) {
    setPendingSections((current) =>
      current?.map((section) =>
        section.entity.id === entityId
          ? { ...section, drafts: section.drafts.filter((draft) => draft.id !== draftId) }
          : section,
      ) ?? current,
    );
    setRowState((current) => {
      const next = { ...current };
      delete next[draftId];
      return next;
    });
  }

  async function approveDraft(section: DraftEntityState, draft: PendingDraft) {
    const current = rowState[draft.id];
    const selectedAccountId = current?.selectedAccountId ?? draftDebitAccountId(draft);
    const originalAccountId = draftDebitAccountId(draft);
    setDraftState(draft.id, { saving: true, error: null });
    try {
      if (selectedAccountId && selectedAccountId !== originalAccountId) {
        const lines: JournalLineInput[] = draft.lines.map((line) => ({
          account_id: line.account_id === originalAccountId && Number(line.debit) > 0 ? selectedAccountId : line.account_id,
          debit: line.debit,
          credit: line.credit,
          description: line.description,
        }));
        await updateJournalEntry(section.entity.id, draft.id, lines);
      }
      await postJournalEntry(section.entity.id, draft.id);
      removeDraft(section.entity.id, draft.id);
    } catch (error) {
      setDraftState(draft.id, {
        saving: false,
        error: errorMessage(error, "Failed to approve draft"),
      });
      return;
    }
  }

  async function declineDraft(section: DraftEntityState, draft: PendingDraft) {
    setDraftState(draft.id, { saving: true, error: null });
    try {
      await deleteJournalEntry(section.entity.id, draft.id);
      removeDraft(section.entity.id, draft.id);
    } catch (error) {
      setDraftState(draft.id, {
        saving: false,
        error: errorMessage(error, "Failed to decline draft"),
      });
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--accent)]">Documents</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">Review queue and ingestion</h1>
      </div>

      {message ? (
        <div className="rounded-2xl border border-[var(--line)] bg-[var(--panel)] px-5 py-4 text-sm">
          {message}
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-2">
        <SectionCard title="Receipt upload" description="Uploads into the Phase 4 document ingestion pipeline.">
          <label className="inline-flex cursor-pointer rounded-xl bg-[var(--accent)] px-4 py-3 font-semibold text-[var(--accent-ink)]">
            <input type="file" accept=".txt,.pdf,.png,.jpg,.jpeg" className="hidden" onChange={onReceiptChange} disabled={busy} />
            {busy ? "Uploading…" : "Upload receipt"}
          </label>
        </SectionCard>

        <SectionCard title="CSV bank import" description="Creates source transaction rows for reconciliation.">
          <label className="inline-flex cursor-pointer rounded-xl border border-[var(--line)] px-4 py-3 font-semibold">
            <input type="file" accept=".csv,text/csv" className="hidden" onChange={onCsvChange} disabled={busy} />
            {busy ? "Importing…" : "Import CSV"}
          </label>
        </SectionCard>
      </div>

      <SectionCard
        title="Pending drafts"
        description="Review imported CSV outflows, correct the debit account if needed, then approve and post."
      >
        {pendingError ? (
          <div className="rounded-xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger-ink)]">
            {pendingError}
          </div>
        ) : pendingSections === null ? (
          <p className="text-sm text-[var(--muted)]">Loading…</p>
        ) : pendingCount === 0 ? (
          <p className="text-sm text-[var(--muted)]">No pending drafts.</p>
        ) : (
          <div className="space-y-6">
            {pendingSections.map((section) => (
              <div key={section.entity.id} className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-semibold uppercase tracking-[0.2em] text-[var(--muted)]">
                    {section.entity.name}
                  </h4>
                  <span className="rounded-full bg-[var(--surface)] px-3 py-1 text-xs uppercase tracking-[0.2em] text-[var(--muted)]">
                    {section.drafts.length} draft{section.drafts.length === 1 ? "" : "s"}
                  </span>
                </div>
                {section.drafts.length === 0 ? (
                  <div className="rounded-xl bg-[var(--surface)] px-4 py-3 text-sm text-[var(--muted)]">
                    No pending drafts for this entity.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {section.drafts.map((draft) => {
                      const state = rowState[draft.id] ?? {
                        selectedAccountId: draftDebitAccountId(draft),
                        saving: false,
                        error: null,
                      };
                      return (
                        <div key={draft.id} className="rounded-2xl bg-[var(--surface)] p-4">
                          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_18rem_auto] xl:items-center">
                            <div className="min-w-0">
                              <p className="truncate font-medium">{displaySourceSummary(draft)}</p>
                              <p className="mt-1 text-sm text-[var(--muted)]">
                                {displayMoney(draft.source.amount, draft.source.currency)}
                                {" · "}
                                {draft.entry_date}
                                {draft.source.posted_at ? ` · source ${draft.source.posted_at.slice(0, 10)}` : ""}
                              </p>
                            </div>

                            <label className="flex min-w-0 flex-col gap-2 text-xs uppercase tracking-[0.2em] text-[var(--muted)]">
                              Debit account
                              <select
                                value={state.selectedAccountId}
                                onChange={(event) =>
                                  setDraftState(draft.id, {
                                    selectedAccountId: event.target.value,
                                    error: null,
                                  })
                                }
                                disabled={state.saving}
                                className="rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2 text-sm text-[var(--ink)] outline-none"
                              >
                                <optgroup label={section.entity.name}>
                                  {section.accounts.map((account) => (
                                    <option key={account.id} value={account.id}>
                                      {account.code} · {account.name}
                                    </option>
                                  ))}
                                </optgroup>
                              </select>
                            </label>

                            <div className="flex flex-wrap items-center justify-end gap-2">
                              <button
                                type="button"
                                onClick={() => void approveDraft(section, draft)}
                                disabled={state.saving}
                                className="rounded-xl bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-[var(--accent-ink)] disabled:opacity-60"
                              >
                                {state.saving ? "Working…" : "Approve & Post"}
                              </button>
                              <button
                                type="button"
                                onClick={() => void declineDraft(section, draft)}
                                disabled={state.saving}
                                className="rounded-xl border border-[var(--line)] px-4 py-2 text-sm font-semibold disabled:opacity-60"
                              >
                                Decline
                              </button>
                            </div>
                          </div>

                          {state.error ? (
                            <div className="mt-3">
                              <span className="rounded-full bg-[var(--danger-bg)] px-3 py-1 text-xs text-[var(--danger-ink)]">
                                {state.error}
                              </span>
                            </div>
                          ) : null}
                        </div>
                      );
                    })}
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
