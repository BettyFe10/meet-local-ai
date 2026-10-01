import { test } from "node:test";
import assert from "node:assert/strict";
import { createController, IDLE } from "../../extension/lib/controller.js";

function setup(apiOverrides = {}) {
  let state = { ...IDLE };
  const calls = [];
  let t = 1_000_000;
  const api = {
    startMeeting: async (p) => { calls.push(["start", p]); return { id: "2026-10-01_10-00_Test", title: p.title || "Riunione" }; },
    stopMeeting: async (id, d) => { calls.push(["stop", id, d]); return { id, status: "stopped" }; },
    getStatus: async () => ({ recording: null }),
    ...apiOverrides,
  };
  const badgeLog = [];
  const ctrl = createController({
    api,
    store: { get: async () => state, set: async (v) => { state = v; } },
    badge: { recording: async () => badgeLog.push("REC"), idle: async () => badgeLog.push("idle") },
    now: () => t,
  });
  return { ctrl, calls, badgeLog, getState: () => state, advance: (ms) => { t += ms; } };
}

const offline = () => { const e = new Error("x"); e.userMessage = "Backend offline."; e.code = "backend_offline"; throw e; };

test("start → recording con badge REC", async () => {
  const { ctrl, badgeLog, getState, calls } = setup();
  const r = await ctrl.start({ title: "Test", meetCode: "abc-defg-hij", tabId: 7 });
  assert.equal(r.ok, true);
  assert.equal(getState().state, "recording");
  assert.equal(getState().tabId, 7);
  assert.deepEqual(calls[0], ["start", { title: "Test", meet_code: "abc-defg-hij", tracks: ["tab"] }]);
  assert.deepEqual(badgeLog, ["REC"]);
});

test("doppio start rifiutato", async () => {
  const { ctrl } = setup();
  await ctrl.start({});
  const r = await ctrl.start({});
  assert.equal(r.ok, false);
  assert.match(r.error, /già in corso/);
});

test("start con backend offline → idle con messaggio", async () => {
  const { ctrl, getState, badgeLog } = setup({ startMeeting: offline });
  const r = await ctrl.start({});
  assert.equal(r.ok, false);
  assert.equal(getState().state, "idle");
  assert.equal(getState().error, "Backend offline.");
  assert.deepEqual(badgeLog, ["idle"]);
});

test("stop invia la durata e torna idle ricordando l'ultima riunione", async () => {
  const { ctrl, calls, getState, advance } = setup();
  await ctrl.start({});
  advance(65_000);
  const r = await ctrl.stop();
  assert.equal(r.ok, true);
  assert.equal(calls[1][0], "stop");
  assert.equal(calls[1][2], 65);
  assert.equal(getState().state, "idle");
  assert.equal(getState().lastMeetingId, "2026-10-01_10-00_Test");
});

test("stop con backend offline resta in registrazione (si può riprovare)", async () => {
  const { ctrl, getState } = setup({ stopMeeting: offline });
  await ctrl.start({});
  const r = await ctrl.stop();
  assert.equal(r.ok, false);
  assert.equal(getState().state, "recording");
  assert.equal(getState().error, "Backend offline.");
});

test("chiusura della scheda Meet registrata → stop automatico; altre schede ignorate", async () => {
  const { ctrl, getState } = setup();
  await ctrl.start({ tabId: 3 });
  assert.equal(await ctrl.onTabClosed(99), null);
  assert.equal(getState().state, "recording");
  await ctrl.onTabClosed(3);
  assert.equal(getState().state, "idle");
});

test("resync: backend non registra più → stato riallineato a idle", async () => {
  const { ctrl, getState } = setup();
  await ctrl.start({});
  await ctrl.resync();
  assert.equal(getState().state, "idle");
});

test("resync: backend offline → stato invariato", async () => {
  const { ctrl, getState } = setup({ getStatus: offline });
  await ctrl.start({});
  await ctrl.resync();
  assert.equal(getState().state, "recording");
});

test("resync: stessa registrazione attiva sul backend → resta recording", async () => {
  const { ctrl, getState } = setup({ getStatus: async () => ({ recording: { id: "2026-10-01_10-00_Test" } }) });
  await ctrl.start({});
  await ctrl.resync();
  assert.equal(getState().state, "recording");
});
