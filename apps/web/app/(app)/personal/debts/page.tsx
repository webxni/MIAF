import { SectionCard } from "../../../_components/cards";

export default function PersonalDebtsPage() {
  return (
    <SectionCard title="Debt tracker" description="Debt CRUD and KPI math are already exposed by the API.">
      <p className="text-sm text-[var(--muted)]">Future work: payoff ordering, monthly due views, and warnings for debt-to-income pressure.</p>
    </SectionCard>
  );
}
