// Radar .gov.co: carga los JSON de data/ y dibuja el radar, la tabla y las fichas.

// En Vercel los datos se copian junto a la web (data/); en local se sirve desde la raíz del repo (../data/).
const DATA = location.pathname.includes("/web/") ? "../data/" : "data/";
const SWEEP_SECONDS = 6;

const COMPONENTS = [
  ["accessibility", "Accesibilidad"],
  ["mobile", "Móvil"],
  ["performance", "Rendimiento"],
  ["best_practices", "Buenas prácticas"],
  ["seo", "SEO"],
  ["failed_resources", "Recursos fallidos"],
];

// Sectores del radar (tipo de entidad).
const SECTORS = [
  { key: "Ministerio", label: "Ministerios" },
  { key: "Entidad nacional", label: "Entidades" },
  { key: "Órgano de control", label: "Control" },
  { key: "Alcaldía", label: "Alcaldías" },
  { key: "Portales", label: "Presidencia y portales", short: "Portales", includes: ["Presidencia", "Portal del Estado"] },
];

// Estados de la identidad común: siempre forma + texto + color.
const LIGHT_LABEL = { verde: "bueno", amarillo: "regular", rojo: "malo", sin_dato: "sin dato" };
const STATUS_CLASS = { verde: "ja-status--good", amarillo: "ja-status--warn", rojo: "ja-status--bad" };
const IMPACT_LABEL = { critical: "crítico", serious: "grave", moderate: "moderado", minor: "menor" };

// Explicación en lenguaje claro de las reglas de axe más comunes.
const RULE_LABELS = {
  "image-alt": "Imágenes sin texto alternativo",
  "color-contrast": "Texto con contraste de color insuficiente",
  "link-name": "Enlaces sin un nombre que se pueda leer",
  "button-name": "Botones sin un nombre que se pueda leer",
  "list": "Listas con una estructura incorrecta",
  "listitem": "Elementos de lista fuera de una lista",
  "html-has-lang": "La página no declara su idioma",
  "html-lang-valid": "El idioma declarado no es válido",
  "meta-viewport": "Impide hacer zoom en el móvil",
  "select-name": "Listas desplegables sin etiqueta",
  "label": "Campos de formulario sin etiqueta",
  "aria-required-children": "Componentes ARIA sin los elementos hijos que exigen",
  "aria-required-parent": "Componentes ARIA fuera del contenedor que exigen",
  "aria-allowed-attr": "Atributos ARIA no permitidos en el elemento",
  "aria-valid-attr-value": "Atributos ARIA con valores no válidos",
  "aria-hidden-focus": "Elementos ocultos que aún reciben el foco",
  "nested-interactive": "Controles interactivos anidados",
  "frame-title": "Marcos (iframe) sin título",
  "document-title": "La página no tiene título",
  "duplicate-id-aria": "Identificadores repetidos usados por ARIA",
  "input-image-alt": "Botones de imagen sin texto alternativo",
  "role-img-alt": "Imágenes ARIA sin texto alternativo",
  "svg-img-alt": "Gráficos SVG sin texto alternativo",
  "link-in-text-block": "Enlaces que solo se distinguen por el color",
  "scrollable-region-focusable": "Zonas con desplazamiento a las que no llega el teclado",
  "td-headers-attr": "Celdas de tabla con encabezados mal referenciados",
  "th-has-data-cells": "Encabezados de tabla sin celdas asociadas",
  "video-caption": "Videos sin subtítulos",
  "area-alt": "Áreas de imagen sin texto alternativo",
  "object-alt": "Objetos incrustados sin texto alternativo",
  "aria-input-field-name": "Campos ARIA sin nombre",
  "aria-toggle-field-name": "Interruptores ARIA sin nombre",
  "aria-command-name": "Comandos ARIA sin nombre",
  "aria-progressbar-name": "Barras de progreso sin nombre",
  "aria-tooltip-name": "Tooltips sin nombre",
  "aria-dialog-name": "Diálogos sin nombre",
  "autocomplete-valid": "Autocompletado de formularios mal declarado",
  "blink": "Contenido que parpadea",
  "marquee": "Texto que se desplaza solo",
  "definition-list": "Listas de definición mal construidas",
  "dlitem": "Elementos de definición fuera de su lista",
  "form-field-multiple-labels": "Campos con varias etiquetas",
  "bypass": "Sin forma de saltar al contenido principal",
};

