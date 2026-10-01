import { DEFAULT_PORT, getHealth, getPort } from "./lib/api.js";

const $ = (id) => document.getElementById(id);

function show(text, ok) {
  $("result").textContent = text;
  $("result").className = `small status ${ok ? "ok" : "off"}`;
}

async function init() {
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
