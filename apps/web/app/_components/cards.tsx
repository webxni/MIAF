export function StatCard({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note?: string;
}) {
  return (
    <article className="rounded-2xl border border-[var(--line)] bg-[var(--panel)] p-5 shadow-[0_18px_60px_rgba(17,24,39,0.08)]">
      <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--muted)]">
        {label}
      </p>
      <p className="mt-3 text-3xl font-semibold tracking-tight">{value}</p>
      {note ? <p className="mt-2 text-sm text-[var(--muted)]">{note}</p> : null}
    </article>
  );
}

export function SectionCard({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-3xl border border-[var(--line)] bg-[var(--panel)] p-5">
      <div className="mb-4">
        <h3 className="text-lg font-semibold">{title}</h3>
        {description ? <p className="mt-1 text-sm text-[var(--muted)]">{description}</p> : null}
      </div>
      {children}
    </section>
  );
}
