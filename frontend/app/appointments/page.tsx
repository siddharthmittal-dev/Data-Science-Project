"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { Modal } from "@/components/Modal";
import { recordOutcome, toApiError } from "@/lib/api";
import { CancelDialog, RescheduleDialog } from "@/components/AppointmentDialogs";
import { LiveRegion, useToast } from "@/components/Toast";
import {
  type Appointment,
  type AppointmentStatus,
  listAppointments,
} from "@/lib/api";
import { formatDate, formatTimeRange } from "@/lib/format";
import { useLoader } from "@/lib/use-loader";
import {
  EmptyState,
  ErrorState,
  Skeleton,
  StatusTag,
  btnPrimary,
  btnSecondary,
  btnDanger,
  eyebrowClass,
  panelClass,
} from "@/components/ui";

type TabId = "upcoming" | "past" | "cancelled";

const TABS: {
  id: TabId;
  label: string;
  statuses: AppointmentStatus[];
  empty: { title: string; body: string };
}[] = [
  {
    id: "upcoming",
    label: "Upcoming",
    statuses: ["booked"],
    empty: {
      title: "No upcoming visits",
      body: "Book a visit with one of our doctors to see it here.",
    },
  },
  {
    id: "past",
    label: "Past",
    statuses: ["completed", "no_show"],
    empty: { title: "No past visits", body: "Completed visits will appear here." },
  },
  {
    id: "cancelled",
    label: "Cancelled",
    statuses: ["cancelled"],
    empty: { title: "No cancelled visits", body: "Visits you cancel will appear here." },
  },
];

type DialogState = { kind: "reschedule" | "cancel" | "completed" | "no_show"; appointment: Appointment } | null;

const HEADERS = ["Doctor", "Specialty", "Date", "Time", "Reason", "Status"];

