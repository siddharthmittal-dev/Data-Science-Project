"use client";

import { useCallback, useState } from "react";
import { SlotPicker } from "@/components/SlotPicker";
import { Modal } from "@/components/Modal";
import { EmptyState, ErrorState, Skeleton, btnDanger, btnPrimary, btnSecondary } from "@/components/ui";
import {
  type Appointment,
  cancelAppointment,
  getDoctorSlots,
  rescheduleAppointment,
  toApiError,
} from "@/lib/api";
import { formatDate, formatTime, formatTimeRange } from "@/lib/format";
import { useLoader } from "@/lib/use-loader";

interface DialogProps {
  appointment: Appointment;
  onClose: () => void;
  onDone: (message: string) => void;
}

const summaryClass = "rounded-[4px] border border-line bg-bg p-4 text-sm leading-7";

function Summary({ appointment }: { appointment: Appointment }) {
  return (
    <div className={summaryClass}>
      <strong className="block font-medium">{appointment.doctor.name}</strong>
      <span className="text-muted">{appointment.doctor.specialty}</span>
      <br />
      <span>
        {formatDate(appointment.slot.starts_at)}, {formatTimeRange(appointment.slot.starts_at, appointment.slot.ends_at)}
      </span>
    </div>
  );
}

export function RescheduleDialog({ appointment, onClose, onDone }: DialogProps) {
  const doctorId = appointment.doctor.id;
  const loadSlots = useCallback(() => getDoctorSlots(doctorId), [doctorId]);
  const { state, refresh, retry } = useLoader(loadSlots);
  const [slotId, setSlotId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    if (slotId === null) return;
    setSubmitting(true);
    setError(null);
    try {
      const updated = await rescheduleAppointment(appointment.id, slotId);
      onDone(
        `Visit moved to ${formatDate(updated.slot.starts_at)} at ${formatTime(updated.slot.starts_at)}.`,
      );
    } catch (err) {
      const apiError = toApiError(err);
      setSubmitting(false);
      if (apiError.code === "slot_taken") {
        setError("That time was just taken. Pick another.");
        setSlotId(null);
        refresh();
      } else if (apiError.code === "invalid_state") {
        setError("This visit can no longer be rescheduled.");
      } else {
        setError(apiError.message);
      }
    }
  }

  return (
    <Modal title="Reschedule visit" onClose={onClose}>
      <>
          <Summary appointment={appointment} />
          {appointment.legacy_schedule && <p className="mt-3 text-xs leading-6 text-muted">Existing visit outside the current clinic schedule. Its original time is preserved; choose a published time to reschedule.</p>}
          <div className="mt-6">
            {state.status === "loading" && <Skeleton lines={4} />}
            {state.status === "error" && (
              <ErrorState message={state.error.message} onRetry={retry} />
            )}
            {state.status === "ready" &&
              (state.data.length === 0 ? (
                <EmptyState
                  title="No free times"
                  body="This doctor has no openings in the next 14 days."
                />
              ) : (
                <SlotPicker
                  slots={state.data}
                  selectedId={slotId}
                  onSelect={setSlotId}
                  disabled={submitting}
                />
              ))}
          </div>
          {error && (
            <p role="alert" className="mt-4 text-sm text-danger">
              {error}
            </p>
          )}
          {state.status === "ready" && slotId !== null && state.data.find(s => s.id === slotId) && <p role="status" className={`${summaryClass} mt-5`}>New time: {formatDate(state.data.find(s => s.id === slotId)!.starts_at)}, {formatTimeRange(state.data.find(s => s.id === slotId)!.starts_at, state.data.find(s => s.id === slotId)!.ends_at)}</p>}
          <div className="mt-8 flex flex-wrap justify-end gap-3">
            <button type="button" onClick={onClose} disabled={submitting} className={btnSecondary}>
              Keep current time
            </button>
            <button
              type="button"
              onClick={confirm}
              disabled={slotId === null || submitting}
              className={btnPrimary}
            >
              {submitting ? "Saving..." : "Confirm new time"}
            </button>
          </div>
      </>
    </Modal>
  );
}

export function CancelDialog({ appointment, onClose, onDone }: DialogProps) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    setSubmitting(true);
    setError(null);
    try {
      await cancelAppointment(appointment.id);
      onDone("Visit cancelled.");
    } catch (err) {
      const apiError = toApiError(err);
      setSubmitting(false);
      setError(
        apiError.code === "invalid_state"
          ? "This visit can no longer be cancelled."
          : apiError.message,
      );
    }
  }

  return (
    <Modal title="Cancel this visit?" onClose={onClose}>
      <>
          <Summary appointment={appointment} />
          <p className="mt-6 text-sm leading-6 text-muted">
            You can book another time afterwards from the Doctors page.
          </p>
          {error && (
            <p role="alert" className="mt-4 text-sm text-danger">
              {error}
            </p>
          )}
          <div className="mt-8 flex flex-wrap justify-end gap-3">
            <button type="button" onClick={onClose} disabled={submitting} className={btnSecondary}>
              Keep visit
            </button>
            <button type="button" onClick={confirm} disabled={submitting} className={btnDanger}>
              {submitting ? "Cancelling..." : "Cancel visit"}
            </button>
          </div>
      </>
    </Modal>
  );
}
