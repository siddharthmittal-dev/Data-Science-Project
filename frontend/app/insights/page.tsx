"use client";

import Link from "next/link";
import { DemandForecast } from "@/components/DemandForecast";
import { CsvEvaluation } from "@/components/CsvEvaluation";
import { useAuth } from "@/lib/auth";
import {
  type Insights,
  type InsightsForecastPoint,
  type InsightsHistoryDay,
  getInsights,
} from "@/lib/api";
import { useLoader } from "@/lib/use-loader";
import {
  ErrorState,
  Skeleton,
  btnPrimary,
  eyebrowClass,
  headingClass,
  panelClass,
} from "@/components/ui";

export default function InsightsPage() {
  const { state } = useAuth();
  // AppShell only renders children once the session is loaded.
  if (state.status !== "authed") return null;

  return (
    <div>
      <p className={eyebrowClass}>Insights</p>
      <h1 className="font-serif text-[clamp(2.25rem,4vw,3.25rem)] leading-[1.1] font-normal tracking-[-0.03em]">
        Clinic activity
      </h1>

      <div className="mt-10">
        {state.user.role === "patient" ? (
          <section aria-labelledby="insights-restricted" className={panelClass}>
            <h2 id="insights-restricted" className={headingClass}>
              Insights are available to receptionists and clinic admins
            </h2>
            <p className="mt-3 max-w-md text-sm leading-6 text-muted">
              Your own visits are on the Appointments page.
            </p>
            <Link href="/appointments" className={`${btnPrimary} mt-6`}>
              Go to appointments
            </Link>
          </section>
        ) : (
          <>
            {state.user.role === "admin" && <CsvEvaluation />}
            <InsightsContent />
          </>
        )}
      </div>
    </div>
  );
}

function InsightsContent() {
  const { state, retry } = useLoader(getInsights);

  if (state.status === "loading") {
    return (
      <div className={panelClass}>
        <Skeleton lines={6} />
      </div>
    );
  }
  if (state.status === "error") {
    return (
      <ErrorState
        title="Could not load insights"
        message={state.error.message}
        onRetry={retry}
      />
    );
  }
  return <InsightsBody data={state.data} />;
}

function InsightsBody({ data }: { data: Insights }) {
  const { totals } = data;
  const tiles = [
    { label: "Scheduled records", value: String(totals.booked) },
    { label: "Completed", value: String(totals.completed) },
    { label: "Cancelled", value: String(totals.cancelled) },
    { label: "No-shows", value: String(totals.no_show) },
    { label: "Cancellation rate", value: percent(totals.cancellation_rate) },
    { label: "No-show rate", value: percent(totals.no_show_rate) },
  ];

  return (
    <div className="space-y-10">
      <p className="text-sm leading-7 text-muted">Last {data.window_days} days · {data.source}. {data.history_note}</p>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
        {tiles.map((tile) => (
          <div key={tile.label} className="rounded-[3px] border border-line bg-panel p-5">
            <p className="text-xs text-muted">{tile.label}</p>
            <p className="mt-3 font-serif text-3xl tabular-nums">{tile.value}</p>
          </div>
        ))}
      </div>

      <section aria-labelledby="history-title" className={panelClass}>
        <h2 id="history-title" className={headingClass}>
          Daily appointment history
        </h2>
        <p className="mt-2 text-sm text-muted">
          Appointment records by scheduled date, including cancellations. Completed visits appear inside each bar. Dates without a published schedule are not assumed to be clinic closures.
        </p>
        <div className="mt-5 flex flex-wrap gap-5 text-sm">
          <span className="inline-flex items-center gap-2">
            <span className="inline-block size-3 bg-accent" />
            Scheduled records
          </span>
          <span className="inline-flex items-center gap-2">
            <span className="inline-block size-3 border border-accent bg-soft" />
            Completed
          </span>
        </div>
        <div className="mt-5">
          <HistoryChart history={data.history} />
        </div>
      </section>

      <section aria-labelledby="forecast-title" className={panelClass}>
        <div className="flex flex-wrap items-center gap-3">
          <span className="inline-flex items-center rounded-[3px] border border-accent px-2 py-1 text-xs font-semibold text-accent">
            {data.forecast.label}
          </span>
        </div>
        <h2 id="forecast-title" className={`${headingClass} mt-4`}>
          Next 7 days
        </h2>
        <p className="mt-2 text-sm leading-6 text-muted">{data.forecast.method}</p>
        <p className="mt-3 text-sm leading-6">
          {data.forecast.message} {data.forecast.status === "limited_history" && `Limited history: ${data.forecast.observed_days} observed days.`} Expected visits exclude cancellations and include no-shows. Confirmed bookings are part of the estimate, not added to it.
        </p>
        <dl className="mt-6 grid grid-cols-2 gap-5 border-y border-line py-5 md:grid-cols-4">
          {[
            ["Expected visits", data.business.expected_visits?.toFixed(1) ?? "Insufficient history"],
            ["Already booked", String(data.business.confirmed_visits)],
            ["Published slots", String(data.business.capacity)],
            ["Expected utilisation", data.business.utilisation === null ? "Unavailable" : percent(data.business.utilisation)],
          ].map(([label, value]) => <div key={label}><dt className="text-xs text-muted">{label}</dt><dd className="mt-2 font-serif text-2xl tabular-nums">{value}</dd></div>)}
        </dl>
        <p className="mt-3 text-xs leading-6 text-muted">Totals cover {data.business.published_days} days with published slots. Expected remaining capacity: {data.business.remaining_capacity?.toFixed(1) ?? "insufficient history"}. Utilisation = expected non-cancelled visits ÷ published slots. Total forecasts are withheld if any published day lacks comparable history. Unpublished days have no forecast. Activity estimates do not represent revenue or profit.</p>
        <div className="mt-6 grid gap-8 lg:grid-cols-[1.4fr_1fr]">
          <ForecastChart points={data.forecast.points} />
          <ForecastTable points={data.forecast.points} />
        </div>
      </section>
      <DemandForecast data={data.model_demo} />
    </div>
  );
}

