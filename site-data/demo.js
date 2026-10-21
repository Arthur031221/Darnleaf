"use strict";
// Replay backend for the Pages demo. It answers the same calls the local server does, from files
// that scripts/build_demo.py wrote after a real run. It never computes a match itself.
(() => {
  let snapshot = null;
  const load = fetch("demo/state.json").then((r) => r.json()).then((s) => (snapshot = s));
  const m = { loaded: false, stage: "idle", step: "pages", done: 0, total: 1, review: false, choice: {}, confirmed: new Set(), exported: false };
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  function state() {
    const s = snapshot;
    const shown = m.review;
    return {
      stage: m.stage, step: m.step, done: m.done, total: m.total, error: "",
      original: m.loaded ? { name: "sample-booklet.pdf", ...s.original } : null,
      rescans: m.loaded ? s.rescans : [],
      proposals: shown ? s.proposals : [],
      choice: shown ? Object.fromEntries(Object.entries(m.choice).map(([k, v]) => [k, v])) : {},
      confirmed: [...m.confirmed].sort((a, b) => a - b),
      conflicts: shown ? conflicts() : [],
      ocr: null, limits: s.limits, exported: m.exported,
    };
  }
  function conflicts() {
    const seen = {};
    for (const p of Object.values(m.choice)) seen[p] = (seen[p] || 0) + 1;
    return Object.keys(seen).filter((p) => seen[p] > 1).map(Number).sort((a, b) => a - b);
  }
  async function replay() {
    const s = snapshot;
    m.stage = "matching";
    const n = s.original.pages, k = s.rescans.length;
    for (const [step, total] of [["pages", n], ["rescans", k], ["matching", k]]) {
      m.step = step; m.total = total;
      for (let i = 1; i <= total; i++) { m.done = i; await wait(step === "pages" ? 22 : 90); }
    }
    m.choice = Object.fromEntries(s.proposals.filter((p) => p.page && p.status !== "none").map((p) => [p.rescan, p.page]));
    m.confirmed = new Set();
    m.review = true;
    m.stage = "review";
  }
  function ready() { return m.loaded && !m.review; }

  const handlers = {
    async "/api/state"() { await load; return state(); },
    async "/api/sample"() { await load; m.loaded = true; m.stage = "ready"; m.review = false; m.exported = false; return state(); },
    async "/api/clear"() { m.loaded = false; m.review = false; m.stage = "idle"; m.exported = false; return state(); },
    async "/api/match"() { await load; if (!m.loaded) throw new Error("Load the sample first."); replay(); await wait(10); return state(); },
    async "/api/cancel"() { return state(); },
    async "/api/choose"(body) {
      if (body.page === null) { delete m.choice[body.rescan]; m.confirmed.delete(body.rescan); }
      else { m.choice[body.rescan] = body.page; body.confirmed ? m.confirmed.add(body.rescan) : m.confirmed.delete(body.rescan); }
      m.exported = false;
      return state();
    },
    async "/api/export"() {
      const s = snapshot;
      const unsure = Object.keys(m.choice).map(Number).filter((r) => {
        const p = s.proposals[r];
        return !m.confirmed.has(r) && !(p.status === "clear" && p.page === m.choice[r]);
      });
      if (unsure.length) throw new Error(`Confirm rescans ${unsure.map((r) => r + 1)} first.`);
      m.exported = true;
      return s.receipt;
    },
  };

  window.DARNLEAF_STATIC = {
    async api(path, body) {
      if (path.startsWith("/api/original") || path.startsWith("/api/rescan")) throw new Error(window.darnleafT ? window.darnleafT("demo.nofiles") : "This replay has no file upload.");
      const h = handlers[path];
      if (!h) throw new Error("not available in the replay");
      return h(body);
    },
    asset(path) {
      let a;
      if ((a = /^\/api\/page\/(\d+)/.exec(path))) return `demo/page-${a[1]}.jpg`;
      if ((a = /^\/api\/rescan\/(\d+)\?.*turns=(\d+)/.exec(path))) return `demo/rescan-${a[1]}-t${+a[2] % 4}.jpg`;
      if ((a = /^\/api\/evidence\/(\d+)\/(\d+)\/(\w+)/.exec(path))) return `demo/ev-${a[1]}-${a[2]}-${a[3]}.jpg`;
      return path;
    },
    onExport(receipt) {
      document.getElementById("dl-pdf").hidden = true;
      const blob = new Blob([JSON.stringify(receipt, null, 2) + "\n"], { type: "application/json" });
      const a = document.getElementById("dl-receipt");
      a.href = URL.createObjectURL(blob);
      a.download = "sample-booklet-receipt.json";
    },
  };
})();
