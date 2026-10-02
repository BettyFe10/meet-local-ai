import { audioUrl, deleteMeeting, exportMeeting, getAudioToken, getMeeting, getSummary, getTranscript, openFolder, renameMeeting, reprocessMeeting } from "./lib/api.js";
import { downloadText, el, fmtBytes, fmtDate, fmtDuration, fmtTime, renderMarkdownLite, statusLabel } from "./lib/ui.js";

const SECTIONS = ["TL;DR", "DECISIONI", "ACTION ITEMS", "PROBLEMI / CRITICITÀ", "INFORMAZIONI IMPORTANTI", "DOMANDE APERTE", "PROSSIMI PASSI"];
const BUSY = ["stopped", "converting", "transcribing", "summarizing"];
const $ = (id) => document.getElementById(id);
const id = new URLSearchParams(location.search).get("id");
let summaryShownFor = null;

const banner = (text) => $("banner").replaceChildren(text ? el("div", { class: "banner off" }, text) : "");

function renderSections(sections, placeholder) {
  $("sections").replaceChildren(
    ...SECTIONS.map((s) => el("div", { class: "card section" }, el("h3", {}, s),
      sections?.[s] ? el("div", {}, renderMarkdownLite(sections[s])) : el("div", { class: "muted" }, placeholder))));
}

async function load() {
  if (!id) { renderSections(null, "—"); banner("Nessuna riunione selezionata."); return; }
  let m;
  try {
    m = await getMeeting(id);
  } catch (e) {
    banner(e.userMessage);
    return;
  }
  document.title = `Meet Local AI — ${m.title}`;
  $("title").textContent = m.title;
  $("date").textContent = `${fmtDate(m.created_at)} ${fmtTime(m.created_at)}`;
  $("duration").textContent = fmtDuration(m.duration_seconds);
  $("status").textContent = statusLabel(m.status);
  $("info").textContent = m.performance?.disk_bytes ? `Spazio occupato: ${fmtBytes(m.performance.disk_bytes)}` : "";
  $("warnings").replaceChildren(...(m.warnings || []).map((w) => el("div", {}, `⚠ ${w}`)));
  banner(m.status === "error" && m.error ? (m.error.user_message || "Elaborazione non riuscita.") : "");

  const hasTranscript = !!m.files?.transcript_txt;
  const hasSummary = !!m.files?.summary_md;
  $("btnTranscript").disabled = !hasTranscript;
  $("btnAudio").disabled = !m.files?.audio;
  $("btnFolder").disabled = false;
  $("btnReprocess").hidden = m.status !== "error";
  $("btnSummary").hidden = !(hasTranscript && !BUSY.includes(m.status));
  $("btnSummary").textContent = hasSummary ? "Rigenera sintesi" : "Genera sintesi";

  if (hasSummary && summaryShownFor !== m.updated_at) {
    try {
      const s = await getSummary(id);
      renderSections(s.sections, "Non chiaramente determinabile dalla trascrizione.");
      $("summaryNote").textContent = `Sintesi generata in locale${s.model ? ` con ${s.model}` : ""} dalla trascrizione automatica: verifica i punti importanti.`;
      summaryShownFor = m.updated_at;
    } catch (e) {
      banner(e.userMessage);
    }
  } else if (!hasSummary) {
    renderSections(null, m.status === "summarizing" ? "Sintesi in corso…" : "Sintesi non ancora disponibile.");
    $("summaryNote").textContent = "";
  }
  if (BUSY.includes(m.status)) setTimeout(load, 4000);
}

$("btnTranscript").addEventListener("click", async () => {
  const box = $("transcriptBox");
  if (!box.hidden) { box.hidden = true; return; }
  try {
    $("transcript").textContent = await getTranscript(id, "txt");
    box.hidden = false;
  } catch (e) {
    banner(e.userMessage);
  }
});

async function requeue(steps) {
  try {
    await reprocessMeeting(id, steps);
    summaryShownFor = null;
    setTimeout(load, 800);
  } catch (e) {
    banner(e.userMessage);
  }
}
$("btnAudio").addEventListener("click", async () => {
  const box = $("audioBox");
  if (!box.hidden) { $("player").pause(); box.hidden = true; return; }
  try {
    if (!$("player").src) {
      const { token } = await getAudioToken(id);      // token temporaneo: il tag <audio> non può inviare header
      $("player").src = await audioUrl(id, token);
    }
    box.hidden = false;
  } catch (e) {
    banner(e.userMessage);
  }
});

$("btnFolder").addEventListener("click", async () => {
  try { await openFolder(id); } catch (e) { banner(e.userMessage); }
});

function toggleRename(on) {
  $("renameBox").hidden = !on;
  $("btnRename").hidden = on;
  $("title").hidden = on;
  if (on) { $("renameInput").value = $("title").textContent; $("renameInput").focus(); $("renameInput").select(); }
}
$("btnRename").addEventListener("click", () => toggleRename(true));
$("renameCancel").addEventListener("click", () => toggleRename(false));
async function saveRename() {
  const t = $("renameInput").value.trim();
  if (!t) return;
  try {
    const m = await renameMeeting(id, t);
    $("title").textContent = m.title;
    document.title = `Meet Local AI — ${m.title}`;
    toggleRename(false);
  } catch (e) {
    banner(e.userMessage);
  }
}
$("renameSave").addEventListener("click", saveRename);
$("renameInput").addEventListener("keydown", (ev) => { if (ev.key === "Enter") saveRename(); if (ev.key === "Escape") toggleRename(false); });

async function doExport(fmt) {
  try {
    const text = await exportMeeting(id, fmt);
    downloadText(`${id}.${fmt}`, text, fmt === "md" ? "text/markdown" : "text/plain");
    $("info").textContent = `Esportato. Una copia è anche in MeetLocalAI/Exports/${id}.${fmt}`;
  } catch (e) {
    banner(e.userMessage);
  }
}
$("btnExportMd").addEventListener("click", () => doExport("md"));
$("btnExportTxt").addEventListener("click", () => doExport("txt"));
$("btnPrint").addEventListener("click", async () => {
  // per la stampa/PDF mostra anche la trascrizione
  try { $("transcript").textContent = await getTranscript(id, "txt"); $("transcriptBox").hidden = false; } catch { /* senza trascrizione */ }
  window.print();
});

$("btnDelete").addEventListener("click", () => { $("confirmDelete").hidden = false; });
$("btnDeleteNo").addEventListener("click", () => { $("confirmDelete").hidden = true; });
$("btnDeleteYes").addEventListener("click", async () => {
  $("btnDeleteYes").disabled = true;
  try {
    $("player").pause();
    $("player").removeAttribute("src");
    await deleteMeeting(id);
    location.href = "dashboard.html";
  } catch (e) {
    $("confirmDelete").hidden = true;
    $("btnDeleteYes").disabled = false;
    banner(e.userMessage);
  }
});

$("btnSummary").addEventListener("click", () => requeue(["summarize"]));
$("btnReprocess").addEventListener("click", () => requeue());

load();
