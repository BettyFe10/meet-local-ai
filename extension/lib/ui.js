// Utilità di interfaccia condivise (niente innerHTML con dati: solo textContent).
export function el(tag, attrs = {}, ...children) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k.startsWith("on") && typeof v === "function") n.addEventListener(k.slice(2), v);
    else if (v !== undefined && v !== null && v !== false) n.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) if (c !== null && c !== undefined) n.append(c instanceof Node ? c : String(c));
  return n;
}

export const STATUS_LABELS = {
  recording: "● In registrazione",
  stopped: "In coda",
  converting: "Conversione audio…",
  transcribing: "Trascrizione…",
  summarizing: "Sintesi…",
  completed: "✓ Completata",
  error: "Errore",
  interrupted: "Interrotta",
};

export function statusLabel(s) { return STATUS_LABELS[s] || s || "—"; }

export function fmtDate(iso) {
  const d = new Date(iso);
  return isNaN(d) ? "—" : d.toLocaleDateString("it-IT", { day: "2-digit", month: "2-digit", year: "numeric" });
}
export function fmtTime(iso) {
  const d = new Date(iso);
  return isNaN(d) ? "—" : d.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" });
}
export function fmtDuration(sec) {
  if (sec === null || sec === undefined) return "—";
  if (sec < 60) return `${Math.round(sec)} s`;
  const m = Math.round(sec / 60);
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${m % 60} min`;
}
export function fmtClock(sec) {
  const s = Math.max(0, Math.floor(sec));
  return [Math.floor(s / 3600), Math.floor((s % 3600) / 60), s % 60].map((x) => String(x).padStart(2, "0")).join(":");
}

export async function openExtensionPage(page) {
  const url = chrome.runtime.getURL(page);
  let existing = null;
  try {
    [existing] = await chrome.tabs.query({ url: url.split("?")[0] + "*" });
  } catch { /* senza permesso "tabs" il filtro può non essere disponibile: apre una nuova scheda */ }
  if (existing) {
    await chrome.tabs.update(existing.id, { active: true, url });
    await chrome.windows.update(existing.windowId, { focused: true });
  } else {
    await chrome.tabs.create({ url });
  }
}

export const MEET_URL_RE = /^https:\/\/meet\.google\.com\/([a-z]{3}-[a-z]{4}-[a-z]{3})(?:[/?#]|$)/;
export function meetCodeFromUrl(url) {
  const m = MEET_URL_RE.exec(url || "");
  return m ? m[1] : null;
}
