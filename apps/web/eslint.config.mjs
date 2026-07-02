import base from "@gulp/config/eslint.config.base.mjs";

export default [
  // next-env.d.ts is Next-generated (triple-slash refs by design).
  { ignores: ["next-env.d.ts"] },
  ...base,
];
