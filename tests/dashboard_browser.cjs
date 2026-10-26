// Rendered check of the dashboard in a real Chromium, at desktop and phone widths.
// It prepares the example campaign on a fresh one-slot node, serves the dashboard,
// clicks Start, waits for the ten real jobs and saves screenshots and a report.
// Needs Playwright with Chromium (require('playwright')) and the native binaries:
//   EXPERIMENT_CRAFT_TEST_BIN_DIR=/abs/bin EXPERIMENT_CRAFT_TEST_PYTHON=/abs/python \
//     node tests/dashboard_browser.cjs /absolute/new/output
"use strict";
const {chromium} = require("playwright");
const {spawn, execFileSync} = require("child_process");
const fs = require("fs"), path = require("path");
const project = path.resolve(__dirname, "..");
const bin = process.env.EXPERIMENT_CRAFT_TEST_BIN_DIR, python = process.env.EXPERIMENT_CRAFT_TEST_PYTHON || "python3";
const out = process.argv[2];
if (!bin || !out || fs.existsSync(out)) { console.error("usage: set EXPERIMENT_CRAFT_TEST_BIN_DIR and give a new output directory"); process.exit(2); }
fs.mkdirSync(out, {recursive: true});
const demo = path.join(out, "demo");
const prepared = JSON.parse(execFileSync(python, [path.join(project, "examples/dashboard/prepare.py"), "--bin-dir", bin,
  "--output", demo, "--port", "0"], {cwd: project}).toString().trim().split("\n").pop());
const [command, ...args] = prepared.dashboard_argv;
const server = spawn(command, args, {cwd: project, stdio: ["ignore", "pipe", "pipe"]});
let stdout = "", stderr = "";
server.stdout.on("data", d => stdout += d); server.stderr.on("data", d => stderr += d);
const checks = [];
const check = (name, ok, detail) => checks.push({name, passed: !!ok, ...(ok ? {} : {detail})});
const jobs = () => JSON.parse(execFileSync(path.join(bin, "optimization-run"), ["--root", path.join(demo, "node"), "jobs", "list"]).toString());
// The phone view goes first, while the campaign can still be stopped.
const views = [
  {name: "phone", options: {viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true, deviceScaleFactor: 2}},
  {name: "desktop", options: {viewport: {width: 1366, height: 900}}},
];
(async () => {
  const until = Date.now() + 30000;
  while (!stdout.includes("\n") && Date.now() < until) await new Promise(r => setTimeout(r, 100));
  const url = JSON.parse(stdout.split("\n")[0]).url;
  const browser = await chromium.launch();
  try {
    for (const view of views) {
      const context = await browser.newContext(view.options), page = await context.newPage(), errors = [];
      page.on("console", m => { if (m.type() === "error") errors.push(m.text()); });
      page.on("pageerror", e => errors.push(String(e)));
      await page.goto(url);
      await page.waitForSelector('[data-action="stop"]:enabled');
      check(`${view.name}: the token leaves the address bar`, !page.url().includes("token"), page.url());
      const [scroll, width] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
      check(`${view.name}: no horizontal page overflow`, scroll <= width, {scroll, width});
      await page.click('[data-action="stop"]');
      check(`${view.name}: Stop opens its confirmation`, await page.isVisible("#stop-dialog"));
      check(`${view.name}: the confirmation names the experiment`, (await page.textContent("#stop-name")) === "Local solver tour");
      check(`${view.name}: the dialog has a visible confirm button`, await page.isVisible('#stop-dialog button[value="stop"]'));
      await page.click('#stop-dialog button[value="cancel"]');
      check(`${view.name}: Keep running closes it without a stop`, !(await page.isVisible("#stop-dialog")));
      if (view.name === "desktop") {
        await page.keyboard.press("Tab");
        const focus = [];
        for (let i = 0; i < 12; i++) {
          await page.keyboard.press("Tab");
          focus.push(await page.evaluate(() => { const e = document.activeElement, s = getComputedStyle(e);
            return {tag: e.tagName, visible: s.outlineStyle !== "none" || s.boxShadow !== "none"}; }));
        }
        const buttons = focus.filter(f => f.tag === "BUTTON");
        check("desktop: Tab reaches the controls with a visible focus ring", buttons.length && buttons.every(f => f.visible), focus);
        await page.screenshot({path: path.join(out, "desktop-before.png"), fullPage: true});
        await page.click('[data-action="continue"]');
        const end = Date.now() + 300000;
        while (Date.now() < end && !(jobs().length === 10 && jobs().every(j => j.state === "completed"))) await page.waitForTimeout(2000);
        await page.waitForFunction(() => /10 \/ 10 steps finished/.test(document.body.innerText), null, {timeout: 30000}).catch(() => {});
        check("desktop: Start runs the ten jobs to completion", jobs().length === 10 && jobs().every(j => j.state === "completed"), jobs().map(j => j.state));
        check("desktop: the page shows the completed campaign", /10 \/ 10 steps finished/.test(await page.innerText("body")));
        await page.screenshot({path: path.join(out, "desktop-after.png"), fullPage: true});
      } else {
        await page.screenshot({path: path.join(out, "phone.png"), fullPage: true});
      }
      check(`${view.name}: no console or page errors`, errors.length === 0, errors);
      await context.close();
    }
  } finally {
    await browser.close();
    server.kill("SIGINT");
    const code = server.exitCode !== null ? server.exitCode : await new Promise(r => server.on("exit", r));
    const last = stdout.split("\n").filter(Boolean).pop() || "{}";
    check("the dashboard shuts down cleanly", code === 0 && JSON.stringify(JSON.parse(last)) ===
      JSON.stringify({checkpoint_errors: [], status: "dashboard_stopped"}), {code, last});
  }
  const report = {status: checks.every(c => c.passed) ? "passed" : "failed", browser: "chromium (Playwright)",
    environment: "rendered pages at 1366x900 and a 390x844 touch viewport; not a physical phone",
    native_jobs: jobs().length, checks, shutdown: stdout.split("\n").filter(Boolean).slice(1), stderr: stderr.slice(-2000)};
  fs.writeFileSync(path.join(out, "report.json"), JSON.stringify(report, null, 2) + "\n");
  console.log(JSON.stringify({status: report.status, failed: checks.filter(c => !c.passed)}));
  process.exit(report.status === "passed" ? 0 : 1);
})().catch(e => { console.error(e); server.kill("SIGKILL"); process.exit(1); });
