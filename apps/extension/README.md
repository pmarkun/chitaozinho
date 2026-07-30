# Chromium extension

Manifest V3 extension implemented with React, TypeScript and Vite.

Build inside the Nix environment:

```sh
nix develop --command pnpm --filter @chitaozinho/extension build
```

For the POC, open `chrome://extensions`, enable developer mode, choose
**Load unpacked**, and select `apps/extension/dist`. Start the API on
`http://127.0.0.1:8000` before beginning a capture.
