import { getMeeting, getTranscript, reprocessMeeting } from "./lib/api.js";
import { el, fmtDate, fmtDuration, fmtTime, statusLabel } from "./lib/ui.js";

const SECTIONS = ["TL;DR", "DECISIONI", "ACTION ITEMS", "PROBLEMI / CRITICITÀ", "DOMANDE APERTE", "PROSSIMI PASSI"];
const $ = (id) => document.getElementById(id);

function renderSections(text) {
  $("sections").replaceChildren(
    ...SECTIONS.map((s) => el("div", { class: "card section" }, el("h3", {}, s), el("div", { class: "muted" }, text)))
  );
}

async function load() {
  const id = new URLSearchParams(location.search).get("id");
  renderSections("Sintesi non ancora disponibile.");
  if (!id) {
    $("banner").replaceChildren(el("div", { class: "banner off" }, "Nessuna riunione selezionata."));
    return;
  }
  try {
    const m = await getMeeting(id);
    document.title = `Meet Local AI — ${m.title}`;
    $("title").textContent = m.title;
    $("date").textContent = `${fmtDate(m.created_at)} ${fmtTime(m.created_at)}`;
    $("duration").textContent = fmtDuration(m.duration_seconds);
    $("status").textContent = statusLabel(m.status);
    if (m.status === "error" && m.error) {
      $("banner").replaceChildren(el("div", { class: "banner off" }, m.error.user_message || "Elaborazione non riuscita."));
      $("btnReprocess").hidden = false;
    }
    if (m.files?.transcript_txt) {
      $("btnTranscript").disabled = false;
      $("btnTranscript").onclick = async () => {
        const box = $("transcriptBox");
        if (!box.hidden) { box.hidden = true; return; }
        try {
          $("transcript").textContent = await getTranscript(id, "txt");
          box.hidden = false;
        } catch (e) {
          $("banner").replaceChildren(el("div", { class: "banner off" }, e.userMessage));
        }
      };
    }
    $("btnReprocess").onclick = async () => {
      $("btnReprocess").disabled = true;
      try { await reprocessMeeting(id); $("status").textContent = "In coda"; } catch (e) {
        $("banner").replaceChildren(el("div", { class: "banner off" }, e.userMessage));
      }
    };
    if (["stopped", "converting", "transcribing", "summarizing"].includes(m.status)) setTimeout(load, 5000);
  } catch (e) {
    $("banner").replaceChildren(el("div", { class: "banner off" }, e.userMessage));
  }
}

load();
