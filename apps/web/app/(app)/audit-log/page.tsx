import { SectionCard } from "../../_components/cards";

export default function AuditLogPage() {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--accent)]">Audit log</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">Sensitive activity trail</h1>
      </div>
      <SectionCard title="Next step" description="The backend already writes detailed audit logs for auth, accounting, business, and document actions.">
        <p className="text-sm text-[var(--muted)]">
          This Phase 5 page is a routed shell for the future table/filter view. The next UI slice can expose
          actual audit rows once a dedicated API read endpoint is added.
        </p>
      </SectionCard>
    </div>
  );
}