export default function AppointmentsPage() {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 30000); return () => clearInterval(timer); }, []);
  const auth = useAuth();
  const staff = auth.state.status === "authed" && auth.state.user.role !== "patient";
  const { state, refresh, retry } = useLoader(listAppointments);
  const { message: toast, show: showToast } = useToast();
  const [tab, setTab] = useState<TabId>("upcoming");
  const [dialog, setDialog] = useState<DialogState>(null);

  function finish(message: string) {
    setDialog(null);
    showToast(message);
    refresh();
  }

  const activeTab = TABS.find((item) => item.id === tab) ?? TABS[0];

  return (
    <div>
      <p className={eyebrowClass}>Appointments</p>
      <h1 className="font-serif text-[clamp(2.25rem,4vw,3.25rem)] leading-[1.1] font-normal tracking-[-0.03em]">
        {staff ? "Clinic appointments" : "Your visits"}
      </h1>

      <div role="tablist" aria-label="Appointment groups" className="mt-8 flex gap-1 border-b border-line">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            id={`tab-${item.id}`}
            aria-selected={tab === item.id}
            tabIndex={tab === item.id ? 0 : -1}
            onKeyDown={event => {
              const index = TABS.findIndex(t => t.id === tab);
              const next = event.key === "ArrowRight" ? (index + 1) % TABS.length : event.key === "ArrowLeft" ? (index + TABS.length - 1) % TABS.length : event.key === "Home" ? 0 : event.key === "End" ? TABS.length - 1 : null;
              if (next !== null) { event.preventDefault(); setTab(TABS[next].id); document.getElementById(`tab-${TABS[next].id}`)?.focus(); }
            }}
            aria-controls="appointments-panel"
            onClick={() => setTab(item.id)}
            className={`min-h-11 border-b-2 px-4 text-sm ${
              tab === item.id
                ? "border-accent font-medium text-ink"
                : "border-transparent text-muted hover:text-ink"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div
        role="tabpanel"
        id="appointments-panel"
        aria-labelledby={`tab-${activeTab.id}`}
        className="mt-6"
      >
        {state.status === "loading" && (
          <div className={panelClass}>
            <Skeleton lines={5} />
          </div>
        )}
        {state.status === "error" && (
          <ErrorState
            title="Could not load appointments"
            message={state.error.message}
            onRetry={retry}
          />
        )}
        {state.status === "ready" && (
          <AppointmentTable
            appointments={state.data.filter((a) => tab === "upcoming" ? a.status === "booked" && Date.parse(a.slot.ends_at) > now : tab === "past" ? a.status !== "cancelled" && (a.status !== "booked" || Date.parse(a.slot.ends_at) <= now) : a.status === "cancelled")}
            tab={activeTab}
            staff={staff}
            onOutcome={(appointment, status) => setDialog({ kind: status, appointment })}
            onReschedule={(appointment) => setDialog({ kind: "reschedule", appointment })}
            onCancel={(appointment) => setDialog({ kind: "cancel", appointment })}
          />
        )}
      </div>

      {dialog?.kind === "reschedule" && (
        <RescheduleDialog
          key={`reschedule-${dialog.appointment.id}`}
          appointment={dialog.appointment}
          onClose={() => setDialog(null)}
          onDone={(message) => finish(message)}
        />
      )}
      {dialog?.kind === "cancel" && (
        <CancelDialog
          key={`cancel-${dialog.appointment.id}`}
          appointment={dialog.appointment}
          onClose={() => setDialog(null)}
          onDone={(message) => finish(message)}
        />
      )}

      <LiveRegion message={toast} />
      {(dialog?.kind === "completed" || dialog?.kind === "no_show") && <OutcomeDialog appointment={dialog.appointment} status={dialog.kind} onClose={() => setDialog(null)} onDone={finish} />}
    </div>
  );
}

function AppointmentTable({
  appointments,
  tab,
  onReschedule,
  onCancel,
  staff,
  onOutcome,
}: {
  appointments: Appointment[];
  tab: (typeof TABS)[number];
  onReschedule: (appointment: Appointment) => void;
  onCancel: (appointment: Appointment) => void;
  staff: boolean;
  onOutcome: (appointment: Appointment, status: "completed" | "no_show") => void;
}) {
  if (appointments.length === 0) {
    return (
      <div className={panelClass}>
        <EmptyState title={tab.empty.title} body={tab.empty.body}>
          {tab.id === "upcoming" && (
            <Link href="/doctors" className={btnPrimary}>
              Find a doctor
            </Link>
          )}
        </EmptyState>
      </div>
    );
  }

  const isUpcoming = tab.id === "upcoming";
  const headers = [...(staff ? ["Patient"] : []), ...HEADERS, ...(isUpcoming || staff ? ["Actions"] : [])];

  return (
    <div className="overflow-x-auto rounded-[4px] border border-line bg-panel">
      <table className="w-full min-w-[760px] border-collapse text-left text-sm">
        <caption className="sr-only">{tab.label} visits</caption>
        <thead>
          <tr>
            {headers.map((header) => (
              <th
                key={header}
                scope="col"
                className="border-b border-line px-4 py-4 text-[10px] font-medium tracking-[0.06em] text-muted uppercase"
              >
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {appointments.map((appointment) => {
            const label = `${appointment.doctor.name}, ${formatDate(appointment.slot.starts_at)}`;
            return (
              <tr key={appointment.id} className="align-top">
                {staff && <td className="border-b border-line px-4 py-4">{appointment.patient.name}</td>}
                <td className="border-b border-line px-4 py-4 font-medium">{appointment.doctor.name}</td>
                <td className="border-b border-line px-4 py-4 text-muted">
                  {appointment.doctor.specialty}
                </td>
                <td className="border-b border-line px-4 py-4 whitespace-nowrap">
                  {formatDate(appointment.slot.starts_at)}
                </td>
                <td className="border-b border-line px-4 py-4 whitespace-nowrap tabular-nums">
                  {formatTimeRange(appointment.slot.starts_at, appointment.slot.ends_at)}
                </td>
                <td className="border-b border-line px-4 py-4 leading-6">{appointment.reason}{appointment.legacy_schedule && <p className="mt-2 text-xs leading-5 text-muted">Legacy booking outside current hours. Original time preserved.</p>}</td>
                <td className="border-b border-line px-4 py-4">
                  <StatusTag status={appointment.status} />
                </td>
                {isUpcoming && (
                  <td className="border-b border-line px-4 py-4">
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        aria-label={`Reschedule ${label}`}
                        onClick={() => onReschedule(appointment)}
                        className={btnSecondary}
                      >
                        Reschedule
                      </button>
                      <button
                        type="button"
                        aria-label={`Cancel ${label}`}
                        onClick={() => onCancel(appointment)}
                        className={btnDanger}
                      >
                        Cancel
                      </button>
                    </div>
                  </td>
                )}
                {!isUpcoming && staff && <td className="border-b border-line px-4 py-4">{appointment.status === "booked" && <div className="flex gap-2">
                  <button className={btnSecondary} onClick={() => onOutcome(appointment, "completed")}>Mark completed</button>
                  <button className={btnSecondary} onClick={() => onOutcome(appointment, "no_show")}>Mark no-show</button>
                </div>}</td>}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function OutcomeDialog({ appointment, status, onClose, onDone }: { appointment: Appointment; status: "completed" | "no_show"; onClose: () => void; onDone: (message: string) => void }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  async function confirm() {
    setPending(true); setError("");
    try { await recordOutcome(appointment.id, status); onDone("Visit outcome recorded."); }
    catch (err) { setError(toApiError(err).message); setPending(false); }
  }
  return <Modal title={status === "completed" ? "Confirm completed visit" : "Confirm no-show"} onClose={onClose}>
    <p className="text-sm leading-7">{appointment.patient.name} · {appointment.doctor.name}<br />{formatDate(appointment.slot.starts_at)}, {formatTimeRange(appointment.slot.starts_at, appointment.slot.ends_at)}</p>
    <p className="mt-3 text-sm text-muted">This records a final outcome for the visit.</p>
    {error && <p role="alert" className="mt-3 text-sm text-danger">{error}</p>}
    <button className={`${btnPrimary} mt-5`} disabled={pending} onClick={confirm}>{pending ? "Saving…" : "Confirm outcome"}</button>
  </Modal>;
}
