const { test, expect } = require("@playwright/test");
const AxeBuilder = require("axe-core");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

test("public pages stay accessible on desktop and mobile", async ({
  browser,
}) => {
  for (const viewport of [
    { width: 1280, height: 900 },
    { width: 360, height: 800 },
  ]) {
    const context = await browser.newContext({ viewport });
    const page = await context.newPage();
    await page.addInitScript({ content: AxeBuilder.source });
    for (const route of ["/", "/validar", "/metodologia"]) {
      await page.goto(route);
      const result = await page.evaluate(async () =>
        globalThis.axe.run(document, {
          runOnly: {
            type: "tag",
            values: [
              "wcag2a",
              "wcag2aa",
              "wcag21a",
              "wcag21aa",
              "wcag22a",
              "wcag22aa",
            ],
          },
        }),
      );
      expect(result.violations, `${route} at ${viewport.width}px`).toEqual([]);
      expect(
        await page.evaluate(
          () =>
            document.documentElement.scrollWidth <=
            document.documentElement.clientWidth,
        ),
        `${route} overflows at ${viewport.width}px`,
      ).toBe(true);
    }
    await context.close();
  }
});

test("public verifier stays local and has no automatic WCAG violations", async ({
  page,
}) => {
  await page.addInitScript({ content: AxeBuilder.source });
  await page.goto("/validar");
  await expect(
    page.getByRole("heading", {
      name: "Confirme a integridade de uma evidência",
    }),
  ).toBeVisible();

  const axeResult = await page.evaluate(async () =>
    globalThis.axe.run(document, {
      runOnly: {
        type: "tag",
        values: [
          "wcag2a",
          "wcag2aa",
          "wcag21a",
          "wcag21aa",
          "wcag22a",
          "wcag22aa",
        ],
      },
    }),
  );
  expect(axeResult.violations).toEqual([]);

  const requestsAfterSelection = [];
  page.on("request", (request) => requestsAfterSelection.push(request.url()));
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "chitaozinho-web-"));
  const invalidPackage = path.join(temporary, "invalid.zip");
  fs.writeFileSync(invalidPackage, "not a zip");
  try {
    await page.locator("#package").setInputFiles(invalidPackage);
    await page.locator(".verify-button").click();
    await expect(
      page.getByRole("alert").getByText("Pacote inválido ou não verificável"),
    ).toBeVisible();
    expect(requestsAfterSelection).toEqual([]);
  } finally {
    fs.rmSync(temporary, { recursive: true, force: true });
  }
});

test("the same production build reloads every public route offline", async ({
  page,
  context,
}) => {
  await page.goto("/metodologia");
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.reload();
  await expect(
    page.getByRole("heading", {
      name: "Como o Chitãozinho fortalece uma evidência digital",
    }),
  ).toBeVisible();

  await context.setOffline(true);
  await page.reload();
  await expect(
    page.getByRole("heading", {
      name: "Como o Chitãozinho fortalece uma evidência digital",
    }),
  ).toBeVisible();
});

test("a supplied real package passes entirely in Chromium", async ({
  page,
}) => {
  const packagePath = process.env.CHITAOZINHO_WEB_TEST_PACKAGE;
  const checksumPath = process.env.CHITAOZINHO_WEB_TEST_CHECKSUM;
  const trustedKey = process.env.CHITAOZINHO_WEB_TEST_SERVER_KEY;
  test.skip(
    !packagePath || !checksumPath || !trustedKey,
    "set the opt-in real-package inputs",
  );

  await page.goto("/validar");
  const requestsAfterSelection = [];
  page.on("request", (request) => requestsAfterSelection.push(request.url()));
  await page.locator("#package").setInputFiles(packagePath);
  await page.locator("#checksum").setInputFiles(checksumPath);
  await page.locator("#trusted-key").fill(trustedKey);
  await page.locator(".verify-button").click();

  await expect(
    page.getByRole("heading", { name: "Integridade confirmada", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Chave confirmada separadamente")).toBeVisible();
  expect(requestsAfterSelection).toEqual([]);
});
