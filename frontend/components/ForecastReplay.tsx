"use client";
import { useState } from "react";
import { replayForecast, toApiError, type ForecastReplay as Replay } from "@/lib/api";
import { btnSecondary } from "@/components/ui";

export function ForecastReplay() {
  const [origin, setOrigin] = useState("2026-11-09");
  const [data, setData] = useState<Replay | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  async function run() {
    setPending(true); setError(""); setData(null);
    try { setData(await replayForecast(origin)); } catch (err) { setError(toApiError(err).message); }
    finally { setPending(false); }
  }
  return <div className="mt-7 border-t border-line pt-5">
    <h3 className="font-serif text-xl">Test an earlier forecast week</h3>
    <p className="mt-2 text-sm leading-6 text-muted">Replay a forecast using only data available before that date, then compare it with recorded outcomes in the evaluation dataset. This does not replace the saved model.</p>
    <form className="mt-4 flex flex-wrap items-end gap-3" onSubmit={e => { e.preventDefault(); void run(); }}>
      <label className="grid gap-2 text-sm">Forecast origin<input type="date" required value={origin} onChange={e => setOrigin(e.target.value)} className="min-h-11 border border-line bg-panel px-3" disabled={pending} /></label>
      <button className={btnSecondary} disabled={pending}>{pending ? "Replaying…" : "Run historical test"}</button>
    </form>
    {error && <p role="alert" className="mt-4 text-sm text-danger">{error}</p>}
    {data && <div className="mt-5" aria-live="polite">
      <p className="text-sm leading-6">Known through {data.known_through}. All-day MAE: regression {data.mae_all_days.regression}, baseline {data.mae_all_days.baseline}. Open-day MAE: regression {data.mae_open_days.regression ?? "Unavailable"}, baseline {data.mae_open_days.baseline ?? "Unavailable"}.</p>
      <div className="mt-4 overflow-x-auto"><table className="w-full text-left text-sm"><caption className="sr-only">Historical actuals compared with predictions</caption><thead><tr>{["Date", "Actual", "Regression", "Baseline"].map(h => <th key={h} className="border-b border-line px-3 py-3" scope="col">{h}</th>)}</tr></thead><tbody>{data.points.map(p => <tr key={p.day}><th scope="row" className="border-b border-line px-3 py-3 font-normal">{p.day}</th><td className="border-b border-line px-3 py-3">{p.actual}</td><td className="border-b border-line px-3 py-3">{p.regression}</td><td className="border-b border-line px-3 py-3">{p.baseline}</td></tr>)}</tbody></table></div>
    </div>}
  </div>;
}