const state = { summary: null, history: null, filter: "todos", details: new Map() };

const $ = (sel, root = document) => root.querySelector(sel);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function svg(tag, attrs = {}) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  return node;
}

async function getJSON(path) {
  const response = await fetch(DATA + path, { cache: "no-cache" });
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

function formatDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d, 12)).toLocaleDateString("es-CO", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
}

function sectorOf(category) {
  return SECTORS.findIndex((s) => s.key === category || (s.includes || []).includes(category));
}

function levelClass(value) {
  if (value === null || value === undefined) return "sin_dato";
  if (value >= 80) return "verde";
  if (value >= 50) return "amarillo";
  return "rojo";
}

function median(values) {
  const sorted = values.filter((v) => typeof v === "number").sort((a, b) => a - b);
  if (!sorted.length) return null;
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

// ---------- Portada ----------

function renderHeader(summary) {
  $("#scan-date").textContent = `Última medición: ${formatDate(summary.date)}`;
  $("#hero-count").textContent = summary.sites_audited;
  $("#kpi-avg").textContent = summary.average_overall ?? "–";
  $("#kpi-green").textContent = `${summary.lights.verde}/${summary.sites_audited}`;
  const rules = median(summary.sites.map((s) => s.wcag_rules));
  $("#kpi-rules").textContent = rules ?? "–";
  const from = summary.measurement?.from;
  $("#measured-from").textContent =
    `Medición del ${formatDate(summary.date)} desde: ${from || "sin dato"}. ` +
    `Lighthouse ${summary.measurement?.lighthouse_versions?.join(", ") || ""}, ${summary.measurement?.lighthouse_runs_per_view || 3} corridas por vista (mediana). ` +
    `Metodología v${summary.methodology_version}.`;
}

function renderWeights(summary) {
  const list = $("#weights");
  list.replaceChildren();
  for (const [key, label] of COMPONENTS) {
    const pct = Math.round((summary.weights[key] || 0) * 100);
    list.append(
      el("li", {},
        el("span", { text: label }),
        el("span", { class: "bar", "aria-hidden": "true" }, el("span", { style: `width:${pct * 2.5}%` })),
        el("span", { class: "pct", text: `${pct} %` }),
      ),
    );
  }
}

// ---------- Radar ----------

function renderRadar(summary) {
  const sectorsGroup = $("#sectors");
  const dotsGroup = $("#dots");
  sectorsGroup.replaceChildren();
  dotsGroup.replaceChildren();

  const span = 360 / SECTORS.length;
  SECTORS.forEach((sector, i) => {
    const start = (i * span * Math.PI) / 180;
    sectorsGroup.append(svg("line", { x1: 0, y1: 0, x2: 104 * Math.sin(start), y2: -104 * Math.cos(start) }));
    const mid = ((i + 0.5) * span * Math.PI) / 180;
    const label = svg("text", { x: 116 * Math.sin(mid), y: -116 * Math.cos(mid) + 3 });
    label.textContent = sector.short || sector.label;
    sectorsGroup.append(label);
  });

  const bySector = SECTORS.map(() => []);
  for (const site of summary.sites) {
    if (site.overall === null || site.overall === undefined) continue;
    const index = sectorOf(site.category);
    if (index >= 0) bySector[index].push(site);
  }

  const tip = el("div", { class: "radar-tip", hidden: true, "aria-hidden": "true" });
  $("#radar").append(tip);

  bySector.forEach((sites, i) => {
    sites.sort((a, b) => a.id.localeCompare(b.id));
    sites.forEach((site, j) => {
      const angleDeg = i * span + ((j + 0.5) / sites.length) * span;
      const angle = (angleDeg * Math.PI) / 180;
      // Escala ampliada: 100 en el centro, 50 o menos en el borde (cada anillo son 10 puntos).
      const radius = Math.max(4, Math.min(102, ((100 - site.overall) * 104) / 50));
      const x = radius * Math.sin(angle);
      const y = -radius * Math.cos(angle);
      const label = `${site.name}: nota ${site.overall}, ${LIGHT_LABEL[site.light]}, puesto ${site.rank}`;
      const group = svg("g", {
        class: `blip ${site.light}`, tabindex: "0", role: "button", "aria-label": label, "data-id": site.id,
        style: `--delay:${((angleDeg / 360) * SWEEP_SECONDS).toFixed(2)}s`,
      });
      group.append(svg("circle", { class: "halo", cx: x, cy: y, r: 3.4 }));
      group.append(statusShape(site.light, x, y));
      const open = () => openSheet(site.id);
      group.addEventListener("click", open);
      group.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); open(); }
      });
      group.addEventListener("pointerenter", () => showTip(tip, group, site));
      group.addEventListener("focus", () => showTip(tip, group, site));
      group.addEventListener("pointerleave", () => { tip.hidden = true; });
      group.addEventListener("blur", () => { tip.hidden = true; });
      dotsGroup.append(group);
    });
  });
}

