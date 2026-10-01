// Service worker: stato dell'estensione. In Fase 4 gestisce solo lo stato "idle";
// registrazione (tabCapture + offscreen) arriva nelle Fasi 5-6.
const DEFAULT_STATE = { state: "idle", meetingId: null, startedAt: null };

chrome.runtime.onInstalled.addListener(async () => {
  await chrome.storage.session.set({ mla: DEFAULT_STATE });
  await chrome.action.setBadgeText({ text: "" });
});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type === "getState") {
    chrome.storage.session.get({ mla: DEFAULT_STATE }).then(({ mla }) => sendResponse(mla));
    return true; // risposta asincrona
  }
  return false;
});
