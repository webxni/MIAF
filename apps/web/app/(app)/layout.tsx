import dynamic from "next/dynamic";

const ProtectedShell = dynamic(
  () =>
    import("../_components/protected-shell").then(
      (module) => module.ProtectedShell,
    ),
  {
    ssr: false,
    loading: () => (
      <div className="flex min-h-screen items-center justify-center bg-[var(--surface)] text-[var(--muted)]">
        Loading FinClaw…
      </div>
    ),
  },
);

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <ProtectedShell>{children}</ProtectedShell>;
}
