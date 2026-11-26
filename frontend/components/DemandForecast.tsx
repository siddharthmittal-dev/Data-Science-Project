import type { WorkloadForecastData } from "@/lib/api";
import { headingClass, panelClass } from "@/components/ui";
import { DemandChart } from "@/components/DemandChart";
import { ForecastReplay } from "@/components/ForecastReplay";

const methodName = (method: string) => method === "linear_regression" ? "Linear regression" : "Weekday baseline";
const dayLabel = (day: string) => new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(new Date(`${day}T12:00:00`));

export function DemandForecast({ data }: { data: WorkloadForecastData }) {
  if (data.status !== "ready") {
    return <section className={panelClass}><h2 className={headingClass}>Appointment-demand model</h2><p role="status" className="mt-3 text-sm leading-6 text-muted">{data.message}</p></section>;
  }
  const total = data.points.reduce((sum, p) => sum + p.predicted_booked, 0);
  const metrics = data.metrics.holdout;
  const peak = data.points.reduce((best, p) => p.predicted_booked > best.predicted_booked ? p : best);

  return (
    <section aria-labelledby="model-title" className={panelClass}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="model-title" className={headingClass}>Appointment-demand model</h2>
        <span className="rounded-[3px] bg-soft px-3 py-2 text-xs font-semibold text-accent">Historical workload forecast</span>
      </div>
      <p className="mt-3 max-w-3xl text-sm leading-7 text-muted">Trained on {data.training_days} days of appointment history. These estimates belong to a separate scenario, and do not include your current bookings. The target is non-cancelled scheduled visits, including no-shows.</p>
      <p className="mt-3 text-sm"><strong>{methodName(data.selected_method)}</strong> selected using earlier validation error. Expected next seven days: <strong>{total.toFixed(1)} visits</strong>. Busiest forecast day: {dayLabel(peak.day)}.</p>

      <DemandChart data={data} />

      <div className="mt-7 grid gap-8 xl:grid-cols-2">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm tabular-nums">
            <caption className="mb-3 text-left font-medium">Scenario forecast · visits per day</caption>
            <thead><tr>{["Date", "Regression", "Baseline", "Capacity"].map(label => <th key={label} scope="col" className="border-b border-line px-2 py-3 font-medium">{label}</th>)}</tr></thead>
            <tbody>{data.points.map(p => <tr key={p.day}><th scope="row" className="border-b border-line px-2 py-3 font-normal">{dayLabel(p.day)}</th><td className="border-b border-line px-2 py-3">{p.linear_regression.toFixed(1)}</td><td className="border-b border-line px-2 py-3">{p.baseline.toFixed(1)}</td><td className="border-b border-line px-2 py-3">{p.capacity === 0 ? "Closed" : p.capacity}</td></tr>)}</tbody>
          </table>
        </div>
        <div>
          <table className="w-full text-left text-sm tabular-nums">
            <caption className="mb-3 text-left font-medium">Held-out evaluation · error in visits/day</caption>
            <thead><tr>{["Method", "All-day MAE", "Open-day MAE", "RMSE"].map(label => <th key={label} scope="col" className="border-b border-line px-2 py-3 font-medium">{label}</th>)}</tr></thead>
            <tbody>{(["linear_regression", "baseline"] as const).map(method => <tr key={method}><th scope="row" className="border-b border-line px-2 py-3 font-normal">{methodName(method)}</th><td className="border-b border-line px-2 py-3">{metrics[method].mae.toFixed(2)}</td><td className="border-b border-line px-2 py-3">{metrics[method].mae_open_days?.toFixed(2) ?? "Unavailable"}</td><td className="border-b border-line px-2 py-3">{metrics[method].rmse.toFixed(2)}</td></tr>)}</tbody>
          </table>
          <p className="mt-4 text-xs leading-6 text-muted">Lower errors are better. MAE is average absolute error; RMSE gives larger mistakes more weight. {metrics.baseline.samples} held-out predictions from {data.metrics.holdout_start} to {data.metrics.holdout_end}. </p>
          <details className="mt-5 border-t border-line pt-4 text-sm">
            <summary className="min-h-11 cursor-pointer font-medium">Data source, training and validation</summary>
            <div className="space-y-3 py-3 text-xs leading-6 text-muted">
              <p>Data source: generated appointment history. Evaluation measures this dataset and does not establish real-clinic accuracy.</p>
              <p>Training data: {data.training_start} to {data.training_end}. Trained: {new Date(data.trained_at).toLocaleString()}.</p>
              <p>{data.metrics.protocol}. {data.metrics.selection_basis}.</p>
              <p>Validation MAE: regression {data.metrics.validation.linear_regression.mae.toFixed(2)}; baseline {data.metrics.validation.baseline.mae.toFixed(2)}.</p>
              <p>Error by horizon (days 1–7), regression: {metrics.linear_regression.mae_by_horizon.map(v => v.toFixed(2)).join(", ")}. Baseline: {metrics.baseline.mae_by_horizon.map(v => v.toFixed(2)).join(", ")}.</p>
              <p>Unconstrained regression outputs on {metrics.linear_regression.open_day_predictions} open-day predictions: {metrics.linear_regression.negative_raw} negative; {metrics.linear_regression.above_capacity_raw} above capacity. Reported errors use the final bounded predictions.</p>
              <p>Features: weekday, open-day trend, last observed matching weekday and the mean of four observed matching weekdays. Configured capacity for six clinicians provides 120 slots per weekday, 48 on Saturday and none on Sunday. These are scheduled-workload estimates; unmet demand is not measured.</p>
              <p>Dataset: {data.dataset_id}. scikit-learn {data.versions.scikit_learn}; NumPy {data.versions.numpy}. No revenue or profit prediction.</p>
            </div>
          </details>
        </div>
      </div>
      {data.comparisons.length > 0 && <details className="mt-6 border-t border-line pt-4"><summary className="min-h-11 cursor-pointer text-sm font-medium">Scenario robustness checks</summary><div className="overflow-x-auto"><table className="w-full text-left text-sm"><caption className="sr-only">Held-out MAE across evaluation scenarios</caption><thead><tr>{["Scenario", "Selected on validation", "Regression MAE", "Baseline MAE"].map(h => <th scope="col" key={h} className="border-b border-line p-3">{h}</th>)}</tr></thead><tbody>{data.comparisons.map(s => <tr key={s.scenario}><th scope="row" className="border-b border-line p-3 font-normal">{s.scenario.replaceAll("_", " ")}</th><td className="border-b border-line p-3">{methodName(s.selected_method)}</td><td className="border-b border-line p-3">{s.holdout.linear_regression.mae}</td><td className="border-b border-line p-3">{s.holdout.baseline.mae}</td></tr>)}</tbody></table></div></details>}
      <ForecastReplay />
    </section>
  );
}
