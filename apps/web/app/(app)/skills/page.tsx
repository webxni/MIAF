"use client";

import { useEffect, useState } from "react";

import { SectionCard } from "../../_components/cards";
import { listSkillRuns, listSkills, type SkillManifest, type SkillRunLog } from "../../_lib/api";

function statusChip(status: string) {
  const cls =
    status === "success"
      ? "bg-emerald-100 text-emerald-800"
      : status === "error"
        ? "bg-red-100 text-red-800"
        : "bg-gray-100 text-gray-600";
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}

export default function SkillsPage() {
  const [skills, setSkills] = useState<SkillManifest[]>([]);
  const [runs, setRuns] = useState<SkillRunLog[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([listSkills(), listSkillRuns(20)])
      .then(([s, r]) => {
        if (active) {
          setSkills(s);
          setRuns(r);
        }
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "Failed to load skills");
      });
    return () => { active = false; };
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--accent)]">Skills</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">Installed skills</h1>
        <p className="mt-3 max-w-3xl text-sm text-[var(--muted)]">
          Built-in finance skills load from the local registry and run against deterministic
          ledger, report, document, and memory services.
        </p>
      </div>

      {error ? (
        <div className="rounded-2xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-5 py-4 text-sm text-[var(--danger-ink)]">
          {error}
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-2">
        {skills.map((skill) => (
          <SectionCard
            key={skill.name}
            title={skill.name}
            description={`${skill.mode} · v${skill.version} · ${skill.risk_level} risk`}
          >
            <div className="space-y-3 text-sm">
              <p className="text-[var(--muted)]">{skill.description}</p>
              <p>
                <span className="font-semibold">Status:</span>{" "}
                {skill.enabled ? "Enabled" : "Disabled"} {skill.builtin ? "· built-in" : "· third-party"}
              </p>
              <p>
                <span className="font-semibold">Permissions:</span> {skill.permissions.join(", ")}
              </p>
              <p>
                <span className="font-semibold">Triggers:</span> {skill.triggers.join(", ")}
              </p>
            </div>
          </SectionCard>
        ))}
      </div>

      {runs.length > 0 ? (
        <div>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-[var(--muted)]">
            Recent run log
          </h2>
          <div className="overflow-x-auto rounded-2xl border border-[var(--line)]">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--line)] bg-[var(--surface)] text-left text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">
                  <th className="px-4 py-3">Skill</th>
                  <th className="px-4 py-3">Version</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Run at</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--line)]">
                {runs.map((run) => (
                  <tr key={run.id} className="bg-[var(--panel)] hover:bg-[var(--surface)] transition-colors">
                    <td className="px-4 py-3 font-medium">{run.skill_name}</td>
                    <td className="px-4 py-3 text-[var(--muted)]">v{run.skill_version}</td>
                    <td className="px-4 py-3">{statusChip(run.result_status)}</td>
                    <td className="px-4 py-3 text-[var(--muted)]">
                      {new Date(run.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}
