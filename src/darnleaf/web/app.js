"use strict";

const LANGS = [
  ["en", "English"], ["zh-TW", "繁體中文"], ["zh-CN", "简体中文"], ["ja", "日本語"], ["ko", "한국어"],
  ["es", "Español"], ["fr", "Français"], ["de", "Deutsch"], ["pt-BR", "Português (Brasil)"],
];
// The Pages demo sets window.DARNLEAF_STATIC to a replay backend; the local app leaves it undefined.
const STATIC = window.DARNLEAF_STATIC || null;
const asset = (path) => (STATIC ? STATIC.asset(path) : path);
const TOKEN = document.querySelector('meta[name="darnleaf-token"]').content;
const $ = (id) => document.getElementById(id);
const state = { data: null, strings: {}, fallback: {}, selected: 0, view: "side", candidate: null, timer: null, stamp: 0 };

// ---------- i18n ----------
function t(key, vars) {
  let s = state.strings[key] ?? state.fallback[key] ?? key;
  for (const [k, v] of Object.entries(vars || {})) s = s.replaceAll(`{${k}}`, v);
  return s;
}
window.darnleafT = t;
async function loadLocale(code) {
  const get = async (c) => (await fetch(`locales/${c}.json`)).json();
  if (!state.fallback.__loaded) state.fallback = { ...(await get("en")), __loaded: true };
  state.strings = code === "en" ? state.fallback : await get(code);
  document.documentElement.lang = code;
  localStorage.setItem("darnleaf-lang", code);
  document.querySelectorAll("[data-i18n]").forEach((el) => (el.textContent = t(el.dataset.i18n)));
  $("theme").textContent = t(document.documentElement.dataset.theme === "dark" ? "ui.light" : "ui.dark");
  document.title = `Darnleaf: ${t("app.tagline")}`;
  if (state.data) render();
}
function pickLanguage() {
  const saved = localStorage.getItem("darnleaf-lang");
  if (saved && LANGS.some(([c]) => c === saved)) return saved;
  const want = (navigator.language || "en").toLowerCase();
  const exact = LANGS.find(([c]) => c.toLowerCase() === want);
  if (exact) return exact[0];
  if (want.startsWith("zh")) return /tw|hk|hant/.test(want) ? "zh-TW" : "zh-CN";
  return (LANGS.find(([c]) => c.toLowerCase() === want.split("-")[0]) || ["en"])[0];
}

// ---------- api ----------
async function api(path, body, extra) {
  if (STATIC) return STATIC.api(path, body);
  const opts = { headers: { "X-Darnleaf-Token": TOKEN, ...(extra || {}) } };
  if (body !== undefined) {
    opts.method = "POST";
    opts.body = body instanceof Blob ? body : JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.error || res.statusText);
  return json;
}
const upload = (path, file) => api(path, file, { "X-Filename": encodeURIComponent(file.name), "Content-Type": "application/octet-stream" });
function showError(el, err) {
  el.textContent = err ? err.message || String(err) : "";
  el.hidden = !err;
}
async function refresh() {
  state.data = await api("/api/state");
  render();
  return state.data;
}

// ---------- rendering ----------
function render() {
  const d = state.data;
  const busy = d.stage === "matching";
  const info = d.original;
  $("original-info").textContent = info ? t("load.original_info", { name: info.name, pages: info.pages }) : "";
  $("rescans-info").textContent = d.rescans.length ? t("load.rescans_info", { n: d.rescans.length }) : "";
  $("go").disabled = busy || !info || !d.rescans.length;
  // The replay cannot take files, so until the sample is loaded it is the one thing to press.
  if (STATIC) $("sample").className = info ? "ghost" : "primary";
  $("clear").hidden = !d.rescans.length;
  $("ocr-wrap").hidden = !d.ocr;
  const notes = $("notes");
  notes.replaceChildren();
  if (info) {
    for (const [list, cls] of [[info.errors, "bad"], [info.warnings, ""]]) {
      for (const line of list) notes.append(Object.assign(document.createElement("li"), { textContent: line, className: cls }));
    }
  }
  $("progress").hidden = !busy;
  if (busy) {
    $("bar").max = Math.max(d.total, 1);
    $("bar").value = d.done;
    $("progress-text").textContent = t(`match.step.${d.step || "pages"}`, { done: d.done, total: d.total });
  }
  if (d.stage === "failed") showError($("error"), new Error(d.error)); else if (!busy) showError($("error"), null);
  $("review").hidden = !["review"].includes(d.stage) && !d.proposals.length;
  $("export").hidden = $("review").hidden;
  if (!$("review").hidden) { renderList(); renderDetail(); renderExport(); }
  clearTimeout(state.timer);
  if (busy) state.timer = setTimeout(refresh, 450);
}

