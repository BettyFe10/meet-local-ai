import { getStatus, listMeetings, openDataRoot } from "./lib/api.js";
import { el, filterMeetings, fmtDate, fmtDuration, fmtTime, statusLabel, STEP_LABELS } from "./lib/ui.js";

const $ = (id) => document.getElementById(id);
let all = [];

function emptyRow(text) {
  return el("tr", {}, el("td", { colspan: "5", class: "empty" }, text));
}

function statusCell(m) {
  const cell = el("td", {}, statusLabel(m.status));
  if (m.error_message) cell.append(el("div", { class: "small muted" }, m.error_message));
  else if (m.warnings) cell.append(el("div", { class: "small muted" }, `⚠ ${m.warnings} avvis${m.warnings === 1 ? "o" : "i"}`));
  return cell;
}

function render() {
  const list = filterMeetings(all, $("search").value, $("statusFilter").value);
  $("count").textContent = all.length ? `(${list.length} di ${all.length})` : "";
  if (!all.length) return $("rows").replaceChildren(emptyRow("Nessuna riunione registrata."));
  if (!list.length) return $("rows").replaceChildren(emptyRow("Nessuna riunione corrisponde alla ricerca."));
  $("rows").replaceChildren(...list.map((m) =>
    el("tr", { onclick: () => (location.href = `meeting.html?id=${encodeURIComponent(m.id)}`) },
      el("td", {}, fmtDate(m.created_at)),
      el("td", {}, fmtTime(m.created_at)),
      el("td", {}, m.title),
      el("td", {}, fmtDuration(m.duration_seconds)),
      statusCell(m))));
}

async function load() {
  try {
    const [{ meetings }, st] = await Promise.all([listMeetings(), getStatus()]);
    all = meetings;
    $("banner").replaceChildren();
    const p = st.processing;
    $("processing").hidden = !p && !st.queue_length;
    if (p || st.queue_length) {
      const title = all.find((m) => m.id === p?.id)?.title || "";
      $("processing").textContent = p
        ? `Elaborazione in corso: ${title} — ${STEP_LABELS[p.step] || p.step}` + (st.queue_length ? ` (altre ${st.queue_length} in coda)` : "")
        : `${st.queue_length} riunioni in coda`;
    }
    render();
    return !!(p || st.queue_length || st.recording);
  } catch (e) {
    $("banner").replaceChildren(el("div", { class: "banner off" }, e.userMessage, " ",
      el("span", { class: "muted" }, "Avvia il backend: "), el("code", {}, "~/MeetLocalAI/app/start_backend.sh")));
    $("processing").hidden = true;
    $("rows").replaceChildren(emptyRow("Elenco non disponibile."));
    return false;
  }
}

// aggiornamento: rapido mentre c'è lavoro in corso, lento altrimenti; fermo se la pagina non è visibile
let timer = null;
async function tick() {
  clearTimeout(timer);
  if (document.visibilityState !== "visible") return;
  const busy = await load();
  timer = setTimeout(tick, busy ? 4000 : 20000);
}
document.addEventListener("visibilitychange", tick);
$("search").addEventListener("input", render);
$("statusFilter").addEventListener("change", render);
$("openRoot").addEventListener("click", async () => {
  try { await openDataRoot(); } catch (e) { $("banner").replaceChildren(el("div", { class: "banner off" }, e.userMessage)); }
});
tick();
