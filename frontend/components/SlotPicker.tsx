"use client";

import type { Slot } from "@/lib/api";
import { useId, useState } from "react";
import { formatTime, groupSlotsByDay } from "@/lib/format";

interface SlotPickerProps {
  slots: Slot[];
  selectedId: number | null;
  onSelect: (slotId: number | null) => void;
  disabled?: boolean;
}

// Free slots grouped by local day. Each time is a toggle button.
export function SlotPicker({ slots, selectedId, onSelect, disabled = false }: SlotPickerProps) {
  const days = groupSlotsByDay(slots);
  const [dateKey, setDateKey] = useState("");
  const selectId = useId();
  const activeDay = days.find(d => d.key === dateKey) ?? days.find(d => d.slots.some(s => s.id === selectedId)) ?? days[0];
  if (!activeDay) return <p className="text-sm text-muted">No available times.</p>;
  return (
    <div className="space-y-6">
      <label htmlFor={selectId} className="grid gap-2 text-sm font-medium">Choose a date
        <select id={selectId} value={activeDay.key} disabled={disabled} onChange={event => { setDateKey(event.target.value); onSelect(null); }} className="min-h-11 w-full rounded-[3px] border border-line bg-panel px-3">
          {days.map(day => <option key={day.key} value={day.key}>{day.label} · {day.slots.length} available</option>)}
        </select>
      </label>
      {[activeDay].map((day) => {
        const headingId = `slot-day-${day.key}`;
        return (
          <div key={day.key} role="group" aria-labelledby={headingId}>
            <h3 id={headingId} className="mb-3 text-sm font-medium">
              {day.label}
            </h3>
            <div className="flex flex-wrap gap-2">
              {day.slots.map((slot) => {
                const selected = slot.id === selectedId;
                return (
                  <button
                    key={slot.id}
                    type="button"
                    aria-pressed={selected}
                    aria-label={`${day.label} at ${formatTime(slot.starts_at)}`}
                    disabled={disabled}
                    onClick={() => onSelect(slot.id)}
                    className={`min-h-11 min-w-[5.5rem] rounded-[3px] border px-3 text-sm tabular-nums transition ${
                      selected
                        ? "border-accent bg-accent text-on"
                        : "border-line bg-bg text-ink hover:border-accent"
                    }`}
                  >
                    {formatTime(slot.starts_at)}
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
