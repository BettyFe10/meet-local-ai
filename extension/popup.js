import { getHealth, MSG_OFFLINE } from "./lib/api.js";
import { el, fmtClock, meetCodeFromUrl, openExtensionPage } from "./lib/ui.js";

const $ = (id) => document.getElementById(id);
let timerHandle = null;
let backendOk = false;
let meetTab = null;

const send = (type, payload) => chrome.runtime.sendMessage({ type, payload });

function setStatus(text, cls) {
  $("status").textContent = text;
  $("status").className = `status ${cls}`;
}

function renderComponents(h) {
  const items = [["FFmpeg", h.ffmpeg?.available], ["Whisper locale", h.whisper?.available], ["Modello locale", h.llm?.available]];
  $("components").replaceChildren(
    ...items.map(([name, ok]) => el("li", {}, el("span", {}, name), el("span", {}, ok ? "✓" : "non disponibile"))));
}

function render(s) {
  const recording = s.state === "recording" || s.state === "stopping";
  $("viewIdle").hidden = recording;
  $("viewRec").hidden = !recording;
  $("error").textContent = s.error || "";
  $("saved").hidden = !(s.state === "idle" && s.lastMeetingId && !s.error);

  clearInterval(timerHandle);
  if (recording) {
    $("recTitle").textContent = s.title || "";
    const tick = () => { $("timer").textContent = fmtClock((Date.now() - s.startedAt) / 1000); };
    tick();
    timerHandle = setInterval(tick, 1000);
    $("stop").disabled = s.state === "stopping";
    $("stop").textContent = s.state === "stopping" ? "Chiusura…" : "■ TERMINA";
  } else {
    const canStart = backendOk && meetTab && s.state === "idle";
    $("start").disabled = !canStart;
    $("start").textContent = s.state === "starting" ? "Avvio…" : "🔴 INIZIA RIUNIONE";
    $("titleRow").hidden = !canStart;
  }
}

async function refresh() {
  render(await send("getState"));
}

async function init() {
  $("dashboard").addEventListener("click", () => openExtensionPage("dashboard.html"));
  $("openSaved").addEventListener("click", async (ev) => {
    ev.preventDefault();
    const s = await send("getState");
    if (s.lastMeetingId) openExtensionPage(`meeting.html?id=${encodeURIComponent(s.lastMeetingId)}`);
  });
  $("start").addEventListener("click", async () => {
    $("start").disabled = true;
    const r = await send("start", { title: $("title").value.trim(), meetCode: meetTab.code, tabId: meetTab.id, tracks: ["tab"] });
    render(r.state);
  });
  $("stop").addEventListener("click", async () => {
    $("stop").disabled = true;
    const r = await send("stop");
    render(r.state);
  });
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === "session" && changes.mla) render(changes.mla.newValue);
  });

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const code = meetCodeFromUrl(tab?.url);
  meetTab = code ? { id: tab.id, code } : null;

  try {
    const h = await getHealth();
    backendOk = true;
    setStatus("● PRONTO", "ok");
    renderComponents(h);
    $("hint").textContent = meetTab
      ? `Riunione rilevata: ${meetTab.code}`
      : "Apri una riunione su meet.google.com per poter registrare.";
  } catch (e) {
    setStatus(`● ${e.userMessage || MSG_OFFLINE}`, "off");
    $("hint").replaceChildren("Avvia il backend dal Terminale: ", el("code", {}, "~/MeetLocalAI/app/start_backend.sh"));
  }
  await refresh();
}

init();
