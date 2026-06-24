// Shared flat ESLint config base. Extend from each package's eslint.config.mjs.
import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    ignores: ["dist/**", ".next/**", "node_modules/**"],
  },
);
