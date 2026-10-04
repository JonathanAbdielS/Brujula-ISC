const $ = (s) => document.querySelector(s);
const log = $("#log"), input = $("#input"), sendBtn = $("#send"), calcBtn = $("#calc");

const historial = [];              // [{role, content}] que se manda al backend
const aprobadas = new Set();       // claves marcadas en la retícula
let materias = [];
let ocupado = false;

/* ---------- markdown mínimo y seguro ---------- */
function esc(t) { return t.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function inline(t) {
  return esc(t)
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, '$1<a href="$2" target="_blank" rel="noopener">enlace</a>')
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/(^|[^*])\*(?!\s)(.+?)\*/g, "$1<em>$2</em>").replace(/`([^`]+)`/g, "<code>$1</code>"); }
function md(texto) {
  const out = []; let lista = null;
  for (const linea of texto.split("\n")) {
    const ul = linea.match(/^\s*[-*•]\s+(.*)/), ol = linea.match(/^\s*\d+[.)]\s+(.*)/);
    if (ul || ol) {
      const tipo = ul ? "ul" : "ol";
      if (lista !== tipo) { if (lista) out.push(`</${lista}>`); out.push(`<${tipo}>`); lista = tipo; }
      out.push(`<li>${inline((ul || ol)[1])}</li>`);
      continue;
    }
    if (lista) { out.push(`</${lista}>`); lista = null; }
    if (linea.trim()) out.push(`<p>${inline(linea.replace(/^#+\s*/, ""))}</p>`);
  }
  if (lista) out.push(`</${lista}>`);
  return out.join("");
}

/* ---------- mensajes ---------- */
function agregar(rol, html, extraClase = "") {
  const div = document.createElement("div");
  div.className = `msg ${rol} ${extraClase}`.trim();
  div.innerHTML = `<div class="bubble">${html}</div>`;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
  return div;
}

const NOMBRES_TOOL = {
  consultar_reticula: "consultó la retícula",
  calcular_avance: "calculó tu avance",
  recomendar_especialidad: "comparó áreas de especialidad",
};

function trazaHerramientas(div, herramientas) {
  if (!herramientas?.length) return;
  const d = document.createElement("details");
  d.className = "tools";
  const etiquetas = herramientas.map((h) => `<span class="tool-name">${esc(h.nombre)}</span>`).join(" ");
  d.innerHTML = `<summary>El agente ${esc(herramientas.map((h) => NOMBRES_TOOL[h.nombre] || h.nombre).join(" y "))} ${etiquetas}</summary>` +
    herramientas.map((h) => `<pre>${esc(h.nombre)}(${esc(JSON.stringify(h.argumentos))})\n→ ${esc(JSON.stringify(h.resultado, null, 1))}</pre>`).join("");
  div.appendChild(d);
}

/* ---------- sincronizar la retícula con lo que hizo el agente ---------- */
function aplicarHerramientas(herramientas = []) {
  for (const h of herramientas) {
    const r = h.resultado || {};
    if (h.nombre === "calcular_avance" && Array.isArray(r.claves_aprobadas)) {
      aprobadas.clear(); r.claves_aprobadas.forEach((c) => aprobadas.add(c));
      $("#ss").checked = !!r.desglose?.servicio_social;
      $("#res").checked = !!r.desglose?.residencia;
      $("#ac").checked = !!r.desglose?.actividades_complementarias;
      pintarChips(); actualizarMedidor(r.creditos_aprobados);
    }
    if (h.nombre === "consultar_reticula" && r.semestre) resaltarSemestre(r.semestre);
    if (h.nombre === "consultar_reticula" && r.materia) resaltarSemestre(r.materia.semestre);
    if (h.nombre === "recomendar_especialidad" && r.perfiles_afines?.length) {
      const rel = new Set(r.perfiles_afines[0].materias_relacionadas);
      document.querySelectorAll(".chip[data-nombre]").forEach((c) => c.classList.toggle("related", rel.has(c.dataset.nombre)));
    }
  }
}

function resaltarSemestre(n) {
  const fila = document.querySelector(`.semester[data-sem="${n}"]`);
  if (!fila) return;
  fila.scrollIntoView({ behavior: "smooth", block: "center" });
  fila.classList.add("flash");
  setTimeout(() => fila.classList.remove("flash"), 2200);
}

/* ---------- envío ---------- */
async function enviar(texto, forzar = null) {
  texto = texto.trim();
  if (!texto || ocupado) return;
  ocupado = true; sendBtn.disabled = calcBtn.disabled = true;
  $("#suggestions").hidden = true;

  agregar("user", `<p>${esc(texto)}</p>`);
  historial.push({ role: "user", content: texto });
  const typing = agregar("bot", '<span class="dot"></span><span class="dot"></span><span class="dot"></span><span class="sr-only">Pensando</span>', "typing");

  try {
    const r = await fetch("/api/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: historial, forzar }),
    });
    const data = await r.json().catch(() => ({}));
    typing.remove();
    if (!r.ok) throw new Error(data.detail || `Error ${r.status}`);
    const div = agregar("bot", md(data.respuesta || "(sin respuesta)"));
    trazaHerramientas(div, data.herramientas);
    aplicarHerramientas(data.herramientas);
    historial.push({ role: "assistant", content: data.respuesta || "" });
  } catch (e) {
    typing.remove();
    agregar("bot", `<p>${esc(e.message === "Failed to fetch" ? "No hay conexión con el servidor." : e.message)}</p>`, "error");
    historial.pop(); // que el mensaje fallido no contamine el contexto
  } finally {
    ocupado = false; sendBtn.disabled = calcBtn.disabled = false; input.focus();
  }
}

