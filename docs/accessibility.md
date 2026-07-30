# Accessibility

The extension popup targets WCAG 2.2 AA. The primary flow uses semantic
headings, labels, native controls, visible keyboard focus, live status/error
announcements and programmatic focus after view changes. It reflows at 320 CSS
pixels.

Automated guards verify AA contrast for normal text and 3:1 contrast for focus
indicators. Full acceptance still requires a manual pass through login,
capture, interruption/recovery, finalization and download using only the
keyboard and a screen reader in Chromium.
