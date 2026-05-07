"use client";

import { FormEvent, useEffect, useState } from "react";

import { SectionCard } from "../../_components/cards";
import {
  ApiRequestError,
  changePassword,
  checkTailscaleStatus,
  createInvite,
  getSettings,
  getTailscaleSettings,
  listInvites,
  me,
  resetTailscaleServe,
  revokeAllSessions,
  revokeInvite,
  startTailscaleServe,
  updateSettings,
  type AIProvider,
  type Invite,
  type TailscaleLiveStatus,
  type User,
  type UserSettings,
} from "../../_lib/api";
import { brand } from "../../_lib/brand";

const PROVIDERS: Array<{ value: AIProvider; label: string }> = [
  { value: "heuristic", label: "Heuristic" },
  { value: "anthropic", label: "Anthropic" },
  { value: "openai", label: "OpenAI" },
  { value: "gemini", label: "Gemini" },
];

const INVITE_ROLES = [
  { value: "admin", label: "Admin" },
  { value: "accountant", label: "Accountant" },
  { value: "viewer", label: "Viewer" },
] as const;

function formatInviteDate(value: string): string {
  return new Date(value).toLocaleString();
}

function isPendingInvite(invite: Invite): boolean {
  return !invite.accepted_at && !invite.is_revoked && new Date(invite.expires_at).getTime() > Date.now();
}

