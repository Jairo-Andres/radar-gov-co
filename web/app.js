// Radar .gov.co: carga los JSON de data/ y dibuja el radar, los hallazgos, la tabla y las fichas (ES/EN).
import {
  TEXT, STATUS_LABEL, IMPACT_LABEL, COMPONENT_LABEL, CATEGORY_LABEL, SECTOR_LABEL, RULE_LABEL, translateNote,
} from "./i18n.js";

// En Vercel los datos se copian junto a la web (data/); en local se sirve desde la raíz del repo (../data/).
const DATA = location.pathname.includes("/web/") ? "../data/" : "data/";
const SWEEP_SECONDS = 6;
const COMPONENT_KEYS = ["accessibility", "mobile", "performance", "best_practices", "seo", "failed_resources"];
const STATUS_CLASS = { verde: "ja-status--good", amarillo: "ja-status--warn", rojo: "ja-status--bad" };

// Sectores del radar (tipo de entidad).
const SECTORS = [
  { key: "Ministerio" },
  { key: "Entidad nacional" },
  { key: "Órgano de control" },
  { key: "Alcaldía" },
  { key: "Portales", includes: ["Presidencia", "Portal del Estado"] },
];

const state = { summary: null, history: null, filter: "todos", details: new Map(), lang: "es", openId: null };

// ---------- Utilidades ----------

const $ = (sel, root = document) => root.querySelector(sel);

function t(key, vars = {}) {
  const template = TEXT[state.lang][key] ?? TEXT.es[key] ?? key;
  return template.replace(/\{(\w+)\}/g, (_, name) => (vars[name] ?? `{${name}}`));
}

const statusLabel = (light) => STATUS_LABEL[state.lang][light] || light;
const categoryLabel = (category) => CATEGORY_LABEL[state.lang][category] || category;
const ruleLabel = (rule) => RULE_LABEL[state.lang][rule] || RULE_LABEL.es[rule] || rule;
const numberFmt = (value, digits = 0) =>
  value === null || value === undefined ? "–" : Number(value).toLocaleString(state.lang === "en" ? "en-US" : "es-CO", { maximumFractionDigits: digits });

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
  return new Date(Date.UTC(y, m - 1, d, 12)).toLocaleDateString(state.lang === "en" ? "en-US" : "es-CO", {
    day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
  });
}

function sectorOf(category) {
  return SECTORS.findIndex((s) => s.key === category || (s.includes || []).includes(category));
}

