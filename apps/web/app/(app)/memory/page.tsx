"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { SectionCard } from "../../_components/cards";
import {
  ApiRequestError,
  createMemory,
  deleteMemory,
  entities,
  expireMemory,
  listMemories,
  reviewMemory,
  type Entity,
  type MemoryRecord,
  type MemoryReviewStatus,
  type MemoryType,
} from "../../_lib/api";

const MEMORY_TYPES: Array<{ value: MemoryType; label: string }> = [
  { value: "user_profile", label: "User profile" },
  { value: "personal_preference", label: "Personal preference" },
  { value: "business_profile", label: "Business profile" },
  { value: "financial_rule", label: "Financial rule" },
  { value: "merchant_rule", label: "Merchant rule" },
  { value: "tax_context", label: "Tax context" },
  { value: "goal_context", label: "Goal context" },
  { value: "risk_preference", label: "Risk preference" },
  { value: "recurring_pattern", label: "Recurring pattern" },
  { value: "advisor_note", label: "Advisor note" },
];

type MemoryRowState = {
  action: "expire" | "delete" | "review" | null;
  error: string | null;
  reviewStatus: MemoryReviewStatus;
};

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) return error.message;
  return error instanceof Error ? error.message : fallback;
}

function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

export default function MemoryPage() {
  const [items, setItems] = useState<MemoryRecord[]>([]);
  const [entitiesList, setEntitiesList] = useState<Entity[]>([]);
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<MemoryType | "">("");
  const [formType, setFormType] = useState<MemoryType>("advisor_note");
  const [entityId, setEntityId] = useState("");
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [content, setContent] = useState("");
  const [keywords, setKeywords] = useState("");
  const [consentGranted, setConsentGranted] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [rowState, setRowState] = useState<Record<string, MemoryRowState>>({});

  async function load(activeRef?: { current: boolean }) {
    try {
      setError(null);
      setLoading(true);
      const [nextEntities, nextMemories] = await Promise.all([
        entities(),
        listMemories({ query, memory_type: typeFilter, limit: 100 }),
      ]);
      if (activeRef && !activeRef.current) return;
      setEntitiesList(nextEntities);
      setItems(nextMemories);
      setRowState((current) => {
        const next: Record<string, MemoryRowState> = {};
        for (const memory of nextMemories) {
          next[memory.id] = current[memory.id] ?? {
            action: null,
            error: null,
            reviewStatus: "accepted",
          };
        }
        return next;
      });
      if (!entityId && nextEntities[0]) {
        setEntityId(nextEntities[0].id);
      }
    } catch (loadError) {
      if (!activeRef || activeRef.current) {
        setError(errorMessage(loadError, "Failed to load memory"));
        setItems([]);
      }
    } finally {
      if (!activeRef || activeRef.current) setLoading(false);
    }
  }

  useEffect(() => {
    const activeRef = { current: true };
    void load(activeRef);
    return () => {
      activeRef.current = false;
    };
  }, [query, typeFilter]);

  const entityById = useMemo(
    () => Object.fromEntries(entitiesList.map((item) => [item.id, item])),
    [entitiesList],
  );

  function resetForm() {
    setFormType("advisor_note");
    setTitle("");
    setSummary("");
    setContent("");
    setKeywords("");
    setConsentGranted(false);
  }

  function setMemoryRowState(memoryId: string, patch: Partial<MemoryRowState>) {
    setRowState((current) => ({
      ...current,
      [memoryId]: {
        action: current[memoryId]?.action ?? null,
        error: current[memoryId]?.error ?? null,
        reviewStatus: current[memoryId]?.reviewStatus ?? "accepted",
        ...patch,
      },
    }));
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const created = await createMemory({
        memory_type: formType,
        title: title.trim(),
        content: content.trim(),
        summary: summary.trim() || null,
        keywords: keywords
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean),
        source: "user",
        entity_id: entityId || null,
        consent_granted: consentGranted,
      });
      setItems((current) => [created, ...current]);
      setRowState((current) => ({
        ...current,
        [created.id]: { action: null, error: null, reviewStatus: "accepted" },
      }));
      setMessage("Memory saved.");
      resetForm();
    } catch (createError) {
      setError(errorMessage(createError, "Failed to save memory"));
    } finally {
      setSaving(false);
    }
  }

  async function handleExpire(memoryId: string) {
    setMemoryRowState(memoryId, { action: "expire", error: null });
    try {
      const updated = await expireMemory(memoryId);
      setItems((current) => current.map((item) => (item.id === memoryId ? updated : item)));
      setMemoryRowState(memoryId, { action: null });
    } catch (actionError) {
      setMemoryRowState(memoryId, {
        action: null,
        error: errorMessage(actionError, "Failed to expire memory"),
      });
    }
  }

  async function handleDelete(memoryId: string) {
    setMemoryRowState(memoryId, { action: "delete", error: null });
    try {
      await deleteMemory(memoryId);
      setItems((current) => current.filter((item) => item.id !== memoryId));
    } catch (actionError) {
      setMemoryRowState(memoryId, {
        action: null,
        error: errorMessage(actionError, "Failed to delete memory"),
      });
    }
  }

  async function handleReview(memoryId: string) {
    const status = rowState[memoryId]?.reviewStatus ?? "accepted";
    setMemoryRowState(memoryId, { action: "review", error: null });
    try {
      await reviewMemory(memoryId, { status });
      setMemoryRowState(memoryId, { action: null });
      setMessage(`Review saved as ${status}.`);
    } catch (actionError) {
      setMemoryRowState(memoryId, {
        action: null,
        error: errorMessage(actionError, "Failed to save review"),
      });
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--accent)]">Memory</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">Memory workspace</h1>
        <p className="mt-3 max-w-3xl text-sm text-[var(--muted)]">
          Review user-approved notes, system-learned merchant rules, and context that helps MIAF
          stay consistent over time.
        </p>
      </div>

      {message ? (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-5 py-4 text-sm text-emerald-900">
          {message}
        </div>
      ) : null}

      {error ? (
        <div className="rounded-2xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-5 py-4 text-sm text-[var(--danger-ink)]">
          {error}
        </div>
      ) : null}

      <SectionCard
        title="Create memory"
        description="Explicit consent is required for user-created memories. Sensitive credentials are blocked."
      >
        <form className="space-y-4" onSubmit={handleCreate}>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <label className="text-sm font-medium">
              Memory type
              <select
                className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
                value={formType}
                onChange={(event) => setFormType(event.target.value as MemoryType)}
                disabled={saving}
              >
                {MEMORY_TYPES.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="text-sm font-medium">
              Entity
              <select
                className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
                value={entityId}
                onChange={(event) => setEntityId(event.target.value)}
                disabled={saving}
              >
                <option value="">No specific entity</option>
                {entitiesList.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} ({item.mode})
                  </option>
                ))}
              </select>
            </label>

            <label className="text-sm font-medium md:col-span-2">
              Title
              <input
                className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                maxLength={200}
                required
                disabled={saving}
              />
            </label>
          </div>

          <label className="block text-sm font-medium">
            Summary
            <input
              className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
              value={summary}
              onChange={(event) => setSummary(event.target.value)}
              maxLength={500}
              placeholder="Optional short summary"
              disabled={saving}
            />
          </label>

          <label className="block text-sm font-medium">
            Content
            <textarea
              className="mt-2 min-h-32 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
              value={content}
              onChange={(event) => setContent(event.target.value)}
              maxLength={4000}
              required
              disabled={saving}
            />
          </label>

          <label className="block text-sm font-medium">
            Keywords
            <input
              className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
              value={keywords}
              onChange={(event) => setKeywords(event.target.value)}
              placeholder="comma, separated, keywords"
              disabled={saving}
            />
          </label>

          <label className="flex items-start gap-3 rounded-2xl border border-[var(--line)] bg-[var(--surface)] px-4 py-3 text-sm">
            <input
              type="checkbox"
              checked={consentGranted}
              onChange={(event) => setConsentGranted(event.target.checked)}
              disabled={saving}
              className="mt-0.5"
            />
            <span>
              I confirm this note is safe to store as memory and does not include passwords, API keys,
              or other credentials.
            </span>
          </label>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={saving || !consentGranted}
              className="rounded-xl bg-[var(--accent)] px-5 py-3 text-sm font-semibold text-[var(--accent-ink)] transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? "Saving…" : "Save memory"}
            </button>
          </div>
        </form>
      </SectionCard>

      <SectionCard
        title="Search and review"
        description="Merchant-rule memories created from corrected imports also appear here."
      >
        <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_16rem]">
          <label className="text-sm font-medium">
            Search
            <input
              className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search title, content, or summary"
            />
          </label>
          <label className="text-sm font-medium">
            Type
            <select
              className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
              value={typeFilter}
              onChange={(event) => setTypeFilter(event.target.value as MemoryType | "")}
            >
              <option value="">All active types</option>
              {MEMORY_TYPES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="mt-5 space-y-4">
          {loading ? (
            <p className="text-sm text-[var(--muted)]">Loading memory…</p>
          ) : items.length === 0 ? (
            <p className="text-sm text-[var(--muted)]">No active memory matches the current filters.</p>
          ) : (
            items.map((item) => {
              const state = rowState[item.id] ?? {
                action: null,
                error: null,
                reviewStatus: "accepted" as MemoryReviewStatus,
              };
              const entity = item.entity_id ? entityById[item.entity_id] : null;
              return (
                <article key={item.id} className="rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-4">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-lg font-semibold">{item.title}</p>
                        <span className="rounded-full bg-[var(--panel)] px-2.5 py-1 text-xs uppercase tracking-[0.15em] text-[var(--muted)]">
                          {item.memory_type}
                        </span>
                        <span className="rounded-full bg-[var(--panel)] px-2.5 py-1 text-xs uppercase tracking-[0.15em] text-[var(--muted)]">
                          {item.source}
                        </span>
                      </div>
                      <p className="mt-2 text-sm text-[var(--muted)]">
                        {entity ? `${entity.name} (${entity.mode})` : "No specific entity"} · Last accessed{" "}
                        {formatTimestamp(item.last_accessed_at)} · Expires {formatTimestamp(item.expires_at)}
                      </p>
                      {item.summary ? <p className="mt-3 text-sm font-medium">{item.summary}</p> : null}
                      <p className="mt-2 whitespace-pre-wrap text-sm leading-6">{item.content}</p>
                      {item.keywords?.length ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {item.keywords.map((keyword) => (
                            <span
                              key={`${item.id}-${keyword}`}
                              className="rounded-full bg-[var(--panel)] px-2.5 py-1 text-xs text-[var(--muted)]"
                            >
                              {keyword}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </div>

                    <div className="w-full max-w-sm space-y-3">
                      <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                        <select
                          className="rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2 text-sm"
                          value={state.reviewStatus}
                          onChange={(event) =>
                            setMemoryRowState(item.id, {
                              reviewStatus: event.target.value as MemoryReviewStatus,
                            })
                          }
                          disabled={state.action !== null}
                        >
                          <option value="accepted">Review: accepted</option>
                          <option value="needs_update">Review: needs update</option>
                          <option value="archived">Review: archived</option>
                        </select>
                        <button
                          type="button"
                          onClick={() => void handleReview(item.id)}
                          disabled={state.action !== null}
                          className="rounded-xl border border-[var(--line)] px-3 py-2 text-sm font-medium disabled:opacity-60"
                        >
                          {state.action === "review" ? "Saving…" : "Save review"}
                        </button>
                      </div>

                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => void handleExpire(item.id)}
                          disabled={state.action !== null}
                          className="rounded-xl border border-[var(--line)] px-3 py-2 text-sm font-medium disabled:opacity-60"
                        >
                          {state.action === "expire" ? "Expiring…" : "Expire"}
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleDelete(item.id)}
                          disabled={state.action !== null}
                          className="rounded-xl bg-[var(--danger-bg)] px-3 py-2 text-sm font-medium text-[var(--danger-ink)] disabled:opacity-60"
                        >
                          {state.action === "delete" ? "Deleting…" : "Delete"}
                        </button>
                      </div>

                      {state.error ? (
                        <p className="text-xs text-[var(--danger-ink)]">{state.error}</p>
                      ) : null}
                    </div>
                  </div>
                </article>
              );
            })
          )}
        </div>
      </SectionCard>
    </div>
  );
}
