"use client";

import { useId, useState } from "react";
import type { WorkloadForecastData } from "@/lib/api";

type ReadyForecast = Extract<WorkloadForecastData, { status: "ready" }>;
const formatDay = (day: string, options: Intl.DateTimeFormatOptions) =>
  new Intl.DateTimeFormat("en", options).format(new Date(`${day}T12:00:00`));

export function DemandChart({ data }: { data: ReadyForecast }) {
  const [view, setView] = useState<"forecast" | "history">("forecast");
  const [selected, setSelected] = useState(0);
  const id = useId();
  const history = data.history.slice(-14);
  const active = data.points[selected];
  const maximum = Math.max(20, ...data.points.flatMap(p => [p.linear_regression, p.baseline, p.capacity]), ...history.map(p => p.demand));
  const ceiling = Math.ceil(maximum / 20) * 20;
  const y = (value: number) => 260 - value / ceiling * 200;
  const slot = 644 / (view === "forecast" ? data.points.length : history.length);
  const x = (i: number) => 56 + slot * (i + 0.5);
  const ticks = Array.from({ length: 5 }, (_, i) => ceiling * i / 4);
  const capacity = Math.max(...data.points.map(p => p.capacity));

  return (
    <div className="mt-7 border-y border-line py-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap gap-4 text-xs">
          {view === "forecast" ? <>
            <span className="inline-flex items-center gap-2"><span className="h-3 w-3 bg-accent" />Linear regression</span>
            <span className="inline-flex items-center gap-2"><span className="h-3 w-3 border border-ink bg-panel" />Weekday baseline</span>
          </> : <span className="inline-flex items-center gap-2"><span className="h-0.5 w-5 bg-ink" />Historical scenario visits</span>}
        </div>
        <div role="group" aria-label="Chart view" className="inline-flex rounded-[3px] border border-line p-1">
          {([['forecast', 'Next 7 days'], ['history', 'Last 14 days']] as const).map(([value, label]) => (
            <button key={value} type="button" aria-pressed={view === value} onClick={() => setView(value)} className={`min-h-11 rounded-[2px] px-3 text-sm ${view === value ? "bg-soft font-medium text-accent" : "text-muted hover:text-ink"}`}>{label}</button>
          ))}
        </div>
      </div>
      <div className="mt-4 overflow-x-auto" role="region" aria-label="Appointment demand chart; scroll horizontally on narrow screens" tabIndex={0}>
        <svg viewBox="0 0 740 330" role="img" aria-labelledby={`${id}-title ${id}-desc`} className="block w-full min-w-[560px]">
          <title id={`${id}-title`}>{view === "forecast" ? "Regression and baseline forecasts for each of the next seven days" : "Daily visits in the evaluation dataset over the last fourteen observed days"}</title>
          <desc id={`${id}-desc`}>Vertical axis shows visits per day from zero to {ceiling}. {view === "forecast" ? "Paired bars compare regression with the weekday baseline. A dashed line marks maximum weekday capacity; Saturday has lower capacity. Choose a date below for exact values." : "Points show observed visit counts in the evaluation dataset, including zero on closed Sundays. This data is separate from live clinic appointments."}</desc>
          <text x="56" y="22" className="fill-muted text-[12px]">Visits / day</text>
          {ticks.map(tick => <g key={tick}><line x1="56" x2="700" y1={y(tick)} y2={y(tick)} className="stroke-line" /><text x="44" y={y(tick) + 4} textAnchor="end" className="fill-muted text-[12px]">{tick}</text></g>)}
          {view === "forecast" ? <>
            <rect x={56 + selected * slot} y="42" width={slot} height="218" rx="3" className="fill-soft" opacity="0.55" />
            <line x1="56" x2="700" y1={y(capacity)} y2={y(capacity)} className="stroke-muted" strokeDasharray="4 5" />
            <text x="700" y={y(capacity) - 8} textAnchor="end" className="fill-muted text-[11px]">Weekday capacity: {capacity}; Saturday: 48</text>
            {data.points.map((point, i) => <g key={point.day} onMouseEnter={() => setSelected(i)}>
              <title>{`${point.day}: regression ${point.linear_regression}, baseline ${point.baseline}, capacity ${point.capacity}`}</title>
              <rect x={x(i) - 25} y={y(point.linear_regression)} width="22" height={260 - y(point.linear_regression)} rx="2" className="fill-accent" />
              <rect x={x(i) + 3} y={y(point.baseline)} width="22" height={260 - y(point.baseline)} rx="2" className="fill-panel stroke-ink" strokeWidth="1.5" />
              <text x={x(i) - 14} y={y(point.linear_regression) - 9} textAnchor="middle" className="fill-accent text-[12px] font-semibold">{point.capacity ? point.linear_regression.toFixed(1) : "Closed"}</text>
              <text x={x(i)} y="284" textAnchor="middle" className="fill-ink text-[12px]">{formatDay(point.day, { weekday: "short" })}</text>
              <text x={x(i)} y="303" textAnchor="middle" className="fill-muted text-[11px]">{formatDay(point.day, { month: "short", day: "numeric" })}</text>
            </g>)}
          </> : <>
            <polyline points={history.map((point, i) => `${x(i)},${y(point.demand)}`).join(" ")} fill="none" className="stroke-ink" strokeWidth="2" />
            {history.map((point, i) => <g key={point.day}>
              <circle cx={x(i)} cy={y(point.demand)} r="4" className="fill-panel stroke-ink" strokeWidth="2"><title>{`${point.day}: ${point.demand} visits`}</title></circle>
              {(i % 3 === 0 || i === history.length - 1) && <text x={x(i)} y="289" textAnchor="middle" className="fill-muted text-[12px]">{formatDay(point.day, { month: "short", day: "numeric" })}</text>}
            </g>)}
          </>}
        </svg>
      </div>
      {view === "forecast" && <>
        <div role="group" aria-label="Inspect forecast date" className="flex flex-wrap gap-2">
          {data.points.map((point, i) => <button key={point.day} type="button" aria-pressed={selected === i} onClick={() => setSelected(i)} onFocus={() => setSelected(i)} className={`min-h-11 rounded-[3px] border px-3 text-xs ${selected === i ? "border-accent bg-soft font-medium text-accent" : "border-line hover:bg-bg"}`}>{formatDay(point.day, { weekday: "short", day: "numeric" })}</button>)}
        </div>
        <div aria-live="polite" aria-atomic="true" className="mt-4 flex flex-wrap gap-x-7 gap-y-2 text-sm tabular-nums">
          <strong>{formatDay(active.day, { weekday: "long", month: "short", day: "numeric" })}</strong>
          <span>Regression: <strong>{active.linear_regression.toFixed(1)}</strong></span>
          <span>Baseline: <strong>{active.baseline.toFixed(1)}</strong></span>
          <span>Capacity: <strong>{active.capacity || "Closed"}</strong></span>
        </div>
      </>}
      <p className="mt-4 text-xs leading-6 text-muted">{view === "forecast" ? "Hover over a day or select its date to compare estimates. These are expected counts, not confirmed bookings." : "Sunday zeros are explicit closures in this scenario, not missing observations."}</p>
    </div>
  );
}
