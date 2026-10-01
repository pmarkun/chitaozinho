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

test("capture requires separate consent and acceptance of the current terms", async ({
  browser,
}) => {
  const page = await scenarioPage(
    browser,
    { authenticated: true, capture: null },
    { width: 360, height: 420 },
  );
  await page.getByRole("button", { name: messages.newEvidence }).click();
  const start = page.getByRole("button", {
    name: messages.startCapture,
    exact: true,
  });
  const consent = page.getByRole("checkbox", {
    name: messages.captureConsent,
    exact: true,
  });
  const terms = page.getByRole("checkbox", {
    name: messages.termsAcceptance,
    exact: true,
  });
  await expect(start).toBeDisabled();
  await consent.check();
  await expect(start).toBeDisabled();
  await terms.check();
  await expect(start).toBeEnabled();
  await consent.uncheck();
  await expect(start).toBeDisabled();
  await consent.check();
  await terms.uncheck();
  await expect(start).toBeDisabled();
  const [termsPage] = await Promise.all([
    page.context().waitForEvent("page"),
    page.getByRole("link", { name: messages.readTerms }).click(),
  ]);
  await expect(termsPage).toHaveTitle("Termos de Uso — Evidências");
  await expect(termsPage.locator("main ol li")).toHaveCount(4);
  await audit(termsPage, "offline terms");
  await termsPage.close();
  await terms.focus();
  await page.keyboard.press("Space");
  await expect(terms).toBeChecked();
  await start.click();
  expect(
    await page.evaluate(() =>
      globalThis.sentMessages.find(
        (message) => message.type === "START_CAPTURE",
      ),
    ),
  ).toMatchObject({ consent: true, termsVersion: "2026-10-01" });
  await page.getByRole("button", { name: messages.newEvidence }).click();
  await expect(
    page.getByRole("checkbox", { name: messages.termsAcceptance, exact: true }),
  ).not.toBeChecked();
  await expect(start).toBeDisabled();
  await audit(page, "terms acceptance in short popup");
  await page.context().close();
});

test("anonymous beta opens directly without requesting email", async ({
  browser,
}) => {
  test.skip(process.env.CHITAOZINHO_E2E_AUTH_MODE !== "anonymous");
  const page = await scenarioPage(browser, {
    authenticated: false,
    capture: null,
  });
  await expect(
    page.getByRole("textbox", { name: messages.emailLabel }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: messages.homeTitle }),
  ).toBeVisible();
  await audit(page, "anonymous beta home");
  await page.context().close();
});

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

test("beta warning remains visible without horizontal overflow in a short popup", async ({
  browser,
}) => {
  const page = await scenarioPage(
    browser,
    { authenticated: false },
    { width: 360, height: 420 },
  );
  await expect(page.getByText(messages.betaTitle)).toBeVisible();
  await expect(page.getByText(messages.betaRetention)).toBeVisible();
  await expect(page.getByText(messages.betaNoImmutability)).toBeVisible();
  await audit(page, "short beta login");
  await page.context().close();
});

test("stale login recovers when the local API is already authenticated", async ({
  browser,
}) => {
  const page = await scenarioPage(browser, {
    authenticated: [false, true],
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
        storageStatus: "stored",
      },
    ],
    [
      "expired",
      {
        ...baseCapture,
        status: "complete",
        captureFinished: true,
        storageStatus: "expired",
      },
    ],
    [
      "bitcoin proof available",
      {
        ...baseCapture,
        status: "complete",
        captureFinished: true,
        blockchainStatus: "bitcoin_attestation_available",
        storageStatus: "stored",
      },
    ],
    [
      "expiration failed",
      {
        ...baseCapture,
        status: "complete",
        captureFinished: true,
        storageStatus: "expiration_failed",
      },
    ],
  ];
  for (const [name, capture] of scenarios) {
    const page = await auditScenario(browser, name, {
      authenticated: true,
      capture,
    });
    if (name === "bitcoin proof available") {
      await expect(
        page.getByText(messages.bitcoinAttestationAvailable),
      ).toBeVisible();
    }
    await page.context().close();
  }
});

test("source selection and missing audio are accessible in tall and short popups", async ({
  browser,
}) => {
  for (const height of [420, 640]) {
    const page = await scenarioPage(
      browser,
      { authenticated: true, capture: null },
      { width: 360, height },
    );
    await page.getByRole("button", { name: messages.newEvidence }).click();
    const source = page.getByRole("combobox", { name: messages.captureSource });
    await expect(source).toHaveValue("tab");
    const microphone = page.getByRole("checkbox", {
      name: messages.includeMicrophone,
    });
    await expect(microphone).not.toBeChecked();
    await microphone.check();
    await expect(
      page.getByRole("button", { name: messages.authorizeMicrophone }),
    ).toBeVisible();
    await microphone.uncheck();
    await source.selectOption("desktop");
    await expect(page.getByText(messages.desktopAudioNotice)).toBeVisible();
    await audit(page, `source selection ${height}`);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= globalThis.innerWidth,
      ),
    ).toBe(true);
    await page.context().close();
  }
  const page = await scenarioPage(browser, {
    authenticated: true,
    capture: {
      ...baseCapture,
      captureSource: "desktop",
      recordingAudio: false,
    },
  });
  await expect(page.getByText(messages.audioUnavailable)).toBeVisible();
  await audit(page, "desktop without audio");
  await page.context().close();
});

async function auditScenario(browser, name, scenario) {
  const page = await scenarioPage(browser, scenario);
  await audit(page, name);
  return page;
}

async function scenarioPage(
  browser,
  scenario,
  viewport = { width: 360, height: 640 },
) {
  const context = await browser.newContext({
    viewport,
  });
  await context.addInitScript(
    ({ localizedMessages, state }) => {
      globalThis.sentMessages = [];
      globalThis.chrome = {
        i18n: {
          getUILanguage: () => "pt-BR",
          getMessage: (key) => localizedMessages[key] ?? key,
        },
        runtime: {
          sendMessage: async (message) => {
            globalThis.sentMessages.push(message);
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
    `${name}: horizontal overflow at 360 CSS pixels`,
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
