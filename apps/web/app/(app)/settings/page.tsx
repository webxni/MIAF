"use client";

import { FormEvent, useEffect, useState } from "react";

import { SectionCard } from "../../_components/cards";
import {
  getSettings,
  me,
  updateSettings,
  type AIProvider,
  type User,
  type UserSettings,
} from "../../_lib/api";

const PROVIDERS: Array<{ value: AIProvider; label: string }> = [
  { value: "heuristic", label: "Heuristic" },
  { value: "anthropic", label: "Anthropic" },
  { value: "openai", label: "OpenAI" },
  { value: "gemini", label: "Gemini" },
];

export default function SettingsPage() {
  const [user, setUser] = useState<User | null>(null);
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [jurisdiction, setJurisdiction] = useState("");
  const [baseCurrency, setBaseCurrency] = useState("USD");
  const [fiscalYearStartMonth, setFiscalYearStartMonth] = useState("1");
  const [aiProvider, setAiProvider] = useState<AIProvider | "">("");
  const [aiModel, setAiModel] = useState("");
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [apiKeyDirty, setApiKeyDirty] = useState(false);
  const [removeApiKey, setRemoveApiKey] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.all([me(), getSettings()])
      .then(([nextUser, nextSettings]) => {
        if (!active) return;
        hydrate(nextUser, nextSettings);
        setLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load settings");
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  function hydrate(nextUser: User, nextSettings: UserSettings) {
    setUser(nextUser);
    setSettings(nextSettings);
    setJurisdiction(nextSettings.jurisdiction ?? "");
    setBaseCurrency(nextSettings.base_currency ?? "USD");
    setFiscalYearStartMonth(String(nextSettings.fiscal_year_start_month ?? 1));
    setAiProvider(nextSettings.ai_provider ?? "");
    setAiModel(nextSettings.ai_model ?? "");
    setApiKeyInput(
      nextSettings.ai_api_key_present && nextSettings.ai_api_key_hint
        ? `••••${nextSettings.ai_api_key_hint}`
        : "",
    );
    setApiKeyDirty(false);
    setRemoveApiKey(false);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const updated = await updateSettings({
        jurisdiction: jurisdiction.trim() || null,
        base_currency: baseCurrency.trim().toUpperCase() || null,
        fiscal_year_start_month: Number(fiscalYearStartMonth),
        ai_provider: aiProvider || null,
        ai_model: aiModel.trim() || null,
        ...(removeApiKey
          ? { ai_api_key_clear: true }
          : apiKeyDirty && apiKeyInput.trim()
            ? { ai_api_key: apiKeyInput.trim() }
            : {}),
      });
      if (user) {
        hydrate(user, updated);
      } else {
        hydrate(await me(), updated);
      }
      setMessage("Settings saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save settings");
    } finally {
      setSaving(false);
    }
  }

  const keyHint = settings?.ai_api_key_hint ?? null;

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--accent)]">Settings</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">User settings</h1>
        <p className="mt-3 max-w-3xl text-sm text-[var(--muted)]">
          Configure the owner profile, accounting defaults, and the provider credentials the agent
          should use on this local-first installation.
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

      <form className="space-y-6" onSubmit={handleSubmit}>
        <SectionCard
          title="Profile"
          description="Name and email are read-only for now and come from the authenticated account."
        >
          <div className="grid gap-4 md:grid-cols-2">
            <label className="text-sm font-medium">
              Name
              <input
                className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm text-[var(--muted)]"
                value={user?.name ?? ""}
                readOnly
                disabled
              />
            </label>
            <label className="text-sm font-medium">
              Email
              <input
                className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm text-[var(--muted)]"
                value={user?.email ?? ""}
                readOnly
                disabled
              />
            </label>
          </div>
        </SectionCard>

        <SectionCard
          title="Accounting"
          description="Tax outputs remain labeled estimates until jurisdiction-specific logic is configured."
        >
          <div className="grid gap-4 md:grid-cols-3">
            <label className="text-sm font-medium">
              Jurisdiction
              <input
                className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
                value={jurisdiction}
                onChange={(event) => setJurisdiction(event.target.value)}
                maxLength={64}
                placeholder="US-CA"
                disabled={loading || saving}
              />
            </label>
            <label className="text-sm font-medium">
              Base currency
              <input
                className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm uppercase"
                value={baseCurrency}
                onChange={(event) => setBaseCurrency(event.target.value.toUpperCase())}
                maxLength={3}
                placeholder="USD"
                disabled={loading || saving}
              />
            </label>
            <label className="text-sm font-medium">
              Fiscal year start month
              <select
                className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
                value={fiscalYearStartMonth}
                onChange={(event) => setFiscalYearStartMonth(event.target.value)}
                disabled={loading || saving}
              >
                {Array.from({ length: 12 }, (_, index) => {
                  const month = String(index + 1);
                  return (
                    <option key={month} value={month}>
                      {month}
                    </option>
                  );
                })}
              </select>
            </label>
          </div>
        </SectionCard>

        <SectionCard
          title="AI provider"
          description="Provider secrets are stored server-side as Fernet-encrypted ciphertext with only a last-four hint returned to the UI."
        >
          <div className="grid gap-4 md:grid-cols-2">
            <label className="text-sm font-medium">
              Provider
              <select
                className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
                value={aiProvider}
                onChange={(event) => setAiProvider(event.target.value as AIProvider | "")}
                disabled={loading || saving}
              >
                <option value="">Not configured</option>
                {PROVIDERS.map((provider) => (
                  <option key={provider.value} value={provider.value}>
                    {provider.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm font-medium">
              Model
              <input
                className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
                value={aiModel}
                onChange={(event) => setAiModel(event.target.value)}
                maxLength={64}
                placeholder="Provider default"
                disabled={loading || saving}
              />
            </label>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
            <label className="text-sm font-medium">
              API key
              <input
                className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
                type={settings?.ai_api_key_present && !apiKeyDirty && !removeApiKey ? "text" : "password"}
                value={apiKeyInput}
                onFocus={() => {
                  if (settings?.ai_api_key_present && !apiKeyDirty && !removeApiKey) {
                    setApiKeyInput("");
                    setApiKeyDirty(true);
                  }
                }}
                onChange={(event) => {
                  setApiKeyDirty(true);
                  setRemoveApiKey(false);
                  setApiKeyInput(event.target.value);
                }}
                placeholder={keyHint ? `••••${keyHint}` : "Paste provider API key"}
                autoComplete="off"
                disabled={loading || saving}
              />
            </label>
            <button
              type="button"
              onClick={() => {
                setRemoveApiKey(true);
                setApiKeyDirty(false);
                setApiKeyInput("");
                setMessage(null);
              }}
              className="rounded-xl border border-[var(--line)] px-4 py-3 text-sm text-[var(--muted)] transition hover:bg-[var(--surface)] hover:text-[var(--ink)] disabled:cursor-not-allowed disabled:opacity-60"
              disabled={loading || saving || !settings?.ai_api_key_present}
            >
              Remove key
            </button>
          </div>
          <p className="mt-2 text-sm text-[var(--muted)]">
            {removeApiKey
              ? "The stored key will be removed when you save."
              : settings?.ai_api_key_present
                ? `Stored key ending in ${keyHint ?? "unknown"}. Focus the field to replace it.`
                : "No provider key is stored yet."}
          </p>
        </SectionCard>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={loading || saving}
            className="rounded-xl bg-[var(--accent)] px-5 py-3 text-sm font-semibold text-[var(--accent-ink)] transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {saving ? "Saving…" : "Save settings"}
          </button>
        </div>
      </form>
    </div>
  );
}
