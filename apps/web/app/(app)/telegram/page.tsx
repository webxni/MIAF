"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { SectionCard } from "../../_components/cards";
import {
  ApiRequestError,
  createTelegramLink,
  entities,
  listTelegramLinks,
  listTelegramMessages,
  type Entity,
  type TelegramActiveMode,
  type TelegramLink,
  type TelegramMessage,
} from "../../_lib/api";

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) return error.message;
  return error instanceof Error ? error.message : fallback;
}

function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

function formatTextPreview(value: string | null): string {
  if (!value) return "—";
  return value.length > 140 ? `${value.slice(0, 140)}…` : value;
}

export default function TelegramPage() {
  const [entitiesList, setEntitiesList] = useState<Entity[]>([]);
  const [links, setLinks] = useState<TelegramLink[]>([]);
  const [messages, setMessages] = useState<TelegramMessage[]>([]);
  const [telegramUserId, setTelegramUserId] = useState("");
  const [telegramChatId, setTelegramChatId] = useState("");
  const [telegramUsername, setTelegramUsername] = useState("");
  const [personalEntityId, setPersonalEntityId] = useState("");
  const [businessEntityId, setBusinessEntityId] = useState("");
  const [activeMode, setActiveMode] = useState<TelegramActiveMode>("personal");
  const [isActive, setIsActive] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function load(activeRef?: { current: boolean }) {
    try {
      setError(null);
      setLoading(true);
      const [nextEntities, nextLinks, nextMessages] = await Promise.all([
        entities(),
        listTelegramLinks(),
        listTelegramMessages({ limit: 50 }),
      ]);
      if (activeRef && !activeRef.current) return;
      setEntitiesList(nextEntities);
      setLinks(nextLinks);
      setMessages(nextMessages);

      if (!personalEntityId || !businessEntityId) {
        const personal = nextEntities.find((item) => item.mode === "personal") ?? null;
        const business = nextEntities.find((item) => item.mode === "business") ?? null;
        if (personal && !personalEntityId) setPersonalEntityId(personal.id);
        if (business && !businessEntityId) setBusinessEntityId(business.id);
      }
    } catch (loadError) {
      if (!activeRef || activeRef.current) {
        setError(errorMessage(loadError, "Failed to load Telegram settings"));
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
  }, []);

  const personalEntities = useMemo(
    () => entitiesList.filter((item) => item.mode === "personal"),
    [entitiesList],
  );
  const businessEntities = useMemo(
    () => entitiesList.filter((item) => item.mode === "business"),
    [entitiesList],
  );
  const entityById = useMemo(
    () => Object.fromEntries(entitiesList.map((item) => [item.id, item])),
    [entitiesList],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const created = await createTelegramLink({
        telegram_user_id: telegramUserId.trim(),
        telegram_chat_id: telegramChatId.trim(),
        telegram_username: telegramUsername.trim() || null,
        personal_entity_id: personalEntityId || null,
        business_entity_id: businessEntityId || null,
        active_mode: activeMode,
        is_active: isActive,
      });
      setLinks((current) => [created, ...current.filter((item) => item.id !== created.id)]);
      setMessage("Telegram link saved.");
    } catch (saveError) {
      setError(errorMessage(saveError, "Failed to save Telegram link"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--accent)]">Telegram</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">Telegram link manager</h1>
        <p className="mt-3 max-w-3xl text-sm text-[var(--muted)]">
          Link a Telegram user and chat to your workspace, choose which entity each mode routes to,
          and review recent inbound and outbound message logs.
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
        title="Setup link"
        description="This page manages the internal workspace link only. Your Telegram bot or webhook still needs to send inbound events to the backend."
      >
        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <label className="text-sm font-medium">
              Telegram user ID
              <input
                className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
                value={telegramUserId}
                onChange={(event) => setTelegramUserId(event.target.value)}
                required
                disabled={saving}
              />
            </label>

            <label className="text-sm font-medium">
              Telegram chat ID
              <input
                className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
                value={telegramChatId}
                onChange={(event) => setTelegramChatId(event.target.value)}
                required
                disabled={saving}
              />
            </label>

            <label className="text-sm font-medium">
              Telegram username
              <input
                className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
                value={telegramUsername}
                onChange={(event) => setTelegramUsername(event.target.value)}
                placeholder="@yourhandle"
                disabled={saving}
              />
            </label>

            <label className="text-sm font-medium">
              Personal mode entity
              <select
                className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
                value={personalEntityId}
                onChange={(event) => setPersonalEntityId(event.target.value)}
                disabled={saving}
              >
                <option value="">No personal entity</option>
                {personalEntities.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="text-sm font-medium">
              Business mode entity
              <select
                className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
                value={businessEntityId}
                onChange={(event) => setBusinessEntityId(event.target.value)}
                disabled={saving}
              >
                <option value="">No business entity</option>
                {businessEntities.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="text-sm font-medium">
              Active mode
              <select
                className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
                value={activeMode}
                onChange={(event) => setActiveMode(event.target.value as TelegramActiveMode)}
                disabled={saving}
              >
                <option value="personal">Personal</option>
                <option value="business">Business</option>
              </select>
            </label>
          </div>

          <label className="flex items-start gap-3 rounded-2xl border border-[var(--line)] bg-[var(--surface)] px-4 py-3 text-sm">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(event) => setIsActive(event.target.checked)}
              disabled={saving}
              className="mt-0.5"
            />
            <span>Keep this Telegram link active for inbound message routing.</span>
          </label>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className="rounded-xl bg-[var(--accent)] px-5 py-3 text-sm font-semibold text-[var(--accent-ink)] transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? "Saving…" : "Save Telegram link"}
            </button>
          </div>
        </form>
      </SectionCard>

      <SectionCard
        title="How routing works"
        description="These commands and behaviors come from the current Telegram service implementation."
      >
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-2xl bg-[var(--surface)] p-4 text-sm text-[var(--muted)]">
            <p className="font-semibold text-[var(--ink)]">Supported commands</p>
            <p className="mt-2">`/start`, `/personal`, `/business`, `/summary`, `/budget`, `/cash`, `/help`</p>
          </div>
          <div className="rounded-2xl bg-[var(--surface)] p-4 text-sm text-[var(--muted)]">
            <p className="font-semibold text-[var(--ink)]">Current message handling</p>
            <p className="mt-2">
              Text messages route into the agent or business-expense drafting flow. Images and PDFs
              are acknowledged as queued documents. Voice notes are still placeholder behavior.
            </p>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="Saved links" description="Most recent links first. Saving the same Telegram user updates the existing link.">
        {loading ? (
          <p className="text-sm text-[var(--muted)]">Loading links…</p>
        ) : links.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">No Telegram links saved yet.</p>
        ) : (
          <div className="space-y-3">
            {links.map((link) => (
              <article key={link.id} className="rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-4">
                <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-semibold">
                        {link.telegram_username ? `@${link.telegram_username.replace(/^@/, "")}` : link.telegram_user_id}
                      </p>
                      <span className="rounded-full bg-[var(--panel)] px-2.5 py-1 text-xs uppercase tracking-[0.15em] text-[var(--muted)]">
                        {link.active_mode}
                      </span>
                      <span className="rounded-full bg-[var(--panel)] px-2.5 py-1 text-xs uppercase tracking-[0.15em] text-[var(--muted)]">
                        {link.is_active ? "active" : "inactive"}
                      </span>
                    </div>
                    <p className="mt-2 text-sm text-[var(--muted)]">
                      User ID {link.telegram_user_id} · Chat ID {link.telegram_chat_id} · Last seen{" "}
                      {formatTimestamp(link.last_seen_at)}
                    </p>
                  </div>
                  <div className="text-sm text-[var(--muted)]">
                    <p>
                      Personal:{" "}
                      {link.personal_entity_id ? entityById[link.personal_entity_id]?.name ?? link.personal_entity_id : "—"}
                    </p>
                    <p>
                      Business:{" "}
                      {link.business_entity_id ? entityById[link.business_entity_id]?.name ?? link.business_entity_id : "—"}
                    </p>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </SectionCard>

      <SectionCard title="Recent message log" description="Newest first. This is the current server-side log of inbound and outbound Telegram traffic.">
        {loading ? (
          <p className="text-sm text-[var(--muted)]">Loading messages…</p>
        ) : messages.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">No Telegram messages logged yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <div className="min-w-[70rem] space-y-3">
              <div className="grid grid-cols-[8rem_8rem_8rem_12rem_minmax(0,1.5fr)] gap-3 px-2 text-xs uppercase tracking-[0.2em] text-[var(--muted)]">
                <span>Direction</span>
                <span>Type</span>
                <span>Status</span>
                <span>Created</span>
                <span>Message</span>
              </div>
              {messages.map((item) => (
                <div key={item.id} className="grid grid-cols-[8rem_8rem_8rem_12rem_minmax(0,1.5fr)] gap-3 rounded-2xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm">
                  <span>{item.direction}</span>
                  <span>{item.message_type}</span>
                  <span>{item.status}</span>
                  <span className="text-xs">{formatTimestamp(item.created_at)}</span>
                  <span className="min-w-0 break-words text-[var(--muted)]">
                    {formatTextPreview(item.text_body) !== "—"
                      ? formatTextPreview(item.text_body)
                      : item.file_name
                        ? `${item.file_name}${item.file_mime_type ? ` · ${item.file_mime_type}` : ""}`
                        : "No text body"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </SectionCard>
    </div>
  );
}
