# Accessibility

The extension popup targets WCAG 2.2 AA. The primary flow uses semantic
headings, labels, native controls, visible keyboard focus, live status/error
announcements and programmatic focus after view changes. It reflows at 320 CSS
pixels. The document language follows the Chrome UI language, and interactive
targets have a minimum size of 24 by 24 CSS pixels.

Automated guards verify AA contrast for normal text and 3:1 contrast for focus
indicators, responsive viewport support, target size, localized document
language, accessible hash names and non-repeating timer announcements.

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

WCAG 2.2 AA acceptance is complete only after this manual pass is recorded.
