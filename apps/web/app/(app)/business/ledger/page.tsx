import { SectionCard } from "../../../_components/cards";

export default function BusinessLedgerPage() {
  return (
    <SectionCard title="Business ledger" description="Ledger and trial balance APIs are available now.">
      <p className="text-sm text-[var(--muted)]">Future work: account picker, running-balance tables, export actions, and journal drilldowns.</p>
    </SectionCard>
  );
}