function inviteErrorMessage(error: ApiRequestError): string {
  if (error.status === 403 || error.code === "role_forbidden") {
    return "Insufficient permission. Only owners and admins can manage team invites.";
  }
  if (error.code === "invite_already_member") {
    return "That email is already part of this workspace.";
  }
  if (error.code === "invite_already_accepted") {
    return "That invite has already been accepted.";
  }
  return error.message;
}

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
  const [openaiDocumentAiEnabled, setOpenaiDocumentAiEnabled] = useState(false);
  const [openaiDocumentAiConsentGranted, setOpenaiDocumentAiConsentGranted] = useState(false);
  const [openaiVisionModel, setOpenaiVisionModel] = useState("gpt-4o-mini");
  const [openaiPdfModel, setOpenaiPdfModel] = useState("gpt-4o-mini");
  const [openaiTranscriptionModel, setOpenaiTranscriptionModel] = useState("gpt-4o-mini-transcribe");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [tailscale, setTailscale] = useState<TailscaleLiveStatus | null>(null);
  const [tsLoading, setTsLoading] = useState(false);
  const [tsError, setTsError] = useState<string | null>(null);

  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [pwMessage, setPwMessage] = useState<string | null>(null);
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwSaving, setPwSaving] = useState(false);

  const [invites, setInvites] = useState<Invite[]>([]);
  const [invitesLoading, setInvitesLoading] = useState(true);
  const [invitesError, setInvitesError] = useState<string | null>(null);
  const [invitePermissionDenied, setInvitePermissionDenied] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<(typeof INVITE_ROLES)[number]["value"]>("viewer");
  const [inviteSaving, setInviteSaving] = useState(false);
  const [inviteMessage, setInviteMessage] = useState<string | null>(null);
  const [inviteActionError, setInviteActionError] = useState<string | null>(null);
  const [latestInviteLink, setLatestInviteLink] = useState<string | null>(null);
  const [copiedInviteLink, setCopiedInviteLink] = useState(false);
  const [revokingInviteId, setRevokingInviteId] = useState<string | null>(null);

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

  useEffect(() => {
    let active = true;
    getTailscaleSettings()
      .then((status) => { if (active) setTailscale(status); })
      .catch(() => { /* silently ignore if endpoint not yet accessible */ });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    loadInvites().catch(() => {
      // Errors are handled in loadInvites state.
    });
    return () => {
      active = false;
    };

    async function loadInvites() {
      setInvitesLoading(true);
      setInvitesError(null);
      setInvitePermissionDenied(false);
      try {
        const rows = await listInvites();
        if (!active) return;
        setInvites(rows);
      } catch (err) {
        if (!active) return;
        if (err instanceof ApiRequestError && (err.status === 403 || err.code === "role_forbidden")) {
          setInvitePermissionDenied(true);
          setInvites([]);
        } else {
          setInvitesError(err instanceof Error ? err.message : "Failed to load invites");
        }
      } finally {
        if (active) setInvitesLoading(false);
      }
    }
  }, []);

  async function handleTsAction(action: () => Promise<TailscaleLiveStatus>) {
    setTsLoading(true);
    setTsError(null);
    try {
      const status = await action();
      setTailscale(status);
    } catch (err) {
      setTsError(err instanceof Error ? err.message : "Tailscale action failed");
    } finally {
      setTsLoading(false);
    }
  }

  async function handlePasswordChange(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (newPw.length < 12) {
      setPwError("New password must be at least 12 characters.");
      return;
    }
    setPwSaving(true);
    setPwMessage(null);
    setPwError(null);
    try {
      await changePassword(currentPw, newPw);
      setPwMessage("Password changed successfully.");
      setCurrentPw("");
      setNewPw("");
    } catch (err) {
      setPwError(err instanceof Error ? err.message : "Password change failed.");
    } finally {
      setPwSaving(false);
    }
  }

  async function handleRevokeAll() {
    if (!confirm("Sign out of all sessions? You will need to log in again.")) return;
    try {
      await revokeAllSessions();
      window.location.replace("/login");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to revoke sessions.");
    }
  }

  async function refreshInvites() {
    setInvitesLoading(true);
    setInvitesError(null);
    try {
      const rows = await listInvites();
      setInvites(rows);
      setInvitePermissionDenied(false);
    } catch (err) {
      if (err instanceof ApiRequestError && (err.status === 403 || err.code === "role_forbidden")) {
        setInvitePermissionDenied(true);
        setInvites([]);
      } else {
        setInvitesError(err instanceof Error ? err.message : "Failed to load invites");
      }
    } finally {
      setInvitesLoading(false);
    }
  }

  async function handleInviteSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setInviteSaving(true);
    setInviteMessage(null);
    setInviteActionError(null);
    setCopiedInviteLink(false);
    try {
      const created = await createInvite(inviteEmail.trim(), inviteRole);
      const inviteLink =
        typeof window === "undefined"
          ? `/accept-invite?token=${encodeURIComponent(created.token)}`
          : `${window.location.origin}/accept-invite?token=${encodeURIComponent(created.token)}`;
      setLatestInviteLink(inviteLink);
      setInviteMessage("Invite created. Copy the link now and share it securely.");
      setInviteEmail("");
      await refreshInvites();
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setInviteActionError(inviteErrorMessage(err));
      } else {
        setInviteActionError(err instanceof Error ? err.message : "Failed to create invite.");
      }
    } finally {
      setInviteSaving(false);
    }
  }

  async function handleCopyInviteLink() {
    if (!latestInviteLink) return;
    try {
      await navigator.clipboard.writeText(latestInviteLink);
      setCopiedInviteLink(true);
      setInviteMessage("Invite created. Link copied to clipboard.");
    } catch {
      setInviteActionError("Invite created, but copying failed. Copy the link manually.");
    }
  }

  async function handleRevokeInvite(inviteId: string) {
    setRevokingInviteId(inviteId);
    setInviteActionError(null);
    setInviteMessage(null);
    try {
      await revokeInvite(inviteId);
      setInviteMessage("Invite revoked.");
      setLatestInviteLink(null);
      setCopiedInviteLink(false);
      await refreshInvites();
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setInviteActionError(inviteErrorMessage(err));
      } else {
        setInviteActionError(err instanceof Error ? err.message : "Failed to revoke invite.");
      }
    } finally {
      setRevokingInviteId(null);
    }
  }

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
    setOpenaiDocumentAiEnabled(nextSettings.openai_document_ai_enabled ?? false);
    setOpenaiDocumentAiConsentGranted(nextSettings.openai_document_ai_consent_granted ?? false);
    setOpenaiVisionModel(nextSettings.openai_vision_model ?? "gpt-4o-mini");
    setOpenaiPdfModel(nextSettings.openai_pdf_model ?? "gpt-4o-mini");
    setOpenaiTranscriptionModel(nextSettings.openai_transcription_model ?? "gpt-4o-mini-transcribe");
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
        openai_document_ai_enabled: openaiDocumentAiEnabled,
        openai_document_ai_consent_granted: openaiDocumentAiConsentGranted,
        openai_vision_model: openaiVisionModel.trim() || null,
        openai_pdf_model: openaiPdfModel.trim() || null,
        openai_transcription_model: openaiTranscriptionModel.trim() || null,
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
  const pendingInvites = invites.filter(isPendingInvite);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--accent)]">Settings</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">User settings</h1>
        <p className="mt-3 max-w-3xl text-sm text-[var(--muted)]">
          Configura el perfil del propietario, los valores contables y las credenciales que{" "}
          {brand.agentName} debe usar en esta instalación local-first.
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

        <SectionCard
          title="AI document reading"
          description="Use this only if you are comfortable sending uploaded documents to your AI provider for extraction. Local parsing remains the default when this is off."
        >
          <div className="grid gap-4 md:grid-cols-2">
            <label className="flex items-start gap-3 rounded-xl border border-[var(--line)] bg-[var(--surface)] px-4 py-4 text-sm">
              <input
                type="checkbox"
                className="mt-1"
                checked={openaiDocumentAiEnabled}
                onChange={(event) => setOpenaiDocumentAiEnabled(event.target.checked)}
                disabled={loading || saving}
              />
              <span>
                <span className="block font-medium text-[var(--ink)]">Enable OpenAI document reading</span>
                <span className="mt-1 block text-[var(--muted)]">
                  Allows MIAF to use OpenAI for scanned PDFs, low-confidence images, ambiguous text, and audio transcription.
                </span>
              </span>
            </label>
            <label className="flex items-start gap-3 rounded-xl border border-[var(--line)] bg-[var(--surface)] px-4 py-4 text-sm">
              <input
                type="checkbox"
                className="mt-1"
                checked={openaiDocumentAiConsentGranted}
                onChange={(event) => setOpenaiDocumentAiConsentGranted(event.target.checked)}
                disabled={loading || saving}
              />
              <span>
                <span className="block font-medium text-[var(--ink)]">Allow MIAF to send uploaded documents to OpenAI for extraction</span>
                <span className="mt-1 block text-[var(--muted)]">
                  Keep this off if you only want local OCR, local PDF text extraction, and deterministic CSV parsing.
                </span>
              </span>
            </label>
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <label className="text-sm font-medium">
              Vision model
              <input
                className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
                value={openaiVisionModel}
                onChange={(event) => setOpenaiVisionModel(event.target.value)}
                maxLength={64}
                placeholder="gpt-4o-mini"
                disabled={loading || saving}
              />
            </label>
            <label className="text-sm font-medium">
              PDF model
              <input
                className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
                value={openaiPdfModel}
                onChange={(event) => setOpenaiPdfModel(event.target.value)}
                maxLength={64}
                placeholder="gpt-4o-mini"
                disabled={loading || saving}
              />
            </label>
            <label className="text-sm font-medium">
              Audio transcription model
              <input
                className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
                value={openaiTranscriptionModel}
                onChange={(event) => setOpenaiTranscriptionModel(event.target.value)}
                maxLength={64}
                placeholder="gpt-4o-mini-transcribe"
                disabled={loading || saving}
              />
            </label>
          </div>
          <p className="mt-3 text-sm text-[var(--muted)]">
            OpenAI document reading stays off by default. Even when enabled, MIAF still keeps accounting deterministic and requires review before posting uncertain records.
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

      <SectionCard
        title="Team invites"
        description="Owners and admins can invite teammates into this workspace and revoke pending invites."
      >
        {inviteMessage ? (
          <div className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            {inviteMessage}
          </div>
        ) : null}
        {inviteActionError ? (
          <div className="mb-4 rounded-xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger-ink)]">
            {inviteActionError}
          </div>
        ) : null}
        {invitesError ? (
          <div className="mb-4 rounded-xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger-ink)]">
            Failed to load invites. {invitesError}
          </div>
        ) : null}
        {invitePermissionDenied ? (
          <div className="rounded-xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger-ink)]">
            Insufficient permission. Only owners and admins can manage team invites.
          </div>
        ) : (
          <div className="space-y-5">
            <form className="grid gap-4 md:grid-cols-[minmax(0,1.5fr)_12rem_auto]" onSubmit={handleInviteSubmit}>
              <label className="text-sm font-medium">
                Invite email
                <input
                  className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
                  type="email"
                  value={inviteEmail}
                  onChange={(event) => setInviteEmail(event.target.value)}
                  placeholder="teammate@example.com"
                  disabled={inviteSaving}
                  required
                />
              </label>
              <label className="text-sm font-medium">
                Role
                <select
                  className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-sm"
                  value={inviteRole}
                  onChange={(event) => setInviteRole(event.target.value as (typeof INVITE_ROLES)[number]["value"])}
                  disabled={inviteSaving}
                >
                  {INVITE_ROLES.map((role) => (
                    <option key={role.value} value={role.value}>
                      {role.label}
                    </option>
                  ))}
                </select>
              </label>
              <div className="flex items-end">
                <button
                  type="submit"
                  disabled={inviteSaving}
                  className="w-full rounded-xl bg-[var(--accent)] px-4 py-3 text-sm font-semibold text-[var(--accent-ink)] transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {inviteSaving ? "Creating…" : "Create invite"}
                </button>
              </div>
            </form>

            {latestInviteLink ? (
              <div className="rounded-2xl border border-[var(--line)] bg-[var(--surface)] px-4 py-4">
                <p className="text-sm font-medium">One-time invite link</p>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  Copy and send this link now. It is only returned when the invite is created.
                </p>
                <div className="mt-3 flex flex-col gap-3 md:flex-row">
                  <input
                    className="w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-3 text-sm"
                    value={latestInviteLink}
                    readOnly
                  />
                  <button
                    type="button"
                    onClick={handleCopyInviteLink}
                    className="rounded-xl border border-[var(--line)] px-4 py-3 text-sm text-[var(--ink)] transition hover:bg-[var(--panel)]"
                  >
                    {copiedInviteLink ? "Copied" : "Copy link"}
                  </button>
                </div>
              </div>
            ) : null}

            <div>
              <div className="mb-3 flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-medium">Pending invites</p>
                  <p className="text-sm text-[var(--muted)]">
                    {pendingInvites.length === 0
                      ? "No pending invites."
                      : `${pendingInvites.length} pending invite${pendingInvites.length === 1 ? "" : "s"}.`}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={refreshInvites}
                  disabled={invitesLoading}
                  className="rounded-xl border border-[var(--line)] px-4 py-2 text-sm text-[var(--muted)] transition hover:bg-[var(--surface)] hover:text-[var(--ink)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Refresh
                </button>
              </div>

              {invitesLoading ? (
                <p className="text-sm text-[var(--muted)]">Loading invites…</p>
              ) : pendingInvites.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-[var(--line)] px-4 py-6 text-sm text-[var(--muted)]">
                  No pending invites to review.
                </div>
              ) : (
                <div className="space-y-3">
                  {pendingInvites.map((invite) => (
                    <div
                      key={invite.id}
                      className="flex flex-col gap-3 rounded-2xl border border-[var(--line)] bg-[var(--surface)] px-4 py-4 md:flex-row md:items-center md:justify-between"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">{invite.email}</p>
                        <p className="mt-1 text-sm text-[var(--muted)]">
                          Role: {invite.role} · Expires {formatInviteDate(invite.expires_at)}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRevokeInvite(invite.id)}
                        disabled={revokingInviteId === invite.id}
                        className="rounded-xl border border-[var(--danger-line)] px-4 py-2 text-sm text-[var(--danger-ink)] transition hover:bg-[var(--danger-bg)] disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {revokingInviteId === invite.id ? "Revoking…" : "Revoke"}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </SectionCard>

      <SectionCard
        title="Tailscale private access"
        description="Access MIAF from your phone over a private Tailscale network. Tailscale Serve keeps traffic inside your tailnet — it is not public internet access."
      >
        {tsError ? (
          <div className="mb-4 rounded-xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger-ink)]">
            {tsError}
          </div>
        ) : null}

        {tailscale ? (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 text-sm">
              <div>
                <span className="font-medium">Binary: </span>
                <span className={tailscale.binary_available ? "text-emerald-600" : "text-[var(--muted)]"}>
                  {tailscale.binary_available ? "Available" : "Not found — run commands manually"}
                </span>
              </div>
              <div>
                <span className="font-medium">Tailscale IP: </span>
                <span className="font-mono">{tailscale.tailscale_ip ?? "—"}</span>
              </div>
              <div>
                <span className="font-medium">Hostname: </span>
                <span className="font-mono">{tailscale.hostname ?? "—"}</span>
              </div>
              <div>
                <span className="font-medium">Private URL: </span>
                {tailscale.private_url ? (
                  <a
                    href={tailscale.private_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-mono text-[var(--accent)] hover:underline"
                  >
                    {tailscale.private_url}
                  </a>
                ) : (
                  <span className="text-[var(--muted)]">—</span>
                )}
              </div>
            </div>

            {tailscale.warnings.length > 0 ? (
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 space-y-1">
                {tailscale.warnings.map((w, i) => <p key={i}>{w}</p>)}
              </div>
            ) : null}

            {tailscale.serve_status ? (
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)] mb-1">Serve status</p>
                <pre className="rounded-xl bg-[var(--surface)] border border-[var(--line)] px-3 py-3 text-xs overflow-x-auto whitespace-pre-wrap">
                  {tailscale.serve_status}
                </pre>
              </div>
            ) : null}

            {tailscale.instructions_only ? (
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)] mb-2">Manual setup</p>
                <ol className="space-y-1 text-sm text-[var(--ink)]">
                  {tailscale.setup_instructions.map((step, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="shrink-0 text-[var(--muted)]">{i + 1}.</span>
                      <span>{step}</span>
                    </li>
                  ))}
                </ol>
                <p className="mt-3 text-xs font-semibold uppercase tracking-widest text-[var(--muted)] mb-1">Commands to copy</p>
                <div className="space-y-1">
                  {Object.entries(tailscale.manual_commands).map(([key, cmd]) => (
                    <div key={key} className="rounded-lg bg-[var(--surface)] border border-[var(--line)] px-3 py-2">
                      <p className="text-xs text-[var(--muted)] mb-0.5">{key}</p>
                      <code className="text-xs font-mono">{cmd}</code>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="flex flex-wrap gap-2 pt-2">
              <button
                type="button"
                onClick={() => handleTsAction(checkTailscaleStatus)}
                disabled={tsLoading}
                className="rounded-xl border border-[var(--line)] px-4 py-2 text-sm hover:bg-[var(--surface)] disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {tsLoading ? "Checking…" : "Check status"}
              </button>
              {tailscale.binary_available ? (
                <>
                  <button
                    type="button"
                    onClick={() => handleTsAction(startTailscaleServe)}
                    disabled={tsLoading}
                    className="rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-2 text-sm text-emerald-800 hover:bg-emerald-100 disabled:opacity-60 disabled:cursor-not-allowed"
                  >
                    Start Serve
                  </button>
                  <button
                    type="button"
                    onClick={() => handleTsAction(resetTailscaleServe)}
                    disabled={tsLoading}
                    className="rounded-xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-4 py-2 text-sm text-[var(--danger-ink)] hover:opacity-90 disabled:opacity-60 disabled:cursor-not-allowed"
                  >
                    Reset Serve
                  </button>
                </>
              ) : null}
            </div>
          </div>
        ) : (
          <p className="text-sm text-[var(--muted)]">Loading Tailscale status…</p>
        )}
      </SectionCard>

      {/* Security */}
      <SectionCard title="Security" description="Change your password or sign out of all active sessions.">
        <form className="space-y-4" onSubmit={handlePasswordChange}>
          {pwMessage ? (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
              {pwMessage}
            </div>
          ) : null}
          {pwError ? (
            <div className="rounded-xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger-ink)]">
              {pwError}
            </div>
          ) : null}
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-sm font-medium mb-1.5" htmlFor="current-password">
                Current password
              </label>
              <input
                id="current-password"
                type="password"
                autoComplete="current-password"
                value={currentPw}
                onChange={(e) => setCurrentPw(e.target.value)}
                className="w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-2 text-sm outline-none focus:border-[var(--accent)]"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5" htmlFor="new-password">
                New password (min 12 chars)
              </label>
              <input
                id="new-password"
                type="password"
                autoComplete="new-password"
                minLength={12}
                value={newPw}
                onChange={(e) => setNewPw(e.target.value)}
                className="w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-2 text-sm outline-none focus:border-[var(--accent)]"
                required
              />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={pwSaving || !currentPw || !newPw}
              className="rounded-xl bg-[var(--accent)] px-4 py-2 text-sm font-medium text-[var(--accent-ink)] hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {pwSaving ? "Saving…" : "Change password"}
            </button>
            <button
              type="button"
              onClick={handleRevokeAll}
              className="rounded-xl border border-[var(--danger-line)] px-4 py-2 text-sm text-[var(--danger-ink)] hover:bg-[var(--danger-bg)]"
            >
              Sign out all sessions
            </button>
          </div>
        </form>
      </SectionCard>
    </div>
  );
}
