import type { ReactNode } from "react";
import type { AppointmentStatus } from "@/lib/api";

const buttonBase =
  "inline-flex min-h-11 items-center justify-center gap-2 whitespace-nowrap rounded-[3px] border px-5 text-sm font-medium transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-40";

export const btnPrimary = `${buttonBase} border-accent bg-accent text-on`;
export const btnSecondary = `${buttonBase} border-line bg-panel text-ink`;
export const btnDanger = `${buttonBase} border-danger bg-danger text-white`;
export const panelClass = "rounded-[4px] border border-line bg-panel p-6";
export const eyebrowClass = "mb-3 text-[10px] font-bold uppercase tracking-[0.15em] text-muted";
export const headingClass = "font-serif text-2xl font-normal tracking-[-0.02em]";

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div aria-busy="true" className="space-y-4">
      <span className="sr-only">Loading</span>
      {Array.from({ length: lines }, (_, i) => (
        <div
          key={i}
          className={`h-5 animate-pulse rounded-[3px] bg-line ${i === lines - 1 ? "w-3/5" : "w-full"}`}
        />
      ))}
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div role="alert" className={panelClass}>
      <h2 className={headingClass}>{title}</h2>
      <p className="mt-2 text-sm leading-6 text-muted">{message}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className={`${btnSecondary} mt-5`}>
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  body,
  children,
}: {
  title: string;
  body: string;
  children?: ReactNode;
}) {
  return (
    <div className="px-4 py-14 text-center">
      <h2 className={headingClass}>{title}</h2>
      <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-muted">{body}</p>
      {children && <div className="mt-6">{children}</div>}
    </div>
  );
}

const STATUS_META: Record<AppointmentStatus, { label: string; className: string }> = {
  booked: { label: "Booked", className: "bg-soft text-accent" },
  completed: { label: "Completed", className: "bg-bg text-muted" },
  cancelled: { label: "Cancelled", className: "bg-line text-muted" },
  no_show: { label: "No show", className: "bg-amber-soft text-amber" },
};

export function StatusTag({ status }: { status: AppointmentStatus }) {
  const meta = STATUS_META[status];
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-[3px] px-2 py-1 text-xs font-semibold ${meta.className}`}
    >
      {meta.label}
    </span>
  );
}
