"use client";

import { AppShell } from "./app-shell";
import { AuthGuard } from "./auth-guard";

export function ProtectedShell({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <AppShell>{children}</AppShell>
    </AuthGuard>
  );
}
