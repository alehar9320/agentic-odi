import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: [
      "dist",
      "coverage",
      "src-tauri/target",
      "src/api/schema.d.ts",
      "node_modules",
      // Chromatic's captured archives and the Storybook it builds from them.
      ".vitest",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  reactHooks.configs.flat["recommended-latest"],
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: { ...globals.browser, ...globals.node },
    },
    plugins: { "react-refresh": reactRefresh },
    rules: {
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
    },
  },
  {
    // Copied presentation stays a leaf: props in, markup out. The product
    // wrapper under src/components owns state and passes data down.
    // src/vendor/boundary.test.ts resolves relative specifiers as well, because
    // a string pattern cannot tell "../assistant/plan" from "../../state/x".
    files: ["src/vendor/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@/state/*", "@/api/*", "@/assistant/*", "@/bff/*"],
              message:
                "src/vendor may not import product state, api, assistant, or bff. Take props from a wrapper under src/components.",
            },
          ],
        },
      ],
    },
  },
);
