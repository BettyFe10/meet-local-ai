// Macchina a stati della registrazione (logica pura, dipendenze iniettate → testabile con Node).
// Stati: idle → starting → recording → stopping → idle. Errori riportati con messaggi per l'utente.

export const IDLE = Object.freeze({
  state: "idle", meetingId: null, title: null, startedAt: null, tabId: null, error: null, lastMeetingId: null,
});

const BUSY = new Set(["starting", "recording", "stopping"]);

export function createController({ api, store, badge, now = () => Date.now(), log = () => {} }) {
  const msg = (e, fallback) => e?.userMessage || fallback;

  async function getState() {
    return { ...IDLE, ...(await store.get()) };
  }

  async function start({ title = "", meetCode = null, tabId = null, tracks = ["tab"] } = {}) {
    const s = await getState();
    if (BUSY.has(s.state)) return { ok: false, error: "Registrazione già in corso.", state: s };
    await store.set({ ...IDLE, lastMeetingId: s.lastMeetingId, state: "starting", tabId });
    try {
      const md = await api.startMeeting({ title, meet_code: meetCode, tracks });
      const ns = { ...IDLE, state: "recording", meetingId: md.id, title: md.title, startedAt: now(), tabId,
                   lastMeetingId: s.lastMeetingId };
      await store.set(ns);
      await badge.recording();
      log("start", md.id);
      return { ok: true, state: ns };
    } catch (e) {
      const ns = { ...IDLE, lastMeetingId: s.lastMeetingId, error: msg(e, "Impossibile avviare la registrazione.") };
      await store.set(ns);
      await badge.idle();
      return { ok: false, error: ns.error, state: ns };
    }
  }

  async function stop() {
    const s = await getState();
    if (s.state !== "recording") return { ok: true, state: s };
    await store.set({ ...s, state: "stopping", error: null });
    const duration = s.startedAt ? (now() - s.startedAt) / 1000 : null;
    try {
      const md = await api.stopMeeting(s.meetingId, duration);
      const ns = { ...IDLE, lastMeetingId: md.id };
      await store.set(ns);
      await badge.idle();
      log("stop", md.id);
      return { ok: true, state: ns, meeting: md };
    } catch (e) {
      // la registrazione resta attiva lato estensione: l'utente può riprovare TERMINA
      const ns = { ...s, state: "recording", error: msg(e, "Impossibile terminare la registrazione.") };
      await store.set(ns);
      return { ok: false, error: ns.error, state: ns };
    }
  }

  async function onTabClosed(tabId) {
    const s = await getState();
    if (s.state === "recording" && s.tabId === tabId) {
      log("tab chiusa durante la registrazione: stop automatico", s.meetingId);
      return stop();
    }
    return null;
  }

  // Riallinea lo stato al backend (es. dopo riavvio del service worker o del browser).
  async function resync() {
    const s = await getState();
    let remote;
    try {
      remote = (await api.getStatus()).recording;
    } catch {
      return s; // backend offline: non cambio nulla
    }
    if (s.state === "recording" && (!remote || remote.id !== s.meetingId)) {
      const ns = { ...IDLE, lastMeetingId: s.meetingId };
      await store.set(ns);
      await badge.idle();
      return ns;
    }
    if (s.state === "recording") await badge.recording();
    else if (!BUSY.has(s.state)) await badge.idle();
    return s;
  }

  return { getState, start, stop, onTabClosed, resync };
}
