"use client";

import { useState } from "react";
import type { CountEvaluation, ClassifierEvaluation } from "@/lib/api";
import { headingClass } from "@/components/ui";

type Point = { x: number; y: number };
type Series = { name: string; points: Point[]; color: string; dots?: boolean };
const ink = "#4b4134", accent = "#98543b", green = "#35645b";
const number = (value: number) => value.toFixed(4);

function Plot({ title, series, xLabel, yLabel, probability = false }: {
  title: string; series: Series[]; xLabel: string; yLabel: string; probability?: boolean;
}) {
  const all = series.flatMap(s => s.points);
  const xmax = probability ? 1 : Math.max(1, ...all.map(p => p.x));
  const ymin = probability ? 0 : Math.min(0, ...all.map(p => p.y));
  const ymax = probability ? 1 : Math.max(1, ...all.map(p => p.y));
  const x = (v: number) => 65 + v / xmax * 590;
  const y = (v: number) => 250 - (v - ymin) / (ymax - ymin) * 210;
  return <figure className="min-w-0 space-y-3">
    <figcaption className="text-sm font-semibold">{title}</figcaption>
    <svg viewBox="0 0 700 310" role="img" aria-label={`${title}. Horizontal axis ${xLabel}. Vertical axis ${yLabel}. Exact values are in the tables below.`} className="w-full">
      {[0, 1, 2, 3, 4].map(i => {
        const v = ymin + (ymax - ymin) * i / 4;
        return <g key={i}><line x1="65" x2="655" y1={y(v)} y2={y(v)} stroke="#e7dfd4" /><text x="57" y={y(v) + 4} textAnchor="end" fontSize="12" fill={ink}>{v.toFixed(2)}</text></g>;
      })}
      {[0, 1, 2, 3, 4].map(i => <text key={i} x={x(xmax * i / 4)} y="271" textAnchor="middle" fontSize="12" fill={ink}>{(xmax * i / 4).toFixed(probability ? 2 : 0)}</text>)}
      {series.map(s => <g key={s.name}>
        {!s.dots && <polyline points={s.points.map(p => `${x(p.x)},${y(p.y)}`).join(" ")} fill="none" stroke={s.color} strokeWidth="2" />}
        {s.points.map((p, i) => <circle key={i} cx={x(p.x)} cy={y(p.y)} r={s.dots ? 3 : 2} fill={s.color}><title>{s.name} — {p.x.toFixed(3)}, {p.y.toFixed(3)}</title></circle>)}
      </g>)}
      <text x="360" y="301" textAnchor="middle" fontSize="13" fill={ink}>{xLabel}</text>
      <text transform="translate(15,145) rotate(-90)" textAnchor="middle" fontSize="13" fill={ink}>{yLabel}</text>
    </svg>
    <div className="flex flex-wrap gap-4 text-xs">{series.map(s => <span key={s.name} style={{ color: s.color }}>{s.name}</span>)}</div>
  </figure>;
}