// Chart geometry is in SVG user units. The viewBox keeps labels readable at phone width.
const HISTORY = { width: 400, height: 240, left: 36, right: 8, top: 10, bottom: 28 };
const FORECAST = { width: 400, height: 200, left: 36, right: 8, top: 16, bottom: 28 };

function HistoryChart({ history }: { history: InsightsHistoryDay[] }) {
  if (history.length === 0) {
    return <p className="text-sm text-muted">No booking history yet.</p>;
  }

  const { width, height, left, right, top, bottom } = HISTORY;
  const plotW = width - left - right;
  const plotH = height - top - bottom;
  const yMax = niceMax(Math.max(...history.map((d) => d.booked)));
  const slot = plotW / history.length;
  const barW = slot * 0.7;
  const x = (i: number) => left + i * slot + (slot - barW) / 2;
  const y = (value: number) => top + plotH * (1 - value / yMax);
  const last = history.length - 1;
  const peak = history.reduce((best, day) => (day.booked > best.booked ? day : best), history[0]);
  const totalBooked = history.reduce((sum, d) => sum + d.booked, 0);
  const totalCompleted = history.reduce((sum, d) => sum + d.completed, 0);
  const summary = `Booked ${totalBooked} and completed ${totalCompleted} appointments over ${history.length} days. Busiest day ${formatShortDay(peak.day)} with ${peak.booked} booked.`;

  return (
    <div className="overflow-hidden">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-labelledby="history-chart-title history-chart-desc"
        className="block h-auto w-full max-w-[640px]"
      >
        <title id="history-chart-title">Daily booked and completed appointments</title>
        <desc id="history-chart-desc">{summary}</desc>
        {[0, yMax / 2, yMax].map((tick) => (
          <g key={tick}>
            <line x1={left} x2={width - right} y1={y(tick)} y2={y(tick)} className="stroke-line" />
            <text x={left - 6} y={y(tick)} dy="0.32em" textAnchor="end" className="fill-muted text-[11px]">
              {formatTick(tick)}
            </text>
          </g>
        ))}
        {history.map((day, i) => {
          const barH = plotH * (day.booked / yMax);
          const doneH = plotH * (day.completed / yMax);
          const doneW = barW * 0.5;
          const doneX = x(i) + (barW - doneW) / 2;
          return (
            <g key={day.day}>
              <rect x={x(i)} y={y(day.booked)} width={barW} height={barH} className="fill-accent">
                <title>{`${formatShortDay(day.day)}: ${day.booked} booked, ${day.completed} completed`}</title>
              </rect>
              <rect
                x={doneX}
                y={y(day.completed)}
                width={doneW}
                height={doneH}
                className="fill-soft stroke-accent"
                strokeWidth={0.5}
              />
            </g>
          );
        })}
        <text x={left} y={height - 8} textAnchor="start" className="fill-muted text-[11px]">
          {formatShortDay(history[0].day)}
        </text>
        <text x={left + plotW / 2} y={height - 8} textAnchor="middle" className="fill-muted text-[11px]">
          {formatShortDay(history[Math.floor(last / 2)].day)}
        </text>
        <text x={width - right} y={height - 8} textAnchor="end" className="fill-muted text-[11px]">
          {formatShortDay(history[last].day)}
        </text>
      </svg>
      <p className="mt-3 text-xs text-muted">{summary}</p>
    </div>
  );
}

