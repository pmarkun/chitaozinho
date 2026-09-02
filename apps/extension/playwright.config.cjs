const path = require("node:path");

module.exports = {
  testDir: path.join(__dirname, "e2e"),
  testMatch: "**/*.pw.cjs",
  timeout: 30_000,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:4173",
    browserName: "chromium",
    viewport: { width: 320, height: 640 },
  },
  webServer: {
    command:
      "CHITAOZINHO_API_BASE_URL=https://api-staging.up.railway.app " +
      "CHITAOZINHO_VERIFIER_URL=https://verifier-web-staging.up.railway.app/validar " +
      "CHITAOZINHO_ENVIRONMENT=beta pnpm build && " +
      "python -m http.server 4173 --bind 127.0.0.1 --directory dist",
    cwd: __dirname,
    url: "http://127.0.0.1:4173/popup.html",
    reuseExistingServer: false,
    timeout: 15_000,
  },
};
