import eslint from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  {
    ignores: ["dist/**", "test-results/**"],
  },
  {
    files: ["public/sw.js", "e2e/**/*.cjs", "playwright.config.cjs"],
    languageOptions: {
      sourceType: "commonjs",
      globals: {
        __dirname: "readonly",
        caches: "readonly",
        document: "readonly",
        fetch: "readonly",
        globalThis: "readonly",
        module: "readonly",
        navigator: "readonly",
        process: "readonly",
        require: "readonly",
        self: "readonly",
        URL: "readonly",
      },
    },
    rules: {
      "@typescript-eslint/no-require-imports": "off",
    },
  },
);
