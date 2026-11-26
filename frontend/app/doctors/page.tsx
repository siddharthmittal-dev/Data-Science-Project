"use client";

import { useLayoutEffect, useRef, useState } from "react";
import { SlotPicker } from "@/components/SlotPicker";
import { LiveRegion, useToast } from "@/components/Toast";
import {
  EmptyState,
  ErrorState,
  Skeleton,
  btnPrimary,
  btnSecondary,
  eyebrowClass,
  headingClass,
  panelClass,
} from "@/components/ui";
import {
  type ApiError,
  type Doctor,
  type Slot,
  bookAppointment,
  getDoctorSlots,
  getDoctors,
  toApiError,
} from "@/lib/api";
import { formatDate, formatTime, formatDateTime, initials } from "@/lib/format";
import { useLoader } from "@/lib/use-loader";
import { useAuth } from "@/lib/auth";
import { getPatients } from "@/lib/api";

function PatientSelector({ value, onChange }: { value: number | null; onChange: (id: number) => void }) {
  const { state, retry } = useLoader(getPatients);
  if (state.status === "loading") return <Skeleton lines={1} />;
  if (state.status === "error") return <ErrorState message={state.error.message} onRetry={retry} />;
  return <label className="mb-5 grid gap-2 text-sm font-medium">Patient
    <select className="min-h-11 rounded-[3px] border border-line bg-panel px-3" value={value ?? ""} onChange={e => onChange(Number(e.target.value))}>
      <option value="" disabled>Choose a patient</option>{state.data.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
    </select></label>;
}

type SlotState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; slots: Slot[] };

type BookingState =
  | { status: "idle" }
  | { status: "submitting" }
  | { status: "booked"; message: string }
  | { status: "error"; message: string };

