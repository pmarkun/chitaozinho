const { test, expect } = require("@playwright/test");
const AxeBuilder = require("axe-core");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

test("Evidências separates capture from validation and credits only Conectas", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/Evidências/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Registre evidências digitais. Compartilhe registros verificáveis.",
  );
  for (const name of [
    "Registre com contexto",
    "Organize e compartilhe",
    "Confira a integridade",
  ]) {
    await expect(
      page.getByRole("heading", { name, exact: true }),
    ).toBeVisible();
  }
  await expect(page.locator("footer")).toContainText("Realização");
  await expect(page.locator("footer")).not.toContainText(/arapy/i);
  await expect(page.locator(".beta-notice")).toContainText(
    "Não guardamos uma cópia para recuperação no servidor.",
  );
  await expect(page.locator(".extension-note")).toContainText("Versão 0.1.5");
  await expect(page.locator("main")).not.toContainText("30 dias");
  await expect(
    page.getByRole("img", { name: "Conectas Direitos Humanos" }),
  ).toBeVisible();
  await page
    .locator(".hero-actions")
    .getByRole("button", { name: "Verificar evidência" })
    .click();
  await expect(page).toHaveURL(/\/validar$/);
  await expect(page.locator("main")).toBeFocused();
  await expect(page.locator(".extension-download")).toHaveCount(0);
  await expect(page.locator(".optional-section[open]")).toHaveCount(0);
  await page.goBack();
  await expect(page.locator(".home-hero")).toBeVisible();
});

test("beta download and keyboard installation instructions work", async ({
  page,
}) => {
  for (const route of ["/"]) {
    await page.goto(route);
    const download = page.getByRole("link", {
      name: "Baixar extensão beta · ZIP",
    });
    await expect(download).toHaveAttribute(
      "href",
      "https://github.com/pmarkun/chitaozinho/releases/download/v0.1.5/chitaozinho-extension-0.1.5.zip",
    );
    const instructions = page.locator(".extension-download summary");
    await instructions.focus();
    await page.keyboard.press("Enter");
    await expect(
      page.getByText("chrome://extensions", { exact: true }),
    ).toBeVisible();
    await expect(page.locator(".extension-download details")).toHaveAttribute(
      "open",
      "",
    );
    await page.keyboard.press("Enter");
    await expect(
      page.locator(".extension-download details"),
    ).not.toHaveAttribute("open", "");
  }
});

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
      name: "Valide um pacote de evidências",
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

  await page.evaluate(() => navigator.serviceWorker.ready);
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
    await page.locator("#package").setInputFiles([]);
    await expect(page.getByRole("alert")).toHaveCount(0);
    await expect(page.locator(".verify-button")).toBeDisabled();
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
      name: "Como o Evidências fortalece uma evidência digital",
    }),
  ).toBeVisible();

  await context.setOffline(true);
  await page.reload();
  await expect(
    page.getByRole("heading", {
      name: "Como o Evidências fortalece uma evidência digital",
    }),
  ).toBeVisible();
});

test("a supplied real package passes entirely in Chromium", async ({
  page,
}) => {
  const packagePath = process.env.CHITAOZINHO_WEB_TEST_PACKAGE;
  const checksumPath = process.env.CHITAOZINHO_WEB_TEST_CHECKSUM;
  test.skip(
    !packagePath || !checksumPath,
    "set the opt-in real-package inputs",
  );

  await page.goto("/validar");
  await page.evaluate(() => navigator.serviceWorker.ready);
  const requestsAfterSelection = [];
  page.on("request", (request) => requestsAfterSelection.push(request.url()));
  await page.locator("#package").setInputFiles(packagePath);
  await page
    .getByText("Adicionar comprovantes opcionais", { exact: true })
    .click();
  await page.locator("#checksum").setInputFiles(checksumPath);
  await page.locator(".verify-button").click();

  await expect(
    page.getByRole("heading", { name: "Integridade confirmada", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Chave certificada pela raiz oficial"),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Baixar complemento temporal" }),
  ).toBeVisible();
  expect(requestsAfterSelection).toHaveLength(2);
  expect(requestsAfterSelection[0]).toMatch(
    /^https:\/\/api\.evidencias\.org\.br\/v1\/public\/proofs\//,
  );
  expect(requestsAfterSelection[1]).toContain("/bundle?");
});