function statusOf(i) {
  const d = state.data, p = d.proposals[i];
  if (d.confirmed.includes(i)) return "done";
  if (!(i in d.choice)) return "none";
  return p && p.page === d.choice[i] ? p.status : "check";
}
const badgeText = (s) => t(`status.${s}`);
const img = (src, alt) => Object.assign(document.createElement("img"), { src, alt: alt || "", loading: "lazy" });

function turnsFor(i, page) {
  const p = state.data.proposals[i];
  const c = p && p.candidates.find((c) => c.page === page);
  return c ? c.quarter_turns : 0;
}

function renderList() {
  const d = state.data, ol = $("rescan-list");
  ol.replaceChildren();
  d.rescans.forEach((r, i) => {
    const s = statusOf(i), page = d.choice[i];
    const b = document.createElement("button");
    b.type = "button";
    b.setAttribute("aria-current", String(i === state.selected));
    const name = Object.assign(document.createElement("span"), { className: "name", textContent: r.label, title: r.label });
    const badge = Object.assign(document.createElement("span"), { className: `badge ${s}`, textContent: `${badgeText(s)}${page ? ` · ${t("review.page_short", { page })}` : ""}` });
    b.append(img(asset(`/api/rescan/${i}?size=160&turns=${page ? turnsFor(i, page) : 0}`), ""), name, badge);
    b.onclick = () => { state.selected = i; state.candidate = null; render(); };
    if (i === state.selected) requestAnimationFrame(() => b.scrollIntoView({ block: "nearest" }));
    const li = document.createElement("li");
    li.append(b);
    ol.append(li);
  });
}

function shownPage() {
  const d = state.data;
  if (state.candidate !== null) return state.candidate;
  const c = d.choice[state.selected];
  if (c) return c;
  const p = d.proposals[state.selected];
  return p && p.candidates.length ? p.candidates[0].page : null;
}

