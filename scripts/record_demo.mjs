// Record assets/demo.gif from a real Chrome session against a real local server.
//
//   PYTHONPATH=src node scripts/record_demo.mjs frames/   # then ffmpeg stitches the frames
import { mkdirSync, rmSync } from "node:fs";
import { join } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";
import { launch, startServer } from "../tests/e2e/cdp.mjs";

const out = process.argv[2] || "frames";
rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });
const server = await startServer();
const page = await launch({ width: 1200, height: 760 });
let n = 0;
const frame = async (hold = 1) => { for (let i = 0; i < hold; i++) await page.shot(join(out, `f${String(n++).padStart(4, "0")}.png`)); };
const settle = (ms = 600) => sleep(ms);

await page.goto(server.url);
await frame(6);
await page.click("#sample");
await page.waitFor("!document.querySelector('#go').disabled");
await settle(); await frame(6);
await page.click("#go");
// Progress is real; sample it while the matcher works.
for (let i = 0; i < 60 && await page.eval("document.querySelector('#review').hidden"); i++) { await frame(1); await sleep(250); }
await page.waitFor("!document.querySelector('#review').hidden", 120000);
await page.eval("document.querySelector('#review').scrollIntoView()");
await settle(900); await frame(8);
await page.eval("document.querySelectorAll('#rescan-list li button')[1].click()");
await settle(1500); await frame(8);
await page.eval("document.querySelector('[data-view=overlay]').click()");
await settle(2500); await frame(10);
await page.eval("document.querySelector('[data-view=features]').click()");
await settle(2500); await frame(8);
const count = await page.eval("document.querySelectorAll('#rescan-list li').length");
for (let i = 0; i < count; i++) {
  await page.eval(`document.querySelectorAll('#rescan-list li button')[${i}].click()`);
  await settle(700);
  if (await page.eval("!document.querySelector('#confirm').disabled && document.querySelector('#d-badge').classList.contains('check')")) {
    await frame(3); await page.click("#confirm"); await settle(300); await frame(3);
  }
}
await page.eval("document.querySelector('#export').scrollIntoView()");
await settle(500); await frame(6);
await page.click("#do-export");
await page.waitFor("!document.querySelector('#done').hidden || !document.querySelector('#export-error').hidden", 120000);
await page.eval("document.querySelector('#done').scrollIntoView({block:'center'})");
await settle(600); await frame(14);
await page.close(); server.stop();
console.log(`${n} frames in ${out}`);
