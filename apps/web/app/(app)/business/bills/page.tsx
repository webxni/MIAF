import { SectionCard } from "../../../_components/cards";

export default function BusinessBillsPage() {
  return (
    <SectionCard title="Bills" description="Vendor bill entry and AP payment flows are already implemented on the backend.">
      <p className="text-sm text-[var(--muted)]">Future work: bill draft editing, due-date monitoring, and AP aging review actions.</p>
    </SectionCard>
  );
}
