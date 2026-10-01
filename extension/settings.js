import { DEFAULT_PORT, getHealth, getPort } from "./lib/api.js";

const $ = (id) => document.getElementById(id);

function show(text, ok) {
  $("result").textContent = text;
  $("result").className = `small status ${ok ? "ok" : "off"}`;
}

async function refreshMic() {
  let state = "prompt";
  try { state = (await navigator.permissions.query({ name: "microphone" })).state; } catch { /* non supportato */ }
  const el = $("micStatus");
  el.textContent = state === "granted" ? "Microfono abilitato." : state === "denied"
    ? "Microfono bloccato: riabilitalo dalle impostazioni del sito dell'estensione in Chrome." : "Microfono non ancora abilitato.";
  el.className = `small status ${state === "granted" ? "ok" : "off"}`;
}

async function init() {
  const { captureMic } = await chrome.storage.local.get({ captureMic: true });
  $("captureMic").checked = captureMic;
  $("captureMic").addEventListener("change", () => chrome.storage.local.set({ captureMic: $("captureMic").checked }));
  $("grantMic").addEventListener("click", async () => {
    try {
      const st = await navigator.mediaDevices.getUserMedia({ audio: true });
      st.getTracks().forEach((t) => t.stop());   // serve solo a concedere il permesso
    } catch (e) {
      console.warn("[MeetLocalAI] permesso microfono:", e?.name);
    }
    refreshMic();
  });
  refreshMic();

  $("version").textContent = chrome.runtime.getManifest().version;
  $("extId").textContent = chrome.runtime.id;
  $("port").value = await getPort();

  $("save").addEventListener("click", async () => {
    const port = Number($("port").value);
    if (!Number.isInteger(port) || port < 1024 || port > 65535) {
      show("Inserisci una porta tra 1024 e 65535.", false);
      return;
    }
    await chrome.storage.local.set({ backendPort: port });
    show(port === DEFAULT_PORT ? "Salvato." : `Salvato. Ricorda di impostare la stessa porta (${port}) in ~/MeetLocalAI/Config/config.json.`, true);
  });

  $("test").addEventListener("click", async () => {
    try {
      const h = await getHealth();
      show(`Backend attivo (versione ${h.version}).`, true);
    } catch (e) {
      show(e.userMessage, false);
    }
  });
}

init();
