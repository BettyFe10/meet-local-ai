// Coda di invio dei blocchi audio al backend, in ordine, con ritentativi.
// Usata dall'offscreen document (Fase 6). Se il backend è offline i blocchi restano in memoria
// fino a maxQueueBytes; oltre il limite si segnala l'errore all'utente.

export class ChunkUploader {
  constructor({ meetingId, track, send, onState = () => {}, maxQueueBytes = 200 * 1024 * 1024,
                retryDelaysMs = [1000, 2000, 5000, 10000], sleep = (ms) => new Promise((r) => setTimeout(r, ms)) }) {
    Object.assign(this, { meetingId, track, send, onState, maxQueueBytes, retryDelaysMs, sleep });
    this.queue = [];
    this.nextSeq = 0;
    this.queuedBytes = 0;
    this.sentChunks = 0;
    this.failures = 0;
    this.fatal = null;
    this.cancelled = false;
    this._pumping = null;
  }

  enqueue(blob) {
    if (this.fatal) return false;
    const size = blob?.size ?? blob?.byteLength ?? 0;
    if (this.queuedBytes + size > this.maxQueueBytes) {
      this._setFatal("Backend offline da troppo tempo: parte dell'audio non è stata salvata.");
      return false;
    }
    this.queue.push({ seq: this.nextSeq++, blob, size });
    this.queuedBytes += size;
    this._pump();
    return true;
  }

  _setFatal(message) {
    this.fatal = message;
    this.onState({ state: "error", message });
  }

  _pump() {
    if (!this._pumping) this._pumping = this._run().finally(() => { this._pumping = null; });
    return this._pumping;
  }

  async _run() {
    while (this.queue.length && !this.fatal && !this.cancelled) {
      const item = this.queue[0];
      try {
        await this.send(this.meetingId, this.track, item.seq, item.blob);
        this._done();
        if (this.failures) this.onState({ state: "online" });
        this.failures = 0;
      } catch (e) {
        const next = e?.data?.next_seq;
        if (e?.status === 409 && e?.code === "seq_gap" && Number.isInteger(next)) {
          if (next > item.seq) { this._done(); continue; } // il backend ha già questo blocco
          this._setFatal("Sequenza audio interrotta: una parte della registrazione è andata persa.");
          return;
        }
        if (e?.status === 409 && e?.code === "not_recording") { this._setFatal("La registrazione non è più attiva sul backend."); return; }
        if (e?.status && e.status >= 400 && e.status < 500 && e.status !== 408 && e.status !== 429) {
          this._setFatal(e.userMessage || "Blocco audio rifiutato dal backend.");
          return;
        }
        const delay = this.retryDelaysMs[Math.min(this.failures, this.retryDelaysMs.length - 1)];
        this.failures += 1;
        this.onState({ state: "offline", queued: this.queue.length, message: e?.userMessage || "Backend offline." });
        await this.sleep(delay);
      }
    }
  }

  _done() {
    const item = this.queue.shift();
    this.queuedBytes -= item.size;
    this.sentChunks += 1;
  }

  // Interrompe i ritentativi (es. dopo uno stop con backend irraggiungibile).
  cancel() {
    this.cancelled = true;
  }

  // Attende lo svuotamento della coda (per lo stop). Ritorna true se tutto è stato inviato.
  async flush(timeoutMs = 30000) {
    const deadline = Date.now() + timeoutMs;
    while (this.queue.length && !this.fatal && Date.now() < deadline) {
      await Promise.race([this._pump(), this.sleep(250)]);
    }
    return this.queue.length === 0 && !this.fatal;
  }
}
