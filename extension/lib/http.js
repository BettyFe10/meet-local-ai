// Client HTTP verso il backend locale, senza API chrome.* (usabile anche nell'offscreen document,
// che può usare solo chrome.runtime). La base URL viene passata da chi lo crea.
export const MSG_OFFLINE = "Backend offline.";

export class BackendError extends Error {
  constructor(userMessage, code, status = 0, data = null) {
    super(userMessage);
    this.userMessage = userMessage;
    this.code = code;
    this.status = status;
    this.data = data;
  }
}

export function makeClient(getBaseUrl, fetchImpl = (...a) => fetch(...a)) {
  async function request(path, { method = "GET", body, rawBody, contentType, timeoutMs = 4000, as = "json" } = {}) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    let res;
    try {
      res = await fetchImpl((await getBaseUrl()) + path, {
        method,
        headers: {
          "X-MeetLocalAI": "1",
          ...(body ? { "Content-Type": "application/json" } : {}),
          ...(rawBody ? { "Content-Type": contentType || "application/octet-stream" } : {}),
        },
        body: rawBody ?? (body ? JSON.stringify(body) : undefined),
        signal: ctrl.signal,
        cache: "no-store",
      });
    } catch (e) {
      console.warn("[MeetLocalAI] backend non raggiungibile:", e?.name || e);
      throw new BackendError(MSG_OFFLINE, "backend_offline");
    } finally {
      clearTimeout(timer);
    }
    if (res.ok && as === "text") return res.text();
    let data = null;
    try { data = await res.json(); } catch { /* risposta non JSON */ }
    if (!res.ok) {
      const msg = data?.user_message || "Si è verificato un errore. I dettagli sono nei log del backend.";
      throw new BackendError(msg, data?.error_code || `http_${res.status}`, res.status, data);
    }
    return data;
  }

  const enc = encodeURIComponent;
  return {
    request,
    getHealth: () => request("/health", { timeoutMs: 3000 }),
    listMeetings: () => request("/meetings"),
    getMeeting: (id) => request(`/meetings/${enc(id)}`),
    getStatus: () => request("/status"),
    startMeeting: (payload) => request("/meetings", { method: "POST", body: payload, timeoutMs: 8000 }),
    stopMeeting: (id, clientDurationSeconds) =>
      request(`/meetings/${enc(id)}/stop`, { method: "POST", body: { client_duration_seconds: clientDurationSeconds }, timeoutMs: 8000 }),
    getTranscript: (id, format = "txt") => request(`/meetings/${enc(id)}/transcript?format=${format}`, { as: "text", timeoutMs: 10000 }),
    getSummary: (id) => request(`/meetings/${enc(id)}/summary`, { timeoutMs: 10000 }),
    reprocessMeeting: (id, steps) => request(`/meetings/${enc(id)}/reprocess`, { method: "POST", body: steps ? { steps } : {} }),
    deleteMeeting: (id) => request(`/meetings/${enc(id)}`, { method: "DELETE", timeoutMs: 35000 }),
    exportMeeting: (id, format) => request(`/meetings/${enc(id)}/export?format=${format}`, { as: "text", timeoutMs: 15000 }),
    getSettings: () => request("/settings", { timeoutMs: 8000 }),
    setSettings: (changes) => request("/settings", { method: "PATCH", body: changes, timeoutMs: 8000 }),
    getStorage: () => request("/storage", { timeoutMs: 15000 }),
    getAudioToken: (id) => request(`/meetings/${enc(id)}/audio-token`, { method: "POST" }),
    audioUrl: async (id, token) => `${await getBaseUrl()}/meetings/${enc(id)}/audio?token=${enc(token)}`,
    openFolder: (id) => request(`/meetings/${enc(id)}/open-folder`, { method: "POST" }),
    openDataRoot: () => request("/open-data-root", { method: "POST" }),
    renameMeeting: (id, title) => request(`/meetings/${enc(id)}`, { method: "PATCH", body: { title } }),
    sendChunk: (id, track, seq, blob) =>
      request(`/meetings/${enc(id)}/chunks?track=${enc(track)}&seq=${seq}`,
        { method: "POST", rawBody: blob, contentType: "audio/webm", timeoutMs: 15000 }),
  };
}
