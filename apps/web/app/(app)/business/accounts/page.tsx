import { SectionCard } from "../../../_components/cards";

export default function BusinessAccountsPage() {
  return (
    <SectionCard title="Business accounts" description="General account CRUD exists from Phase 1.">
      <p className="text-sm text-[var(--muted)]">Future work: chart-of-accounts hierarchy explorer, active/inactive toggles, and statement mapping helpers.</p>
    </SectionCard>
  );
}
