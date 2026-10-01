const { test, expect, chromium, firefox, webkit } = require("@playwright/test");
const axe = require("axe-core");

for (const [name, engine] of Object.entries({ chromium, firefox, webkit })) {
  for (const viewport of [
    { width: 1280, height: 900 },
    { width: 360, height: 800 },
  ]) {
    test(`privacy: ${name} ${viewport.width}px`, async () => {
      const browser = await test.step("Launch browser", () =>
        engine.launch({ timeout: 10_000 }));
      // This matrix checks policy navigation, not offline service-worker
      // lifecycle (covered by verifier.pw.cjs). Isolate that lifecycle on WebKit.
      const context = await browser.newContext({
        viewport,
        serviceWorkers: "block",
      });
      const page = await test.step("Create page", () => context.newPage());
      await page.addInitScript({ content: axe.source });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      try {
        await page.goto("http://127.0.0.1:4174/", {
          waitUntil: "domcontentloaded",
        });
        for (const [label, id] of [
          ["O que é", "o-que-e"],
          ["Quem faz", "quem-faz"],
        ]) {
          const link = page
            .getByRole("navigation", { name: "Sobre o projeto" })
            .getByRole("link", { name: label, exact: true });
          await link.focus();
          await page.keyboard.press("Enter");
          await expect(page).toHaveURL(new RegExp(`#${id}$`));
          await expect(page.locator(`#${id}`)).toBeInViewport();
        }
        await expect(page.locator(".home-about").last()).toContainText(
          "em parceria com a Conectas Direitos Humanos",
        );
        await expect(
          page.getByRole("list", { name: "Realizadores" }).getByRole("img"),
        ).toHaveCount(5);
        for (const logo of await page
          .locator(".organization-logos img")
          .all()) {
          expect(
            await logo.evaluate((img) => img.complete && img.naturalWidth > 0),
          ).toBe(true);
        }
        await page
          .getByRole("link", { name: "Termos de Uso", exact: true })
          .click();
        await expect(page).toHaveURL(/\/termos-de-uso$/);
        await expect(page).toHaveTitle("Termos de Uso — Evidências");
        await expect(page.locator("main")).toBeFocused();
        await expect(page.locator("main ol li")).toHaveCount(4);
        await expect(page.locator("main")).toContainText(
          "única e integralmente responsável",
        );
        expect(
          await page.evaluate(
            () =>
              document.documentElement.scrollWidth <=
              document.documentElement.clientWidth,
          ),
        ).toBe(true);
        expect(
          (
            await page.evaluate(() =>
              axe.run(document, {
                runOnly: {
                  type: "tag",
                  values: ["wcag2a", "wcag2aa", "wcag21aa"],
                },
              }),
            )
          ).violations,
        ).toEqual([]);
        await page.goBack({ waitUntil: "domcontentloaded" });
        const homeAudit = await page.evaluate(() =>
          axe.run(document, {
            runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] },
          }),
        );
        expect(homeAudit.violations).toEqual([]);
        expect(
          await page.evaluate(
            () =>
              document.documentElement.scrollWidth <=
              document.documentElement.clientWidth,
          ),
        ).toBe(true);
        await page
          .getByRole("link", { name: "Política de privacidade" })
          .click();
        await expect(page).toHaveURL(/\/privacidade$/);
        await expect(page).toHaveTitle("Política de privacidade — Evidências");
        await expect(page.locator("main")).toBeFocused();
        await expect(page.locator("main")).toContainText("12 meses");
        await expect(page.locator("main")).toContainText("30 dias");
        await expect(page.locator(".privacy-status")).toContainText(
          "rotina diária",
        );
        await expect(page.locator("main a").first()).toHaveAttribute(
          "href",
          "mailto:contato@evidencias.org.br",
        );
        await page.locator("main a").first().focus();
        await expect(page.locator("main a").first()).toBeFocused();
        expect(
          await page.evaluate(
            () =>
              document.documentElement.scrollWidth <=
              document.documentElement.clientWidth,
          ),
        ).toBe(true);
        const result = await page.evaluate(() =>
          axe.run(document, {
            runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] },
          }),
        );
        expect(result.violations).toEqual([]);
        await page.getByRole("button", { name: "Início", exact: true }).click();
        await expect(page).toHaveURL("http://127.0.0.1:4174/");
        await page.goBack({ waitUntil: "domcontentloaded" });
        await expect(page.getByRole("heading", { level: 1 })).toHaveText(
          "Política de privacidade",
        );
        expect(errors).toEqual([]);
      } finally {
        await context.close();
        await browser.close();
      }
    });
  }
}

test("terms are readable on the public construction host", async ({ page }) => {
  await page.route("https://evidencias.org.br/**", async (route) => {
    const url = new URL(route.request().url());
    const response = await route.fetch({
      url: `http://127.0.0.1:4174${url.pathname}`,
    });
    await route.fulfill({ response });
  });
  await page.goto("https://evidencias.org.br/termos-de-uso");
  await expect(page).toHaveTitle("Termos de Uso — Evidências");
  await expect(page.locator("main ol li")).toHaveCount(4);
  await page.getByRole("link", { name: "Voltar ao início" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Evidências",
  );
  await expect(
    page.getByText("SITE EM CONSTRUÇÃO", { exact: true }),
  ).toBeVisible();
});
