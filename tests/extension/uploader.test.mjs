import { test } from "node:test";
import assert from "node:assert/strict";
import { ChunkUploader } from "../../extension/lib/uploader.js";

const blob = (n) => ({ size: n });
const err = (status, code, data, userMessage) => Object.assign(new Error(code), { status, code, data, userMessage });

function make(sendImpl, opts = {}) {
  const sent = [];
  const states = [];
  const up = new ChunkUploader({
    meetingId: "m", track: "tab",
    send: async (id, track, seq, b) => { await sendImpl(seq, b); sent.push(seq); },
    onState: (s) => states.push(s.state),
    sleep: async () => {},
    ...opts,
  });
  return { up, sent, states };
}

test("invia i blocchi in ordine con seq crescente", async () => {
  const { up, sent } = make(async () => {});
  up.enqueue(blob(10)); up.enqueue(blob(10)); up.enqueue(blob(10));
  assert.equal(await up.flush(1000), true);
  assert.deepEqual(sent, [0, 1, 2]);
  assert.equal(up.queuedBytes, 0);
});

test("backend offline: ritenta e poi recupera senza perdere blocchi", async () => {
  let fails = 3;
  const { up, sent, states } = make(async () => { if (fails-- > 0) throw err(0, "backend_offline", null, "Backend offline."); });
  up.enqueue(blob(5)); up.enqueue(blob(5));
  assert.equal(await up.flush(1000), true);
  assert.deepEqual(sent, [0, 1]);
  assert.ok(states.includes("offline") && states.includes("online"));
});

test("seq_gap con next_seq più avanti → blocco già presente, si prosegue", async () => {
  let first = true;
  const { up, sent } = make(async (seq) => { if (first && seq === 0) { first = false; throw err(409, "seq_gap", { next_seq: 1 }); } });
  up.enqueue(blob(1)); up.enqueue(blob(1));
  assert.equal(await up.flush(1000), true);
  assert.deepEqual(sent, [1]);
});

test("seq_gap con next_seq indietro → errore esplicito (audio perso)", async () => {
  const { up, states } = make(async (seq) => { if (seq === 1) throw err(409, "seq_gap", { next_seq: 0 }); });
  up.enqueue(blob(1)); up.enqueue(blob(1));
  assert.equal(await up.flush(1000), false);
  assert.match(up.fatal, /persa/);
  assert.equal(states.at(-1), "error");
});

test("registrazione non più attiva → stop della coda con messaggio", async () => {
  const { up } = make(async () => { throw err(409, "not_recording"); });
  up.enqueue(blob(1));
  assert.equal(await up.flush(1000), false);
  assert.match(up.fatal, /non è più attiva/);
});

test("coda oltre il limite (backend offline a lungo) → errore e blocchi rifiutati", async () => {
  const { up } = make(async () => { throw err(0, "backend_offline"); }, { maxQueueBytes: 15 });
  assert.equal(up.enqueue(blob(10)), true);
  assert.equal(up.enqueue(blob(10)), false);
  assert.match(up.fatal, /Backend offline/);
});
