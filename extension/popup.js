import { getHealth, MSG_OFFLINE } from "./lib/api.js";
import { el, meetCodeFromUrl, openExtensionPage } from "./lib/ui.js";

const $ = (id) => document.getElementById(id);

function setStatus(text, cls) {
  $("status").textContent = text;
  $("status").className = `status ${cls}`;
}

async function activeMeetCode() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return meetCodeFromUrl(tab?.url);
}

function renderComponents(h) {
  const items = [
    ["FFmpeg", h.ffmpeg?.available],
    ["Whisper locale", h.whisper?.available],
    ["Modello locale", h.llm?.available],
  ];
  $("components").replaceChildren(
    ...items.map(([name, ok]) => el("li", {}, el("span", {}, name), el("span", {}, ok ? "✓" : "non disponibile")))
  );
}

async function init() {
  $("dashboard").addEventListener("click", () => openExtensionPage("dashboard.html"));
  const meetCode = await activeMeetCode();
  try {
    const h = await getHealth();
    setStatus("● PRONTO", "ok");
    renderComponents(h);
    $("hint").textContent = meetCode
      ? `Riunione rilevata: ${meetCode}`
      : "Apri una riunione su meet.google.com per poter registrare.";
  } catch (e) {
    setStatus(`● ${e.userMessage || MSG_OFFLINE}`, "off");
    $("hint").replaceChildren("Avvia il backend dal Terminale: ", el("code", {}, "~/MeetLocalAI/app/start_backend.sh"));
  }
  // La registrazione viene abilitata nelle Fasi 5-6.
  $("startNote").textContent = "La registrazione sarà disponibile in una prossima versione.";
}

init();
