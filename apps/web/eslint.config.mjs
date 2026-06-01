import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

const eslintConfig = [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    // The `_`-prefixed test fixture holds TS-syntax source stripped into a
    // .mjs for a parser test; it is not meant to be linted as JavaScript.
    ignores: [
      ".next/**",
      "out/**",
      "build/**",
      "next-env.d.ts",
      "src/__tests__/_filter_dsl_stripped.mjs",
    ],
  },
];

export default eslintConfig;