/* ---------- retícula ---------- */
function creditosLocales() {
  let c = materias.filter((m) => aprobadas.has(m.clave)).reduce((a, m) => a + m.creditos, 0);
  if ($("#ss").checked) c += 10;
  if ($("#res").checked) c += 10;
  if ($("#ac").checked) c += 5;
  return c;
}
function actualizarMedidor(c = creditosLocales()) {
  const pct = Math.round((1000 * c) / 260) / 10;
  $("#gaugeFill").style.width = `${Math.min(100, pct)}%`;
  $("#gaugeCred").textContent = c;
  $("#gaugePct").textContent = `(${pct} %)`;
}
function pintarChips() {
  document.querySelectorAll(".chip[data-clave]").forEach((c) => c.setAttribute("aria-pressed", aprobadas.has(c.dataset.clave)));
}

async function cargarReticula() {
  const data = await (await fetch("/api/reticula")).json();
  materias = data.materias;
  const cont = $("#semesters");
  for (let s = 1; s <= 10; s++) {
    const fila = document.createElement("div");
    fila.className = "semester"; fila.dataset.sem = s;
    const chips = materias.filter((m) => m.semestre === s).map((m) =>
      `<button type="button" class="chip${m.especialidad ? " esp" : ""}" data-clave="${m.clave}" data-nombre="${esc(m.nombre)}" aria-pressed="false" title="${m.clave} · ${m.htp}">${esc(m.nombre)}<small>${m.creditos}</small></button>`);
    if (s === 10) (data.semestre_10 || []).forEach((t) => chips.push(`<span class="chip fixed">${esc(t)}</span>`));
    fila.innerHTML = `<div class="sem-num">${s}</div><div class="chips">${chips.join("")}</div>`;
    cont.appendChild(fila);
  }
  cont.addEventListener("click", (e) => {
    const chip = e.target.closest(".chip[data-clave]");
    if (!chip) return;
    const k = chip.dataset.clave;
    aprobadas.has(k) ? aprobadas.delete(k) : aprobadas.add(k);
    pintarChips(); actualizarMedidor();
  });
}

/* ---------- eventos ---------- */
sendBtn.addEventListener("click", () => { const t = input.value; input.value = ""; autoAlto(); enviar(t); });
input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendBtn.click(); } });
function autoAlto() { input.style.height = "auto"; input.style.height = `${input.scrollHeight}px`; }
input.addEventListener("input", autoAlto);

$("#suggestions").addEventListener("click", (e) => { if (e.target.matches("button")) enviar(e.target.textContent); });

["#ss", "#res", "#ac"].forEach((id) => $(id).addEventListener("input", () => actualizarMedidor()));

calcBtn.addEventListener("click", () => {
  const nombres = materias.filter((m) => aprobadas.has(m.clave)).map((m) => m.nombre);
  const args = {
    materias_aprobadas: nombres,
    servicio_social: $("#ss").checked, residencia: $("#res").checked,
    actividades_complementarias: $("#ac").checked,
  };
  const texto = nombres.length
    ? `Calcula mi avance. Marqué ${nombres.length} materias aprobadas en mi retícula.`
    : "Calcula mi avance (todavía no marco materias).";
  cerrarPanel();
  enviar(texto, { nombre: "calcular_avance", argumentos: args });
});

$("#clear").addEventListener("click", () => {
  aprobadas.clear(); ["#ss", "#res", "#ac"].forEach((id) => ($(id).checked = false));
  document.querySelectorAll(".chip.related").forEach((c) => c.classList.remove("related"));
  pintarChips(); actualizarMedidor();
});

const panel = $("#panel"), toggle = $("#togglePanel");
function cerrarPanel() { panel.classList.remove("open"); toggle.setAttribute("aria-expanded", "false"); }
toggle.addEventListener("click", () => {
  const abierto = panel.classList.toggle("open");
  toggle.setAttribute("aria-expanded", String(abierto));
});

cargarReticula().then(() => actualizarMedidor());