function sectorLabel(index, short = false) {
  const key = SECTORS[index].key;
  return SECTOR_LABEL[state.lang][short && key === "Portales" ? "PortalesShort" : key];
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

function describeRule(rule) {
  const criteria = rule.criteria || [];
  if (!criteria.length) return t("criterion0", { rule: rule.rule });
  return t(criteria.length === 1 ? "criterion1" : "criterionN", { c: criteria.join(", "), rule: rule.rule });
}

// ---------- Idioma ----------

function initialLang() {
  const param = new URLSearchParams(location.search).get("lang");
  if (param === "es" || param === "en") return param;
  try {
    const saved = localStorage.getItem("radar-lang");
    if (saved === "es" || saved === "en") return saved;
  } catch { /* almacenamiento no disponible */ }
  return (navigator.language || "es").toLowerCase().startsWith("en") ? "en" : "es";
}

function applyStaticText() {
  document.documentElement.lang = state.lang;
  document.title = t("pageTitle");
  for (const node of document.querySelectorAll("[data-i18n]")) node.textContent = t(node.dataset.i18n);
  for (const node of document.querySelectorAll("[data-i18n-aria]")) node.setAttribute("aria-label", t(node.dataset.i18nAria));
  const toggle = $("#lang-toggle");
  toggle.textContent = t("langButton");
  toggle.setAttribute("aria-label", t("langLabel"));
  toggle.setAttribute("lang", state.lang === "es" ? "en" : "es");
  renderHero(state.summary?.sites_audited ?? 30);
}

function setLang(lang) {
  state.lang = lang;
  try { localStorage.setItem("radar-lang", lang); } catch { /* sin almacenamiento */ }
  const url = new URL(location.href);
  if (lang === "en") url.searchParams.set("lang", "en"); else url.searchParams.delete("lang");
  history.replaceState(null, "", url);
  applyStaticText();
  if (state.summary) renderAll();
  if (state.openId && $("#sheet").open) openSheet(state.openId);
}

// ---------- Portada ----------

function renderHero(count) {
  $("#hero-title").replaceChildren(t("heroBefore"), el("span", { class: "accent", text: String(count) }), t("heroAfter"));
}

function renderHeader(summary) {
  $("#scan-date").textContent = t("lastScan", { date: formatDate(summary.date) });
  renderHero(summary.sites_audited);
  $("#kpi-avg").textContent = numberFmt(summary.average_overall);
  $("#kpi-green").textContent = `${summary.lights.verde}/${summary.sites_audited}`;
  $("#kpi-rules").textContent = numberFmt(median(summary.sites.map((s) => s.wcag_rules)), 1);
  const m = summary.measurement || {};
  $("#measured-from").textContent = t("measuredFrom", {
    date: formatDate(summary.date),
    from: m.from || t("noData"),
    lh: (m.lighthouse_versions || []).join(", "),
    runs: m.lighthouse_runs_per_view || 3,
    v: summary.methodology_version,
  });
}

function renderWeights(summary) {
  $("#weights").replaceChildren(
    ...COMPONENT_KEYS.map((key) => {
      const pct = Math.round((summary.weights[key] || 0) * 100);
      return el("li", {},
        el("span", { text: COMPONENT_LABEL[state.lang][key] }),
        el("span", { class: "bar", "aria-hidden": "true" }, el("span", { style: `width:${pct * 2.5}%` })),
        el("span", { class: "pct", text: `${pct} %` }),
      );
    }),
  );
}

// ---------- Hallazgos ----------

function renderFindings(summary) {
  const f = summary.findings;
  const section = $("#findings");
  section.hidden = !f || !f.sites_measured;
  if (section.hidden) return;
  const n = f.sites_measured;
  $("#findings-title").textContent = f.sites_with_any_wcag_rule === n
    ? t("findingsTitleAll", { n })
    : t("findingsTitleSome", { k: f.sites_with_any_wcag_rule, n });
  $("#findings-lead").textContent = t("findingsLead");

  const rule = (id) => f.top_rules.find((r) => r.rule === id);
  const cards = [
    [f.sites_with_critical_rule, "fCritical"],
    [rule("link-name")?.sites, "fTopRule"],
    [rule("color-contrast")?.sites, "fContrast"],
    [f.sites_with_mobile_overflow, "fOverflow"],
  ].filter(([value]) => typeof value === "number");

  $("#findings-grid").replaceChildren(
    ...cards.map(([value, key]) =>
      el("article", { class: "finding ja-card" },
        el("p", { class: "finding-num" }, el("span", { text: String(value) }), el("span", { class: "finding-of", text: ` ${t("ofSites", { n })}` })),
        el("p", { class: "finding-text", text: t(key) }),
      ),
    ),
    el("article", { class: "finding ja-card" },
      el("p", { class: "finding-num" },
        el("span", { text: numberFmt(f.median_accessibility) }),
        el("span", { class: "finding-of", text: " / " }),
        el("span", { text: numberFmt(f.median_mobile_performance) }),
      ),
      el("p", { class: "finding-text", text: t("fMedians", { a11y: numberFmt(f.median_accessibility), perf: numberFmt(f.median_mobile_performance) }) }),
    ),
  );

  $("#top-rules").replaceChildren(
    ...f.top_rules.map((r) =>
      el("li", {},
        el("span", { class: "rb-label" }, el("strong", { text: ruleLabel(r.rule) }), el("span", { class: "rb-crit", text: `WCAG ${r.criteria.join(", ")} · ${IMPACT_LABEL[state.lang][r.impact] || r.impact}` })),
        el("span", { class: "rb-bar", "aria-hidden": "true" }, el("span", { style: `width:${(r.sites / n) * 100}%` })),
        el("span", { class: "rb-val", text: t("sitesCount", { k: r.sites, n }) }),
      ),
    ),
  );

  $("#by-category").replaceChildren(
    ...f.by_category.map((c) =>
      el("li", {},
        el("span", { class: "rb-label" }, el("strong", { text: categoryLabel(c.category) })),
        el("span", { class: "rb-bar", "aria-hidden": "true" }, el("span", { class: levelClass(c.average_overall), style: `width:${c.average_overall}%` })),
        el("span", { class: "rb-val", text: t("categoryRow", { avg: numberFmt(c.average_overall, 1), n: c.sites, sites: c.sites === 1 ? t("site1") : t("sitesN") }) }),
      ),
    ),
  );
}

// ---------- Radar ----------

function renderRadar(summary) {
  const sectorsGroup = $("#sectors");
  const dotsGroup = $("#dots");
  sectorsGroup.replaceChildren();
  dotsGroup.replaceChildren();

  const span = 360 / SECTORS.length;
  SECTORS.forEach((_, i) => {
    const start = (i * span * Math.PI) / 180;
    sectorsGroup.append(svg("line", { x1: 0, y1: 0, x2: 104 * Math.sin(start), y2: -104 * Math.cos(start) }));
    const mid = ((i + 0.5) * span * Math.PI) / 180;
    const label = svg("text", { x: 116 * Math.sin(mid), y: -116 * Math.cos(mid) + 3 });
    label.textContent = sectorLabel(i, true);
    sectorsGroup.append(label);
  });

  const bySector = SECTORS.map(() => []);
  for (const site of summary.sites) {
    if (site.overall === null || site.overall === undefined) continue;
    const index = sectorOf(site.category);
    if (index >= 0) bySector[index].push(site);
  }

  let tip = $(".radar-tip");
  if (!tip) {
    tip = el("div", { class: "radar-tip", hidden: true, "aria-hidden": "true" });
    $("#radar").append(tip);
  }

  bySector.forEach((sites, i) => {
    sites.sort((a, b) => a.id.localeCompare(b.id));
    sites.forEach((site, j) => {
      const angleDeg = i * span + ((j + 0.5) / sites.length) * span;
      const angle = (angleDeg * Math.PI) / 180;
      // Escala ampliada: 100 en el centro, 50 o menos en el borde (cada anillo son 10 puntos).
      const radius = Math.max(4, Math.min(102, ((100 - site.overall) * 104) / 50));
      const x = radius * Math.sin(angle);
      const y = -radius * Math.cos(angle);
      const label = t("tipLabel", { name: site.name, score: site.overall, label: statusLabel(site.light), rank: site.rank });
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
  dimRadar();
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
  if (!STATUS_CLASS[site.light]) return el("span", { class: "na", text: text ?? t("noData") });
  return el("span", { class: `ja-status ${STATUS_CLASS[site.light]}` }, text, el("span", { class: "sr-only", text: `, ${statusLabel(site.light)}` }));
}

function showTip(tip, group, site) {
  const box = group.getBoundingClientRect();
  const parent = $("#radar").getBoundingClientRect();
  tip.replaceChildren(document.createTextNode(`${site.name} · `), el("b", { text: String(site.overall) }), ` (${statusLabel(site.light)})`);
  tip.style.left = `${box.left - parent.left + box.width / 2}px`;
  tip.style.top = `${box.top - parent.top}px`;
  tip.hidden = false;
}

// ---------- Tabla ----------

function renderFilters(summary) {
  const present = new Set(summary.sites.map((s) => sectorOf(s.category)));
  const options = [{ key: "todos", label: t("all") }, ...SECTORS.map((s, i) => ({ key: s.key, label: sectorLabel(i), i })).filter((o) => present.has(o.i))];
  $("#filters").replaceChildren(
    ...options.map((option) =>
      el("button", {
        class: "chip", type: "button", "aria-pressed": String(state.filter === option.key), text: option.label,
        onclick: () => { state.filter = option.key; renderFilters(summary); renderTable(summary); dimRadar(); },
      }),
    ),
  );
}

function matchesFilter(site) {
  if (state.filter === "todos") return true;
  return SECTORS[sectorOf(site.category)]?.key === state.filter;
}

function dimRadar() {
  if (!state.summary) return;
  for (const blip of document.querySelectorAll(".blip")) {
    const site = state.summary.sites.find((s) => s.id === blip.dataset.id);
    blip.classList.toggle("dim", !matchesFilter(site));
  }
}

function valueCell(value, extraClass = "") {
  if (value === null || value === undefined) return el("td", { class: `num ${extraClass}` }, el("span", { class: "na", text: t("noData") }));
  const level = value < 50 ? "low" : value < 80 ? "mid" : "";
  return el("td", { class: `num ${extraClass}` }, el("span", { class: `cell-bar ${level}`, text: String(value) }));
}

function renderTable(summary) {
  const body = $("#ranking-body");
  body.replaceChildren(
    ...summary.sites.filter(matchesFilter).map((site) => {
      const scores = site.scores || {};
      return el("tr", {},
        el("td", { class: "rank", text: site.rank ?? "–" }),
        el("td", {},
          el("button", { class: "site-btn", type: "button", onclick: () => openSheet(site.id), text: site.name }),
          el("span", { class: "site-cat", text: categoryLabel(site.category) }),
        ),
        el("td", {}, statusBadge(site, site.overall === null || site.overall === undefined ? null : String(site.overall))),
        ...COMPONENT_KEYS.map((key) => valueCell(scores[key], "c-wide")),
        el("td", { class: "num c-mid", text: site.wcag_rules ?? "–", title: t("casesTitle", { n: site.wcag_cases ?? 0 }) }),
      );
    }),
  );
  const skipped = summary.sites.filter((s) => s.overall === null || s.overall === undefined);
  const note = $("#status-note");
  note.hidden = !skipped.length;
  note.textContent = skipped.length ? t("skipped", { names: skipped.map((s) => s.name).join(", ") }) : "";
}

// ---------- Ficha ----------

async function openSheet(id) {
  const site = state.summary.sites.find((s) => s.id === id);
  if (!site) return;
  state.openId = id;
  const dialog = $("#sheet");
  $("#sheet-category").textContent = t("sheetMeta", { category: categoryLabel(site.category), rank: site.rank ?? "–", total: state.summary.sites_audited });
  $("#sheet-title").textContent = site.name;
  const link = $("#sheet-url");
  link.href = site.url;
  link.textContent = site.url.replace(/^https?:\/\//, "").replace(/\/$/, "");
  const body = $("#sheet-body");
  body.replaceChildren(el("p", { class: "note", text: t("sheetLoading") }));
  if (!dialog.open) dialog.showModal();
  history.replaceState(null, "", `${location.pathname}${location.search}#${id}`);

  try {
    if (!state.details.has(id)) state.details.set(id, await getJSON(`${state.summary.date}/${site.detail}`));
    body.replaceChildren(...buildSheet(site, state.details.get(id)));
  } catch (error) {
    body.replaceChildren(el("p", { class: "note", text: t("sheetError") }));
  }
}

function buildSheet(site, detail) {
  const base = `${DATA}${state.summary.date}/`;
  const nodes = [];

  nodes.push(
    el("div", { class: "sheet-score" },
      el("span", { class: "big-score", text: site.overall ?? "–" }),
      STATUS_CLASS[site.light]
        ? el("span", { class: `ja-status ${STATUS_CLASS[site.light]}`, text: t("level", { label: statusLabel(site.light) }) })
        : el("span", { class: "pill", text: t("noScore") }),
    ),
  );

  const desktop = site.screenshots?.find((s) => s.includes("-desktop"));
  const mobile = site.screenshots?.find((s) => s.includes("-mobile"));
  if (desktop || mobile) {
    nodes.push(
      el("div", { class: "shots" },
        desktop ? el("figure", {}, el("img", { src: base + desktop, alt: t("shotAlt", { name: site.name, view: t("viewDesktop") }), loading: "lazy", width: 1366, height: 768 }), el("figcaption", { text: t("desktop") })) : null,
        mobile ? el("figure", {}, el("img", { src: base + mobile, alt: t("shotAlt", { name: site.name, view: t("viewMobile") }), loading: "lazy", width: 390, height: 844 }), el("figcaption", { text: t("mobileShot") })) : null,
      ),
    );
  }

  const scores = site.scores || {};
  nodes.push(
    el("section", {},
      el("h3", { text: t("components") }),
      el("ul", { class: "components" },
        COMPONENT_KEYS.map((key) => {
          const value = scores[key];
          return el("li", {},
            el("span", { text: COMPONENT_LABEL[state.lang][key] }),
            el("span", { class: "meter", "aria-hidden": "true" }, el("span", { class: levelClass(value), style: `width:${value ?? 0}%` })),
            el("span", { class: "val", text: value ?? "–" }),
          );
        }),
      ),
    ),
  );

  const wcag = detail.wcag || { rules: [], rules_count: 0, cases: 0 };
  nodes.push(
    el("section", {},
      el("h3", { text: t("a11yHeading", { rules: wcag.rules_count, cases: wcag.cases }) }),
      wcag.rules.length
        ? el("ul", { class: "rules" },
            wcag.rules.slice(0, 8).map((rule) =>
              el("li", {},
                el("span", { class: `impact ${rule.impact}`, text: IMPACT_LABEL[state.lang][rule.impact] || rule.impact }),
                el("strong", { text: ruleLabel(rule.rule) }),
                ` · ${rule.cases} ${rule.cases === 1 ? t("case1") : t("casesN")}`,
                el("span", { class: "crit", text: describeRule(rule) }),
              ),
            ),
            wcag.rules.length > 8 ? el("li", { text: t("moreRules", { n: wcag.rules.length - 8 }) }) : null,
          )
        : el("p", { class: "note", text: t("noViolations") }),
    ),
  );

  const lhMobile = detail.lighthouse?.mobile;
  const lhDesktop = detail.lighthouse?.desktop;
  const seconds = (ms) => (ms === undefined || ms === null ? "–" : `${numberFmt(ms / 1000, 1)} s`);
  const overflow = detail.mobile?.overflow_px;
  nodes.push(
    el("section", {},
      el("h3", { text: t("facts") }),
      el("dl", { class: "facts" },
        el("div", {}, el("dt", { text: t("lcpMobile") }), el("dd", { text: seconds(lhMobile?.metrics?.lcp_ms) })),
        el("div", {}, el("dt", { text: t("lcpDesktop") }), el("dd", { text: seconds(lhDesktop?.metrics?.lcp_ms) })),
        el("div", {}, el("dt", { text: t("overflow") }), el("dd", { text: overflow === undefined || overflow === null ? "–" : `${overflow} px` })),
        el("div", {}, el("dt", { text: t("failed") }), el("dd", { text: detail.failed_resources_first_party ?? "–" })),
      ),
      el("p", { class: "fineprint", text: t("pagesNote", { pages: new Set((detail.pages || []).map((p) => p.url)).size, third: detail.third_party_failures ?? 0 }) }),
      detail.errors?.length ? el("p", { class: "fineprint", text: t("notes", { notes: detail.errors.map((n) => translateNote(n, state.lang)).join(" · ") }) }) : null,
    ),
  );

  nodes.push(buildEvolution(site));
  return nodes;
}

function buildEvolution(site) {
  const series = (state.history?.sites?.[site.id]?.series || []).filter((p) => p.overall !== null);
  const section = el("section", {}, el("h3", { text: t("evolution") }));
  if (series.length < 2) {
    section.append(el("p", { class: "note", text: t("firstRun") }));
    return section;
  }
  const w = 300, h = 48, pad = 4;
  const xs = (i) => pad + (i * (w - pad * 2)) / (series.length - 1);
  const ys = (v) => h - pad - (v / 100) * (h - pad * 2);
  const chart = svg("svg", { class: "spark", viewBox: `0 0 ${w} ${h}`, role: "img", "aria-label": t("sparkLabel", { points: series.map((p) => `${p.date} ${p.overall}`).join(", ") }) });
  chart.append(svg("polyline", { points: series.map((p, i) => `${xs(i)},${ys(p.overall)}`).join(" ") }));
  series.forEach((p, i) => chart.append(svg("circle", { cx: xs(i), cy: ys(p.overall), r: 3 })));
  section.append(chart);
  return section;
}

function setupDialog() {
  const dialog = $("#sheet");
  $("#sheet-close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
  dialog.addEventListener("close", () => {
    state.openId = null;
    history.replaceState(null, "", location.pathname + location.search);
  });
}

// ---------- Inicio ----------

function renderAll() {
  const summary = state.summary;
  renderHeader(summary);
  renderFindings(summary);
  renderWeights(summary);
  renderRadar(summary);
  renderFilters(summary);
  renderTable(summary);
}

async function main() {
  state.lang = initialLang();
  applyStaticText();
  setupDialog();
  $("#lang-toggle").addEventListener("click", () => setLang(state.lang === "es" ? "en" : "es"));
  try {
    const latest = await getJSON("latest.json");
    const [summary, historyData] = await Promise.all([getJSON(latest.summary), getJSON("history.json").catch(() => null)]);
    state.summary = summary;
    state.history = historyData;
    renderAll();
    const hash = decodeURIComponent(location.hash.slice(1));
    if (hash && summary.sites.some((s) => s.id === hash)) openSheet(hash);
  } catch (error) {
    $("#scan-date").textContent = t("loadError");
    console.error(error);
  }
}

main();
