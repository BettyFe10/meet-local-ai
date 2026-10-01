// Offscreen document: unico punto in cui l'audio vive nel browser.
// Riceve ordini dal service worker, registra, invia i blocchi direttamente al backend locale.
import { makeClient } from "./lib/http.js";
import { RecorderSession } from "./lib/session.js";

let session = null;

const notify = (event) => chrome.runtime.sendMessage({ type: "offscreen-event", event }).catch(() => {});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id || msg?.target !== "offscreen") return false;
  (async () => {
    if (msg.type === "start") {
      if (session) return { ok: false, error: "Registrazione audio già attiva." };
      const client = makeClient(async () => msg.baseUrl);
      session = new RecorderSession({
        meetingId: msg.meetingId, streamId: msg.streamId, tracks: msg.tracks, chunkMs: msg.chunkMs || 5000,
        send: client.sendChunk, notify,
        getUserMedia: (c) => navigator.mediaDevices.getUserMedia(c),
        MediaRecorderImpl: MediaRecorder, AudioContextImpl: AudioContext,
      });
      try {
        return { ok: true, ...(await session.start()) };
      } catch (e) {
        console.error("[MeetLocalAI] cattura audio fallita:", e);
        session = null;
        return { ok: false, error: "Impossibile catturare l'audio della scheda Meet.", detail: e?.name };
      }
    }
    if (msg.type === "stop") {
      if (!session) return { ok: true, tracks: {} };
      const s = session;
      const r = await s.stop();
      session = null;
      return r;
    }
    if (msg.type === "ping") return { ok: true, active: !!session };
    return { ok: false, error: "Comando sconosciuto." };
  })().then(sendResponse);
  return true;
});
