// Sessione di registrazione audio (vive nell'offscreen document).
// Dipendenze iniettate → testabile in Node senza browser.
//  - traccia "tab": audio della scheda Meet (altri partecipanti), via tabCapture streamId
//  - traccia "mic": microfono dell'utente (facoltativa; se non disponibile si prosegue solo con la scheda)
// L'audio della scheda viene anche riprodotto all'utente: tabCapture altrimenti lo silenzierebbe.
import { ChunkUploader } from "./uploader.js";

export const MIME = "audio/webm;codecs=opus";

export class RecorderSession {
  constructor({ meetingId, streamId, tracks = ["tab"], chunkMs = 5000, send, notify = () => {},
                getUserMedia, MediaRecorderImpl, AudioContextImpl, uploaderOpts = {} }) {
    Object.assign(this, { meetingId, streamId, tracks, chunkMs, send, notify, getUserMedia, MediaRecorderImpl, AudioContextImpl, uploaderOpts });
    this.parts = {};       // track -> { stream, recorder, uploader, stopped: Promise }
    this.audioCtx = null;
    this.activeTracks = [];
    this.warnings = [];
    this.stopping = false;
  }

  async start() {
    const tabStream = await this.getUserMedia({
      audio: { mandatory: { chromeMediaSource: "tab", chromeMediaSourceId: this.streamId } },
      video: false,
    });
    // riproduzione all'utente
    this.audioCtx = new this.AudioContextImpl();
    this.audioCtx.createMediaStreamSource(tabStream).connect(this.audioCtx.destination);
    this._addPart("tab", tabStream);
    for (const t of tabStream.getAudioTracks()) {
      t.addEventListener?.("ended", () => { if (!this.stopping) this.notify({ type: "capture-ended", reason: "tab" }); });
    }

    if (this.tracks.includes("mic")) {
      try {
        const micStream = await this.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
          video: false,
        });
        this._addPart("mic", micStream);
      } catch (e) {
        const w = "Microfono non disponibile: registro solo l'audio della riunione (abilitalo da Impostazioni).";
        this.warnings.push(w);
        this.notify({ type: "warning", message: w, detail: e?.name });
      }
    }
    return { tracks: this.activeTracks.slice(), warnings: this.warnings.slice() };
  }

  _addPart(track, stream) {
    const uploader = new ChunkUploader({
      meetingId: this.meetingId, track, send: this.send, ...this.uploaderOpts,
      onState: (s) => this.notify({ type: "upload", track, ...s }),
    });
    const recorder = new this.MediaRecorderImpl(stream, { mimeType: MIME, audioBitsPerSecond: 64000 });
    const stopped = new Promise((resolve) => recorder.addEventListener("stop", resolve, { once: true }));
    recorder.addEventListener("dataavailable", (e) => { if (e.data && e.data.size > 0) uploader.enqueue(e.data); });
    recorder.addEventListener("error", (e) => this.notify({ type: "error", message: "Errore del registratore audio.", detail: e?.error?.name }));
    recorder.start(this.chunkMs);
    this.parts[track] = { stream, recorder, uploader, stopped };
    this.activeTracks.push(track);
  }

  // Ferma i registratori, attende l'invio di tutti i blocchi, rilascia le risorse.
  async stop({ flushTimeoutMs = 30000 } = {}) {
    this.stopping = true;
    const parts = Object.entries(this.parts);
    for (const [, p] of parts) if (p.recorder.state !== "inactive") p.recorder.stop();
    await Promise.all(parts.map(([, p]) => p.stopped));
    const results = await Promise.all(parts.map(async ([track, p]) => {
      const ok = await p.uploader.flush(flushTimeoutMs);
      p.uploader.cancel();
      return [track, { ok, sentChunks: p.uploader.sentChunks, pending: p.uploader.queue.length, error: p.uploader.fatal }];
    }));
    for (const [, p] of parts) for (const t of p.stream.getTracks()) t.stop();
    try { await this.audioCtx?.close(); } catch { /* già chiuso */ }
    const summary = Object.fromEntries(results);
    return { ok: results.every(([, r]) => r.ok), tracks: summary };
  }
}
