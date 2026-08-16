#!/usr/bin/env node
// Usage: node render.js <gcode-path> <out-png> [--bed 220x220] [--title name]
// Renders the composite preview (tube views, line views, bed placement map)
// by driving headless Chromium.

const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright-core");

function findChromium() {
  if (process.env.PRINTD_CHROMIUM) return process.env.PRINTD_CHROMIUM;
  const cache = path.join(process.env.HOME, ".cache", "ms-playwright");
  if (fs.existsSync(cache)) {
    for (const d of fs.readdirSync(cache).sort().reverse()) {
      if (d.startsWith("chromium")) {
        for (const rel of ["chrome-linux/chrome", "chrome-linux/headless_shell", "chrome-headless-shell-linux/headless_shell"]) {
          const p = path.join(cache, d, rel);
          if (fs.existsSync(p)) return p;
        }
      }
    }
  }
  throw new Error("no Chromium found; set PRINTD_CHROMIUM");
}

async function main() {
  const [gcodePath, outPng] = process.argv.slice(2);
  if (!gcodePath || !outPng) {
    console.error("usage: render.js <gcode> <out.png> [--bed 220x220] [--title t]");
    process.exit(2);
  }
  const bedArg = (process.argv.indexOf("--bed") + 1 || 0) && process.argv[process.argv.indexOf("--bed") + 1];
  const titleArg = (process.argv.indexOf("--title") + 1 || 0) && process.argv[process.argv.indexOf("--title") + 1];
  const [bedX, bedY] = (bedArg || "220x220").split("x").map(Number);

  const gcode = fs.readFileSync(gcodePath, "utf8");
  const browser = await chromium.launch({
    executablePath: findChromium(),
    args: ["--enable-unsafe-swiftshader", "--use-angle=swiftshader"],
  });
  try {
    const page = await browser.newPage();
    await page.setContent("<!doctype html><html><body></body></html>");
    await page.addScriptTag({ path: path.join(__dirname, "dist", "bundle.js") });
    const result = await page.evaluate(
      ([text, opts]) => window.PrintdRender.renderComposite(text, opts),
      [gcode, { bedX, bedY, title: titleArg || path.basename(gcodePath, ".gcode") }]
    );
    const write = (p, dataUrl) => fs.writeFileSync(p, Buffer.from(dataUrl.split(",")[1], "base64"));
    write(outPng, result.full);
    const stem = outPng.replace(/\.png$/, "");
    write(`${stem}.1.png`, result.top);
    write(`${stem}.2.png`, result.bottom);
    console.log(outPng);
  } finally {
    await browser.close();
  }
}

main().catch((e) => { console.error(e.message || e); process.exit(1); });
