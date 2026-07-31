import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { relative, resolve } from "node:path";

const extensionRoot = import.meta.dirname;
const repositoryRoot = resolve(extensionRoot, "../..");
const packageMetadata = JSON.parse(
  readFileSync(resolve(extensionRoot, "package.json"), "utf8"),
) as { version: string };
const commit = git(["rev-parse", "HEAD"]);
const dirty = git([
  "status",
  "--porcelain",
  "--",
  "apps/extension",
  "packages/protocol-ts",
  "pnpm-lock.yaml",
]);
const buildIdentity = {
  name: "Chitãozinho Chromium Extension",
  version: packageMetadata.version,
  commit: dirty ? `${commit}-dirty` : commit,
  build_hash: sourceHash([
    resolve(extensionRoot, "src"),
    resolve(extensionRoot, "public"),
    resolve(extensionRoot, "offscreen.html"),
    resolve(extensionRoot, "popup.html"),
    resolve(extensionRoot, "package.json"),
    resolve(repositoryRoot, "packages/protocol-ts/src"),
    resolve(repositoryRoot, "pnpm-lock.yaml"),
  ]),
};
const endpoints = {
  api: process.env.CHITAOZINHO_API_BASE_URL ?? "http://127.0.0.1:8000",
  verifier:
    process.env.CHITAOZINHO_VERIFIER_URL ??
    "https://verifier-web-staging.up.railway.app/validar",
  environment: process.env.CHITAOZINHO_ENVIRONMENT ?? "desenvolvimento",
};

export default defineConfig({
  plugins: [react()],
  define: {
    __CHITAOZINHO_BUILD__: JSON.stringify(buildIdentity),
    __CHITAOZINHO_ENDPOINTS__: JSON.stringify(endpoints),
  },
  resolve: {
    alias: {
      "@chitaozinho/protocol": resolve(
        import.meta.dirname,
        "../../packages/protocol-ts/src/index.ts",
      ),
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        popup: resolve(import.meta.dirname, "popup.html"),
        offscreen: resolve(import.meta.dirname, "offscreen.html"),
        background: resolve(import.meta.dirname, "src/background.ts"),
      },
      output: {
        entryFileNames: "assets/[name].js",
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]",
      },
    },
  },
});

function git(arguments_: string[]): string {
  return execFileSync("git", arguments_, {
    cwd: repositoryRoot,
    encoding: "utf8",
  }).trim();
}

function sourceHash(roots: string[]): string {
  const files = roots.flatMap(filesUnder).sort();
  const digest = createHash("sha256");
  for (const file of files) {
    digest.update(relative(repositoryRoot, file));
    digest.update("\0");
    digest.update(readFileSync(file));
    digest.update("\0");
  }
  return `sha256:${digest.digest("hex")}`;
}

function filesUnder(path: string): string[] {
  if (!statSync(path).isDirectory()) return [path];
  return readdirSync(path, { withFileTypes: true }).flatMap((entry) =>
    filesUnder(resolve(path, entry.name)),
  );
}
