// Sessione di registrazione audio (vive nell'offscreen document).
// Dipendenze iniettate → testabile in Node senza browser.
//  - traccia "tab": audio della scheda Meet (altri partecipanti), via tabCapture streamId
//  - traccia "mic": microfono dell'utente (facoltativa; se non disponibile si prosegue solo con la scheda)
// L'audio della scheda viene anche riprodotto all'utente: tabCapture altrimenti lo silenzierebbe.
import { ChunkUploader } from "./uploader.js";

export const MIME = "audio/webm;codecs=opus";

// Spiega perché il microfono non si è aperto (il nome dell'errore viene dal browser).
export function micProblem(name) {
  if (name === "NotFoundError" || name === "OverconstrainedError") return "nessun microfono collegato a questo Mac.";
  if (name === "NotAllowedError" || name === "SecurityError") {
    return "permesso mancante. Abilitalo da Impostazioni dell'estensione e controlla sul Mac: Impostazioni di Sistema → Privacy e sicurezza → Microfono → Google Chrome.";
  }
  if (name === "NotReadableError" || name === "AbortError") return "è in uso da un altro programma o bloccato da macOS (Impostazioni di Sistema → Privacy e sicurezza → Microfono → Google Chrome).";
  return "non è stato possibile aprirlo.";
}

export class RecorderSession {
  constructor({ meetingId, streamId, tracks = ["tab"], chunkMs = 5000, send, notify = () => {},
                getUserMedia, MediaRecorderImpl, AudioContextImpl, uploaderOpts = {},
                silenceWarnMs = 45000, silenceCheckMs = 2000, setIntervalImpl = setInterval, clearIntervalImpl = clearInterval }) {
    Object.assign(this, { meetingId, streamId, tracks, chunkMs, send, notify, getUserMedia, MediaRecorderImpl, AudioContextImpl, uploaderOpts,
                          silenceWarnMs, silenceCheckMs, setIntervalImpl, clearIntervalImpl });
    this.silence = { timer: null, quietMs: 0, warned: false };
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
    const source = this.audioCtx.createMediaStreamSource(tabStream);
    source.connect(this.audioCtx.destination);
    this._watchSilence(source);
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
        const w = `Microfono non disponibile: ${micProblem(e?.name)} Registro solo l'audio della riunione.`;
        this.warnings.push(w);
        this.notify({ type: "warning", message: w, detail: e?.name });
      }
    }
    return { tracks: this.activeTracks.slice(), warnings: this.warnings.slice() };
  }

  // Avvisa se dalla scheda Meet non arriva alcun suono (scheda silenziata, riunione non ancora iniziata…).
  // Misura solo il livello: nessun audio viene analizzato o conservato qui.
  _watchSilence(source) {
    if (typeof this.audioCtx.createAnalyser !== "function") return;
    const analyser = this.audioCtx.createAnalyser();
    analyser.fftSize = 2048;
    source.connect(analyser);
    const buf = new Float32Array(analyser.fftSize);
    const s = this.silence;
    s.timer = this.setIntervalImpl(() => {
      analyser.getFloatTimeDomainData(buf);
      let peak = 0;
      for (let i = 0; i < buf.length; i++) { const v = Math.abs(buf[i]); if (v > peak) peak = v; }
      if (peak > 0.001) {            // circa -60 dB: c'è audio
        s.quietMs = 0;
        if (s.warned) { s.warned = false; this.notify({ type: "tab-audio" }); }
      } else {
        s.quietMs += this.silenceCheckMs;
        if (!s.warned && s.quietMs >= this.silenceWarnMs) { s.warned = true; this.notify({ type: "tab-silent" }); }
      }
    }, this.silenceCheckMs);
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
    if (this.silence.timer !== null) this.clearIntervalImpl(this.silence.timer);
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
