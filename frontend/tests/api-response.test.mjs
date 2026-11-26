import assert from "node:assert/strict";
import { test } from "node:test";
import { getDoctors, logout, bookAppointment } from "../lib/api.ts";

test("API client handles delayed success, non-JSON errors, validation and empty responses", async () => {
  const previousFetch = globalThis.fetch;
  try {
    globalThis.fetch = () => new Promise(resolve => setTimeout(() => resolve(new Response("[]")), 30));
    assert.deepEqual(await getDoctors(), []);
    globalThis.fetch = async () => new Response("upstream failed", { status: 502 });
    await assert.rejects(getDoctors, error => error.status === 502 && error.code === "http_error");
    globalThis.fetch = async () => new Response(JSON.stringify({ detail: [{ msg: "invalid" }] }), { status: 422 });
    await assert.rejects(getDoctors, error => error.code === "validation_error" && /Check the form/.test(error.message));
    globalThis.fetch = async () => new Response(null, { status: 204 });
    assert.equal(await logout(), undefined);
    let request;
    globalThis.fetch = async (_url, init) => { request = init; return new Response("{}"); };
    await bookAppointment({ slot_id: 7, reason: "Synthetic QA" }, "retry-key");
    assert.equal(request.method, "POST");
    assert.equal(request.credentials, "include");
    assert.equal(request.headers["Idempotency-Key"], "retry-key");
    assert.deepEqual(JSON.parse(request.body), { slot_id: 7, reason: "Synthetic QA" });
  } finally {
    globalThis.fetch = previousFetch;
  }
});