function renderDetail() {
  const d = state.data, i = state.selected, p = d.proposals[i];
  if (!d.rescans[i]) return;
  const s = statusOf(i), page = shownPage();
  $("d-title").textContent = d.rescans[i].label;
  $("d-badge").className = `badge ${s}`;
  $("d-badge").textContent = badgeText(s);
  $("d-reason").textContent = p ? `${t("review.details")}: ${p.reason}` : "";
  document.querySelectorAll(".tabs button").forEach((b) => {
    b.setAttribute("aria-selected", String(b.dataset.view === state.view));
    b.tabIndex = b.dataset.view === state.view ? 0 : -1;
  });
  const stage = $("stage");
  stage.replaceChildren();
  stage.className = "stage";
  if (page === null) {
    stage.append(Object.assign(document.createElement("p"), { className: "msg", textContent: t("view.nothing") }));
  } else {
    const turns = turnsFor(i, page);
    const fig = (src, cap) => {
      const f = document.createElement("figure");
      f.append(img(src, cap), Object.assign(document.createElement("figcaption"), { textContent: cap }));
      return f;
    };
    if (state.view === "side") {
      stage.append(fig(asset(`/api/page/${page - 1}?size=900`), t("view.original", { page })), fig(asset(`/api/rescan/${i}?size=900&turns=${turns}`), t("view.rescan")));
    } else {
      stage.classList.add("one");
      const kind = state.view === "overlay" ? "overlay" : "features";
      const probe = new Image();
      const stamp = ++state.stamp;
      stage.append(Object.assign(document.createElement("p"), { className: "msg", textContent: t("view.loading") }));
      probe.onload = () => { if (stamp === state.stamp) { stage.replaceChildren(fig(probe.src, t(`view.${kind}_caption`))); } };
      probe.onerror = async () => {
        if (stamp !== state.stamp) return;
        const r = STATIC ? null : await fetch(probe.src, { headers: { "X-Darnleaf-Token": TOKEN } });
        const j = r ? await r.json().catch(() => ({})) : {};
        stage.replaceChildren(Object.assign(document.createElement("p"), { className: "msg", textContent: `${t("view.unavailable")} ${j.error || ""}` }));
      };
      probe.src = asset(`/api/evidence/${i}/${page - 1}/${kind}`);
    }
  }
  const strip = $("cands");
  strip.replaceChildren();
  for (const c of p ? p.candidates.slice(0, 8) : []) {
    const b = document.createElement("button");
    b.type = "button";
    b.setAttribute("aria-pressed", String(c.page === page));
    b.append(img(asset(`/api/page/${c.page - 1}?size=140`), ""), document.createTextNode(`${t("review.page_short", { page: c.page })} · ${Math.round(c.score * 100)}`));
    b.title = t("review.cand_title", { inliers: c.inliers, score: c.score });
    b.onclick = () => { state.candidate = c.page; renderDetail(); };
    strip.append(b);
  }
  const input = $("page-input");
  input.max = d.original ? d.original.pages : 1;
  if (document.activeElement !== input) input.value = page ?? "";
  $("confirm").disabled = page === null;
  $("confirm").textContent = d.confirmed.includes(i) && d.choice[i] === page ? t("review.confirmed") : t("review.confirm");
  $("unassign").disabled = !(i in d.choice);
}

function renderExport() {
  const d = state.data;
  const total = d.rescans.length, assigned = Object.keys(d.choice).length;
  const unsure = Object.keys(d.choice).filter((r) => statusOf(+r) !== "clear" && statusOf(+r) !== "done").length;
  let text = t("export.summary", { assigned, total, untouched: (d.original?.pages || 0) - assigned });
  if (d.conflicts.length) text += " " + t("export.conflict", { pages: d.conflicts.join(", ") });
  if (unsure) text += " " + t("export.unsure", { n: unsure });
  $("export-summary").textContent = text;
  $("do-export").disabled = !assigned || unsure > 0 || d.conflicts.length > 0;
  const annotated = d.original?.annotated_pages?.filter((p) => Object.values(d.choice).includes(p)) || [];
  $("drop-wrap").hidden = !annotated.length;
  $("done").hidden = !d.exported;
}

// ---------- actions ----------
// The next rescan after `from` that still needs a decision, wrapping around, or -1.
function nextOpen(from) {
  const n = state.data.rescans.length;
  for (let step = 1; step < n; step++) {
    const i = (from + step) % n;
    if (statusOf(i) === "check") return i;
  }
  return -1;
}

async function choose(page, confirmed) {
  try {
    const from = state.selected;
    state.data = await api("/api/choose", { rescan: from, page, confirmed });
    state.candidate = null;
    if (confirmed) {
      const next = nextOpen(from);
      if (next >= 0) state.selected = next;
    }
    render();
  } catch (e) { showError($("export-error"), e); }
}
async function guarded(fn, target) {
  try { showError(target, null); await fn(); } catch (e) { showError(target, e); }
}
async function sendFiles(files, path) {
  for (const f of files) await upload(path, f);
  await refresh();
}

function wireDrop(zone, input, handler) {
  zone.onclick = () => input.click();
  zone.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } };
  input.onchange = () => { const f = [...input.files]; input.value = ""; guarded(() => handler(f), $("error")); };
  zone.ondragover = (e) => { e.preventDefault(); zone.classList.add("over"); };
  zone.ondragleave = () => zone.classList.remove("over");
  zone.ondrop = (e) => { e.preventDefault(); zone.classList.remove("over"); guarded(() => handler([...e.dataTransfer.files]), $("error")); };
}

