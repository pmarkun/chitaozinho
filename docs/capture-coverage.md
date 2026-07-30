# Capture coverage

The metadata artifact records coverage without claiming access the browser did
not provide:

- the top-level DOM is serialized when scripting is allowed;
- iframe pixels may appear in screenshots and video, but nested documents are
  not serialized and the capture is marked incomplete when frames exist;
- canvas and WebGL are covered only by visible viewport pixels; backing buffers
  and WebGL contexts are not inspected;
- media with attached EME `MediaKeys` is declared unavailable; decrypted DRM
  content is never extracted;
- protected browser pages that reject scripting preserve visual artifacts as
  best effort and explicitly declare DOM and feature detection unavailable.

Coverage details are stored under `capture_coverage` in
`capture/metadata.json`. Material limitations are copied to the signed
`known_gaps` list, so the API and offline verifier report an incomplete capture
instead of silently presenting it as complete.