export function RegressionDetails({ title, data }: { title: string; data: CountEvaluation }) {
  const [day, setDay] = useState(0);
  const point = data.points[day];
  const holdout = data.evaluation_points.holdout;
  const model = data.model;
  const predicted = holdout.map((p, i) => ({ x: i + 1, y: p.linear_regression }));
  const actual = holdout.map((p, i) => ({ x: i + 1, y: p.actual }));
  return <section className="space-y-6 border-t border-line pt-7" aria-label={`${title} regression details`}>
    <h3 className={headingClass}>{title} — linear regression</h3>
    <p className="text-sm leading-7">The fitted equation is ŷ = β₀ + Σ βⱼxⱼ. Ordinary least squares estimates all coefficients together by minimizing Σ(yᵢ − ŷᵢ)² using scikit-learn LinearRegression. The model uses six weekday indicators (Sunday is the reference), published capacity, elapsed days divided by 180, and the mean count from the last four observed matching weekdays. No feature scaling is applied to this regression.</p>
    <p className="text-sm leading-7">May–August trains the September validation model. September daily MAE selects the method. A May–September refit predicts October holdout. A final May–October refit predicts November, using history frozen at 1 November. Future November outcomes never enter the calculation.</p>
    <div className="grid gap-8 xl:grid-cols-2">
      <Plot title={`${title} — November 2026 forecast`} xLabel="November day" yLabel="Expected count" series={[
        { name: "Regression", color: accent, points: data.points.map((p, i) => ({ x: i + 1, y: p.regression })) },
        { name: "Weekday baseline", color: green, points: data.points.map((p, i) => ({ x: i + 1, y: p.baseline })) },
        { name: "Capacity", color: ink, points: data.points.map((p, i) => ({ x: i + 1, y: p.capacity })) },
      ]} />
      {data.uncertainty && <Plot title="November approximate 95% prediction range" xLabel="November day" yLabel="Count" series={[
        { name: "Regression", color: accent, points: data.points.map((p, i) => ({ x: i + 1, y: p.regression })) },
        { name: "Lower prediction bound", color: green, points: data.uncertainty.prediction_intervals.map((p, i) => ({ x: i + 1, y: p[0] })) },
        { name: "Upper prediction bound", color: ink, points: data.uncertainty.prediction_intervals.map((p, i) => ({ x: i + 1, y: p[1] })) },
      ]} />}
      <Plot title="October actual and predicted" xLabel="October day" yLabel="Count" series={[
        { name: "Observed", color: ink, points: actual }, { name: "Regression", color: accent, points: predicted },
      ]} />
      <Plot title="October residuals" xLabel="October day" yLabel="Actual − predicted" series={[
        { name: "Zero error", color: ink, points: [{ x: 1, y: 0 }, { x: holdout.length, y: 0 }] },
        { name: "Residual", color: accent, dots: true, points: holdout.map((p, i) => ({ x: i + 1, y: p.actual - p.linear_regression })) },
      ]} />
      <Plot title="October predicted versus observed" xLabel="Predicted count" yLabel="Observed count" series={[
        { name: "Perfect agreement", color: green, points: [{ x: 0, y: 0 }, { x: Math.max(...predicted.map(p => p.y), ...actual.map(p => p.y)), y: Math.max(...predicted.map(p => p.y), ...actual.map(p => p.y)) }] },
        { name: "Daily observation", color: accent, dots: true, points: holdout.map(p => ({ x: p.linear_regression, y: p.actual })) },
      ]} />
    </div>
    <div className="overflow-x-auto"><table className="w-full text-left text-sm"><caption className="mb-3 text-left">Validation and holdout metrics</caption>
      <thead><tr>{["Period / method", "MAE", "RMSE", "R²", "Predicted total", "Actual total"].map(s => <th key={s} className="border-b border-line px-2 py-3">{s}</th>)}</tr></thead>
      <tbody>{Object.entries(data.metrics).flatMap(([phase, methods]) => Object.entries(methods).map(([method, scores]) => <tr key={phase + method}>
        <th className="px-2 py-3 text-left font-normal">{phase} / {method.replaceAll("_", " ")}</th>
        {[scores.daily_mae, scores.rmse, scores.r2, scores.predicted_total, scores.actual_total].map((v, i) => <td className="px-2 tabular-nums" key={i}>{number(v)}</td>)}
      </tr>))}</tbody></table></div>
    <p className="text-sm leading-7">MAE = mean(|y − ŷ|). RMSE = √mean((y − ŷ)²). R² = 1 − Σ(y − ŷ)² / Σ(y − mean(y))². Lower MAE and RMSE indicate smaller errors. A negative R² indicates performance below a constant mean on that evaluation period. Reported count metrics use the capacity-bounded predictions.</p>
    <details className="space-y-4 text-sm leading-7"><summary className="cursor-pointer font-semibold">Fitted coefficients and a worked November prediction</summary>
      <p>The final fit uses {model.training_days} daily observations, {model.training_start} through {model.training_end}. Intercept β₀ = {number(model.intercept)}. Raw training RMSE = {number(model.training_rmse_raw)}. Design matrix rank {model.design_rank} of {model.design_columns} columns. A deficient rank makes individual coefficients non-unique. Coefficients describe association within this fit.</p>
      <label className="flex flex-wrap items-center gap-3">Inspect a forecast date<select className="min-h-11 border border-line bg-panel px-3" value={day} onChange={e => setDay(Number(e.target.value))}>{data.points.map((p, i) => <option key={p.day} value={i}>{p.day}</option>)}</select></label>
      <div className="overflow-x-auto"><table className="w-full text-left"><thead><tr>{["Feature", "Coefficient β", "Value x", "Contribution β × x"].map(s => <th className="border-b border-line p-2" key={s}>{s}</th>)}</tr></thead><tbody>{model.features.map((name, i) => <tr key={name}><th className="p-2 text-left font-normal">{name.replaceAll("_", " ")}</th><td className="p-2 tabular-nums">{number(model.coefficients[i])}</td><td className="p-2 tabular-nums">{number(point.features[i])}</td><td className="p-2 tabular-nums">{number(model.coefficients[i] * point.features[i])}</td></tr>)}</tbody></table></div>
      <p>Raw prediction = intercept {number(model.intercept)} + summed contributions {number(point.raw - model.intercept)} = {number(point.raw)}. Published capacity = {point.capacity}. Displayed regression prediction = min(capacity, max(0, raw)) = {number(point.regression)}. Closed days are set to zero. November total is the sum of unrounded daily selected-model predictions = {data.forecast_total.toFixed(2)}.</p>
    </details>
    {data.uncertainty && <details className="text-sm leading-7"><summary className="cursor-pointer font-semibold">Uncertainty assumptions and exact intervals</summary>
      <p className="mt-3">{data.uncertainty.method} Draws: {data.uncertainty.draws}; seed: {data.uncertainty.seed}. Blocks contain {data.uncertainty.block_days} consecutive residuals, preserving weekday alignment. No future outcomes are used. These ranges apply to the linear regression, independently of baseline selection.</p>
      <p className="mt-3">A mean confidence range describes uncertainty in the fitted expectation; a prediction range additionally includes resampled outcome variation. Counts are bounded by capacity. Resampling assumes the historical residual process remains representative; sparse counts, structural changes and feature uncertainty can invalidate coverage. These are not proven 95% accuracy guarantees.</p>
      <p className="mt-3">November regression total prediction range: {data.uncertainty.monthly_prediction_interval.map(number).join(" to ")}. Monthly bounds come from sums within each draw, not sums of daily bounds.</p>
      <div className="overflow-x-auto"><table className="mt-4 w-full text-left"><caption>Approximate 95% coefficient confidence ranges</caption><thead><tr><th>Term</th><th>Lower</th><th>Upper</th></tr></thead><tbody>{["Intercept", ...model.features].map((term, i) => <tr key={term}><td>{term}</td><td>{number(data.uncertainty!.coefficient_intervals[i][0])}</td><td>{number(data.uncertainty!.coefficient_intervals[i][1])}</td></tr>)}</tbody></table></div>
      <div className="overflow-x-auto"><table className="mt-4 w-full text-left"><caption>Daily mean confidence and outcome prediction ranges</caption><thead><tr><th>Date</th><th>Mean lower</th><th>Mean upper</th><th>Prediction lower</th><th>Prediction upper</th></tr></thead><tbody>{data.points.map((p, i) => <tr key={p.day}><td>{p.day}</td>{[...data.uncertainty!.mean_intervals[i], ...data.uncertainty!.prediction_intervals[i]].map((v, j) => <td key={j}>{number(v)}</td>)}</tr>)}</tbody></table></div>
    </details>}
    <details className="text-sm leading-7"><summary className="cursor-pointer font-semibold">Exact daily predictions and October errors</summary><div className="overflow-x-auto"><table className="mt-4 w-full text-left"><thead><tr><th>Date</th><th>Regression</th><th>Baseline</th><th>Observed</th><th>Residual</th></tr></thead><tbody>
      {holdout.map(p => <tr key={p.day}><td>{p.day}</td><td>{number(p.linear_regression)}</td><td>{number(p.weekday_baseline)}</td><td>{p.actual}</td><td>{number(p.actual - p.linear_regression)}</td></tr>)}
      {data.points.map(p => <tr key={p.day}><td>{p.day}</td><td>{number(p.regression)}</td><td>{number(p.baseline)}</td><td>Awaiting outcome</td><td>—</td></tr>)}
    </tbody></table></div></details>
  </section>;
}

