"use client";

import { FormEvent, useEffect, useState } from "react";

import { login } from "../_lib/api";

export default function LoginPage() {
  const [next, setNext] = useState("/dashboard");
  const [email, setEmail] = useState("owner@example.com");
  const [password, setPassword] = useState("change-me-on-first-login");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const value = new URLSearchParams(window.location.search).get("next");
    if (value) {
      setNext(value);
    }
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
      window.location.replace(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="grid min-h-screen bg-[var(--surface)] px-6 py-12 lg:grid-cols-[1.1fr_0.9fr]">
      <section className="flex flex-col justify-between rounded-[2rem] bg-[var(--hero)] p-8 text-[var(--hero-ink)]">
        <div>
          <p className="text-xs uppercase tracking-[0.35em] text-[var(--hero-accent)]">FinClaw</p>
          <h1 className="mt-4 max-w-xl font-serif text-5xl leading-tight">
            Financial control for one person, one business, one ledger spine.
          </h1>
          <p className="mt-5 max-w-lg text-base text-[var(--hero-copy)]">
            The application is now beyond scaffolding: personal dashboards, business reports,
            journal controls, and document ingestion are already live on the API.
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl bg-white/8 p-4">
            <p className="text-xs uppercase tracking-[0.2em] text-[var(--hero-accent)]">Personal</p>
            <p className="mt-2 text-sm text-[var(--hero-copy)]">Budget, goals, debt, net worth, savings rate.</p>
          </div>
          <div className="rounded-2xl bg-white/8 p-4">
            <p className="text-xs uppercase tracking-[0.2em] text-[var(--hero-accent)]">Business</p>
            <p className="mt-2 text-sm text-[var(--hero-copy)]">AR/AP, statements, cash flow, closing checklist.</p>
          </div>
          <div className="rounded-2xl bg-white/8 p-4">
            <p className="text-xs uppercase tracking-[0.2em] text-[var(--hero-accent)]">Documents</p>
            <p className="mt-2 text-sm text-[var(--hero-copy)]">Receipt ingestion, CSV import, review queue.</p>
          </div>
        </div>
      </section>

      <section className="flex items-center justify-center p-6">
        <form onSubmit={handleSubmit} className="w-full max-w-md rounded-[2rem] border border-[var(--line)] bg-[var(--panel)] p-8 shadow-[0_24px_100px_rgba(17,24,39,0.12)]">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-[var(--accent)]">Login</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight">Open the workspace</h2>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Default dev credentials are prefilled. Replace them in your environment for real use.
            </p>
          </div>

          <label className="mt-6 block text-sm font-medium">
            Email
            <input
              className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
            />
          </label>

          <label className="mt-4 block text-sm font-medium">
            Password
            <input
              className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
            />
          </label>

          {error ? (
            <div className="mt-4 rounded-xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger-ink)]">
              {error}
            </div>
          ) : null}

          <button
            type="submit"
            disabled={loading}
            className="mt-6 w-full rounded-xl bg-[var(--accent)] px-4 py-3 font-semibold text-[var(--accent-ink)] transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
