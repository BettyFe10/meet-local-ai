import { test } from "node:test";
import assert from "node:assert/strict";
import { createController, IDLE } from "../../extension/lib/controller.js";

function setup({ api: apiOv = {}, capture: capOv = {} } = {}) {
  let state = { ...IDLE };
  const calls = [];
  let t = 1_000_000;
  const api = {
    startMeeting: async (p) => { calls.push(["start", p]); return { id: "2026-10-01_10-00_Test", title: p.title || "Riunione" }; },
    stopMeeting: async (id, d) => { calls.push(["stop", id, d]); return { id, status: "stopped" }; },
    getStatus: async () => ({ recording: { id: "2026-10-01_10-00_Test" } }),
    ...apiOv,
  };
  const capture = {
    start: async (a) => { calls.push(["cap.start", a]); return { ok: true, tracks: a.tracks, warnings: [] }; },
    stop: async () => { calls.push(["cap.stop"]); return { ok: true, tracks: {} }; },
    close: async () => { calls.push(["cap.close"]); },
    isActive: async () => true,
    ...capOv,
  };
  const badgeLog = [];
  const ctrl = createController({
    api, capture,
    store: { get: async () => state, set: async (v) => { state = v; } },
    badge: { recording: async () => badgeLog.push("REC"), idle: async () => badgeLog.push("idle") },
    now: () => t,
  });
  return { ctrl, calls, badgeLog, getState: () => state, advance: (ms) => { t += ms; } };
}

const offline = () => { const e = new Error("x"); e.userMessage = "Backend offline."; e.code = "backend_offline"; throw e; };
const START = { title: "Test", meetCode: "abc-defg-hij", tabId: 7, tracks: ["tab", "mic"], streamId: "S1" };
const names = (calls) => calls.map((c) => c[0]);

test("start: backend → cattura → recording con badge REC", async () => {
  const { ctrl, badgeLog, getState, calls } = setup();
  const r = await ctrl.start(START);
  assert.equal(r.ok, true);
  assert.deepEqual(names(calls), ["start", "cap.start"]);
  assert.deepEqual(calls[1][1], { meetingId: "2026-10-01_10-00_Test", streamId: "S1", tracks: ["tab", "mic"] });
  assert.equal(getState().state, "recording");
  assert.deepEqual(getState().tracks, ["tab", "mic"]);
  assert.deepEqual(badgeLog, ["REC"]);
});

