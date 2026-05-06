"use client";

import { useEffect, useMemo, useState } from "react";

import { entities, listAlerts, logout, me, type Entity, type User } from "../_lib/api";

type NavItem = { href: string; label: string };

const NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/agent", label: "Agent" },
  { href: "/alerts", label: "Alerts" },
  { href: "/personal", label: "Personal" },
  { href: "/business", label: "Business" },
  { href: "/documents", label: "Documents" },
  { href: "/skills", label: "Skills" },
  { href: "/settings", label: "Settings" },
  { href: "/audit-log", label: "Audit Log" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const [pathname, setPathname] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [items, setItems] = useState<Entity[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [openAlertCount, setOpenAlertCount] = useState<number | null>(null);

  useEffect(() => {
    setPathname(window.location.pathname);
  }, []);

  useEffect(() => {
    let active = true;
    Promise.all([me(), entities()])
      .then(([nextUser, nextEntities]) => {
        if (!active) return;
        setUser(nextUser);
        setItems(nextEntities);
        if (!selected && nextEntities[0]) {
          setSelected(nextEntities[0].id);
        }
      })
      .catch(() => {
        if (!active) return;
        window.location.replace("/login");
      });
    return () => {
      active = false;
    };
  }, [selected]);

  useEffect(() => {
    let active = true;
    listAlerts({ only_open: true, limit: 100 })
      .then((alerts) => {
        if (active) setOpenAlertCount(alerts.length);
      })
      .catch(() => {
        if (active) setOpenAlertCount(null);
      });
    return () => {
      active = false;
    };
  }, []);

  const selectedEntity = useMemo(
    () => items.find((entity) => entity.id === selected) ?? items[0] ?? null,
    [items, selected],
  );

  async function handleLogout() {
    await logout();
    window.location.replace("/login");
  }

  return (
    <div className="min-h-screen bg-[var(--surface)] text-[var(--ink)]">
      <div className="mx-auto grid min-h-screen max-w-[1600px] grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="border-b border-[var(--line)] bg-[var(--panel)] px-5 py-6 lg:border-b-0 lg:border-r">
          <div className="mb-8">
            <p className="text-xs uppercase tracking-[0.35em] text-[var(--accent)]">
              FinClaw
            </p>
            <h1 className="mt-2 font-serif text-3xl tracking-tight">Ledger First</h1>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Personal and business finance from the same deterministic core.
            </p>
          </div>

          <div className="mb-6 space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--muted)]">
              Entity
            </label>
            <select
              className="w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-2 text-sm"
              value={selectedEntity?.id ?? ""}
              onChange={(event) => setSelected(event.target.value)}
            >
              {items.map((entity) => (
                <option key={entity.id} value={entity.id}>
                  {entity.name} ({entity.mode})
                </option>
              ))}
            </select>
            <div className="rounded-xl bg-[var(--surface)] px-3 py-2 text-sm text-[var(--muted)]">
              {user ? `${user.name} · ${user.email}` : "Loading user…"}
            </div>
          </div>

          <nav className="space-y-2">
            {NAV.map((item) => {
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <a
                  key={item.href}
                  href={item.href}
                  className={`flex items-center justify-between rounded-xl px-3 py-2 text-sm transition ${
                    active
                      ? "bg-[var(--accent)] text-[var(--accent-ink)]"
                      : "text-[var(--ink)] hover:bg-[var(--surface)]"
                  }`}
                >
                  <span>{item.label}</span>
                  {item.href === "/alerts" && openAlertCount !== null ? (
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                        active
                          ? "bg-[color:rgba(255,255,255,0.24)] text-[var(--accent-ink)]"
                          : "bg-[var(--surface)] text-[var(--muted)]"
                      }`}
                    >
                      {openAlertCount}
                    </span>
                  ) : null}
                </a>
              );
            })}
          </nav>

          <button
            type="button"
            onClick={handleLogout}
            className="mt-8 rounded-xl border border-[var(--line)] px-3 py-2 text-sm text-[var(--muted)] transition hover:bg-[var(--surface)] hover:text-[var(--ink)]"
          >
            Log out
          </button>
        </aside>

        <div className="min-w-0">
          <header className="border-b border-[var(--line)] px-5 py-4 md:px-8">
            <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.25em] text-[var(--muted)]">
                  Active entity
                </p>
                <div className="mt-1 flex items-center gap-3">
                  <h2 className="text-2xl font-semibold">{selectedEntity?.name ?? "Loading…"}</h2>
                  {selectedEntity ? (
                    <span className="rounded-full bg-[var(--surface)] px-3 py-1 text-xs uppercase tracking-[0.2em] text-[var(--muted)]">
                      {selectedEntity.mode}
                    </span>
                  ) : null}
                </div>
              </div>
              <p className="max-w-xl text-sm text-[var(--muted)]">
                Dashboard pages read directly from the API routes already implemented in Phases 1–4.
              </p>
            </div>
          </header>
          <main className="px-5 py-6 md:px-8">{children}</main>
        </div>
      </div>
    </div>
  );
}
