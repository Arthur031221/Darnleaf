// Minimal Chrome DevTools Protocol driver, enough to click through the UI. No dependencies.
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

export const CHROME = process.env.CHROME_BIN || "google-chrome";

export async function launch({ width = 1280, height = 860, port = 9333 + Math.floor(Math.random() * 400) } = {}) {
  const dir = mkdtempSync(join(tmpdir(), "darnleaf-chrome-"));
  const proc = spawn(CHROME, [
    "--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${dir}`, `--window-size=${width},${height}`,
    "--no-first-run", "--no-default-browser-check", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1", "about:blank",
  ], { stdio: "ignore" });
  let target;
  for (let i = 0; i < 100 && !target; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
      target = list.find((t) => t.type === "page");
    } catch { await sleep(100); }
  }
  if (!target) { proc.kill(); throw new Error("Chrome did not start"); }
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
  let nextId = 1;
  const pending = new Map();
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? reject(new Error(msg.error.message)) : resolve(msg.result);
    }
  };
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = nextId++;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
  await send("Page.enable");
  await send("Runtime.enable");
  await send("DOM.enable");

  const page = {
    send,
    async goto(url) { await send("Page.navigate", { url }); await sleep(300); await page.waitFor("document.readyState === 'complete'"); },
    async eval(expression) {
      const r = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
      if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
      return r.result.value;
    },
    async waitFor(expression, timeout = 60000) {
      const end = Date.now() + timeout;
      while (Date.now() < end) {
        try { if (await page.eval(expression)) return; } catch { /* page still loading */ }
        await sleep(120);
      }
      throw new Error(`timed out waiting for: ${expression}`);
    },
    click: (selector) => page.eval(`document.querySelector(${JSON.stringify(selector)}).click()`),
    async files(selector, paths) {
      const { root } = await send("DOM.getDocument");
      const { nodeId } = await send("DOM.querySelector", { nodeId: root.nodeId, selector });
      await send("DOM.setFileInputFiles", { nodeId, files: paths });
    },
    async shot(path, { width, height } = {}) {
      if (width) await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: false });
      const { data } = await send("Page.captureScreenshot", { format: "png" });
      (await import("node:fs")).writeFileSync(path, Buffer.from(data, "base64"));
    },
    async close() { ws.close(); proc.kill(); await sleep(150); rmSync(dir, { recursive: true, force: true }); },
  };
  return page;
}

export async function startServer(python = process.env.PYTHON || "python3", port = 0) {
  const proc = spawn(python, ["-m", "darnleaf", "serve", "--no-open", "--port", String(port || 18000 + Math.floor(Math.random() * 1000))], { stdio: ["ignore", "pipe", "inherit"], env: process.env });
  const url = await new Promise((resolve, reject) => {
    proc.stdout.on("data", (chunk) => { const m = /(http:\/\/[\d.]+:\d+\/)/.exec(String(chunk)); if (m) resolve(m[1]); });
    proc.on("exit", (code) => reject(new Error(`server exited early (${code})`)));
    setTimeout(() => reject(new Error("server did not start")), 20000);
  });
  return { url, stop: () => proc.kill() };
}