test("start senza streamId → errore, nessuna riunione creata", async () => {
  const { ctrl, calls, getState } = setup();
  const r = await ctrl.start({ ...START, streamId: null });
  assert.equal(r.ok, false);
  assert.equal(calls.length, 0);
  assert.match(getState().error, /catturare l'audio/);
});

test("cattura fallita → riunione chiusa sul backend, stato idle con errore", async () => {
  const { ctrl, calls, getState } = setup({ capture: { start: async () => ({ ok: false, error: "Impossibile catturare l'audio della scheda Meet." }) } });
  const r = await ctrl.start(START);
  assert.equal(r.ok, false);
  assert.deepEqual(names(calls), ["start", "cap.close", "stop"]);
  assert.equal(getState().state, "idle");
});

test("microfono non disponibile → registra solo la scheda con avviso", async () => {
  const { ctrl, getState } = setup({ capture: { start: async () => ({ ok: true, tracks: ["tab"], warnings: ["Microfono non disponibile"] }) } });
  await ctrl.start(START);
  assert.deepEqual(getState().tracks, ["tab"]);
  assert.equal(getState().warning, "Microfono non disponibile");
});

test("doppio start rifiutato", async () => {
  const { ctrl } = setup();
  await ctrl.start(START);
  const r = await ctrl.start(START);
  assert.equal(r.ok, false);
  assert.match(r.error, /già in corso/);
});

test("start con backend offline → idle con messaggio, nessuna cattura", async () => {
  const { ctrl, getState, calls } = setup({ api: { startMeeting: offline } });
  const r = await ctrl.start(START);
  assert.equal(r.ok, false);
  assert.equal(getState().error, "Backend offline.");
  assert.ok(!names(calls).includes("cap.start"));
});

test("stop: prima svuota la cattura, poi chiude la riunione con la durata", async () => {
  const { ctrl, calls, getState, advance } = setup();
  await ctrl.start(START);
  advance(65_000);
  const r = await ctrl.stop();
  assert.equal(r.ok, true);
  assert.deepEqual(names(calls), ["start", "cap.start", "cap.stop", "stop", "cap.close"]);
  assert.equal(calls[3][2], 65);
  assert.equal(getState().state, "idle");
  assert.equal(getState().lastMeetingId, "2026-10-01_10-00_Test");
});

test("stop con invio incompleto → avviso di audio parziale", async () => {
  const { ctrl, getState } = setup({ capture: { stop: async () => ({ ok: false }) } });
  await ctrl.start(START);
  await ctrl.stop();
  assert.match(getState().warning, /audio potrebbe non/);
});

test("stop con backend offline resta in registrazione (si può riprovare)", async () => {
  const { ctrl, getState } = setup({ api: { stopMeeting: offline } });
  await ctrl.start(START);
  const r = await ctrl.stop();
  assert.equal(r.ok, false);
  assert.equal(getState().state, "recording");
});

test("fine della cattura (scheda chiusa/condivisione interrotta) → stop automatico", async () => {
  const { ctrl, getState } = setup();
  await ctrl.start(START);
  await ctrl.onCaptureEvent({ type: "capture-ended" });
  assert.equal(getState().state, "idle");
});

test("eventi di upload: offline → avviso, online → avviso rimosso", async () => {
  const { ctrl, getState } = setup();
  await ctrl.start(START);
  await ctrl.onCaptureEvent({ type: "upload", state: "offline" });
  assert.match(getState().warning, /Backend offline/);
  await ctrl.onCaptureEvent({ type: "upload", state: "online" });
  assert.equal(getState().warning, null);
});

test("chiusura della scheda registrata → stop; altre schede ignorate", async () => {
  const { ctrl, getState } = setup();
  await ctrl.start(START);
  assert.equal(await ctrl.onTabClosed(99), null);
  await ctrl.onTabClosed(7);
  assert.equal(getState().state, "idle");
});

test("resync: cattura non più attiva → riunione chiusa con avviso", async () => {
  const { ctrl, getState, calls } = setup({ capture: { isActive: async () => false } });
  await ctrl.start(START);
  await ctrl.resync();
  assert.equal(getState().state, "idle");
  assert.match(getState().warning, /interrotta/);
  assert.ok(names(calls).includes("stop"));
});

test("resync: backend non registra più → idle", async () => {
  const { ctrl, getState } = setup({ api: { getStatus: async () => ({ recording: null }) } });
  await ctrl.start(START);
  await ctrl.resync();
  assert.equal(getState().state, "idle");
});

test("resync: backend offline → stato invariato", async () => {
  const { ctrl, getState } = setup({ api: { getStatus: offline } });
  await ctrl.start(START);
  await ctrl.resync();
  assert.equal(getState().state, "recording");
});

test("scheda muta → avviso; audio tornato → avviso rimosso (senza cancellare altri avvisi)", async () => {
  const { ctrl, getState } = setup();
  await ctrl.start(START);
  await ctrl.onCaptureEvent({ type: "tab-silent" });
  assert.match(getState().warning, /Nessun audio dalla riunione/);
  await ctrl.onCaptureEvent({ type: "tab-audio" });
  assert.equal(getState().warning, null);
  await ctrl.onCaptureEvent({ type: "upload", state: "offline" });
  await ctrl.onCaptureEvent({ type: "tab-audio" });
  assert.match(getState().warning, /Backend offline/);
});
