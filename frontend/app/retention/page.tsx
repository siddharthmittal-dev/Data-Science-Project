"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useLoader } from "@/lib/use-loader";
import { getRetention, createFollowUp, completeFollowUp, toApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { Modal } from "@/components/Modal";
import { Skeleton, ErrorState, EmptyState, panelClass, headingClass, btnPrimary, btnSecondary } from "@/components/ui";

const percent = (n: number | null) => n === null ? "Insufficient history" : `${Math.round(n * 100)}%`;

export default function RetentionPage() {
  const auth = useAuth();
  if (auth.state.status !== "authed") return null;
  if (auth.state.user.role !== "admin") return <EmptyState title="Admin access required" body="This view includes previous patient records and follow-up notes." />;
  return <RetentionContent />;
}

function RetentionContent() {
  const { state, retry, refresh } = useLoader(getRetention);
  const [reviewOnly, setReviewOnly] = useState(false);
  const [limit, setLimit] = useState(10);
  const [action, setAction] = useState<{ patientId?: number; taskId?: number; name: string } | null>(null);
  const [saved, setSaved] = useState("");
  if (state.status === "loading") return <Skeleton lines={6} />;
  if (state.status === "error") return <ErrorState message={state.error.message} onRetry={retry} />;
  const data = state.data;
  const patients = data.patients.filter(p => !reviewOnly || p.review_eligible).slice(0, limit);
  const metrics = data.model?.metrics.holdout;
  return <div>
    <h1 className="font-serif text-[clamp(2.25rem,4vw,3.25rem)] tracking-[-0.03em]">Patient follow-up</h1>
    <p className="mt-4 max-w-3xl text-sm leading-7 text-muted">Review return estimates, check existing bookings and record internal follow-up tasks. A return is another completed visit within 90 days, not a medical requirement.</p>
    <p className="mt-5 border-y border-line py-4 text-sm leading-7">{data.notice}</p>
    {saved && <p role="status" className="mt-4 text-sm text-accent">{saved}</p>}
    <section className={`${panelClass} mt-8`}>
      <h2 className={headingClass}>Patient review</h2>
      <div className="my-5 flex flex-wrap items-center gap-5 text-sm">
        <label className="flex min-h-11 items-center gap-2"><input type="checkbox" checked={reviewOnly} onChange={e => setReviewOnly(e.target.checked)} />Show only patients with completed history and no upcoming booking</label>
        <label>Review capacity <select value={limit} onChange={e => setLimit(Number(e.target.value))} className="min-h-11 border border-line bg-panel px-2">{[5, 10, 25].map(n => <option key={n}>{n}</option>)}</select></label>
      </div>
      {!data.model && <p role="status" className="mb-4 text-sm text-muted">Return model unavailable or older than 30 days. History and task management remain available.</p>}
      {patients.length === 0 ? <EmptyState title="No patients in this review" body="Try showing all patients. Existing bookings and incomplete histories are not treated as missed returns." /> : <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-sm"><caption className="sr-only">Patient return estimates and current bookings</caption>
          <thead><tr>{["Patient", "90-day return estimate", "History", "Next booking", "Review"].map(h => <th key={h} scope="col" className="border-b border-line px-3 py-3 font-medium">{h}</th>)}</tr></thead>
          <tbody>{patients.map(p => <tr key={p.id}>
            <th scope="row" className="border-b border-line px-3 py-4 font-medium">{p.name}</th>
            <td className="border-b border-line px-3 py-4 tabular-nums">{percent(p.return_probability)}<span className="mt-1 block text-xs text-muted">Model estimate</span></td>
            <td className="border-b border-line px-3 py-4">{p.completed_visits} completed visits<br /><span className="text-xs text-muted">{p.last_completed ? `Last: ${formatDateTime(p.last_completed)}` : "No completed history"}</span></td>
            <td className="border-b border-line px-3 py-4">{p.next_booking ? `${formatDateTime(p.next_booking)}` : "None booked"}</td>
            <td className="border-b border-line px-3 py-4"><p className="mb-2 text-xs text-muted">{p.reason}</p>{p.open_task ? <span className="text-xs">Task #{p.open_task} already open</span> : <button className={btnSecondary} onClick={() => setAction({ patientId: p.id, name: p.name })}>Create follow-up task</button>}</td>
          </tr>)}</tbody>
        </table>
      </div>}
      <p className="mt-4 text-xs leading-6 text-muted">Patients suitable for review appear first, ordered by estimated return probability. Check context before creating a task. No automatic risk labels or outreach.</p>
    </section>
    <section className={`${panelClass} mt-6`}>
      <h2 className={headingClass}>Internal tasks</h2>
      {data.tasks.length === 0 ? <p className="mt-4 text-sm text-muted">No follow-up tasks yet.</p> : <ul className="mt-4 divide-y divide-line">{data.tasks.map(t => <li key={t.id} className="flex flex-wrap items-start justify-between gap-4 py-5">
        <div className="max-w-2xl"><h3 className="text-sm font-semibold">{t.patient_name} · {t.status}</h3><p className="mt-2 whitespace-pre-wrap text-sm leading-6">{t.note}</p><p className="mt-2 text-xs text-muted">Created {formatDateTime(t.created_at)}</p>
          {t.outcome && <p className="mt-2 text-sm">Outcome: {t.outcome}</p>}<p className="mt-2 text-xs text-muted">{t.subsequent_return ? "A subsequent completed visit is recorded; this does not establish an effect of the task." : "No subsequent completed visit recorded yet; follow-up may still be incomplete."}</p>
        </div>{t.status === "open" && <button className={btnSecondary} onClick={() => setAction({ taskId: t.id, name: t.patient_name })}>Record outcome</button>}
      </li>)}</ul>}
    </section>
    {data.model && <details className={`${panelClass} mt-6`}><summary className="min-h-11 cursor-pointer font-serif text-xl">Retention model and evaluation</summary>
      <p className="mt-3 text-sm leading-7">{data.model.population} generated patient histories; {data.model.training_samples} training snapshots. Selected method: {data.model.selected_method}. Selection uses validation Brier error; lower is better. Threshold 50% is for evaluation only.</p>
      <p className="mt-3 text-sm leading-7">Held-out Brier error: model {metrics?.logistic.brier}, baseline {metrics?.baseline.brier}. ROC AUC: {metrics?.logistic.roc_auc}. Precision: {percent(metrics?.logistic.precision_at_half ?? null)}; recall: {percent(metrics?.logistic.recall_at_half ?? null)}.</p>
      <p className="mt-3 text-xs leading-6 text-muted">Training labels observed through {data.model.training_label_end}; validation snapshot {data.model.validation_origin}; held-out snapshot {data.model.holdout_origin}. Validation selects the method before probability calibration. Calibration uses that earlier validation cohort; held-out metrics use calibrated probabilities and the latest observable cohort-rate baseline. All labels have a complete 90-day window. This evaluates later snapshots of the same synthetic population, not generalisation to a different clinic.</p>
      <h3 className="mt-5 text-sm font-semibold">Illustrative predictions</h3><ul className="mt-3 grid gap-3 text-sm sm:grid-cols-2">{data.model.examples.map(e => <li key={e.name}>{e.name.replace(/^Synthetic patient /, "Example patient ")}: {percent(e.probability)} · {e.features[0]} days since last completed visit</li>)}</ul>
      <h3 className="mt-5 text-sm font-semibold">Held-out probability calibration</h3><ul className="mt-3 space-y-2 text-xs leading-6">{metrics?.logistic.calibration.map(b => <li key={b.range[0]}>{percent(b.range[0])}–{percent(b.range[1])}: predicted average {percent(b.predicted)}, observed return rate {percent(b.observed)} across {b.count} patients</li>)}</ul>
    </details>}
    {action && <TaskDialog action={action} onClose={() => setAction(null)} onDone={() => { setAction(null); setSaved("Task saved. No external message was sent."); refresh(); }} />}
  </div>;
}

function TaskDialog({ action, onClose, onDone }: { action: { patientId?: number; taskId?: number; name: string }; onClose: () => void; onDone: () => void }) {
  const [text, setText] = useState(""); const [error, setError] = useState(""); const [pending, setPending] = useState(false);
  async function save() {
    setPending(true); setError("");
    try { if (action.patientId) await createFollowUp(action.patientId, text.trim()); else if (action.taskId) await completeFollowUp(action.taskId, text.trim()); onDone(); }
    catch (err) { setError(toApiError(err).message); setPending(false); }
  }
  return <Modal title={action.patientId ? "Create internal follow-up" : "Record follow-up outcome"} onClose={onClose}>
    <p className="text-sm">Patient: {action.name}</p><label className="mt-4 grid gap-2 text-sm">{action.patientId ? "What should staff review or do?" : "What happened during follow-up?"}<textarea value={text} onChange={e => setText(e.target.value)} maxLength={500} rows={4} className="border border-line bg-panel p-3" disabled={pending} /></label>
    <p className="mt-3 text-xs leading-6 text-muted">Internal record only. This action sends no email, SMS or other message.</p>{error && <p role="alert" className="mt-3 text-sm text-danger">{error}</p>}
    <button className={`${btnPrimary} mt-5`} disabled={!text.trim() || pending} onClick={save}>{pending ? "Saving…" : "Save record"}</button>
  </Modal>;
}
