"use client";

import Link from "next/link";
import { CareArt } from "@/components/CareArt";
import {
  EmptyState,
  ErrorState,
  Skeleton,
  StatusTag,
  btnPrimary,
  btnSecondary,
  eyebrowClass,
  headingClass,
  panelClass,
} from "@/components/ui";
import { type Dashboard, getDashboard } from "@/lib/api";
import { formatDateTime, formatDate, formatTimeRange } from "@/lib/format";
import { useLoader } from "@/lib/use-loader";

export default function OverviewPage() {
  const { state, retry } = useLoader(getDashboard);
  const staff = state.status === "ready" && state.data.user.role !== "patient";

  return (
    <div>
      <section className="grid items-center gap-10 border-b border-line pb-10 md:grid-cols-[1.1fr_1fr] md:gap-[6%]">
        <div>
          <p className={eyebrowClass}>
            {state.status === "ready" ? `Welcome back, ${state.data.user.name}` : "Welcome back"}
          </p>
          <h1 className="font-serif text-[clamp(2.5rem,4.5vw,4.2rem)] leading-[1.06] font-normal tracking-[-0.03em]">
            {staff ? "Your clinic, at a glance" : "Care that fits your day"}
          </h1>
          <p className="mt-6 max-w-md text-sm leading-7 text-muted">
            {staff ? "Review today's workload, record visit outcomes and coordinate the next steps for your patients." : "Pick a time that works, keep track of your visits and get clinic answers in one place."}
          </p>
          <Link href={staff ? "/appointments" : "/doctors"} className={`${btnPrimary} mt-8`}>
            {staff ? "Manage clinic appointments" : "Book a visit"}
          </Link>
        </div>
        <CareArt />
      </section>

      <div className="mt-10">
        {state.status === "loading" && <OverviewSkeleton />}
        {state.status === "error" && (
          <ErrorState
            title="Could not load your overview"
            message={state.error.message}
            onRetry={retry}
          />
        )}
        {state.status === "ready" && <DashboardBody data={state.data} />}
      </div>
    </div>
  );
}

function OverviewSkeleton() {
  return (
    <div className="grid gap-8 lg:grid-cols-[1.4fr_1fr]">
      <div className={panelClass}>
        <Skeleton lines={4} />
      </div>
      <div className={panelClass}>
        <Skeleton lines={4} />
      </div>
    </div>
  );
}

function DashboardBody({ data }: { data: Dashboard }) {
  const stats = [
    { label: "Upcoming", value: data.counts.upcoming },
    { label: "Completed", value: data.counts.completed },
    { label: "Cancelled", value: data.counts.cancelled },
  ];
  const next = data.next_appointment;

  return (
    <div className="space-y-8">
      {data.staff_summary && <section className={panelClass}><h2 className={headingClass}>Today’s priorities</h2>
        <p className="mt-4 text-sm leading-7">{data.staff_summary.today_visits} scheduled visits today · {data.staff_summary.awaiting_outcome} visits awaiting an outcome.</p>
        <div className="mt-4 flex flex-wrap gap-3"><Link href="/appointments" className={btnSecondary}>Record outcomes</Link>{data.user.role === "admin" && <Link href="/retention" className={btnSecondary}>Patient follow-up</Link>}</div>
      </section>}
      <div className="grid grid-cols-3 gap-4">
        {stats.map((stat) => (
          <div key={stat.label} className="rounded-[3px] border border-line bg-panel p-5">
            <p className="text-xs text-muted">{stat.label}</p>
            <p className="mt-3 font-serif text-3xl tabular-nums">{stat.value}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-8 lg:grid-cols-[1.4fr_1fr]">
        <section aria-labelledby="next-visit" className={panelClass}>
          <p className={eyebrowClass}>{data.user.role === "patient" ? "Next visit" : "Next clinic appointment"}</p>
          {next ? (
            <>
              <h2 id="next-visit" className={headingClass}>
                {next.doctor.name}
              </h2>
              <p className="mt-1 text-sm text-muted">{next.doctor.specialty}</p>
              {next.legacy_schedule && <p className="mt-2 text-xs leading-6 text-muted">Legacy booking outside current clinic hours. Original time preserved.</p>}
              {data.user.role !== "patient" && <p className="mt-2 text-sm">Patient: {next.patient.name}</p>}
              <dl className="mt-6 grid gap-3 border-y border-line py-5 text-sm">
                <div className="flex justify-between gap-4">
                  <dt className="text-muted">Date</dt>
                  <dd>{formatDate(next.slot.starts_at)}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted">Time</dt>
                  <dd className="tabular-nums">
                    {formatTimeRange(next.slot.starts_at, next.slot.ends_at)}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted">Reason</dt>
                  <dd className="text-right">{next.reason}</dd>
                </div>
              </dl>
              <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
                <StatusTag status={next.status} />
                <Link href="/appointments" className={btnSecondary}>
                  Manage appointments
                </Link>
              </div>
            </>
          ) : (
            <div className="mt-2">
              <EmptyState
                title="No upcoming visits"
                body="Find a doctor and choose a time that suits you."
              >
                <Link href="/doctors" className={btnPrimary}>
                  Find a doctor
                </Link>
              </EmptyState>
            </div>
          )}
        </section>

        <section aria-labelledby="recent-activity" className={panelClass}>
          <p className={eyebrowClass}>Activity</p>
          <h2 id="recent-activity" className={headingClass}>
            Recent activity
          </h2>
          {data.recent_activity.length === 0 ? (
            <p className="mt-6 text-sm text-muted">No recent activity yet.</p>
          ) : (
            <ul className="mt-5">
              {data.recent_activity.map((item, index) => (
                <li
                  key={`${item.at}-${index}`}
                  className="flex items-start justify-between gap-4 border-t border-line py-4"
                >
                  <p className="text-sm leading-6">{item.text}</p>
                  <time dateTime={item.at} className="whitespace-nowrap text-xs text-muted">
                    {formatDateTime(item.at)}
                  </time>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