export default function DoctorsPage() {
  const auth = useAuth();
  const staff = auth.state.status === "authed" && auth.state.user.role !== "patient";
  const [patientId, setPatientId] = useState<number | null>(null);
  const [specialty, setSpecialty] = useState("");
  const bookingKey = useRef<{ signature: string; key: string } | null>(null);
  const { state, retry, refresh } = useLoader(getDoctors);
  const { message: toast, show: showToast } = useToast();
  const [selected, setSelected] = useState<Doctor | null>(null);
  const [slotState, setSlotState] = useState<SlotState>({ status: "idle" });
  const [slotId, setSlotId] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [booking, setBooking] = useState<BookingState>({ status: "idle" });
  // Ignores responses from a slot request that a newer click has overtaken.
  const requestSeq = useRef(0);
  const bookingTitleRef = useRef<HTMLHeadingElement>(null);
  const focusBooking = useRef(false);

  useLayoutEffect(() => {
    if (!focusBooking.current || !selected || slotState.status === "loading" || slotState.status === "idle") return;
    // Wait for the final form height so the jump isn't clamped to a short loading panel.
    bookingTitleRef.current?.focus({ preventScroll: true });
    bookingTitleRef.current?.scrollIntoView({ block: "start", behavior: "instant" });
    focusBooking.current = false;
  }, [selected, slotState.status]);

  async function loadSlots(doctor: Doctor) {
    const seq = ++requestSeq.current;
    setSlotState({ status: "loading" });
    try {
      const slots = await getDoctorSlots(doctor.id);
      if (seq === requestSeq.current) setSlotState({ status: "ready", slots });
    } catch (err) {
      if (seq === requestSeq.current) {
        setSlotState({ status: "error", error: toApiError(err) });
      }
    }
  }

  function checkAvailability(doctor: Doctor) {
    focusBooking.current = true;
    setSelected(doctor);
    setSlotId(null);
    setBooking({ status: "idle" });
    void loadSlots(doctor);
  }

  async function book(doctor: Doctor) {
    if (slotId === null || (staff && patientId === null) || !reason.trim()) return;
    const input = { slot_id: slotId, reason: reason.trim(), ...(staff && patientId ? { patient_id: patientId } : {}) };
    const signature = JSON.stringify(input);
    if (bookingKey.current?.signature !== signature) bookingKey.current = { signature, key: crypto.randomUUID() };
    setBooking({ status: "submitting" });
    try {
      const appointment = await bookAppointment(input, bookingKey.current.key);
      bookingKey.current = null;
      const message = `Booked with ${doctor.name} on ${formatDate(appointment.slot.starts_at)} at ${formatTime(appointment.slot.starts_at)}.`;
      setBooking({ status: "booked", message });
      showToast("Appointment booked.");
      setSlotId(null);
      setReason("");
      void loadSlots(doctor);
      refresh();
    } catch (err) {
      const apiError = toApiError(err);
      if (apiError.code === "slot_taken" || apiError.code === "slot_not_found") {
        setBooking({
          status: "error",
          message:
            apiError.code === "slot_taken"
              ? "That time was just taken. Pick another."
              : "That time is no longer available. Pick another.",
        });
        setSlotId(null);
        void loadSlots(doctor);
      } else {
        setBooking({ status: "error", message: apiError.message });
      }
    }
  }

  return (
    <div>
      <p className={eyebrowClass}>Doctors</p>
      <h1 className="font-serif text-[clamp(2.25rem,4vw,3.25rem)] leading-[1.1] font-normal tracking-[-0.03em]">
        Find a doctor
      </h1>
      <p className="mt-4 max-w-xl text-sm leading-7 text-muted">
        Choose a specialist, check the free times over the next two weeks and book a visit.
      </p>

      <div className="mt-10">
        {state.status === "ready" && <label className="mb-6 flex flex-wrap items-center gap-3 text-sm">Filter by specialty
          <select value={specialty} onChange={e => setSpecialty(e.target.value)} className="min-h-11 rounded-[3px] border border-line bg-panel px-3">
            <option value="">All specialties</option>{[...new Set(state.data.map(d => d.specialty))].map(s => <option key={s}>{s}</option>)}
          </select></label>}
        {state.status === "loading" && (
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className={panelClass}>
                <Skeleton lines={4} />
              </div>
            ))}
          </div>
        )}
        {state.status === "error" && (
          <ErrorState
            title="Could not load doctors"
            message={state.error.message}
            onRetry={retry}
          />
        )}
        {state.status === "ready" && state.data.length === 0 && (
          <EmptyState title="No doctors yet" body="The clinic has not listed any doctors." />
        )}
        {state.status === "ready" && state.data.length > 0 && (
          <ul className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {state.data.filter(d => !specialty || d.specialty === specialty).map((doctor) => {
              const isSelected = selected?.id === doctor.id;
              return (
                <li key={doctor.id}>
                  <article
                    className={`${panelClass} flex h-full flex-col ${isSelected ? "border-accent" : ""}`}
                  >
                    <div
                      aria-hidden="true"
                      className="mb-5 grid h-16 w-16 place-items-center rounded-full bg-soft font-serif text-xl text-accent"
                    >
                      {initials(doctor.name)}
                    </div>
                    <h2 className={headingClass}>{doctor.name}</h2>
                    <p className="mt-2 text-xs font-semibold tracking-widest text-accent uppercase">
                      {doctor.specialty}
                    </p>
                    <p className="mt-4 flex-1 text-sm leading-6 text-muted">{doctor.bio}</p>
                    <p className="mt-4 text-xs text-muted">{doctor.clinic.name}</p>
                    <p className="mt-3 text-xs leading-6">Next available: {doctor.next_available ? `${formatDateTime(doctor.next_available)}` : "No published time in the next 14 days"}</p>
                    <button
                      type="button"
                      onClick={() => checkAvailability(doctor)}
                      className={`${isSelected ? btnPrimary : btnSecondary} mt-5 w-full`}
                    >
                      Check availability
                    </button>
                  </article>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {selected && (
        <section aria-labelledby="booking-title" className={`${panelClass} mt-10`}>
          <p className={eyebrowClass}>Availability</p>
          <h2 ref={bookingTitleRef} tabIndex={-1} id="booking-title" className={`${headingClass} scroll-mt-6`}>
            Book with {selected.name}
          </h2>

          {booking.status === "booked" && (
            <p role="status" className="mt-5 rounded-[3px] bg-soft p-4 text-sm text-accent">
              {booking.message}
            </p>
          )}

          <div className="mt-6">
            {staff && <PatientSelector value={patientId} onChange={setPatientId} />}
            {slotState.status === "loading" && <Skeleton lines={4} />}
            {slotState.status === "error" && (
              <ErrorState
                message={slotState.error.message}
                onRetry={() => loadSlots(selected)}
              />
            )}
            {slotState.status === "ready" && slotState.slots.length === 0 && (
              <EmptyState
                title="No free times"
                body="There are no openings in the next 14 days. Try another doctor."
              />
            )}
            {slotState.status === "ready" && slotState.slots.length > 0 && (
              <>
                <SlotPicker
                  slots={slotState.slots}
                  selectedId={slotId}
                  onSelect={setSlotId}
                  disabled={booking.status === "submitting"}
                />
                <div className="mt-8 grid gap-2">
                  <label htmlFor="booking-reason" className="text-sm font-medium">
                    Reason for visit
                  </label>
                  <textarea
                    id="booking-reason"
                    value={reason}
                    maxLength={200}
                    onChange={(event) => setReason(event.target.value)}
                    disabled={booking.status === "submitting"}
                    rows={4}
                    className="w-full resize-y rounded-[4px] border border-line bg-panel p-3 text-ink"
                  />
                </div>
                {booking.status === "error" && (
                  <p role="alert" className="mt-4 text-sm text-danger">
                    {booking.message}
                  </p>
                )}
                <button
                  type="button"
                  onClick={() => book(selected)}
                  disabled={slotId === null || !reason.trim() || (staff && patientId === null) || booking.status === "submitting"}
                  className={`${btnPrimary} mt-6`}
                >
                  {booking.status === "submitting" ? "Booking..." : "Book appointment"}
                </button>
              </>
            )}
          </div>
        </section>
      )}

      <LiveRegion message={toast} />
    </div>
  );
}
