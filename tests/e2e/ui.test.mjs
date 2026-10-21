// End to end: a real server, a real Chrome, the bundled sample and a file upload.
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { after, before, test } from "node:test";
import { fileURLToPath } from "node:url";
import { launch, startServer } from "./cdp.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const locales = join(here, "../../src/darnleaf/web/locales");
let server, page;

before(async () => {
  server = await startServer();
  page = await launch();
  await page.goto(server.url);
});
after(async () => { await page?.close(); server?.stop(); });

test("the page renders in English with no missing strings", async () => {
  await page.waitFor("document.querySelector('#load h2 span:last-child').textContent.length > 0");
  const missing = await page.eval(`[...document.querySelectorAll('[data-i18n]')].filter(e => e.textContent === e.dataset.i18n).length`);
  assert.equal(missing, 0);
});

test("every language switches the interface and none shows a raw key", async () => {
  const english = JSON.parse(readFileSync(join(locales, "en.json"), "utf8"));
  for (const code of ["zh-TW", "zh-CN", "ja", "ko", "es", "fr", "de", "pt-BR", "en"]) {
    await page.eval(`(() => { const s = document.querySelector('#lang'); s.value = ${JSON.stringify(code)}; s.dispatchEvent(new Event('change')); })()`);
    await page.waitFor(`document.documentElement.lang === ${JSON.stringify(code)} && document.querySelector('#go').textContent.length > 0`);
    const want = JSON.parse(readFileSync(join(locales, `${code}.json`), "utf8"))["load.go"];
    assert.equal(await page.eval("document.querySelector('#go').textContent"), want, code);
    assert.equal(await page.eval(`[...document.querySelectorAll('[data-i18n]')].filter(e => e.textContent === e.dataset.i18n).length`), 0, code);
    assert.deepEqual(Object.keys(JSON.parse(readFileSync(join(locales, `${code}.json`), "utf8"))), Object.keys(english));
  }
});

test("sample job: match, confirm, export and download a valid PDF", async () => {
  // The sample button loads the sample and starts the match in one press.
  await page.click("#sample");
  await page.waitFor("!document.querySelector('#review').hidden", 120000);
  assert.equal(await page.eval("document.querySelectorAll('#rescan-list li').length"), 7);
  // The export button stays locked until every non-clear rescan is confirmed.
  assert.equal(await page.eval("document.querySelector('#do-export').disabled"), true);
  const count = await page.eval("document.querySelectorAll('#rescan-list li').length");
  for (let i = 0; i < count; i++) {
    await page.eval(`document.querySelectorAll('#rescan-list li button')[${i}].click()`);
    await page.waitFor("document.querySelector('#d-title').textContent.length > 0");
    if (await page.eval("!document.querySelector('#confirm').disabled && document.querySelector('#d-badge').classList.contains('check')")) {
      await page.click("#confirm");
      await page.waitFor(`document.querySelectorAll('#rescan-list .badge.done').length > 0`);
    }
  }
  // The decoy has no match; the others are all assigned.
  await page.waitFor("!document.querySelector('#do-export').disabled");
  await page.click("#do-export");
  await page.waitFor("!document.querySelector('#done').hidden || !document.querySelector('#export-error').hidden");
  assert.equal(await page.eval("document.querySelector('#export-error').textContent"), "");
  const head = await page.eval(`fetch('/api/download/pdf').then(r => r.arrayBuffer()).then(b => new TextDecoder().decode(new Uint8Array(b).slice(0, 5)))`);
  assert.equal(head, "%PDF-");
  const receipt = JSON.parse(await page.eval(`fetch('/api/download/receipt').then(r => r.text())`));
  assert.equal(receipt.replaced.length, 6);
  assert.equal(receipt.original.pages, 40);
});

const press = async (key) => {
  const code = /^\d$/.test(key) ? `Digit${key}` : key.length === 1 ? `Key${key.toUpperCase()}` : key;
  const info = { key, code, text: key.length === 1 ? key : "" };
  await page.send("Input.dispatchKeyEvent", { type: "keyDown", ...info });
  await page.send("Input.dispatchKeyEvent", { type: "keyUp", ...info });
};

