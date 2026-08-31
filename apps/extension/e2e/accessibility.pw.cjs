const fs = require("node:fs");
const path = require("node:path");
const { expect, test } = require("@playwright/test");

const axeSource = fs.readFileSync(
  require.resolve("axe-core/axe.min.js"),
  "utf8",
);
const locale = JSON.parse(
  fs.readFileSync(
    path.join(__dirname, "../public/_locales/pt_BR/messages.json"),
    "utf8",
  ),
);
const messages = Object.fromEntries(
  Object.entries(locale).map(([key, value]) => [key, value.message]),
);

const baseCapture = {
  id: "synthetic-accessibility-session",
  status: "recording",
  startedAt: "2026-07-30T12:00:00Z",
  uploadedParts: 3,
  durationMs: 65_000,
  unavailableArtifacts: 0,
  captureFinished: false,
};

test("login and authenticated navigation have no automatic WCAG violations", async ({
  browser,
}) => {
  const login = await scenarioPage(browser, { authenticated: false });
  await audit(login, "login");
  await expect(login.locator("[data-view-heading]")).toBeFocused();
  await login.keyboard.press("Tab");
  await expect(
    login.getByRole("textbox", { name: messages.emailLabel }),
  ).toBeFocused();
  await login
    .getByRole("textbox", { name: messages.emailLabel })
    .fill("teste@example.test");
  await login.keyboard.press("Tab");
  await expect(
    login.getByRole("button", { name: messages.sendAccessLink }),
  ).toBeFocused();
  await login.context().close();

  const page = await scenarioPage(browser, {
    authenticated: true,
    capture: null,
    sessions: [],
  });
  await audit(page, "home");
  await expect(page.locator("[data-view-heading]")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("button", { name: messages.newEvidence }),
  ).toBeFocused();
  for (const name of [
    messages.newEvidence,
    messages.myEvidence,
    messages.settings,
  ]) {
    await page.getByRole("button", { name }).click();
    await audit(page, name);
    await page.getByRole("button", { name: new RegExp(messages.back) }).click();
  }
  await page.context().close();
});

test("stale login recovers when the local API is already authenticated", async ({
  browser,
}) => {
  const page = await scenarioPage(browser, {
    authenticated: [false, false],
    magicLinkStatus: 404,
  });
  await page
    .getByRole("textbox", { name: messages.emailLabel })
    .fill("teste@example.test");
  await page.getByRole("button", { name: messages.sendAccessLink }).click();
  await expect(
    page.getByRole("heading", { name: messages.homeTitle }),
  ).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await page.context().close();
});

test("capture states have no automatic WCAG violations", async ({
  browser,
}) => {
  const scenarios = [
    ["recording", baseCapture],
    [
      "interrupted",
      {
        ...baseCapture,
        status: "interrupted",
        unavailableArtifacts: 1,
      },
    ],
    [
      "error",
      {
        ...baseCapture,
        status: "error",
        error: "Falha sintética de captura.",
      },
    ],
    [
      "complete",
      {
        ...baseCapture,
        status: "complete",
        captureFinished: true,
        packageHash: `sha256:${"a".repeat(64)}`,
        integrityStatus: "complete",
        timestampStatus: "valid",
        blockchainStatus: "confirmed",
        storageStatus: "locked",
      },
    ],
  ];
  for (const [name, capture] of scenarios) {
    await auditScenario(browser, name, {
      authenticated: true,
      capture,
    });
  }
});

async function auditScenario(browser, name, scenario) {
  const page = await scenarioPage(browser, scenario);
  await audit(page, name);
  await page.context().close();
}

async function scenarioPage(browser, scenario) {
  const context = await browser.newContext({
    viewport: { width: 320, height: 640 },
  });
  await context.addInitScript(
    ({ localizedMessages, state }) => {
      globalThis.chrome = {
        i18n: {
          getUILanguage: () => "pt-BR",
          getMessage: (key) => localizedMessages[key] ?? key,
        },
        runtime: {
          sendMessage: async (message) => {
            if (message.type === "GET_STATE") {
              return { ok: true, result: state.capture ?? null };
            }
            if (message.type === "LIST_SESSIONS") {
              return { ok: true, result: state.sessions ?? [] };
            }
            return { ok: true, result: state.capture ?? null };
          },
        },
      };
      globalThis.fetch = async (input) => {
        if (String(input).endsWith("/v1/auth/session")) {
          const authenticated = Array.isArray(state.authenticated)
            ? (state.authenticated.shift() ?? true)
            : state.authenticated;
          return new Response(JSON.stringify({ authenticated }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (String(input).endsWith("/v1/auth/magic-links")) {
          return new Response(
            state.magicLinkStatus === 404
              ? JSON.stringify({ detail: "authentication unavailable" })
              : "{}",
            {
              status: state.magicLinkStatus ?? 200,
              headers: { "Content-Type": "application/json" },
            },
          );
        }
        return new Response("{}", {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      };
    },
    { localizedMessages: messages, state: scenario },
  );
  const page = await context.newPage();
  await page.goto("/popup.html");
  await page.locator("[data-view-heading]").waitFor();
  return page;
}

async function audit(page, name) {
  await page.addScriptTag({ content: axeSource });
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth <=
        document.documentElement.clientWidth,
    ),
    `${name}: horizontal overflow at 320 CSS pixels`,
  ).toBe(true);
  const results = await page.evaluate(async () =>
    globalThis.axe.run(document, {
      runOnly: {
        type: "tag",
        values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"],
      },
    }),
  );
  expect(
    results.violations,
    `${name}: ${results.violations
      .map(
        (violation) =>
          `${violation.id} (${violation.nodes
            .map((node) => node.target.join(" "))
            .join(", ")})`,
      )
      .join("; ")}`,
  ).toEqual([]);
}
