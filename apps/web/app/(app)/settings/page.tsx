import { SectionCard } from "../../_components/cards";

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--accent)]">Settings</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">Workspace settings</h1>
      </div>
      <SectionCard title="Security and session controls" description="Phase 5 shell page. Backend settings and audit controls already exist; UI refinement can continue from here.">
        <ul className="space-y-2 text-sm text-[var(--muted)]">
          <li>Session timeout and cookie lifecycle are enforced by the API.</li>
          <li>Secrets are server-side only and never exposed to the frontend.</li>
          <li>Future work: profile editing, entity preferences, and display toggles for sensitive values.</li>
        </ul>
      </SectionCard>
    </div>
  );
}
