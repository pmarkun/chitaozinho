// Run explicitly with scripts/test-hash-only-capture (isolated browser and database).
const { test, expect, chromium } = require("@playwright/test");
const { mkdtempSync, readFileSync, existsSync } = require("node:fs");
const { tmpdir } = require("node:os");
const path = require("node:path");
const { execFileSync, spawn } = require("node:child_process");

test("real extension captures locally, sends no content, and downloads a verifiable ZIP", async () => {
  test.setTimeout(90_000);
  const root = path.resolve(__dirname, "../../..");
  const temporary = mkdtempSync(path.join(tmpdir(), "evidencias-capture-"));
  const env = {
    ...process.env,
    CHITAOZINHO_ENV: "test",
    CHITAOZINHO_AUTH_MODE: "development",
    CHITAOZINHO_EVIDENCE_MODE: "hash_only",
    CHITAOZINHO_DATABASE_URL: `sqlite:///${temporary}/api.db`,
    CHITAOZINHO_STORAGE_PATH: `${temporary}/evidence`,
    CHITAOZINHO_PROOFS_PATH: `${temporary}/proofs`,
    CHITAOZINHO_SERVER_SEED_HEX: "11".repeat(32),
    CHITAOZINHO_SERVER_KEY_ID: "integration",
  };
  execFileSync("uv", ["run", "alembic", "upgrade", "head"], {
    cwd: root,
    env,
    stdio: "pipe",
  });
  const api = spawn(
    "uv",
    [
      "run",
      "uvicorn",
      "chitaozinho_api.main:app",
      "--host",
      "127.0.0.1",
      "--port",
      "8000",
      "--no-access-log",
    ],
    { cwd: root, env, stdio: "pipe" },
  );
  let context;
  try {
    await expect
      .poll(async () => {
        if (api.exitCode !== null)
          throw new Error("isolated API failed to start (check port 8000)");
        return fetch("http://127.0.0.1:8000/readyz")
          .then((r) => r.status)
          .catch(() => 0);
      })
      .toBe(200);
    const extension = path.join(root, "apps/extension/dist");
    context = await chromium.launchPersistentContext(
      path.join(temporary, "profile"),
      {
        channel: "chromium",
        headless: true,
        acceptDownloads: true,
        downloadsPath: path.join(temporary, "downloads"),
        args: [
          `--disable-extensions-except=${extension}`,
          `--load-extension=${extension}`,
        ],
      },
    );
    const worker =
      context.serviceWorkers()[0] ??
      (await context.waitForEvent("serviceworker"));
    const id = new URL(worker.url()).host;
    await context.setOffline(true);
    const termsPage = await context.newPage();
    await termsPage.goto(`chrome-extension://${id}/terms.html`);
    await expect(termsPage).toHaveTitle("Termos de Uso — Evidências");
    await expect(termsPage.locator("main ol li")).toHaveCount(4);
    await termsPage.close();
    await context.setOffline(false);
    const page = await context.newPage();
    await page.goto("http://127.0.0.1:8000/healthz");
    await page.setContent(
      "<title>PRIVATE_CAPTURE_TITLE</title><h1>PRIVATE_CAPTURE_SENTINEL</h1><p>Synthetic evidence only</p>",
    );
    const popup = await context.newPage();
    await popup.goto(`chrome-extension://${id}/popup.html`);
    const requests = [];
    context.on("request", (request) => {
      if (request.url().includes("127.0.0.1:8000/v1/"))
        requests.push({
          url: request.url(),
          body: request.postData(),
          headers: request.headers(),
        });
    });
    for (const termsVersion of [undefined, "obsolete"]) {
      const rejected = await popup.evaluate(
        (version) =>
          chrome.runtime.sendMessage({
            type: "START_CAPTURE",
            consent: true,
            termsVersion: version,
          }),
        termsVersion,
      );
      expect(rejected.ok).toBe(false);
      expect(rejected.error).toContain(
        "acceptance of current terms is required",
      );
    }
    expect(requests).toHaveLength(0);
    const started = await popup.evaluate(async () => {
      const tabs = await chrome.tabs.query({ url: "http://127.0.0.1:8000/*" });
      await chrome.tabs.update(tabs[0].id, { active: true });
      return chrome.runtime.sendMessage({
        type: "START_CAPTURE",
        termsVersion: "2026-10-01",
        consent: true,
      });
    });
    expect(started.ok, JSON.stringify(started)).toBe(true);
    const acceptance = await popup.evaluate(async () => {
      const request = globalThis.indexedDB.open("chitaozinho");
      return await new Promise((resolve) => {
        request.onsuccess = () => {
          const records = request.result
            .transaction("sessions")
            .objectStore("sessions")
            .getAll();
          records.onsuccess = () =>
            resolve(
              records.result[0]?.localEvents?.find(
                (event) => event.type === "capture_started",
              )?.data,
            );
        };
      });
    });
    expect(acceptance).toMatchObject({
      terms_accepted: true,
      terms_version: "2026-10-01",
    });
    const stopped = await popup.evaluate(() =>
      chrome.runtime.sendMessage({ type: "STOP_CAPTURE" }),
    );
    expect(stopped.ok, JSON.stringify(stopped)).toBe(true);
    expect(stopped.result.storageStatus).toBe("hash_only");
    expect(JSON.stringify(requests)).not.toMatch(
      /PRIVATE_CAPTURE_(TITLE|SENTINEL)/,
    );
    for (const request of requests) {
      if (request.headers["x-entry-json"]) {
        expect(
          Buffer.from(request.headers["x-entry-json"], "base64url").toString(),
        ).not.toMatch(/PRIVATE_CAPTURE_(TITLE|SENTINEL)/);
      }
    }
    expect(requests.some((request) => /\/parts\/\d+$/.test(request.url))).toBe(
      false,
    );
    expect(
      requests.some((request) => /\/parts\/\d+\/hash$/.test(request.url)),
    ).toBe(true);
    expect(existsSync(path.join(temporary, "evidence"))).toBe(false);
    expect(
      readFileSync(path.join(temporary, "api.db")).includes(
        Buffer.from("PRIVATE_CAPTURE_SENTINEL"),
      ),
    ).toBe(false);
    await expect
      .poll(() =>
        popup.evaluate(
          async () =>
            (await chrome.downloads.search({})).filter(
              (item) => item.state === "complete",
            ).length,
        ),
      )
      .toBe(2);
    const downloads = await popup.evaluate(() => chrome.downloads.search({}));
    const zip = downloads.find((item) => item.mime === "application/zip");
    expect(zip).toBeTruthy();
    expect(zip.filename.startsWith(temporary)).toBe(true);
    const key = execFileSync(
      "uv",
      [
        "run",
        "python",
        "-c",
        "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat; print(Ed25519PrivateKey.from_private_bytes(bytes.fromhex('11'*32)).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex())",
      ],
      { cwd: root, encoding: "utf8" },
    ).trim();
    const report = execFileSync(
      "cargo",
      [
        "run",
        "-q",
        "-p",
        "chitaozinho-verifier",
        "--",
        "verify",
        zip.filename,
        "--trusted-server-key-hex",
        key,
        "--json",
      ],
      { cwd: root, encoding: "utf8" },
    );
    expect(JSON.parse(report).result).toMatch(/^integral/);
    expect(JSON.parse(report).checks).toContain("hash_only_custody");
    console.log(
      `Capture result: ${JSON.parse(report).result}; unavailable artifacts: ${stopped.result.unavailableArtifacts}`,
    );
    // The local cached package can be downloaded again without the API.
    api.kill("SIGTERM");
    const requestCount = requests.length;
    const replay = await popup.evaluate(
      (sessionId) =>
        chrome.runtime.sendMessage({ type: "DOWNLOAD_PACKAGE", sessionId }),
      stopped.result.id,
    );
    expect(replay.ok, JSON.stringify(replay)).toBe(true);
    expect(requests.length).toBe(requestCount);
    console.log(
      `Synthetic capture and ZIP retained for inspection: ${temporary}`,
    );
  } finally {
    await context?.close();
    api.kill("SIGTERM");
  }
});
