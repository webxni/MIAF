import { SectionCard } from "../../../_components/cards";

export default function BusinessInvoicesPage() {
  return (
    <SectionCard title="Invoices" description="Customer, invoice, post, and payment flows are already implemented on the backend.">
      <p className="text-sm text-[var(--muted)]">Future work: invoice draft table, status chips, AR aging links, and payment capture forms.</p>
    </SectionCard>
  );
}
