"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { ErrorState, Skeleton, btnSecondary, panelClass, headingClass } from "@/components/ui";
import { getPatientDocument, getPatientDocuments, getPatientSummary, getPatientPdf, toApiError, uploadPatientDocument, type PatientDocument } from "@/lib/api";
import { useLoader } from "@/lib/use-loader";

function Source({ slug, patientId }: { slug: string; patientId?: number }) {
  const load = useCallback(() => getPatientDocument(slug, patientId), [slug, patientId]);
  const { state, retry } = useLoader(load);
  if (state.status === "loading") return <Skeleton />;
  if (state.status === "error") return <ErrorState message={state.error.message} onRetry={retry} />;
  return <p className="whitespace-pre-wrap text-sm leading-7">{state.data.body}</p>;
}

function Record({ doc, patientId }: { doc: PatientDocument; patientId?: number }) {
  const [pdf, setPdf] = useState<string | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!doc.title.toLowerCase().endsWith(".pdf")) return;
    const controller = new AbortController();
    let url: string | null = null;
    getPatientPdf(doc.slug, controller.signal, patientId).then(blob => {
      if (controller.signal.aborted) return;
      url = URL.createObjectURL(blob);
      setPdf(url);
    }).catch(err => { if (!controller.signal.aborted) setError(toApiError(err).message); });
    return () => { controller.abort(); if (url) URL.revokeObjectURL(url); };
  }, [doc.slug, doc.title, patientId]);
  return <section className={panelClass} aria-label="Selected patient document">
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
      <h2 className={headingClass}>{doc.title.replace(".pdf", "")}</h2>
      {pdf && <a className={btnSecondary} href={pdf} target="_blank" rel="noreferrer">Open original PDF</a>}
    </div>
    {pdf && <iframe title="Original patient PDF" src={pdf} className="mb-6 h-[430px] w-full border border-line" />}
    {error && <p role="alert" className="mb-4 text-sm text-danger">{error}</p>}
    <details open={!pdf}><summary className="cursor-pointer py-2 text-sm font-semibold">Read extracted text</summary>
      <div className="mt-4"><Source slug={doc.slug} patientId={patientId} /></div>
    </details>
  </section>;
}


