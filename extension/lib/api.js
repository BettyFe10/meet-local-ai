// Comunicazione con il backend locale (solo 127.0.0.1). Messaggi d'errore semplici per l'utente.
export const DEFAULT_PORT = 8765;
export const MSG_OFFLINE = "Backend offline.";

export async function getPort() {
  const { backendPort } = await chrome.storage.local.get({ backendPort: DEFAULT_PORT });
  return backendPort;
}

export async function baseUrl() {
  return `http://127.0.0.1:${await getPort()}/api/v1`;
}

export class BackendError extends Error {
  constructor(userMessage, code, status = 0, data = null) {
    super(userMessage);
    this.userMessage = userMessage;
    this.code = code;
    this.status = status;
    this.data = data;
  }
}

export async function request(path, { method = "GET", body, rawBody, contentType, timeoutMs = 4000 } = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  let res;
  try {
    res = await fetch((await baseUrl()) + path, {
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
  let data = null;
  try { data = await res.json(); } catch { /* risposta non JSON */ }
  if (!res.ok) {
    const msg = data?.user_message || "Si è verificato un errore. I dettagli sono nei log del backend.";
    throw new BackendError(msg, data?.error_code || `http_${res.status}`, res.status, data);
  }
  return data;
}

export const getHealth = () => request("/health", { timeoutMs: 3000 });
export const listMeetings = () => request("/meetings");
export const getMeeting = (id) => request(`/meetings/${encodeURIComponent(id)}`);
export const getStatus = () => request("/status");
export const startMeeting = (payload) => request("/meetings", { method: "POST", body: payload, timeoutMs: 8000 });
export const stopMeeting = (id, clientDurationSeconds) =>
  request(`/meetings/${encodeURIComponent(id)}/stop`, { method: "POST", body: { client_duration_seconds: clientDurationSeconds }, timeoutMs: 8000 });
export const renameMeeting = (id, title) => request(`/meetings/${encodeURIComponent(id)}`, { method: "PATCH", body: { title } });
export const sendChunk = (id, track, seq, blob) =>
  request(`/meetings/${encodeURIComponent(id)}/chunks?track=${encodeURIComponent(track)}&seq=${seq}`,
    { method: "POST", rawBody: blob, contentType: "audio/webm", timeoutMs: 15000 });