// Bueno = círculo, regular = triángulo, malo = cuadrado (regla de la identidad común).
function statusShape(light, x, y) {
  if (light === "amarillo") {
    const r = 4.4;
    return svg("path", { class: "core", d: `M${x} ${y - r} L${x + r * 0.93} ${y + r * 0.62} L${x - r * 0.93} ${y + r * 0.62} Z` });
  }
  if (light === "rojo") return svg("rect", { class: "core", x: x - 3.2, y: y - 3.2, width: 6.4, height: 6.4, rx: 0.6 });
  return svg("circle", { class: "core", cx: x, cy: y, r: 3.6 });
}

function statusBadge(site, text) {
  if (!STATUS_CLASS[site.light]) return el("span", { class: "na", text: text ?? "sin dato" });
  return el("span", { class: `ja-status ${STATUS_CLASS[site.light]}` }, text, el("span", { class: "sr-only", text: `, ${LIGHT_LABEL[site.light]}` }));
}

function showTip(tip, group, site) {
  const box = group.getBoundingClientRect();
  const parent = $("#radar").getBoundingClientRect();
  tip.replaceChildren(document.createTextNode(`${site.name} · `), el("b", { text: String(site.overall) }), ` (${LIGHT_LABEL[site.light]})`);
  tip.style.left = `${box.left - parent.left + box.width / 2}px`;
  tip.style.top = `${box.top - parent.top}px`;
  tip.hidden = false;
}

// ---------- Tabla ----------

function renderFilters(summary) {
  const box = $("#filters");
  box.replaceChildren();
  const present = new Set(summary.sites.map((s) => sectorOf(s.category)));
  const options = [{ key: "todos", label: "Todos" }, ...SECTORS.filter((_, i) => present.has(i))];
  for (const option of options) {
    box.append(
      el("button", {
        class: "chip", type: "button", "aria-pressed": String(state.filter === option.key), text: option.label,
        onclick: () => { state.filter = option.key; renderFilters(summary); renderTable(summary); dimRadar(); },
      }),
    );
  }
}

function matchesFilter(site) {
  if (state.filter === "todos") return true;
  return SECTORS[sectorOf(site.category)]?.key === state.filter;
}

function dimRadar() {
  for (const blip of document.querySelectorAll(".blip")) {
    const site = state.summary.sites.find((s) => s.id === blip.dataset.id);
    blip.classList.toggle("dim", !matchesFilter(site));
  }
}

function valueCell(value, extraClass = "") {
  if (value === null || value === undefined) return el("td", { class: `num ${extraClass}` }, el("span", { class: "na", text: "sin dato" }));
  const level = value < 50 ? "low" : value < 80 ? "mid" : "";
  return el("td", { class: `num ${extraClass}` }, el("span", { class: `cell-bar ${level}`, text: String(value) }));
}

