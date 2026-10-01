import { test } from "node:test";
import assert from "node:assert/strict";
import { fmtClock, fmtDuration, meetCodeFromUrl, statusLabel } from "../../extension/lib/ui.js";

test("fmtDuration", () => {
  assert.equal(fmtDuration(null), "—");
  assert.equal(fmtDuration(10), "10 s");
  assert.equal(fmtDuration(47 * 60), "47 min");
  assert.equal(fmtDuration(95 * 60), "1 h 35 min");
});

test("fmtClock", () => {
  assert.equal(fmtClock(23 * 60 + 14 + 3600 * 0), "00:23:14");
  assert.equal(fmtClock(-5), "00:00:00");
});

test("meetCodeFromUrl", () => {
  assert.equal(meetCodeFromUrl("https://meet.google.com/pcm-iaqh-vds?authuser=0"), "pcm-iaqh-vds");
  assert.equal(meetCodeFromUrl("https://meet.google.com/landing"), null);
  assert.equal(meetCodeFromUrl("https://evil.example/pcm-iaqh-vds"), null);
  assert.equal(meetCodeFromUrl(undefined), null);
});

test("statusLabel", () => {
  assert.equal(statusLabel("completed"), "✓ Completata");
  assert.equal(statusLabel("stopped"), "In coda");
});
