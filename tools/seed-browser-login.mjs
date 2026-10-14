// Copies the LinkedIn login saved by the LinkedIn MCP server (one --login) into the
// coach's own browser profile, so the user signs in once instead of twice.
//
// Usage:  node tools/seed-browser-login.mjs [--browser chrome|msedge] [--check-only]
// Exit 0 = the browser profile is logged in to LinkedIn. Exit 2 = it is not.

import { chromium } from "playwright";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const kitDir = path.resolve(here, "..");
const profileDir = path.join(kitDir, ".browser-profile");
const cookieFile = path.join(os.homedir(), ".linkedin-mcp", "cookies.json");

const args = process.argv.slice(2);
const browserIdx = args.indexOf("--browser");
const channel = browserIdx !== -1 ? args[browserIdx + 1] : "chrome";
const checkOnly = args.includes("--check-only");

async function isLoggedIn(page) {
  await page.goto("https://www.linkedin.com/feed/", { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(4000);
  const url = page.url();
  // Logged-out visitors are redirected to /login, /authwall, /checkpoint or the public homepage.
  return url.includes("/feed") && !/login|authwall|checkpoint|signup/.test(url);
}

const ctx = await chromium.launchPersistentContext(profileDir, { channel, headless: true });
try {
  const page = ctx.pages()[0] ?? (await ctx.newPage());

  if (!checkOnly) {
    if (!fs.existsSync(cookieFile)) {
      console.log(`NO_COOKIE_FILE ${cookieFile} (run the LinkedIn login first)`);
      process.exitCode = 2;
    } else {
      const cookies = JSON.parse(fs.readFileSync(cookieFile, "utf8"))
        .filter((c) => c.domain && c.domain.includes("linkedin.com"))
        .map((c) => {
          const out = {
            name: c.name,
            value: c.value,
            domain: c.domain,
            path: c.path || "/",
            httpOnly: !!c.httpOnly,
            secure: !!c.secure,
          };
          if (typeof c.expires === "number" && c.expires > 0) out.expires = c.expires;
          if (["Strict", "Lax", "None"].includes(c.sameSite)) out.sameSite = c.sameSite;
          return out;
        });
      await ctx.addCookies(cookies);
      console.log(`SEEDED ${cookies.length} cookies`);
    }
  }

  if (process.exitCode !== 2) {
    const ok = await isLoggedIn(page);
    console.log(ok ? "LOGGED_IN" : `NOT_LOGGED_IN url=${page.url()}`);
    process.exitCode = ok ? 0 : 2;
  }
} finally {
  await ctx.close();
}