function renderTable(summary) {
  const body = $("#ranking-body");
  body.replaceChildren();
  for (const site of summary.sites.filter(matchesFilter)) {
    const scores = site.scores || {};
    body.append(
      el("tr", {},
        el("td", { class: "rank", text: site.rank ?? "–" }),
        el("td", {},
          el("button", { class: "site-btn", type: "button", onclick: () => openSheet(site.id), text: site.name }),
          el("span", { class: "site-cat", text: site.category }),
        ),
        el("td", {}, statusBadge(site, site.overall === null || site.overall === undefined ? null : String(site.overall))),
        ...COMPONENTS.map(([key]) => valueCell(scores[key], "c-wide")),
        el("td", { class: "num c-mid", text: site.wcag_rules ?? "–", title: `${site.wcag_cases ?? 0} casos` }),
      ),
    );
  }
  const skipped = summary.sites.filter((s) => s.overall === null || s.overall === undefined);
  const note = $("#status-note");
  note.hidden = !skipped.length;
  note.textContent = skipped.length
    ? `Sin nota esta semana: ${skipped.map((s) => s.name).join(", ")} (no se pudo leer su robots.txt o el sitio no respondió).`
    : "";
}

// ---------- Ficha ----------

async function openSheet(id) {
  const site = state.summary.sites.find((s) => s.id === id);
  if (!site) return;
  const dialog = $("#sheet");
  $("#sheet-category").textContent = `${site.category} · puesto ${site.rank ?? "–"} de ${state.summary.sites_audited}`;
  $("#sheet-title").textContent = site.name;
  const link = $("#sheet-url");
  link.href = site.url;
  link.textContent = site.url.replace(/^https?:\/\//, "").replace(/\/$/, "");
  const body = $("#sheet-body");
  body.replaceChildren(el("p", { class: "note", text: "Cargando ficha…" }));
  if (!dialog.open) dialog.showModal();
  history.replaceState(null, "", `#${id}`);

  try {
    if (!state.details.has(id)) state.details.set(id, await getJSON(`${state.summary.date}/${site.detail}`));
    body.replaceChildren(...buildSheet(site, state.details.get(id)));
  } catch (error) {
    body.replaceChildren(el("p", { class: "note", text: "No se pudo cargar la ficha de este portal." }));
  }
}

function buildSheet(site, detail) {
  const base = `${DATA}${state.summary.date}/`;
  const nodes = [];

  nodes.push(
    el("div", { class: "sheet-score" },
      el("span", { class: "big-score", text: site.overall ?? "–" }),
      STATUS_CLASS[site.light]
        ? el("span", { class: `ja-status ${STATUS_CLASS[site.light]}`, text: `Nivel ${LIGHT_LABEL[site.light]}` })
        : el("span", { class: "pill", text: "Sin nota" }),
      site.status === "parcial" ? el("span", { class: "pill", text: "Medición parcial" }) : null,
    ),
  );

  const desktop = site.screenshots?.find((s) => s.includes("-desktop"));
  const mobile = site.screenshots?.find((s) => s.includes("-mobile"));
  if (desktop || mobile) {
    nodes.push(
      el("div", { class: "shots" },
        desktop ? el("figure", {}, el("img", { src: base + desktop, alt: `Página de inicio de ${site.name} en escritorio`, loading: "lazy", width: 1366, height: 768 }), el("figcaption", { text: "Escritorio" })) : null,
        mobile ? el("figure", {}, el("img", { src: base + mobile, alt: `Página de inicio de ${site.name} en móvil`, loading: "lazy", width: 390, height: 844 }), el("figcaption", { text: "Móvil (390 px)" })) : null,
      ),
    );
  }

  const scores = site.scores || {};
  nodes.push(
    el("section", {},
      el("h3", { text: "Componentes de la nota" }),
      el("ul", { class: "components" },
        COMPONENTS.map(([key, label]) => {
          const value = scores[key];
          return el("li", {},
            el("span", { text: label }),
            el("span", { class: "meter", "aria-hidden": "true" },
              el("span", { class: levelClass(value), style: `width:${value ?? 0}%` })),
            el("span", { class: "val", text: value ?? "–" }),
          );
        }),
      ),
    ),
  );

  const wcag = detail.wcag || { rules: [], rules_count: 0, cases: 0 };
  nodes.push(
    el("section", {},
      el("h3", { text: `Accesibilidad: ${wcag.rules_count} reglas WCAG incumplidas, ${wcag.cases} casos` }),
      wcag.rules.length
        ? el("ul", { class: "rules" },
            wcag.rules.slice(0, 8).map((rule) =>
              el("li", {},
                el("span", { class: `impact ${rule.impact}`, text: IMPACT_LABEL[rule.impact] || rule.impact }),
                el("strong", { text: RULE_LABELS[rule.rule] || rule.rule }),
                ` · ${rule.cases} ${rule.cases === 1 ? "caso" : "casos"}`,
                el("span", { class: "crit", text: rule.description }),
              ),
            ),
            wcag.rules.length > 8 ? el("li", { text: `Y ${wcag.rules.length - 8} reglas más en el JSON del sitio.` }) : null,
          )
        : el("p", { class: "note", text: "axe-core no encontró incumplimientos WCAG 2.1 A/AA en las páginas revisadas." }),
    ),
  );

  const lhMobile = detail.lighthouse?.mobile;
  const lhDesktop = detail.lighthouse?.desktop;
  const seconds = (ms) => (ms === undefined || ms === null ? "–" : `${(ms / 1000).toFixed(1).replace(".", ",")} s`);
  nodes.push(
    el("section", {},
      el("h3", { text: "Datos de la medición" }),
      el("dl", { class: "facts" },
        el("div", {}, el("dt", { text: "Carga del contenido principal (LCP), móvil" }), el("dd", { text: seconds(lhMobile?.metrics?.lcp_ms) })),
        el("div", {}, el("dt", { text: "LCP en escritorio" }), el("dd", { text: seconds(lhDesktop?.metrics?.lcp_ms) })),
        el("div", {}, el("dt", { text: "Desborde horizontal en móvil" }), el("dd", { text: detail.mobile?.overflow_px === undefined || detail.mobile?.overflow_px === null ? "–" : `${detail.mobile.overflow_px} px` })),
        el("div", {}, el("dt", { text: "Recursos propios fallidos" }), el("dd", { text: detail.failed_resources_first_party ?? "–" })),
      ),
      el("p", { class: "fineprint", text: `Páginas revisadas: ${new Set((detail.pages || []).map((p) => p.url)).size}. Fallos en recursos de terceros (no restan): ${detail.third_party_failures ?? 0}.` }),
      detail.errors?.length ? el("p", { class: "fineprint", text: `Notas: ${detail.errors.join(" · ")}` }) : null,
    ),
  );

  nodes.push(buildEvolution(site));
  return nodes;
}

function buildEvolution(site) {
  const series = (state.history?.sites?.[site.id]?.series || []).filter((p) => p.overall !== null);
  const section = el("section", {}, el("h3", { text: "Evolución semanal" }));
  if (series.length < 2) {
    section.append(el("p", { class: "note", text: "Primera medición. La evolución aparece desde la segunda semana." }));
    return section;
  }
  const w = 300, h = 48, pad = 4;
  const xs = (i) => pad + (i * (w - pad * 2)) / (series.length - 1);
  const ys = (v) => h - pad - (v / 100) * (h - pad * 2);
  const chart = svg("svg", { class: "spark", viewBox: `0 0 ${w} ${h}`, role: "img", "aria-label": `Notas: ${series.map((p) => `${p.date} ${p.overall}`).join(", ")}` });
  chart.append(svg("polyline", { points: series.map((p, i) => `${xs(i)},${ys(p.overall)}`).join(" ") }));
  series.forEach((p, i) => chart.append(svg("circle", { cx: xs(i), cy: ys(p.overall), r: 3 })));
  section.append(chart);
  return section;
}

function setupDialog() {
  const dialog = $("#sheet");
  $("#sheet-close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
  dialog.addEventListener("close", () => history.replaceState(null, "", location.pathname + location.search));
}

// ---------- Inicio ----------

async function main() {
  setupDialog();
  try {
    const latest = await getJSON("latest.json");
    const [summary, historyData] = await Promise.all([getJSON(latest.summary), getJSON("history.json").catch(() => null)]);
    state.summary = summary;
    state.history = historyData;
    renderHeader(summary);
    renderWeights(summary);
    renderRadar(summary);
    renderFilters(summary);
    renderTable(summary);
    const hash = decodeURIComponent(location.hash.slice(1));
    if (hash && summary.sites.some((s) => s.id === hash)) openSheet(hash);
  } catch (error) {
    $("#scan-date").textContent = "No se pudieron cargar los resultados.";
    console.error(error);
  }
}

main();
