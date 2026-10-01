// Service worker: orchestrazione dello stato di registrazione e badge "REC".
// L'audio vero (tabCapture + offscreen) arriva in Fase 6.
import * as api from "./lib/api.js";
import { createController, IDLE } from "./lib/controller.js";

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

const controller = createController({ api, store, badge, log: (...a) => console.log("[MeetLocalAI]", ...a) });

chrome.runtime.onInstalled.addListener(() => controller.resync());
chrome.runtime.onStartup.addListener(() => controller.resync());
chrome.tabs.onRemoved.addListener((tabId) => { controller.onTabClosed(tabId); });

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  // accetta messaggi solo dalle pagine di questa estensione
  if (sender.id !== chrome.runtime.id) return false;
  const handlers = {
    getState: () => controller.getState(),
    start: () => controller.start(msg.payload || {}),
    stop: () => controller.stop(),
    resync: () => controller.resync(),
  };
  const h = handlers[msg?.type];
  if (!h) return false;
  h().then(sendResponse, (e) => sendResponse({ ok: false, error: e?.userMessage || "Errore interno dell'estensione." }));
  return true; // risposta asincrona
});