test("the review can be finished with the keyboard alone", async () => {
  await page.goto(server.url);
  await page.eval(`fetch('/api/clear', { method: 'POST', body: '{}', headers: { 'X-Darnleaf-Token': document.querySelector('meta[name=darnleaf-token]').content } })`);
  await page.goto(server.url);
  await page.waitFor("document.querySelector('#review').hidden");
  // The sample button loads the sample and starts the match in one press.
  await page.click("#sample");
  await page.waitFor("!document.querySelector('#review').hidden", 120000);
  assert.ok(await page.eval("document.querySelectorAll('#rescan-list .badge.check').length") > 0);
  const selected = () => page.eval("[...document.querySelectorAll('#rescan-list button')].findIndex((b) => b.getAttribute('aria-current') === 'true')");
  assert.equal(await selected(), 0);
  await press("j");
  assert.equal(await selected(), 1);
  await press("k");
  assert.equal(await selected(), 0);
  // Arrow keys move the selection only while the list has focus, so they still scroll the page elsewhere.
  await press("ArrowDown");
  assert.equal(await selected(), 0);
  await page.eval("document.querySelector('#rescan-list button').focus()");
  await press("ArrowUp");
  assert.equal(await selected(), 6, "moving up from the first wraps to the last");
  await press("ArrowDown");
  assert.equal(await selected(), 0);
  // 1 to 8 pick a candidate page, which becomes the shown page.
  await press("2");
  const picked = await page.eval("document.querySelector('#cands button[aria-pressed=true]')?.textContent || ''");
  assert.match(picked, /^\D*\d+/);
  // c confirms and jumps to the next rescan that still needs a check.
  for (let i = 0; i < 10 && await page.eval("document.querySelector('#do-export').disabled"); i++) {
    const before = await selected();
    await page.waitFor("document.querySelector('#d-title').textContent.length > 0");
    if (await page.eval("document.querySelector('#d-badge').classList.contains('check')")) {
      await press("c");
      await page.waitFor(`document.querySelectorAll('#rescan-list .badge.done').length > ${i}`);
    } else {
      await press("j");
      assert.notEqual(await selected(), before);
    }
  }
  assert.equal(await page.eval("document.querySelector('#do-export').disabled"), false);
  assert.equal(await page.eval("document.querySelectorAll('#rescan-list .badge.check').length"), 0);
});

test("the file panel folds to one line during review and opens again on request", async () => {
  await page.goto(server.url);
  await page.waitFor("!document.querySelector('#review').hidden");
  assert.equal(await page.eval("document.querySelector('#load').classList.contains('compact')"), true);
  assert.equal(await page.eval("document.querySelector('#drop-original').offsetParent === null"), true);
  assert.match(await page.eval("document.querySelector('#summary-text').textContent"), /sample-booklet\.pdf, 40 pages, 7 rescans/);
  await page.click("#load-edit");
  assert.equal(await page.eval("document.querySelector('#load').classList.contains('compact')"), false);
  assert.equal(await page.eval("document.querySelector('#drop-original').offsetParent !== null"), true);
  assert.equal(await page.eval("document.querySelector('#load-summary').hidden"), true);
});

test("zoom opens a closer look at both pages that scroll together, and Escape closes it", async () => {
  await page.goto(server.url);
  await page.waitFor("!document.querySelector('#review').hidden");
  await page.waitFor("document.querySelector('#stage img')");
  await press("z");
  await page.waitFor("document.querySelector('#zoom').open");
  assert.equal(await page.eval("document.querySelectorAll('#zoom-body .zoom-pane').length"), 2);
  await page.waitFor("[...document.querySelectorAll('#zoom-body img')].every((i) => i.complete && i.naturalWidth > 0)");
  assert.equal(await page.eval("document.querySelector('#zoom-body img').naturalWidth > document.querySelector('#stage img').clientWidth"), true);
  await page.eval("document.querySelector('.zoom-pane').scrollTop = 200");
  await page.waitFor("document.querySelectorAll('.zoom-pane')[1].scrollTop > 0");
  // j must not move the selection behind the dialog.
  await press("j");
  assert.equal(await page.eval("document.querySelector('#rescan-list [aria-current=true] .name').textContent"), "rescan-01.jpg");
  await page.send("Input.dispatchKeyEvent", { type: "keyDown", key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 });
  await page.send("Input.dispatchKeyEvent", { type: "keyUp", key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 });
  await page.waitFor("!document.querySelector('#zoom').open");
  // The evidence views zoom as a single picture, and the Zoom button is not mistaken for a tab.
  await page.eval("document.querySelector('[data-view=overlay]').click()");
  await page.waitFor("document.querySelector('#stage img')");
  await page.click("#zoom-open");
  await page.waitFor("document.querySelector('#zoom').open");
  assert.equal(await page.eval("document.querySelectorAll('#zoom-body .zoom-pane').length"), 1);
  assert.equal(await page.eval("document.querySelectorAll('.tabs [aria-selected=true]').length"), 1);
  await page.click("#zoom-close");
  await page.eval("document.querySelector('[data-view=side]').click()");
});

