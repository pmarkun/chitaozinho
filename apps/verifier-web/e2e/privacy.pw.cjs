const { test, expect, chromium, firefox, webkit } = require("@playwright/test");
const axe = require("axe-core");

for (const [name, engine] of Object.entries({ chromium, firefox, webkit })) {
  for (const viewport of [
    { width: 1280, height: 900 },
    { width: 360, height: 800 },
  ]) {
    test(`privacy: ${name} ${viewport.width}px`, async () => {
      const browser = await test.step("Launch browser", () =>
        engine.launch({ timeout: 10_000 }),
      );
      // This matrix checks policy navigation, not offline service-worker
      // lifecycle (covered by verifier.pw.cjs). Isolate that lifecycle on WebKit.
      const context = await browser.newContext({
        viewport,
        serviceWorkers: "block",
      });
      await context.tracing.start({ screenshots: true, snapshots: true });
      const page = await test.step("Create page", () => context.newPage());
      await page.addInitScript({ content: axe.source });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      try {
        await page.goto("http://127.0.0.1:4174/", {
          waitUntil: "domcontentloaded",
        });
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
        await context.tracing.stop({
          path: test.info().outputPath("privacy-trace.zip"),
        });
        await context.close();
        await browser.close();
      }
    });
  }
}
