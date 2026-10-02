import { DEFAULT_PORT, getHealth, getPort, getSettings, setSettings } from "./lib/api.js";
import { el } from "./lib/ui.js";
import { micProblem } from "./lib/session.js";

const $ = (id) => document.getElementById(id);

function show(text, ok) {
  $("result").textContent = text;
  $("result").className = `small status ${ok ? "ok" : "off"}`;
}

async function refreshMic(problem) {
  let state = "prompt";
  try { state = (await navigator.permissions.query({ name: "microphone" })).state; } catch { /* non supportato */ }
  const el = $("micStatus");
  el.textContent = state === "granted" ? "Microfono abilitato." : state === "denied"
    ? "Microfono bloccato: riabilitalo dalle impostazioni del sito dell'estensione in Chrome." : "Microfono non ancora abilitato.";
  el.className = `small status ${state === "granted" ? "ok" : "off"}`;
  if (problem) {
    el.textContent = `Microfono non disponibile: ${micProblem(problem)}`;
    el.className = "small status off";
  }
}

function renderLlm(s) {
  const sel = $("llmModel");
  sel.replaceChildren(...s.llm.choices.map((c) => el("option", { value: c.value }, `${c.label} — ${c.model}`)));
  sel.value = s.llm.setting;
  sel.disabled = false;
  const cur = s.llm.choices.find((c) => c.value === s.llm.setting);
  $("llmNote").textContent = cur?.note ? `⚠ ${cur.note}` : "";
  const st = $("llmStatus");
  if (cur?.downloaded) {
    st.textContent = "Modello presente su questo Mac.";
    st.className = "small status ok";
  } else {
    st.replaceChildren("Modello non ancora scaricato: finché manca, le riunioni vengono solo trascritte. Per scaricarlo apri il Terminale ed esegui: ",
      el("code", {}, cur?.install_command || ""));
    st.className = "small status off";
  }
}

function renderGlossary(s, saved) {
  const g = s.glossary || { terms: [], max_terms: 0, used_terms: 0 };
  $("glossary").value = g.terms.join("\n");
  $("glossary").disabled = false;
  $("saveGlossary").disabled = false;
  const st = $("glossaryStatus");
  let msg = saved ? "Salvato. " : "";
  msg += g.terms.length ? `${g.terms.length} termini.` : "Nessun termine.";
  if (g.used_terms < g.terms.length) msg += ` Attenzione: ne vengono usati solo i primi ${g.used_terms} (limite del riconoscimento): metti in alto i più importanti.`;
  st.textContent = msg;
  st.className = `small status ${g.used_terms < g.terms.length ? "wait" : "ok"}`;
}

async function initLlm() {
  try {
    const s = await getSettings();
    renderLlm(s);
    renderGlossary(s, false);
    $("saveGlossary").addEventListener("click", async () => {
      const terms = $("glossary").value.split("\n").map((t) => t.trim()).filter(Boolean);
      try {
        renderGlossary(await setSettings({ glossary: terms }), true);
      } catch (e) {
        $("glossaryStatus").textContent = e.userMessage;
        $("glossaryStatus").className = "small status off";
      }
    });
  } catch (e) {
    $("llmStatus").textContent = e.userMessage;
    $("llmStatus").className = "small status off";
    return;
  }
  $("llmModel").addEventListener("change", async () => {
    try {
      renderLlm(await setSettings({ llm_model: $("llmModel").value }));
    } catch (e) {
      $("llmStatus").textContent = e.userMessage;
      $("llmStatus").className = "small status off";
    }
  });
}

// ---- scelta e prova del microfono ----
async function loadMicDevices() {
  const sel = $("micDevice");
  let devices = [];
  try { devices = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "audioinput"); } catch { /* non disponibile */ }
  const named = devices.filter((d) => d.label && d.deviceId && d.deviceId !== "default" && d.deviceId !== "communications");
  const { micDeviceId } = await chrome.storage.local.get({ micDeviceId: "" });
  const opts = [el("option", { value: "" }, "Predefinito del Mac")];
  for (const d of named) opts.push(el("option", { value: d.deviceId }, d.label));
  if (micDeviceId && !named.some((d) => d.deviceId === micDeviceId)) {
    opts.push(el("option", { value: micDeviceId }, "Microfono scelto (non collegato ora)"));
  }
  sel.replaceChildren(...opts);
  sel.value = micDeviceId;
  // i nomi dei microfoni sono visibili solo dopo aver dato il permesso
  sel.disabled = named.length === 0;
  $("testMic").disabled = named.length === 0;
  if (named.length === 0) $("micTest").textContent = "Per scegliere il microfono premi prima \"Abilita microfono\".";
  else if ($("micTest").textContent.startsWith("Per scegliere")) $("micTest").textContent = "";
}

let micTestStop = null;
async function testMic() {
  if (micTestStop) return micTestStop();
  const id = $("micDevice").value;
  const out = $("micTest");
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: id ? { deviceId: { exact: id } } : true });
  } catch (e) {
    out.textContent = `Microfono non disponibile: ${micProblem(e?.name)}`;
    out.className = "small status off";
    return;
  }
  const ctx = new AudioContext();
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 2048;
  ctx.createMediaStreamSource(stream).connect(analyser);
  const buf = new Float32Array(analyser.fftSize);
  let max = 0;
  $("micLevel").hidden = false;
  $("testMic").textContent = "Ferma prova";
  out.textContent = "Parla per qualche secondo…";
  out.className = "small muted";
  const timer = setInterval(() => {
    analyser.getFloatTimeDomainData(buf);
    let peak = 0;
    for (let i = 0; i < buf.length; i++) { const v = Math.abs(buf[i]); if (v > peak) peak = v; }
    max = Math.max(max, peak);
    $("micLevel").value = Math.min(1, peak * 3);
  }, 100);
  const auto = setTimeout(() => micTestStop && micTestStop(), 8000);
  micTestStop = () => {
    clearInterval(timer);
    clearTimeout(auto);
    stream.getTracks().forEach((t) => t.stop());
    ctx.close().catch(() => {});
    $("micLevel").hidden = true;
    $("testMic").textContent = "Prova microfono";
    micTestStop = null;
    if (max > 0.02) {
      out.textContent = "Il microfono funziona: la voce arriva.";
      out.className = "small status ok";
    } else {
      out.textContent = "Nessun suono da questo microfono: scegline un altro dall'elenco (i microfoni \"virtuali\" di altre app spesso restano muti).";
      out.className = "small status off";
    }
  };
}

async function init() {
  $("micDevice").addEventListener("change", () => chrome.storage.local.set({ micDeviceId: $("micDevice").value }));
  $("testMic").addEventListener("click", testMic);
  navigator.mediaDevices.addEventListener?.("devicechange", loadMicDevices);
  loadMicDevices();
  initLlm();
  const { captureMic } = await chrome.storage.local.get({ captureMic: true });
  $("captureMic").checked = captureMic;
  $("captureMic").addEventListener("change", () => chrome.storage.local.set({ captureMic: $("captureMic").checked }));
  $("grantMic").addEventListener("click", async () => {
    try {
      const st = await navigator.mediaDevices.getUserMedia({ audio: true });
      st.getTracks().forEach((t) => t.stop());   // serve solo a concedere il permesso
      refreshMic();
      loadMicDevices();
    } catch (e) {
      console.warn("[MeetLocalAI] permesso microfono:", e?.name);
      refreshMic(e?.name || "errore");
    }
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
