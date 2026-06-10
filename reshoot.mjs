import { chromium } from "playwright";
const browser = await chromium.launch({ args: ["--no-sandbox"] });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
await page.goto("http://localhost:3300/", { waitUntil: "networkidle" });
await page.waitForTimeout(1800);
await page.screenshot({ path: "/tmp/shots/landing-fraunces.png" });
await browser.close();
