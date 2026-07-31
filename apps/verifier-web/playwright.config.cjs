const { defineConfig } = require("@playwright/test");
const path = require("node:path");

module.exports = defineConfig({
  testDir: path.join(__dirname, "e2e"),
  testMatch: "**/*.pw.cjs",
  timeout: 30_000,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:4174",
    browserName: "chromium",
    headless: true,
    viewport: { width: 1280, height: 900 },
    ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? {
          launchOptions: {
            executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
          },
        }
      : {}),
  },
  webServer: {
    command: "python3 -m http.server 4174 --bind 127.0.0.1 --directory dist",
    cwd: __dirname,
    url: "http://127.0.0.1:4174/",
    reuseExistingServer: false,
  },
});
