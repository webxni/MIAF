"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { ApiRequestError, acceptInvite } from "../_lib/api";
import { brand } from "../_lib/brand";

function messageForInviteError(error: ApiRequestError): string {
  if (error.code === "invite_expired") return "This invite has expired. Ask your admin to create a new one.";
  if (error.code === "invite_revoked") return "This invite has been revoked.";
  if (error.code === "invite_already_accepted") return "This invite has already been accepted.";
  if (error.code === "invalid_invite") return "This invite link is invalid.";
  if (error.code === "email_taken") return "This email address is already registered.";
  return error.message;
}

export default function AcceptInvitePage() {
  const [token, setToken] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    setToken(params.get("token") ?? "");
  }, []);

  const missingToken = useMemo(() => token.trim().length === 0, [token]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (missingToken) {
      setError("Missing invite token. Use the full invite link your admin shared.");
      return;
    }
    if (!name.trim()) {
      setError("Name is required.");
      return;
    }
    if (password.length < 12) {
      setError("Password must be at least 12 characters.");
      return;
    }

    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      await acceptInvite(token, name.trim(), password);
      setMessage("Invite accepted. Redirecting to your dashboard…");
      window.location.replace("/dashboard");
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setError(messageForInviteError(err));
      } else {
        setError(err instanceof Error ? err.message : "Failed to accept invite.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="grid min-h-screen bg-[var(--surface)] px-6 py-12 lg:grid-cols-[1.1fr_0.9fr]">
      <section
        className="flex flex-col justify-between rounded-[2rem] p-8 text-[var(--hero-ink)]"
        style={{ background: "var(--hero)" }}
      >
        <div>
          <p className="text-xs uppercase tracking-[0.35em] text-[var(--hero-accent)]">
            {brand.displayName}
          </p>
          <h1 className="mt-4 max-w-xl font-serif text-5xl leading-tight text-[var(--hero-ink)]">
            Join the workspace
          </h1>
          <p className="mt-5 max-w-lg text-base text-[var(--hero-copy)]">
            Accept your team invite to access the shared MIAF workspace with the role assigned by your admin.
          </p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/12 p-4 text-sm text-[var(--hero-ink)]/90">
          <p className="font-medium text-[var(--hero-ink)]">What happens next</p>
          <p className="mt-2">
            Your account will be created, your workspace access will be activated, and you will be signed in automatically.
          </p>
        </div>
      </section>

      <section className="flex items-center justify-center p-6">
        <form
          onSubmit={handleSubmit}
          className="w-full max-w-md rounded-[2rem] border border-[var(--line)] bg-[var(--panel)] p-8 text-[var(--ink)] shadow-[0_24px_100px_rgba(17,24,39,0.12)]"
        >
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-[var(--accent)]">Accept invite</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-[var(--ink)]">Create your account</h2>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Use a password with at least 12 characters.
            </p>
          </div>

          {message ? (
            <div className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
              {message}
            </div>
          ) : null}

          {error ? (
            <div className="mt-6 rounded-xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger-ink)]">
              {error}
            </div>
          ) : null}

          {missingToken ? (
            <div className="mt-6 rounded-xl border border-[var(--line)] bg-[var(--surface)] px-4 py-3 text-sm text-[var(--muted)]">
              Missing invite token. Open the full invite link from your admin, or ask for a new one.
            </div>
          ) : null}

          <label className="mt-6 block text-sm font-medium text-[var(--ink)]">
            Full name
            <input
              className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-[var(--ink)] placeholder:text-[var(--muted)]"
              value={name}
              onChange={(event) => setName(event.target.value)}
              autoComplete="name"
              maxLength={200}
              disabled={loading}
              required
            />
          </label>

          <label className="mt-4 block text-sm font-medium text-[var(--ink)]">
            Password
            <input
              className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-[var(--ink)] placeholder:text-[var(--muted)]"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="new-password"
              minLength={12}
              disabled={loading}
              required
            />
          </label>

          <button
            type="submit"
            disabled={loading || missingToken}
            className="mt-6 w-full rounded-xl bg-[var(--accent)] px-4 py-3 font-semibold text-[var(--accent-ink)] transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Accepting…" : "Accept invite"}
          </button>

          <p className="mt-4 text-center text-sm text-[var(--muted)]">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-[var(--accent)] hover:underline">
              Sign in
            </Link>
          </p>
        </form>
      </section>
    </main>
  );
}
