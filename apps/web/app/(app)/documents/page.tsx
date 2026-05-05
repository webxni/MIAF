"use client";

import { ChangeEvent, useState } from "react";

import { SectionCard } from "../../_components/cards";
import { entities } from "../../_lib/api";

type UploadResult = {
  attachment: { filename: string; id: string };
  extraction?: { confidence_score?: string | null; extracted_data?: Record<string, { value: string | null; confidence: string }> };
  batch?: { rows_imported: number; rows_total: number };
};

export default function DocumentsPage() {
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function upload(kind: "receipts" | "csv-imports", file: File) {
    setBusy(true);
    setMessage(null);
    try {
      const allEntities = await entities();
      const entity = allEntities[0];
      if (!entity) {
        throw new Error("No entity available");
      }
      const form = new FormData();
      form.append("file", file);
      const response = await fetch(`/api/entities/${entity.id}/documents/${kind}`, {
        method: "POST",
        credentials: "include",
        body: form,
      });
      const body = (await response.json()) as UploadResult | { error?: { message?: string } };
      if (!response.ok) {
        throw new Error("error" in body ? body.error?.message ?? "Upload failed" : "Upload failed");
      }
      if (kind === "receipts" && "attachment" in body) {
        setMessage(`Receipt ${body.attachment.filename} uploaded and parsed.`);
      } else if (kind === "csv-imports" && "batch" in body) {
        setMessage(`Imported ${body.batch?.rows_imported ?? 0} of ${body.batch?.rows_total ?? 0} rows.`);
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  function onReceiptChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) void upload("receipts", file);
  }

  function onCsvChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) void upload("csv-imports", file);
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--accent)]">Documents</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">Review queue and ingestion</h1>
      </div>

      {message ? (
        <div className="rounded-2xl border border-[var(--line)] bg-[var(--panel)] px-5 py-4 text-sm">
          {message}
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-2">
        <SectionCard title="Receipt upload" description="Uploads into the Phase 4 document ingestion pipeline.">
          <label className="inline-flex cursor-pointer rounded-xl bg-[var(--accent)] px-4 py-3 font-semibold text-[var(--accent-ink)]">
            <input type="file" accept=".txt,.pdf,.png,.jpg,.jpeg" className="hidden" onChange={onReceiptChange} disabled={busy} />
            {busy ? "Uploading…" : "Upload receipt"}
          </label>
        </SectionCard>

        <SectionCard title="CSV bank import" description="Creates source transaction rows for reconciliation.">
          <label className="inline-flex cursor-pointer rounded-xl border border-[var(--line)] px-4 py-3 font-semibold">
            <input type="file" accept=".csv,text/csv" className="hidden" onChange={onCsvChange} disabled={busy} />
            {busy ? "Importing…" : "Import CSV"}
          </label>
        </SectionCard>
      </div>
    </div>
  );
}