export function PatientRecords({ selected, onSelect, onUploadStateChange, disabled, patientId, canUpload }: {
  selected: string | null; onSelect: (id: string | null) => void; onUploadStateChange: (busy: boolean) => void; disabled: boolean; patientId?: number; canUpload: boolean;
}) {
  const load = useCallback(async () => ({
    documents: await getPatientDocuments(patientId), summary: await getPatientSummary(patientId),
  }), [patientId]);
  const { state, retry, refresh } = useLoader(load);
  const fileInput = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("");
  const [uploadError, setUploadError] = useState("");

  async function upload(file: File) {
    setUploadStatus("");
    setUploadError("");
    if (file.size > 12 * 1024 * 1024) {
      setUploadError("Choose a file smaller than or equal to 12 MiB.");
      return;
    }
    setUploading(true);
    onUploadStateChange(true);
    try {
      const document = await uploadPatientDocument(file);
      refresh();
      onSelect(document.slug);
      setUploadStatus(`${document.title} is ready for your questions.`);
    } catch (error) {
      setUploadError(toApiError(error).message);
    } finally {
      setUploading(false);
      onUploadStateChange(false);
    }
  }
  if (state.status === "loading") return <Skeleton />;
  if (state.status === "error") return <ErrorState message={state.error.message} onRetry={retry} />;
  const active = state.data.documents.find(doc => doc.slug === selected);
  const summary = state.data.summary;
  const restricted = summary.access === "current_shared";
  const sharedCases = new Set(state.data.documents.map(doc => doc.patient_case_id).filter(Boolean)).size > 1;
  return <div aria-label="Conversation records" className="min-w-0 text-sm">
    <div className="flex flex-wrap items-center gap-3">
      {canUpload && <button type="button" className="inline-flex min-h-11 items-center gap-2 rounded-full px-3 text-muted hover:bg-soft hover:text-ink disabled:opacity-40" disabled={disabled || uploading}
        aria-describedby="upload-document-formats" onClick={() => fileInput.current?.click()}>
        <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="m8 12 6-6a3 3 0 0 1 4 4l-8 8a5 5 0 0 1-7-7l9-9" /></svg>
        {uploading ? "Processing…" : "Upload document"}
      </button>}
      {active && <span className="max-w-full truncate rounded-full bg-soft px-3 py-2 text-xs" title={active.title}>{active.title.replace(".pdf", "")}</span>}
    </div>
    {canUpload && <>
      <input ref={fileInput} type="file" accept=".pdf,.png,.jpg,.jpeg,.txt" hidden onChange={event => {
        const file = event.currentTarget.files?.[0];
        event.currentTarget.value = "";
        if (file) void upload(file);
      }} />
      <span id="upload-document-formats" className="sr-only">PDF, PNG, JPEG or TXT, up to 12 MiB.</span>
      {uploading && <p role="status" className="px-3 py-2 text-xs text-muted">Extracting and indexing your document…</p>}
      {uploadStatus && <p role="status" className="break-words px-3 py-2 text-xs text-muted">{uploadStatus}</p>}
      {uploadError && <p role="alert" className="px-3 py-2 text-sm text-danger">{uploadError}</p>}
    </>}
    <details className="group mt-1">
      <summary className="w-fit cursor-pointer rounded-full px-3 py-2 text-xs text-muted hover:bg-soft hover:text-ink">Records & appointments{state.data.documents.length > 0 ? ` · ${state.data.documents.length}` : ""}</summary>
      <div className="mt-3 max-h-[50dvh] space-y-4 overflow-y-auto rounded-xl border border-line bg-bg p-4">
    <h2 className={headingClass}>{patientId ? summary.patient.name : "Your records"}</h2>
    {summary.patient.email && <p className="text-sm text-muted">{summary.patient.email}</p>}
    {sharedCases && <p className="text-sm leading-6 text-muted">Shared patient workspace. These records belong to different patients. Select a document before asking about its prescription or history.</p>}
    <p className="text-sm leading-6 text-muted">{restricted ? "Current shared doctor notes and prescriptions" : "Prescriptions, uploaded documents and past visit records"}</p>
    <label className="grid gap-2 text-sm">Document for this conversation
      <select className="min-h-11 w-full border border-line bg-panel px-3" disabled={disabled || uploading}
        value={selected ?? ""} onChange={event => onSelect(event.target.value || null)}>
        <option value="">{sharedCases ? "Choose a patient record" : restricted ? "All current shared documents" : "All permitted records"}</option>
        {state.data.documents.map(doc => <option key={doc.slug} value={doc.slug}>{doc.title.replace(".pdf", "")}</option>)}
      </select>
    </label>
    {state.data.documents.length === 0 && <p className="text-sm text-muted">No documents are available for this access level.</p>}
    {active && <Record key={active.slug} doc={active} patientId={patientId} />}
    <details className={panelClass}>
      <summary className="cursor-pointer text-sm font-semibold">{restricted ? "Upcoming appointments" : "All appointment details"}</summary>
      {summary.appointments.length === 0 && <p className="mt-4 text-sm text-muted">No appointments available.</p>}
      <ul className="mt-4 space-y-4 text-sm">{summary.appointments.map(a =>
        <li key={a.id} className="border-t border-line pt-3">
          <p>{a.doctor.name} · {a.status}</p>
          <p className="mt-1 text-muted">{new Date(a.slot.starts_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })}</p>
          {a.reason && <p className="mt-2 whitespace-pre-wrap">{a.reason}</p>}
        </li>)}</ul>
    </details>

      </div>
    </details>
  </div>;
}
