import assert from "node:assert/strict";
import { test } from "node:test";
import { getDoctors, getMe, ApiError, SESSION_EXPIRED_EVENT } from "../lib/api.ts";

test("protected 401 signals expiry; auth checks, permissions and outages do not", async () => {
  const previousWindow = globalThis.window;
  const previousFetch = globalThis.fetch;
  const events = new EventTarget();
  let expirations = 0;
  events.addEventListener(SESSION_EXPIRED_EVENT, () => expirations++);
  globalThis.window = events;
  try {
    globalThis.fetch = async () => new Response("{}", { status: 401 });
    await assert.rejects(getDoctors, (error) => error instanceof ApiError && error.status === 401);
    assert.equal(expirations, 1);
    await assert.rejects(getMe, (error) => error.status === 401);
    assert.equal(expirations, 1);
    for (const status of [403, 500]) {
      globalThis.fetch = async () => new Response("{}", { status });
      await assert.rejects(getDoctors, (error) => error.status === status);
    }
    globalThis.fetch = async () => { throw new Error("offline"); };
    await assert.rejects(getDoctors, (error) => error.code === "network_error");
    assert.equal(expirations, 1);
  } finally {
    globalThis.window = previousWindow;
    globalThis.fetch = previousFetch;
  }
});
