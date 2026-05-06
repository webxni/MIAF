"use client";

import { ChangeEvent, useEffect, useMemo, useState } from "react";

import { SectionCard } from "../../_components/cards";
import {
  answerDocumentQuestion,
  ApiRequestError,
  classifyDocument,
  createDraftFromDocument,
  deleteJournalEntry,
  entities,
  findEntityByMode,
  ingestText,
  listAccounts,
  listDocuments,
  listPendingDrafts,
  postJournalEntry,
  rejectDocument,
  uploadDocument,
  updateJournalEntry,
  type Account,
  type DocumentUploadResult,
  type Entity,
  type JournalLineInput,
  type PendingDraft,
  type StoredDocument,
} from "../../_lib/api";

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
  const [textBusy, setTextBusy] = useState(false);
  const [textEntry, setTextEntry] = useState("");
  const [pendingSections, setPendingSections] = useState<DraftEntityState[] | null>(null);
  const [pendingError, setPendingError] = useState<string | null>(null);
  const [documents, setDocuments] = useState<StoredDocument[] | null>(null);
  const [documentsError, setDocumentsError] = useState<string | null>(null);
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

  async function loadDocuments(activeRef?: { current: boolean }) {
    try {
      setDocumentsError(null);
      const allEntities = await entities();
      if (activeRef && !activeRef.current) return;
      const entity = allEntities[0];
      if (!entity) {
        setDocuments([]);
        return;
      }
      const rows = await listDocuments({ entity_id: entity.id, limit: 20 });
      if (activeRef && !activeRef.current) return;
      setDocuments(rows);
    } catch (error) {
      if (!activeRef || activeRef.current) {
        setDocumentsError(errorMessage(error, "Failed to load documents"));
        setDocuments([]);
      }
    }
  }

  useEffect(() => {
    const activeRef = { current: true };
    void loadPendingDrafts(activeRef);
    void loadDocuments(activeRef);
    return () => {
      activeRef.current = false;
    };
  }, []);

  const pendingCount = useMemo(
    () => pendingSections?.reduce((total, section) => total + section.drafts.length, 0) ?? 0,
    [pendingSections],
  );

  async function upload(file: File) {
    setBusy(true);
    setMessage(null);
    try {
      const allEntities = await entities();
      const entity = allEntities[0];
      if (!entity) {
        throw new Error("No entity available");
      }
      const body = await uploadDocument(entity.id, file);
      handleUploadResult(body, file.name);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  function handleUploadResult(body: DocumentUploadResult, fallbackName: string) {
    if (body.stored_document) {
      const warningText = body.warnings.length ? ` Warnings: ${body.warnings.join("; ")}` : "";
      const questions = body.stored_document.extracted_items[0]?.questions.length ?? 0;
      setMessage(
        `${body.stored_document.attachment.filename || fallbackName} uploaded as ${body.input_type}.` +
          ` Confidence: ${body.stored_document.extracted_items[0]?.confidence_level ?? "low"}.` +
          (questions ? ` ${questions} question${questions === 1 ? "" : "s"} need review.` : "") +
          warningText,
      );
      setDocuments((current) =>
        current
          ? [body.stored_document!, ...current.filter((item) => item.attachment.id !== body.stored_document!.attachment.id)]
          : [body.stored_document!],
      );
    } else if (body.csv_import) {
      setMessage(
        `Imported ${body.csv_import.batch.rows_imported} of ${body.csv_import.batch.rows_total} rows.` +
          (body.csv_import.batch.error_message ? ` ${body.csv_import.batch.error_message}` : ""),
      );
      void loadPendingDrafts();
      void loadDocuments();
    }
  }

  function onReceiptChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) void upload(file);
  }

  function onCsvChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) void upload(file);
  }

  async function handleTextIngest() {
    if (!textEntry.trim()) return;
    setTextBusy(true);
    setMessage(null);
    try {
      const allEntities = await entities();
      const entity = allEntities[0];
      if (!entity) throw new Error("No entity available");
      const result = await ingestText(entity.id, textEntry.trim());
      setDocuments((current) =>
        current
          ? [result.stored_document, ...current.filter((item) => item.attachment.id !== result.stored_document.attachment.id)]
          : [result.stored_document],
      );
      setTextEntry("");
      setMessage("Text note ingested into the review queue.");
    } catch (error) {
      setMessage(errorMessage(error, "Failed to ingest text"));
    } finally {
      setTextBusy(false);
    }
  }

  async function handleDocumentAction(attachmentId: string, action: "classify" | "draft" | "reject" | "answer") {
    try {
      if (action === "classify") {
        const updated = await classifyDocument(attachmentId);
        setDocuments((current) => current?.map((item) => (item.attachment.id === attachmentId ? updated : item)) ?? current);
        setMessage("Document reclassified.");
        return;
      }
      if (action === "draft") {
        await createDraftFromDocument(attachmentId);
        setMessage("Draft journal entry created from document.");
        await loadPendingDrafts();
        await loadDocuments();
        return;
      }
      if (action === "reject") {
        const updated = await rejectDocument(attachmentId);
        setDocuments((current) => current?.map((item) => (item.attachment.id === attachmentId ? updated : item)) ?? current);
        setMessage("Document marked as rejected.");
        return;
      }
      const document = documents?.find((item) => item.attachment.id === attachmentId) ?? null;
      const firstQuestion = document?.extracted_items[0]?.questions[0] ?? null;
      if (!firstQuestion) {
        setMessage("No open question found for this document.");
        return;
      }
      const answer = window.prompt(firstQuestion.question);
      if (!answer?.trim()) return;
      const updated = await answerDocumentQuestion(attachmentId, firstQuestion.code, answer.trim());
      setDocuments((current) => current?.map((item) => (item.attachment.id === attachmentId ? updated : item)) ?? current);
      setMessage("Question answered and document reclassified.");
    } catch (error) {
      setMessage(errorMessage(error, "Document action failed"));
    }
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
            <input type="file" accept=".txt,.pdf,.png,.jpg,.jpeg,.webp,.mp3,.m4a,.wav,.ogg" className="hidden" onChange={onReceiptChange} disabled={busy} />
            {busy ? "Uploading…" : "Upload document"}
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
        title="Manual text entry"
        description="Use this for chat-like spending notes or manual dashboard capture when you do not have a file."
      >
        <div className="space-y-3">
          <textarea
            className="min-h-28 w-full rounded-2xl border border-[var(--line)] bg-[var(--surface)] px-4 py-3 text-sm"
            value={textEntry}
            onChange={(event) => setTextEntry(event.target.value)}
            placeholder="Examples: I spent $25 on gas today. Business paid $120 for internet. Client paid invoice 1003."
            disabled={textBusy}
          />
          <div className="flex justify-end">
            <button
              type="button"
              onClick={() => void handleTextIngest()}
              disabled={textBusy || !textEntry.trim()}
              className="rounded-xl bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-[var(--accent-ink)] disabled:opacity-60"
            >
              {textBusy ? "Ingesting…" : "Ingest text note"}
            </button>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        title="Recent documents"
        description="Uploaded files remain untrusted until extracted, classified, and reviewed."
      >
        {documentsError ? (
          <div className="rounded-xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger-ink)]">
            {documentsError}
          </div>
        ) : documents === null ? (
          <p className="text-sm text-[var(--muted)]">Loading…</p>
        ) : documents.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">No uploaded documents yet.</p>
        ) : (
          <div className="space-y-4">
            {documents.map((document) => {
              const item = document.extracted_items[0] ?? null;
              const duplicate = document.extraction?.duplicate_detected ?? false;
              return (
                <article key={document.attachment.id} className="rounded-2xl bg-[var(--surface)] p-4">
                  <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium">{document.attachment.filename}</p>
                        <span className="rounded-full bg-[var(--panel)] px-3 py-1 text-xs uppercase tracking-[0.2em] text-[var(--muted)]">
                          {document.attachment.content_type}
                        </span>
                        {document.extraction ? (
                          <span className="rounded-full bg-[var(--panel)] px-3 py-1 text-xs uppercase tracking-[0.2em] text-[var(--muted)]">
                            {document.extraction.status}
                          </span>
                        ) : null}
                        {item ? (
                          <span className="rounded-full bg-[var(--panel)] px-3 py-1 text-xs uppercase tracking-[0.2em] text-[var(--muted)]">
                            {item.detected_document_type}
                          </span>
                        ) : null}
                        {duplicate ? (
                          <span className="rounded-full bg-[var(--danger-bg)] px-3 py-1 text-xs uppercase tracking-[0.2em] text-[var(--danger-ink)]">
                            duplicate
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-2 text-sm text-[var(--muted)]">
                        {item?.amount ? displayMoney(item.amount, item.currency) : "No amount"} ·{" "}
                        {item?.date ?? "No date"} · {item?.candidate_entity_type ?? "unknown entity"}
                      </p>
                      <p className="mt-2 text-sm text-[var(--muted)]">
                        {item?.merchant ?? item?.vendor ?? item?.customer ?? "No merchant/vendor/customer detected"}
                      </p>
                      <p className="mt-2 text-sm">
                        Confidence: {item?.confidence_level ?? "low"}
                        {item?.questions.length ? ` · ${item.questions.length} open question${item.questions.length === 1 ? "" : "s"}` : ""}
                        {document.candidate?.rationale ? ` · ${document.candidate.rationale}` : ""}
                      </p>
                      {item?.raw_text_reference ? (
                        <pre className="mt-3 overflow-x-auto rounded-xl bg-[var(--panel)] p-3 text-xs text-[var(--muted)]">
                          {item.raw_text_reference}
                        </pre>
                      ) : null}
                      {item?.questions.length ? (
                        <div className="mt-3 space-y-2">
                          {item.questions.map((question) => (
                            <div key={`${document.attachment.id}-${question.code}`} className="rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2 text-sm">
                              {question.question}
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </div>

                    <div className="flex flex-wrap items-center gap-2 xl:justify-end">
                      <button
                        type="button"
                        onClick={() => void handleDocumentAction(document.attachment.id, "classify")}
                        className="rounded-xl border border-[var(--line)] px-3 py-2 text-sm font-semibold"
                      >
                        Reclassify
                      </button>
                      {item?.questions.length ? (
                        <button
                          type="button"
                          onClick={() => void handleDocumentAction(document.attachment.id, "answer")}
                          className="rounded-xl border border-[var(--line)] px-3 py-2 text-sm font-semibold"
                        >
                          Answer question
                        </button>
                      ) : null}
                      {document.candidate ? (
                        <button
                          type="button"
                          onClick={() => void handleDocumentAction(document.attachment.id, "draft")}
                          className="rounded-xl bg-[var(--accent)] px-3 py-2 text-sm font-semibold text-[var(--accent-ink)]"
                        >
                          Create draft
                        </button>
                      ) : null}
                      <button
                        type="button"
                        onClick={() => void handleDocumentAction(document.attachment.id, "reject")}
                        className="rounded-xl border border-[var(--line)] px-3 py-2 text-sm font-semibold"
                      >
                        Reject
                      </button>
                      <a href="/audit-log" className="rounded-xl border border-[var(--line)] px-3 py-2 text-sm font-semibold">
                        Audit trail
                      </a>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </SectionCard>

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
