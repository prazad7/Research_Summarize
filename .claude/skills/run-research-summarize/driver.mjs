#!/usr/bin/env node
/**
 * chromium-cli-style headless browser REPL, used as a fallback when the
 * `chromium-cli` tool itself isn't available in this environment (it
 * wasn't, here). Same command vocabulary as chromium-cli so the same
 * scripting patterns transfer: pipe a script to stdin, or drive it one
 * line at a time under tmux for iterative debugging.
 *
 * Usage:
 *   node driver.mjs --session <name> <<'EOF'
 *   nav http://localhost:8080
 *   wait-for text=Research & Summarize
 *   screenshot 01-home
 *   fill input[aria-label="URL to summarize"] https://example.com
 *   click text=Summarize link
 *   wait-for text=Extracting
 *   screenshot 02-processing
 *   console --errors
 *   quit
 *   EOF
 *
 * Commands:
 *   nav <url>                    Navigate to a URL
 *   wait-for text=<text>         Wait for text to appear on the page
 *   wait-for <css-selector>      Wait for a selector to appear
 *   click <css-selector>         Click an element (also accepts text=...)
 *   fill <css-selector> <text>   Fill an input (fires real input events)
 *   press <key>                  Press a key (e.g. Enter) on the focused element
 *   get-text <css-selector>      Print an element's text content
 *   mock-get <url-glob> <file>   Fulfill matching GET requests with a JSON file's contents
 *   screenshot [name]            Save a full-page screenshot
 *   console --errors             Print captured console errors so far
 *   sleep <ms>                   Last resort only -- prefer wait-for
 *   quit                         Close the browser and exit
 *
 * Screenshots land in sessions/<session>/screenshots/NN-<name>.png
 */
import { chromium } from "playwright";
import readline from "node:readline";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const sessionArgIndex = process.argv.indexOf("--session");
const sessionName = sessionArgIndex !== -1 ? process.argv[sessionArgIndex + 1] : "default";
const sessionDir = path.join(__dirname, "sessions", sessionName);
const screenshotDir = path.join(sessionDir, "screenshots");
fs.mkdirSync(screenshotDir, { recursive: true });

let shotCount = 0;
const consoleErrors = [];

function resolveTarget(selector) {
  if (selector.startsWith("text=")) {
    return { locator: (page) => page.getByText(selector.slice(5), { exact: false }) };
  }
  return { locator: (page) => page.locator(selector) };
}

async function main() {
  const browser = await chromium.launch({ args: ["--no-sandbox"] });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();

  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(String(err)));

  const rl = readline.createInterface({ input: process.stdin, terminal: false });

  for await (const rawLine of rl) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const [cmd, ...rest] = line.split(" ");
    const arg = rest.join(" ");

    try {
      switch (cmd) {
        case "nav": {
          await page.goto(arg, { waitUntil: "domcontentloaded" });
          console.log(`OK nav ${arg}`);
          break;
        }
        case "wait-for": {
          // 90s, not 20s: a real end-to-end job (extract -> analyze ->
          // research -> summarize against real OpenAI/Serper calls) can
          // take 30-60s+ on its own, on top of whatever came before this
          // command in the script.
          if (arg.startsWith("text=")) {
            await page.getByText(arg.slice(5), { exact: false }).first().waitFor({ timeout: 90000 });
          } else {
            await page.locator(arg).first().waitFor({ timeout: 90000 });
          }
          console.log(`OK wait-for ${arg}`);
          break;
        }
        case "click": {
          const [selector, ...textParts] = rest;
          const target =
            arg.startsWith("text=") ? resolveTarget(arg).locator(page) : page.locator(selector);
          await target.first().click();
          console.log(`OK click ${arg}`);
          break;
        }
        case "fill": {
          const selector = rest[0];
          const text = rest.slice(1).join(" ");
          await page.locator(selector).first().fill(text);
          console.log(`OK fill ${selector}`);
          break;
        }
        case "press": {
          await page.keyboard.press(arg);
          console.log(`OK press ${arg}`);
          break;
        }
        case "get-attr": {
          // Last token is the attribute name; everything else (rejoined) is
          // the selector, so multi-word CSS descendant selectors work.
          const attr = rest[rest.length - 1];
          const selector = rest.slice(0, -1).join(" ");
          const value = await page.locator(selector).first().getAttribute(attr);
          console.log(`ATTR ${selector}[${attr}] => ${value}`);
          break;
        }
        case "mock-get": {
          const [glob, filePath] = rest;
          const body = fs.readFileSync(filePath, "utf8");
          await page.route(glob, (route) => {
            if (route.request().method() !== "GET") return route.continue();
            route.fulfill({ status: 200, contentType: "application/json", body });
          });
          console.log(`OK mock-get ${glob} -> ${filePath}`);
          break;
        }
        case "get-text": {
          const text = await page.locator(arg).first().textContent();
          console.log(`TEXT ${arg} => ${text}`);
          break;
        }
        case "screenshot": {
          shotCount += 1;
          const name = arg || "shot";
          const file = path.join(screenshotDir, `${String(shotCount).padStart(2, "0")}-${name}.png`);
          await page.screenshot({ path: file, fullPage: true });
          console.log(`OK screenshot -> ${file}`);
          break;
        }
        case "console": {
          if (arg.includes("--errors")) {
            console.log(
              consoleErrors.length === 0
                ? "OK console: no errors captured"
                : `CONSOLE_ERRORS:\n${consoleErrors.join("\n")}`
            );
          }
          break;
        }
        case "sleep": {
          await new Promise((r) => setTimeout(r, Number(arg) || 1000));
          console.log(`OK sleep ${arg}`);
          break;
        }
        case "quit": {
          await browser.close();
          process.exit(0);
        }
        default:
          console.log(`ERR unknown command: ${cmd}`);
      }
    } catch (err) {
      console.log(`ERR ${cmd} ${arg} :: ${err.message.split("\n")[0]}`);
    }
  }

  await browser.close();
}

main();
