// Macchina a stati della registrazione (logica pura, dipendenze iniettate → testabile con Node).
// Stati: idle → starting → recording → stopping → idle.
// Dipendenze: api (backend), store (stato persistente), badge, capture (offscreen document).

export const IDLE = Object.freeze({
  state: "idle", meetingId: null, title: null, startedAt: null, tabId: null, tracks: [],
  error: null, warning: null, lastMeetingId: null,
});

const BUSY = new Set(["starting", "recording", "stopping"]);
const MSG_CAPTURE = "Impossibile catturare l'audio della scheda Meet.";

export function createController({ api, store, badge, capture, now = () => Date.now(), log = () => {} }) {
  const msg = (e, fallback) => e?.userMessage || fallback;

  async function getState() {
    return { ...IDLE, ...(await store.get()) };
  }

  async function patch(changes) {
    const ns = { ...(await getState()), ...changes };
    await store.set(ns);
    return ns;
  }

  async function start({ title = "", meetCode = null, tabId = null, tracks = ["tab"], streamId = null } = {}) {
    const s = await getState();
    if (BUSY.has(s.state)) return { ok: false, error: "Registrazione già in corso.", state: s };
    const keep = { lastMeetingId: s.lastMeetingId };
    if (!streamId) {
      const ns = { ...IDLE, ...keep, error: MSG_CAPTURE };
      await store.set(ns);
      return { ok: false, error: ns.error, state: ns };
    }
    await store.set({ ...IDLE, ...keep, state: "starting", tabId });
    let md;
    try {
      md = await api.startMeeting({ title, meet_code: meetCode, tracks });
    } catch (e) {
      const ns = { ...IDLE, ...keep, error: msg(e, "Impossibile avviare la registrazione.") };
      await store.set(ns);
      await badge.idle();
      return { ok: false, error: ns.error, state: ns };
    }
    const cap = await capture.start({ meetingId: md.id, streamId, tracks }).catch((e) => ({ ok: false, error: MSG_CAPTURE, detail: e?.message }));
    if (!cap?.ok) {
      log("cattura fallita", cap?.detail || cap?.error);
      await capture.close().catch(() => {});
      await api.stopMeeting(md.id, 0).catch(() => {});
      const ns = { ...IDLE, ...keep, error: cap?.error || MSG_CAPTURE };
      await store.set(ns);
      await badge.idle();
      return { ok: false, error: ns.error, state: ns };
    }
    const ns = { ...IDLE, ...keep, state: "recording", meetingId: md.id, title: md.title, startedAt: now(), tabId,
                 tracks: cap.tracks || ["tab"], warning: (cap.warnings || [])[0] || null };
    await store.set(ns);
    await badge.recording();
    log("start", md.id, ns.tracks);
    return { ok: true, state: ns };
  }

  async function stop() {
    const s = await getState();
    if (s.state !== "recording") return { ok: true, state: s };
    await store.set({ ...s, state: "stopping", error: null });
    const duration = s.startedAt ? (now() - s.startedAt) / 1000 : null;
    let warning = null;
    const cap = await capture.stop().catch(() => ({ ok: false }));
    if (!cap?.ok) warning = "Parte dell'audio potrebbe non essere stata salvata.";
    try {
      const md = await api.stopMeeting(s.meetingId, duration);
      await capture.close().catch(() => {});
      const ns = { ...IDLE, lastMeetingId: md.id, warning };
      await store.set(ns);
      await badge.idle();
      log("stop", md.id, cap);
      return { ok: true, state: ns, meeting: md, capture: cap };
    } catch (e) {
      // l'audio è già fermo; la riunione resta da chiudere sul backend: TERMINA si può ripetere
      const ns = { ...s, state: "recording", warning, error: msg(e, "Impossibile terminare la registrazione.") };
      await store.set(ns);
      return { ok: false, error: ns.error, state: ns };
    }
  }

  async function onTabClosed(tabId) {
    const s = await getState();
    if (s.state === "recording" && s.tabId === tabId) {
      log("scheda chiusa durante la registrazione: stop automatico", s.meetingId);
      return stop();
    }
    return null;
  }

  async function onCaptureEvent(ev = {}) {
    const s = await getState();
    if (s.state !== "recording" && s.state !== "stopping") return s;
    if (ev.type === "capture-ended") return (await stop()).state;
    if (ev.type === "warning") return patch({ warning: ev.message });
    if (ev.type === "error") return patch({ warning: ev.message });
    if (ev.type === "upload") {
      if (ev.state === "offline") return patch({ warning: "Backend offline: l'audio è in attesa di invio." });
      if (ev.state === "online") return patch({ warning: null });
      if (ev.state === "error") return patch({ warning: ev.message });
    }
    return s;
  }

  // Riallinea lo stato a backend e cattura (es. dopo riavvio del service worker o del browser).
  async function resync() {
    const s = await getState();
    if (s.state === "recording" && !(await capture.isActive().catch(() => false))) {
      // la cattura non esiste più (browser riavviato/estensione ricaricata): chiudo la riunione
      await api.stopMeeting(s.meetingId, s.startedAt ? (now() - s.startedAt) / 1000 : null).catch(() => {});
      const ns = { ...IDLE, lastMeetingId: s.meetingId, warning: "Registrazione interrotta (browser o estensione riavviati)." };
      await store.set(ns);
      await badge.idle();
      return ns;
    }
    let remote;
    try {
      remote = (await api.getStatus()).recording;
    } catch {
      return s; // backend offline: non cambio nulla
    }
    if (s.state === "recording" && (!remote || remote.id !== s.meetingId)) {
      await capture.stop().catch(() => {});
      await capture.close().catch(() => {});
      const ns = { ...IDLE, lastMeetingId: s.meetingId };
      await store.set(ns);
      await badge.idle();
      return ns;
    }
    if (s.state === "recording") await badge.recording();
    else if (!BUSY.has(s.state)) await badge.idle();
    return s;
  }

  return { getState, start, stop, onTabClosed, onCaptureEvent, resync };
}
