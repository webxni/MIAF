"use client";

import { useEffect, useState } from "react";

import { me, type User } from "../_lib/api";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    me()
      .then((nextUser) => {
        if (!active) return;
        setUser(nextUser);
        setLoading(false);
      })
      .catch(() => {
        if (!active) return;
        setLoading(false);
        const pathname = window.location.pathname;
        window.location.replace(`/login?next=${encodeURIComponent(pathname)}`);
      });
    return () => {
      active = false;
    };
  }, []);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--surface)] text-[var(--muted)]">
        Loading FinClaw…
      </div>
    );
  }

  return <>{children}</>;
}
