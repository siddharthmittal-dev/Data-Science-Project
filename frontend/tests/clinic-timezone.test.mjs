import assert from "node:assert/strict";
import { test } from "node:test";
import { formatTime, formatDate, groupSlotsByDay } from "../lib/format.ts";

test("clinic dates and slot grouping stay in IST across viewer timezones", () => {
  const slots = [
    { id: 1, starts_at: "2026-11-21T18:20:00Z", ends_at: "2026-11-21T18:30:00Z" },
    { id: 2, starts_at: "2026-11-21T18:30:00Z", ends_at: "2026-11-21T19:00:00Z" },
  ];
  assert.deepEqual(groupSlotsByDay(slots).map(day => day.key), ["2026-11-21", "2026-11-22"]);
  assert.equal(formatTime(slots[1].starts_at), new Intl.DateTimeFormat(undefined, {
    timeZone: "Asia/Kolkata", hour: "numeric", minute: "2-digit",
  }).format(new Date(slots[1].starts_at)));
  assert.match(formatDate(slots[1].starts_at), /22/);
});