// j/k (and the arrow keys inside the list) move through the rescans, 1 to 8 pick a candidate, c confirms.
function onKey(e) {
  if (e.ctrlKey || e.metaKey || e.altKey || !state.data || $("review").hidden) return;
  if (e.target.closest("input, select, textarea")) return;
  const n = state.data.rescans.length, key = e.key;
  const tab = e.target.closest(".tabs button");
  if (tab && (key === "ArrowRight" || key === "ArrowLeft")) {
    const tabs = [...document.querySelectorAll(".tabs button")];
    const next = tabs[(tabs.indexOf(tab) + (key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length];
    e.preventDefault();
    state.view = next.dataset.view;
    renderDetail();
    next.focus();
    return;
  }
  if (tab && key.startsWith("Arrow")) return;
  const inList = !!e.target.closest(".rlist");
  if (key === "j" || key === "k" || (inList && (key === "ArrowDown" || key === "ArrowUp"))) {
    e.preventDefault();
    const step = key === "j" || key === "ArrowDown" ? 1 : -1;
    state.selected = (state.selected + step + n) % n;
    state.candidate = null;
    render();
    if (inList) document.querySelector('.rlist [aria-current="true"]')?.focus();
  } else if (/^[1-8]$/.test(key)) {
    const c = state.data.proposals[state.selected]?.candidates[+key - 1];
    if (c) { state.candidate = c.page; renderDetail(); }
  } else if (key === "c") {
    const p = shownPage();
    if (p !== null) choose(p, true);
  }
}

function init() {
  const sel = $("lang");
  LANGS.forEach(([c, n]) => sel.append(new Option(n, c)));
  const code = pickLanguage();
  sel.value = code;
  sel.onchange = () => loadLocale(sel.value);
  const saved = localStorage.getItem("darnleaf-theme");
  document.documentElement.dataset.theme = saved || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  $("theme").onclick = () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("darnleaf-theme", next);
    $("theme").textContent = t(next === "dark" ? "ui.light" : "ui.dark");
  };
  wireDrop($("drop-original"), $("file-original"), (f) => sendFiles(f.slice(0, 1), "/api/original"));
  wireDrop($("drop-rescans"), $("file-rescans"), (f) => sendFiles(f, "/api/rescan"));
  $("sample").onclick = () => guarded(async () => { $("sample").disabled = true; try { state.data = await api("/api/sample", {}); render(); } finally { $("sample").disabled = false; } }, $("error"));
  $("clear").onclick = () => guarded(async () => { state.data = await api("/api/clear", {}); render(); }, $("error"));
  $("go").onclick = () => guarded(async () => { state.selected = 0; state.candidate = null; state.data = await api("/api/match", { ocr: $("ocr").checked }); render(); }, $("error"));
  $("cancel").onclick = () => guarded(async () => { await api("/api/cancel", {}); }, $("error"));
  document.querySelectorAll(".tabs button").forEach((b) => (b.onclick = () => { state.view = b.dataset.view; renderDetail(); }));
  $("use-page").onclick = () => { const v = parseInt($("page-input").value, 10); if (v >= 1) { state.candidate = v; renderDetail(); } };
  $("page-input").onkeydown = (e) => { if (e.key === "Enter") $("use-page").click(); };
  $("confirm").onclick = () => { const p = shownPage(); if (p !== null) choose(p, true); };
  $("unassign").onclick = () => choose(null, false);
  $("do-export").onclick = () => guarded(async () => {
    const r = await api("/api/export", { mode: $("mode").value, drop_annotations: $("drop").checked });
    await refresh();
    $("done-text").textContent = t("export.done", { n: r.replaced.length, untouched: r.untouched_pages });
    if (STATIC && STATIC.onExport) STATIC.onExport(r);
  }, $("export-error"));
  document.addEventListener("keydown", onKey);
  if (STATIC) {
    $("demo-banner").hidden = false;
    document.querySelectorAll(".drop").forEach((z) => z.classList.add("off"));
  }
  loadLocale(code).then(refresh);
}
init();
