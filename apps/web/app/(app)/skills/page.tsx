"use client";

import { useEffect, useState } from "react";

import { SectionCard } from "../../_components/cards";
import { listSkills, type SkillManifest } from "../../_lib/api";

export default function SkillsPage() {
  const [skills, setSkills] = useState<SkillManifest[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listSkills()
      .then((result) => {
        if (active) setSkills(result);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "Failed to load skills");
      });
    return () => {
      active = false;
    };
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
    </div>
  );
}
