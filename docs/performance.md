# Capture performance gate

Measure the same public page and Chrome profile twice, without interacting with
other tabs. Close unrelated tabs first.

```sh
nix develop --command scripts/measure-browser-resources \
  baseline 30 /tmp/chitaozinho-performance.csv
nix develop --command scripts/measure-browser-resources \
  capture 75 /tmp/chitaozinho-performance.csv
nix develop --command uv run python scripts/analyze_browser_resources.py \
  /tmp/chitaozinho-performance.csv \
  --output /tmp/chitaozinho-performance-report.json
```

Leave the page idle during `baseline`. Start a 60-second Chitãozinho capture
immediately after starting the `capture` phase, then finalize it. The CSV
records aggregate Chrome CPU, resident memory and process I/O once per second.
Aggregate browser metrics are intentionally used because stable per-extension
process attribution is not available to a Chromium extension.

The analyzer uses the observed wall-clock interval rather than assuming one
sample per second, compares both phases, applies the limits below and binds the
JSON report to the source CSV with SHA-256. A non-passing resource gate exits
with status 1.

For the POC, investigate before acceptance if capture adds more than 25 average
CPU percentage points, 250 MiB peak RSS, or 100 MiB of browser writes per
minute compared with baseline, or if scrolling and controls visibly stop
responding. Record the machine, Chrome version, page, result and CSV hash in
`docs/smoke-tests.md`.
