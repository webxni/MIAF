import { SectionCard } from "../../../_components/cards";

export default function PersonalBudgetPage() {
  return (
    <SectionCard title="Budget workspace" description="Budget CRUD already exists on the API. This page is the route anchor for a fuller budget table and overspend review UI.">
      <p className="text-sm text-[var(--muted)]">Connect this screen to `/api/entities/:id/personal/budgets` and budget actuals for full editing and review.</p>
    </SectionCard>
  );
}
