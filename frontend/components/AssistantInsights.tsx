"use client";

import Link from "next/link";
import { getInsights } from "@/lib/api";
import { useLoader } from "@/lib/use-loader";
import { ErrorState, Skeleton, headingClass, panelClass, btnSecondary } from "@/components/ui";

export function AssistantInsights() {
  const { state, retry } = useLoader(getInsights);
  if (state.status === "loading") return <Skeleton />;
  if (state.status === "error") return <ErrorState message={state.error.message} onRetry={retry} />;
  const data = state.data;
  return <aside aria-label="Clinic Insights context" className={panelClass}>
    <h2 className={headingClass}>Your clinic at a glance</h2>
    <p className="mt-3 text-sm leading-6 text-muted">Ask the assistant about activity, cancellations or available capacity.</p>
    <dl className="my-6 space-y-4 text-sm">
      <div className="flex justify-between gap-4"><dt>Scheduled visits in the last {data.window_days} days</dt><dd>{data.totals.booked}</dd></div>
      <div className="flex justify-between gap-4"><dt>Completed visits</dt><dd>{data.totals.completed}</dd></div>
      <div className="flex justify-between gap-4"><dt>Cancelled visits</dt><dd>{data.totals.cancelled}</dd></div>
      <div className="flex justify-between gap-4"><dt>Confirmed visits in the next seven days</dt><dd>{data.business.confirmed_visits}</dd></div>
    </dl>
    <Link href="/insights" className={btnSecondary}>Open clinic Insights</Link>
    <p className="mt-4 text-xs leading-6 text-muted">{data.source}. Figures refresh when this view opens.</p>
  </aside>;
}