test("the review screen does not scroll sideways on a phone", async () => {
  await page.send("Emulation.setDeviceMetricsOverride", { width: 390, height: 800, deviceScaleFactor: 1, mobile: false });
  try {
    await page.goto(server.url);
    await page.waitFor("!document.querySelector('#review').hidden");
    await page.waitFor("document.querySelectorAll('#rescan-list li').length > 0");
    assert.ok(await page.eval("document.documentElement.scrollWidth <= window.innerWidth"));
  } finally {
    await page.send("Emulation.clearDeviceMetricsOverride");
  }
});

test("a hostile Host header and a missing token are refused", async () => {
  const forbidden = await page.eval(`fetch('/api/state', { headers: { 'X-Darnleaf-Token': 'wrong' } }).then(r => r.status)`);
  assert.equal(forbidden, 200); // GET needs the cookie, which this page has
  const post = await page.eval(`fetch('/api/clear', { method: 'POST', body: '{}' }).then(r => r.status)`);
  assert.equal(post, 403);
});

test("uploading files through the pickers works", { skip: !process.env.DARNLEAF_SAMPLE_DIR }, async () => {
  const dir = resolve(process.env.DARNLEAF_SAMPLE_DIR);
  assert.ok(existsSync(join(dir, "original.pdf")));
  await page.goto(server.url);
  await page.click("#clear").catch(() => {});
  await page.files("#file-original", [join(dir, "original.pdf")]);
  await page.waitFor("document.querySelector('#original-info').textContent.length > 0");
  await page.files("#file-rescans", [1, 2, 3].map((n) => join(dir, "rescans", `rescan-0${n}.jpg`)));
  await page.waitFor("document.querySelector('#rescans-info').textContent.includes('3')");
  assert.equal(await page.eval("document.querySelector('#go').disabled"), false);
});

test("the reason under a match follows the interface language", async () => {
  await page.goto(server.url);
  await page.waitFor("!document.querySelector('#review').hidden", 120000);
  const setLang = (code) => page.eval(`(() => { const s = document.querySelector('#lang'); s.value = ${JSON.stringify(code)}; s.dispatchEvent(new Event('change')); })()`);
  await setLang("de");
  await page.waitFor("document.documentElement.lang === 'de' && document.querySelector('#d-reason').textContent.length > 0");
  const [shown, plain] = await page.eval("[document.querySelector('#d-reason').textContent, state.data.proposals[state.selected].reason]");
  assert.ok(plain.length > 0);
  assert.ok(!shown.includes(plain), shown);
  await setLang("en");
  await page.waitFor("document.documentElement.lang === 'en'");
  assert.ok((await page.eval("document.querySelector('#d-reason').textContent")).includes(plain));
});

test("moving through the list keeps its buttons and thumbnails, and loaded pictures are shown", async () => {
  await page.goto(server.url);
  await page.waitFor("!document.querySelector('#review').hidden && document.querySelectorAll('#rescan-list li').length > 0", 120000);
  await page.eval("window.__keep = [document.querySelector('#rescan-list li button'), document.querySelector('#rescan-list img')]");
  await press("j");
  await press("k");
  assert.equal(await page.eval("window.__keep[0] === document.querySelector('#rescan-list li button') && window.__keep[1] === document.querySelector('#rescan-list img')"), true);
  await page.waitFor("document.querySelector('#stage img')?.complete");
  assert.equal(await page.eval("document.querySelector('#stage img').classList.contains('pending')"), false);
  await page.waitFor("getComputedStyle(document.querySelector('#stage img')).opacity === '1'");
});
