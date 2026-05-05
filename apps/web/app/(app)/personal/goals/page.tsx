import { SectionCard } from "../../../_components/cards";

export default function PersonalGoalsPage() {
  return (
    <SectionCard title="Goals workspace" description="Goal tracking endpoints are available; this page is ready for richer editing and progress visualisation.">
      <p className="text-sm text-[var(--muted)]">Future work: grouped goals, progress bars, target-date warnings, and dependency annotations.</p>
    </SectionCard>
  );
}
