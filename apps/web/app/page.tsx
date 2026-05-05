"use client";

import { useEffect, useState } from "react";

type Health =
  | { status: string }
  | { status: "error"; code: number }
  | { status: "unreachable" };

async function fetchHealth(): Promise<Health> {
  const base = process.env.NEXT_PUBLIC_API_URL ?? "/api";
  try {
    const res = await fetch(`${base}/health`, { cache: "no-store" });
    if (!res.ok) return { status: "error", code: res.status };
    return (await res.json()) as { status: string };
  } catch {
    return { status: "unreachable" };
  }
}

export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    let mounted = true;
    fetchHealth().then((h) => mounted && setHealth(h));
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-6 p-8">
      <header>
        <h1 className="text-4xl font-bold tracking-tight">FinClaw</h1>
        <p className="mt-2 text-neutral-400">
          Phase 0 scaffold. Ledger lands in Phase 1.
        </p>
      </header>

      <section className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-400">
          API health
        </h2>
        <pre className="mt-2 overflow-auto text-sm">
          {health ? JSON.stringify(health, null, 2) : "checking…"}
        </pre>
      </section>

      <footer className="text-xs text-neutral-500">
        See <code>FinClaw.md</code> for the build plan.
      </footer>
    </main>
  );
}
