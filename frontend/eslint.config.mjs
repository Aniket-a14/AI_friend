import { fileURLToPath } from "url";
import path from "path";
import { FlatCompat } from "@eslint/eslintrc";
import js from "@eslint/js";
import tsEslint from "typescript-eslint";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
  recommendedConfig: js.configs.recommended,
});

const eslintConfig = tsEslint.config(
  {
    ignores: [".next/**", "out/**", "build/**", "next-env.d.ts"],
  },
  js.configs.recommended,
  ...tsEslint.configs.recommended,
  ...compat.config({
    extends: ["next/core-web-vitals"],
    rules: {
      // Explicitly disable the broken Next.js parser for everything
      // and ensure we use the TS parser established by tsEslint.config
    },
  }),
  {
    languageOptions: {
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
        ecmaFeatures: {
          jsx: true,
        },
      },
    },
    rules: {
      // Standard Next.js rules are already loaded via compat.config
      "@next/next/no-html-link-for-pages": "error",
    },
  }
);

export default eslintConfig;
