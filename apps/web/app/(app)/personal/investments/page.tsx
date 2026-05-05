import { SectionCard } from "../../../_components/cards";

export default function PersonalInvestmentsPage() {
  return (
    <SectionCard title="Investment tracking" description="Manual investment tracking is wired on the backend with advisory-only constraints.">
      <p className="text-sm text-[var(--muted)]">Future work: holdings tables, allocation charts, and explicit risk-warning banners on all suggestion surfaces.</p>
    </SectionCard>
  );
}