export function ClassifierDetails({ data }: { data: ClassifierEvaluation }) {
  return <section className="space-y-6 border-t border-line pt-7" aria-label="No-show classification diagnostics">
    <h3 className={headingClass}>Individual no-show classification</h3>
    <p className="text-sm leading-7">A no-show is positive (1), attendance is negative (0). The classifier standardizes booking-time features as z = (x − mean) / scale and calculates p = 1 / (1 + exp(−(β₀ + Σβⱼzⱼ))). LogisticRegression uses its default L2 regularization. October has {data.samples} appointments and {data.no_shows} positives, so these curves have limited support.</p>
    <div className="grid gap-8 xl:grid-cols-2">
      <Plot title={`October ROC — AUC ${data.roc_auc}`} xLabel="False positive rate" yLabel="True positive rate" probability series={[
        { name: "No-show classifier", color: accent, points: data.roc }, { name: "Chance diagonal", color: ink, points: [{ x: 0, y: 0 }, { x: 1, y: 1 }] },
      ]} />
      <Plot title={`October precision–recall — AP ${number(data.average_precision)}`} xLabel="Recall" yLabel="Precision" probability series={[
        { name: "No-show classifier", color: accent, points: data.precision_recall },
        { name: "Prevalence baseline", color: ink, points: [{ x: 0, y: data.no_shows / data.samples }, { x: 1, y: data.no_shows / data.samples }] },
      ]} />
      <Plot title="October probability calibration" xLabel="Mean predicted probability" yLabel="Observed no-show fraction" probability series={[
        { name: "Occupied probability bins", color: accent, dots: true, points: data.calibration.map(p => ({ x: p.predicted, y: p.observed })) },
        { name: "Perfect calibration", color: ink, points: [{ x: 0, y: 0 }, { x: 1, y: 1 }] },
      ]} />
    </div>
    <p className="text-sm leading-7">TPR = TP / (TP + FN), FPR = FP / (FP + TN). The ROC varies the decision threshold. ROC AUC measures ranking across thresholds. Precision = TP / (TP + FP), recall = TPR, and F1 = 2 × precision × recall / (precision + recall). Average precision summarizes the precision–recall curve. Brier = mean((p − y)²).</p>
    <p className="text-sm leading-7">At threshold 0.5, precision = {number(data.precision_at_half)}, recall = {number(data.recall_at_half)}, F1 = {number(data.f1_at_half)}. Brier = {data.logistic_brier}, baseline = {data.baseline_brier}. The classifier underperformed its baseline in October.</p>
    <table className="text-sm"><caption className="mb-3 text-left">Confusion matrix at threshold 0.5</caption><thead><tr><th className="p-3">Actual outcome</th><th className="p-3">Predicted attendance</th><th className="p-3">Predicted no-show</th></tr></thead><tbody>{["Attendance", "No-show"].map((name, i) => <tr key={name}><th className="p-3 text-left font-normal">{name}</th><td className="p-3">{data.confusion_matrix[i][0]}</td><td className="p-3">{data.confusion_matrix[i][1]}</td></tr>)}</tbody></table>
    <details className="text-sm leading-7"><summary className="cursor-pointer font-semibold">Classifier coefficients, scaling and exact curve values</summary>
      <p className="mt-4">The October model trained on {data.model.training_samples} outcomes recorded before October. Intercept = {number(data.model.intercept)}. A patient with no prior completed visit uses 180 for days since completion.</p>
      <div className="overflow-x-auto"><table className="w-full text-left"><thead><tr><th>Feature</th><th>Coefficient</th><th>Training mean</th><th>Training scale</th></tr></thead><tbody>{data.model.features.map((name, i) => <tr key={name}><td>{name.replaceAll("_", " ")}</td><td>{number(data.model.coefficients[i])}</td><td>{number(data.model.mean[i])}</td><td>{number(data.model.scale[i])}</td></tr>)}</tbody></table></div>
      <table className="mt-4 w-full text-left"><caption className="text-left">ROC thresholds</caption><thead><tr><th>Threshold</th><th>FPR</th><th>TPR</th></tr></thead><tbody>{data.roc.map((p, i) => <tr key={i}><td>{p.threshold === null ? "Above maximum" : number(p.threshold)}</td><td>{number(p.x)}</td><td>{number(p.y)}</td></tr>)}</tbody></table>
      <table className="mt-4 w-full text-left"><caption className="text-left">Calibration bins containing observations</caption><thead><tr><th>Predicted</th><th>Observed</th><th>Samples</th></tr></thead><tbody>{data.calibration.map((p, i) => <tr key={i}><td>{number(p.predicted)}</td><td>{number(p.observed)}</td><td>{p.count}</td></tr>)}</tbody></table>
    </details>
  </section>;
}