function ForecastChart({ points }: { points: InsightsForecastPoint[] }) {
  const { width, height, left, right, top, bottom } = FORECAST;
  const plotW = width - left - right;
  const plotH = height - top - bottom;
  const yMax = niceMax(Math.max(0, ...points.map((p) => p.predicted_booked ?? 0)));
  const slot = plotW / Math.max(points.length, 1);
  const barW = slot * 0.6;
  const x = (i: number) => left + i * slot + (slot - barW) / 2;
  const y = (value: number) => top + plotH * (1 - value / yMax);
  const summary = points
    .map((p) => `${formatShortDay(p.day)}: ${p.predicted_booked?.toFixed(1) ?? (p.estimate_status === "insufficient_history" ? "insufficient history" : "no published schedule")}`)
    .join(", ");

  return (
    <div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-labelledby="forecast-chart-title forecast-chart-desc"
        className="block h-auto w-full max-w-[640px]"
      >
        <title id="forecast-chart-title">Predicted bookings for the next 7 days</title>
        <desc id="forecast-chart-desc">{`Predicted bookings: ${summary}.`}</desc>
        {[0, yMax / 2, yMax].map((tick) => (
          <g key={tick}>
            <line x1={left} x2={width - right} y1={y(tick)} y2={y(tick)} className="stroke-line" />
            <text x={left - 6} y={y(tick)} dy="0.32em" textAnchor="end" className="fill-muted text-[11px]">
              {formatTick(tick)}
            </text>
          </g>
        ))}
        {points.map((point, i) => {
          const value = point.predicted_booked ?? 0;
          const barH = plotH * (value / yMax);
          return (
            <g key={point.day}>
              <rect
                x={x(i)}
                y={y(value)}
                width={barW}
                height={barH}
                className="fill-soft stroke-accent"
                strokeWidth={1}
                strokeDasharray="4 3"
              />
              <text
                x={x(i) + barW / 2}
                y={y(value) - 4}
                textAnchor="middle"
                className="fill-ink text-[11px] tabular-nums"
              >
                {point.predicted_booked?.toFixed(1) ?? "—"}
              </text>
              <text
                x={x(i) + barW / 2}
                y={height - 8}
                textAnchor="middle"
                className="fill-muted text-[11px]"
              >
                {formatWeekdayShort(point.day)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function ForecastTable({ points }: { points: InsightsForecastPoint[] }) {
  return (
    <div className="overflow-x-auto rounded-[3px] border border-line bg-bg">
      <table className="w-full border-collapse text-left text-sm">
        <caption className="sr-only">Live expected visits, confirmed bookings and capacity for the next 7 days</caption>
        <thead>
          <tr>
            <th scope="col" className="border-b border-line px-4 py-3 text-[10px] font-medium tracking-[0.06em] text-muted uppercase">
              Date
            </th>
            <th scope="col" className="border-b border-line px-4 py-3 text-right text-[10px] font-medium tracking-[0.06em] text-muted uppercase">
              Expected visits
            </th>
            <th scope="col" className="border-b border-line px-3 py-3 text-right font-medium">Booked</th>
            <th scope="col" className="border-b border-line px-3 py-3 text-right font-medium">Slots</th>
            <th scope="col" className="border-b border-line px-3 py-3 text-right font-medium">Utilisation</th>
          </tr>
        </thead>
        <tbody>
          {points.map((point) => (
            <tr key={point.day}>
              <td className="border-b border-line px-4 py-3 whitespace-nowrap">{formatLongDay(point.day)}</td>
              <td className="border-b border-line px-4 py-3 text-right tabular-nums">
                {point.predicted_booked?.toFixed(1) ?? (point.estimate_status === "insufficient_history" ? "Insufficient history" : "No schedule")}
              </td>
              <td className="border-b border-line px-3 py-3 text-right">{point.confirmed}</td>
              <td className="border-b border-line px-3 py-3 text-right">{point.capacity || "—"}</td>
              <td className="border-b border-line px-3 py-3 text-right">{point.utilisation === null ? "—" : percent(point.utilisation)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function percent(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`;
}

// Returns a round axis maximum (1, 2, 5 or 10 times a power of ten) at or above value.
function niceMax(value: number): number {
  if (value <= 0) return 1;
  const exponent = Math.pow(10, Math.floor(Math.log10(value)));
  const scaled = value / exponent;
  const step = scaled <= 1 ? 1 : scaled <= 2 ? 2 : scaled <= 5 ? 5 : 10;
  return step * exponent;
}

function formatTick(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

// "YYYY-MM-DD" from the API is parsed as a local calendar day, so it never shifts a day.
function parseDay(day: string): Date {
  const [year, month, date] = day.split("-").map(Number);
  return new Date(year, month - 1, date);
}

const shortDayFormat = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short" });
const weekdayShortFormat = new Intl.DateTimeFormat(undefined, { weekday: "short", day: "numeric" });
const longDayFormat = new Intl.DateTimeFormat(undefined, {
  weekday: "short",
  day: "numeric",
  month: "short",
  year: "numeric",
});

function formatShortDay(day: string): string {
  return shortDayFormat.format(parseDay(day));
}

function formatWeekdayShort(day: string): string {
  return weekdayShortFormat.format(parseDay(day));
}

function formatLongDay(day: string): string {
  return longDayFormat.format(parseDay(day));
}
