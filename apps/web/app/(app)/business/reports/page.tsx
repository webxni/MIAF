import { SectionCard } from "../../../_components/cards";

export default function BusinessReportsPage() {
  return (
    <SectionCard title="Business reports" description="Balance sheet, income statement, cash flow, AR aging, AP aging, and closing checklist are all available via API.">
      <p className="text-sm text-[var(--muted)]">Future work: statement tables, date filters, print/export layouts, and report comparison periods.</p>
    </SectionCard>
  );
}
