"use client";

import { getCsvEvaluation } from "@/lib/api";
import { useLoader } from "@/lib/use-loader";
import { ErrorState, Skeleton, headingClass, panelClass } from "@/components/ui";
import { RegressionDetails, ClassifierDetails } from "@/components/ModelDetails";

export function CsvEvaluation() {
  const { state, retry } = useLoader(getCsvEvaluation);
  if (state.status === "loading") return <Skeleton />;
  if (state.status === "error") return <ErrorState message={state.error.message} onRetry={retry} />;
  const data = state.data;
  const individual = data.individual_no_shows.metrics.holdout;
  return <section className={`${panelClass} mt-10 space-y-5`} aria-label="Appointment dataset analysis">
    <h2 className={headingClass}>Your dataset forecasts</h2>
    <p className="text-sm leading-6 text-muted">{data.validation.appointments} appointments across {data.validation.patients} patients. Forecasts use the completed May–October 2026 observation window.</p>
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <caption className="mb-4 text-left">November 2026 estimates and October holdout results</caption>
        <thead><tr className="border-b border-line"><th className="py-3 pr-4">Measure</th><th className="px-4 text-right">November estimate</th><th className="px-4 text-right">October predicted / actual</th><th className="pl-4 text-right">Daily mean absolute error</th></tr></thead>
        <tbody>{[["Completed visits", data.busyness], ["No-shows", data.no_show_counts]].map(([label, raw]) => {
          const model = raw as typeof data.busyness;
          const scores = model.metrics.holdout[model.selected_method];
          return <tr key={String(label)} className="border-b border-line">
            <th className="py-4 pr-4 font-medium">{String(label)}</th>
            <td className="px-4 text-right tabular-nums">{model.forecast_total.toFixed(1)}</td>
            <td className="px-4 text-right tabular-nums">{scores.predicted_total.toFixed(1)} / {scores.actual_total}</td>
            <td className="pl-4 text-right tabular-nums">{scores.daily_mae.toFixed(3)}</td>
          </tr>;
        })}</tbody>
      </table>
    </div>
    <p className="text-sm leading-6 text-muted">Both count models selected linear regression using September validation. The no-show model performed worse than its weekday baseline on October holdout. Forecasts use the uploaded appointment history.</p>
    <p className="text-sm leading-6">Daily count models use ordinary least squares. ROC and AUC evaluate the separate appointment-level no-show classifier. The graphs below show the forecasts, errors and fitted calculation for each.</p>
    <details className="text-sm leading-6"><summary className="cursor-pointer font-medium">Data source and evaluation scope</summary><p className="mt-3">Source: {data.source}. These results evaluate the supplied generated appointment history; they do not establish performance at an operating clinic.</p></details>
    <RegressionDetails title="Completed visits" data={data.busyness} />
    <RegressionDetails title="No-show counts" data={data.no_show_counts} />
    <ClassifierDetails data={individual} />
    <details className="text-sm leading-6"><summary className="cursor-pointer font-medium">Individual no-show evaluation</summary>
      <p className="mt-3">Predictions use information available at booking time. October contains {individual.samples} appointments and {individual.no_shows} no-shows. Logistic Brier score {individual.logistic_brier}, historical-rate baseline {individual.baseline_brier}. Lower Brier scores are better. October ROC AUC {individual.roc_auc ?? "unavailable"}.</p>
      <p className="mt-2 text-muted">The logistic model won September validation and underperformed the baseline on October holdout. These results do not establish reliable individual risk predictions.</p>
    </details>
    <p className="text-sm leading-6 text-muted">90-day retention — {data.retention.message}</p>
  </section>;
}
