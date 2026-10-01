import { listMeetings } from "./lib/api.js";
import { el, fmtDate, fmtDuration, fmtTime, statusLabel } from "./lib/ui.js";

const rows = document.getElementById("rows");
const banner = document.getElementById("banner");

function emptyRow(text) {
  return el("tr", {}, el("td", { colspan: "5", class: "empty" }, text));
}

async function load() {
  try {
    const { meetings } = await listMeetings();
    banner.replaceChildren();
    if (!meetings.length) {
      rows.replaceChildren(emptyRow("Nessuna riunione registrata."));
      return;
    }
    rows.replaceChildren(
      ...meetings.map((m) =>
        el("tr", { onclick: () => (location.href = `meeting.html?id=${encodeURIComponent(m.id)}`) },
          el("td", {}, fmtDate(m.created_at)),
          el("td", {}, fmtTime(m.created_at)),
          el("td", {}, m.title),
          el("td", {}, fmtDuration(m.duration_seconds)),
          el("td", {}, statusLabel(m.status)))
      )
    );
  } catch (e) {
    banner.replaceChildren(el("div", { class: "banner off" }, e.userMessage, " ",
      el("span", { class: "muted" }, "Avvia il backend: "), el("code", {}, "~/MeetLocalAI/app/start_backend.sh")));
    rows.replaceChildren(emptyRow("Elenco non disponibile."));
  }
}

load();
// aggiornamento periodico leggero mentre la pagina è visibile
setInterval(() => { if (document.visibilityState === "visible") load(); }, 15000);
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") load(); });
