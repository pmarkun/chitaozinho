# Accessibility

The extension popup targets WCAG 2.2 AA. The primary flow uses semantic
headings, labels, native controls, visible keyboard focus, live status/error
announcements and programmatic focus after view changes. It reflows at 320 CSS
pixels. The document language follows the Chrome UI language, and interactive
targets have a minimum size of 24 by 24 CSS pixels.

Automated guards verify AA contrast for normal text and 3:1 contrast for focus
indicators, responsive viewport support, target size, localized document
language, accessible hash names and non-repeating timer announcements.
Playwright renders login, menus and recording, interrupted, error and complete
states at 320 CSS pixels. Axe-core checks WCAG 2.0, 2.1 and 2.2 A/AA rules; the
test also rejects horizontal overflow and verifies the initial keyboard path
and programmatic heading focus.

```sh
nix develop --command playwright test \
  --config apps/extension/playwright.config.cjs
```

## Manual acceptance

Run the primary flow in Chromium at 100% and 400% zoom:

- complete login, start, screenshot, marker, finish and download using only the
  keyboard;
- confirm focus remains visible and moves to the heading after each view change;
- repeat the flow with a screen reader and confirm headings, labels, status,
  errors and results are announced once and in a useful order;
- confirm the popup has no clipped content or two-dimensional scrolling at a
  320 CSS pixel viewport;
- interrupt and resume one capture, confirming that recovery controls and
  errors are operable and announced.

Automated success does not prove screen-reader usability, browser zoom behavior
or the complete real-extension keyboard flow. WCAG 2.2 AA acceptance is
complete only after this manual pass is recorded.
