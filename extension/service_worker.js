// Service worker: orchestrazione (stato, badge REC, offscreen document). Non tocca mai l'audio.
import * as api from "./lib/api.js";
import { createController, IDLE } from "./lib/controller.js";

const OFFSCREEN_URL = "offscreen.html";

const store = {
  get: async () => (await chrome.storage.session.get({ mla: IDLE })).mla,
  set: (v) => chrome.storage.session.set({ mla: v }),
};

const badge = {
  recording: async () => {
    await chrome.action.setBadgeBackgroundColor({ color: "#e11d48" });
    await chrome.action.setBadgeText({ text: "REC" });
    await chrome.action.setTitle({ title: "Meet Local AI — REGISTRAZIONE ATTIVA" });
  },
  idle: async () => {
    await chrome.action.setBadgeText({ text: "" });
    await chrome.action.setTitle({ title: "Meet Local AI" });
  },
};

const toOffscreen = (msg) => chrome.runtime.sendMessage({ ...msg, target: "offscreen" });

const capture = {
  async start({ meetingId, streamId, tracks }) {
    if (!(await chrome.offscreen.hasDocument())) {
      await chrome.offscreen.createDocument({
        url: OFFSCREEN_URL,
        reasons: ["USER_MEDIA"],
        justification: "Registrazione audio della riunione Google Meet avviata dall'utente.",
      });
    }
    const { chunkSeconds, micDeviceId } = await chrome.storage.local.get({ chunkSeconds: 5, micDeviceId: "" });
    return toOffscreen({ type: "start", meetingId, streamId, tracks, baseUrl: await api.baseUrl(), chunkMs: chunkSeconds * 1000, micDeviceId });
  },
  async stop() {
    if (!(await chrome.offscreen.hasDocument())) return { ok: true, tracks: {} };
    return toOffscreen({ type: "stop" });
  },
  async close() {
    if (await chrome.offscreen.hasDocument()) await chrome.offscreen.closeDocument();
  },
  async isActive() {
    if (!(await chrome.offscreen.hasDocument())) return false;
    return !!(await toOffscreen({ type: "ping" }))?.active;
  },
};

const controller = createController({ api, store, badge, capture, log: (...a) => console.log("[MeetLocalAI]", ...a) });

chrome.runtime.onInstalled.addListener(() => controller.resync());
chrome.runtime.onStartup.addListener(() => controller.resync());
chrome.tabs.onRemoved.addListener((tabId) => { controller.onTabClosed(tabId); });

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id || msg?.target === "offscreen") return false;
  const handlers = {
    getState: () => controller.getState(),
    start: () => controller.start(msg.payload || {}),
    stop: () => controller.stop(),
    resync: () => controller.resync(),
    "offscreen-event": () => controller.onCaptureEvent(msg.event),
  };
  const h = handlers[msg?.type];
  if (!h) return false;
  h().then(sendResponse, (e) => sendResponse({ ok: false, error: e?.userMessage || "Errore interno dell'estensione." }));
  return true;
});
