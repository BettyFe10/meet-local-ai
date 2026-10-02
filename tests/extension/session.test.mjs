import { test } from "node:test";
import assert from "node:assert/strict";
import { RecorderSession, MIME } from "../../extension/lib/session.js";

class FakeTrack extends EventTarget { constructor() { super(); this.stopped = false; } stop() { this.stopped = true; } }
class FakeStream {
  constructor() { this.tracks = [new FakeTrack()]; }
  getTracks() { return this.tracks; }
  getAudioTracks() { return this.tracks; }
}
class FakeRecorder extends EventTarget {
  static instances = [];
  constructor(stream, opts) { super(); this.stream = stream; this.opts = opts; this.state = "inactive"; FakeRecorder.instances.push(this); }
  start(ms) { this.state = "recording"; this.timeslice = ms; }
  emit(size) { const e = new Event("dataavailable"); e.data = { size }; this.dispatchEvent(e); }
  stop() { this.emit(7); this.state = "inactive"; this.dispatchEvent(new Event("stop")); }
}
class FakeAudioContext {
  constructor() { this.connected = false; this.closed = false; this.destination = {}; }
  createMediaStreamSource() { return { connect: (d) => { this.connected = d === this.destination; } }; }
  async close() { this.closed = true; }
}

function make({ micFails = false, sendImpl, sleep = async () => {} } = {}) {
  FakeRecorder.instances = [];
  const sent = [];
  const events = [];
  const constraints = [];
  const s = new RecorderSession({
    meetingId: "m", streamId: "S1", tracks: ["tab", "mic"], chunkMs: 5000,
    send: sendImpl || (async (id, track, seq, blob) => { sent.push([track, seq, blob.size]); }),
    notify: (e) => events.push(e),
    getUserMedia: async (c) => {
      constraints.push(c);
      if (micFails && !c.audio.mandatory) { const e = new Error("no"); e.name = "NotAllowedError"; throw e; }
      return new FakeStream();
    },
    MediaRecorderImpl: FakeRecorder, AudioContextImpl: FakeAudioContext,
    uploaderOpts: { sleep },
  });
  return { s, sent, events, constraints };
}

test("start: cattura scheda con streamId, riproduce l'audio, registra scheda + microfono in webm/opus a 5 s", async () => {
  const { s, constraints } = make();
  const r = await s.start();
  assert.deepEqual(r.tracks, ["tab", "mic"]);
  assert.equal(constraints[0].audio.mandatory.chromeMediaSource, "tab");
  assert.equal(constraints[0].audio.mandatory.chromeMediaSourceId, "S1");
  assert.equal(constraints[1].audio.echoCancellation, true);
  assert.equal(s.audioCtx.connected, true);
  assert.equal(FakeRecorder.instances.length, 2);
  for (const rec of FakeRecorder.instances) {
    assert.equal(rec.opts.mimeType, MIME);
    assert.equal(rec.timeslice, 5000);
  }
});

test("microfono negato → prosegue solo con la scheda e avvisa", async () => {
  const { s, events } = make({ micFails: true });
  const r = await s.start();
  assert.deepEqual(r.tracks, ["tab"]);
  assert.equal(r.warnings.length, 1);
  assert.equal(events[0].type, "warning");
});

test("i blocchi vengono inviati per traccia con seq; stop svuota la coda e rilascia tutto", async () => {
  const { s, sent } = make();
  await s.start();
  const [tab, mic] = FakeRecorder.instances;
  tab.emit(100); tab.emit(100); mic.emit(50); tab.emit(0);
  const r = await s.stop({ flushTimeoutMs: 1000 });
  assert.equal(r.ok, true);
  assert.deepEqual(sent.filter((x) => x[0] === "tab").map((x) => x[1]), [0, 1, 2]); // ultimo blocco emesso allo stop
  assert.deepEqual(sent.filter((x) => x[0] === "mic").map((x) => x[1]), [0, 1]);
  assert.equal(r.tracks.tab.sentChunks, 3);
  assert.ok(Object.values(s.parts).every((p) => p.stream.getTracks().every((t) => t.stopped)));
  assert.equal(s.audioCtx.closed, true);
});

test("fine della traccia della scheda → evento capture-ended (non durante lo stop)", async () => {
  const { s, events } = make();
  await s.start();
  s.parts.tab.stream.getAudioTracks()[0].dispatchEvent(new Event("ended"));
  assert.ok(events.some((e) => e.type === "capture-ended"));
  const n = events.length;
  await s.stop({ flushTimeoutMs: 100 });
  s.parts.tab.stream.getAudioTracks()[0].dispatchEvent(new Event("ended"));
  assert.equal(events.filter((e) => e.type === "capture-ended").length, events.slice(0, n).filter((e) => e.type === "capture-ended").length);
});

test("backend irraggiungibile allo stop → risultato non ok con blocchi in sospeso", async () => {
  const err = Object.assign(new Error("off"), { status: 0, code: "backend_offline" });
  const { s } = make({ sendImpl: async () => { throw err; }, sleep: (ms) => new Promise((r) => setTimeout(r, 2)) });
  await s.start();
  FakeRecorder.instances[0].emit(10);
  const r = await s.stop({ flushTimeoutMs: 50 });
  assert.equal(r.ok, false);
  assert.ok(r.tracks.tab.pending > 0);
});

test("avviso se la scheda resta muta, ritirato quando arriva l'audio", async () => {
  let level = 0;
  let tickFn = null;
  let cleared = false;
  class CtxWithAnalyser extends FakeAudioContext {
    createMediaStreamSource() { return { connect: () => {} }; }
    createAnalyser() { return { fftSize: 0, getFloatTimeDomainData: (buf) => buf.fill(level) }; }
  }
  const events = [];
  const s = new RecorderSession({
    meetingId: "m", streamId: "S", tracks: ["tab"], send: async () => {}, notify: (e) => events.push(e.type),
    getUserMedia: async () => new FakeStream(), MediaRecorderImpl: FakeRecorder, AudioContextImpl: CtxWithAnalyser,
    silenceWarnMs: 6000, silenceCheckMs: 2000,
    setIntervalImpl: (fn) => { tickFn = fn; return 1; }, clearIntervalImpl: () => { cleared = true; },
    uploaderOpts: { sleep: async () => {} },
  });
  await s.start();
  tickFn(); tickFn();
  assert.deepEqual(events.filter((e) => e.startsWith("tab-")), []);          // 4 s: ancora presto
  tickFn(); tickFn();
  assert.deepEqual(events.filter((e) => e.startsWith("tab-")), ["tab-silent"]); // una sola volta
  level = 0.2; tickFn();
  assert.deepEqual(events.filter((e) => e.startsWith("tab-")), ["tab-silent", "tab-audio"]);
  level = 0; tickFn(); tickFn();
  assert.equal(events.filter((e) => e === "tab-silent").length, 1);           // il conteggio riparte da zero
  await s.stop();
  assert.equal(cleared, true);
});
