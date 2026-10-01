# Chromium extension

Manifest V3 extension implemented with React, TypeScript and Vite.

Build inside the Nix environment:

```sh
nix develop --command pnpm --filter @chitaozinho/extension build
```

For the POC, open `chrome://extensions`, enable developer mode, choose
**Load unpacked**, and select `apps/extension/dist`. Start the API on
`http://127.0.0.1:8000` before beginning a capture.

The popup and manifest use Chrome's native locale selection, with pt-BR as the
default and an equivalent English catalog.

Starting a new capture requires separate capture consent and explicit acceptance
of the current Terms of Use. `terms.html` includes the full approved Portuguese
text offline, sourced from `packages/project-content/terms.json` along with the
website. The background rejects missing/obsolete versions; the local signed
`capture_started` event records acceptance and the terms version. Acceptance is
reset for each new capture, without changing existing session formats.

Capture records video and output audio from the selected Chrome tab, not the
whole computer or microphone. An AudioContext restores local tab playback while
MediaRecorder keeps the original audio/video stream. Playback resources and
tracks are released on stop or startup failure. Validate audibility and the
downloaded WebM with a real tone/video before releasing a new extension build.

The screen/window mode uses Chrome's explicit desktopCapture picker. Audio is
requested only when `canRequestAudioTrack` permits it, and absence of an audio
track is shown in the popup and recorded in the signed event chain. System audio
availability varies by OS, browser version and selected surface; it is not a
cross-platform guarantee. Cancellation fails without falling back to a tab.
This mode does not collect an unrelated tab's DOM, URL, scroll or screenshots.
External sharing stop preserves chunks and marks the capture interrupted.
The new desktopCapture permission needs justification in the Chrome Store.

Microphone capture is opt-in, off by default and requires Chrome permission.
For first use, open the dedicated authorization page, grant access and return
to the popup. The permission probe stops its tracks immediately and never
records/uploads audio. The offscreen recorder then mixes microphone and source
audio into the recorded WebM only (not speaker playback), with 0.5 gain per
source. Use headphones to avoid acoustic echo. Denial/startup failure does not
silently continue a requested microphone capture. Device disconnection marks
the recording interrupted. Signed markers identify requested/present sources.
