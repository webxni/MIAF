"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  checkTailscaleStatus,
  startTailscaleServe,
  type TailscaleLiveStatus,
} from "../../_lib/api";
import { brand } from "../../_lib/brand";

export default function TailscaleOnboardingPage() {
  const [status, setStatus] = useState<TailscaleLiveStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    checkTailscaleStatus()
      .then((s) => { if (active) { setStatus(s); setLoading(false); } })
      .catch((err) => { if (active) { setError(err instanceof Error ? err.message : "Failed to check Tailscale"); setLoading(false); } });
    return () => { active = false; };
  }, []);

  async function handleStartServe() {
    setActionLoading(true);
    setError(null);
    try {
      const s = await startTailscaleServe();
      setStatus(s);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start Tailscale Serve");
    } finally {
      setActionLoading(false);
    }
  }

  const hasPrivateUrl = Boolean(status?.private_url);

  return (
    <main className="min-h-screen bg-[var(--surface)] px-6 py-12">
      <div className="mx-auto max-w-2xl">
        <div className="mb-8">
          <p className="text-xs uppercase tracking-[0.3em] text-[var(--accent)]">{brand.displayName} — Setup step 2 of 2</p>
          <h1 className="mt-3 text-4xl font-semibold tracking-tight">Access from your phone</h1>
          <p className="mt-3 text-sm text-[var(--muted)]">
            Tailscale Serve creates a private HTTPS endpoint inside your tailnet so you can reach{" "}
            {brand.shortName} from any device — phone, tablet, laptop — without exposing it to the
            public internet. This step is optional.
          </p>
        </div>

        {error ? (
          <div className="mb-6 rounded-2xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-5 py-4 text-sm text-[var(--danger-ink)]">
            {error}
          </div>
        ) : null}

        {loading ? (
          <div className="rounded-2xl border border-[var(--line)] bg-[var(--panel)] px-6 py-8 text-center text-sm text-[var(--muted)]">
            Checking Tailscale status…
          </div>
        ) : status ? (
          <div className="space-y-6">
            <div className="rounded-2xl border border-[var(--line)] bg-[var(--panel)] p-6 space-y-4">
              <div className="grid gap-3 sm:grid-cols-2 text-sm">
                <div>
                  <span className="font-medium">Tailscale binary: </span>
                  <span className={status.binary_available ? "text-emerald-600 font-medium" : "text-amber-600"}>
                    {status.binary_available ? "Found" : "Not found on this host"}
                  </span>
                </div>
                {status.tailscale_ip ? (
                  <div>
                    <span className="font-medium">Tailscale IP: </span>
                    <code className="font-mono">{status.tailscale_ip}</code>
                  </div>
                ) : null}
                {status.hostname ? (
                  <div>
                    <span className="font-medium">Hostname: </span>
                    <code className="font-mono">{status.hostname}</code>
                  </div>
                ) : null}
                {status.private_url ? (
                  <div className="sm:col-span-2">
                    <span className="font-medium">Private URL: </span>
                    <a
                      href={status.private_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-mono text-[var(--accent)] hover:underline"
                    >
                      {status.private_url}
                    </a>
                  </div>
                ) : null}
              </div>

              {status.warnings.length > 0 ? (
                <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 space-y-1">
                  {status.warnings.map((w, i) => <p key={i}>{w}</p>)}
                </div>
              ) : null}
            </div>

            {status.binary_available && !hasPrivateUrl ? (
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-6">
                <h2 className="text-base font-semibold text-emerald-900">Option A — Automatic (recommended)</h2>
                <p className="mt-2 text-sm text-emerald-800">
                  Click below to run <code className="font-mono">tailscale serve --bg</code> from the API
                  container. This shares {brand.shortName} privately inside your tailnet.
                </p>
                <button
                  type="button"
                  onClick={handleStartServe}
                  disabled={actionLoading}
                  className="mt-4 rounded-xl bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {actionLoading ? "Starting Serve…" : "Start Tailscale Serve"}
                </button>
              </div>
            ) : null}

            {hasPrivateUrl ? (
              <div className="rounded-2xl border border-emerald-300 bg-emerald-50 p-6">
                <h2 className="text-base font-semibold text-emerald-900">Tailscale Serve is active</h2>
                <p className="mt-2 text-sm text-emerald-800">
                  Open{" "}
                  <a
                    href={status.private_url!}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-mono underline"
                  >
                    {status.private_url}
                  </a>{" "}
                  on your phone (with Tailscale installed and signed into the same tailnet).
                </p>
              </div>
            ) : null}

            {status.instructions_only || !status.binary_available ? (
              <div className="rounded-2xl border border-[var(--line)] bg-[var(--panel)] p-6 space-y-4">
                <h2 className="text-base font-semibold">Option B — Manual setup</h2>
                <p className="text-sm text-[var(--muted)]">
                  The Tailscale binary is not available inside the API container. Run these commands
                  on the host machine where {brand.shortName} is deployed:
                </p>
                <ol className="space-y-2 text-sm">
                  {status.setup_instructions.map((step, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="shrink-0 text-[var(--muted)]">{i + 1}.</span>
                      <span>{step}</span>
                    </li>
                  ))}
                </ol>
                <div className="space-y-2">
                  {Object.entries(status.manual_commands).map(([key, cmd]) => (
                    <div key={key} className="rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-2">
                      <p className="text-xs text-[var(--muted)] mb-0.5">{key}</p>
                      <code className="text-xs font-mono">{cmd}</code>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {status.serve_status ? (
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)] mb-1">Current serve output</p>
                <pre className="rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3 text-xs overflow-x-auto whitespace-pre-wrap">
                  {status.serve_status}
                </pre>
              </div>
            ) : null}
          </div>
        ) : null}

        <div className="mt-8 flex items-center justify-between">
          <p className="text-sm text-[var(--muted)]">
            You can always configure this later in{" "}
            <Link href="/settings" className="text-[var(--accent)] hover:underline">
              Settings → Tailscale
            </Link>
            .
          </p>
          <Link
            href="/dashboard"
            className="rounded-xl bg-[var(--accent)] px-5 py-3 text-sm font-semibold text-[var(--accent-ink)] hover:brightness-95"
          >
            {hasPrivateUrl ? "Go to dashboard" : "Skip for now"}
          </Link>
        </div>
      </div>
    </main>
  );
}
