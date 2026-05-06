"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import { ApiRequestError, registerOwner } from "../_lib/api";
import { brand } from "../_lib/brand";

export default function OnboardingPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await registerOwner(name, email, password);
      window.location.replace("/dashboard");
    } catch (err) {
      if (err instanceof ApiRequestError && err.status === 409 && err.code === "owner_already_exists") {
        const message = encodeURIComponent(
          `${brand.shortName} ya está configurado. Inicia sesión con tu cuenta existente.`,
        );
        window.location.replace(`/login?message=${message}`);
        return;
      }
      setError(err instanceof Error ? err.message : "Account creation failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="grid min-h-screen bg-[var(--surface)] px-6 py-12 lg:grid-cols-[1.1fr_0.9fr]">
      <section className="flex flex-col justify-between rounded-[2rem] bg-[var(--hero)] p-8 text-[var(--hero-ink)]">
        <div>
          <p className="text-xs uppercase tracking-[0.35em] text-[var(--hero-accent)]">
            {brand.displayName}
          </p>
          <h1 className="mt-4 max-w-xl font-serif text-5xl leading-tight">
            {brand.agentIntro}
          </h1>
          <p className="mt-5 max-w-lg text-base text-[var(--hero-copy)]">
            {brand.description}
          </p>
          <p className="mt-3 max-w-lg text-sm text-[var(--hero-copy)]">
            {brand.subheading} {brand.tagline}
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl bg-white/8 p-4">
            <p className="text-xs uppercase tracking-[0.2em] text-[var(--hero-accent)]">Tenant</p>
            <p className="mt-2 text-sm text-[var(--hero-copy)]">
              Un nuevo espacio de trabajo de {brand.shortName} con propiedad de datos aislada.
            </p>
          </div>
          <div className="rounded-2xl bg-white/8 p-4">
            <p className="text-xs uppercase tracking-[0.2em] text-[var(--hero-accent)]">Entities</p>
            <p className="mt-2 text-sm text-[var(--hero-copy)]">One personal entity and one business entity, both owned by you.</p>
          </div>
          <div className="rounded-2xl bg-white/8 p-4">
            <p className="text-xs uppercase tracking-[0.2em] text-[var(--hero-accent)]">Audit</p>
            <p className="mt-2 text-sm text-[var(--hero-copy)]">Registration is session-backed and logged from the first action.</p>
          </div>
        </div>
      </section>

      <section className="flex items-center justify-center p-6">
        <form
          onSubmit={handleSubmit}
          className="w-full max-w-md rounded-[2rem] border border-[var(--line)] bg-[var(--panel)] p-8 shadow-[0_24px_100px_rgba(17,24,39,0.12)]"
        >
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-[var(--accent)]">Onboarding</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight">Create the owner account</h2>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Use a password with at least 12 characters. This endpoint is only available before the first user exists.
            </p>
          </div>

          <label className="mt-6 block text-sm font-medium">
            Name
            <input
              className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3"
              value={name}
              onChange={(event) => setName(event.target.value)}
              autoComplete="name"
              maxLength={100}
              required
            />
          </label>

          <label className="mt-4 block text-sm font-medium">
            Email
            <input
              className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              type="email"
              required
            />
          </label>

          <label className="mt-4 block text-sm font-medium">
            Password
            <input
              className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="new-password"
              minLength={12}
              required
            />
            <span className="mt-2 block text-xs text-[var(--muted)]">Minimum 12 characters.</span>
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
            {loading ? "Creating account…" : "Create account"}
          </button>

          <p className="mt-4 text-center text-sm text-[var(--muted)]">
            Already set up?{" "}
            <Link href="/login" className="font-medium text-[var(--accent)] hover:underline">
              Sign in
            </Link>
          </p>
        </form>
      </section>
    </main>
  );
}
