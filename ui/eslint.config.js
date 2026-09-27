import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";

/* Vite compila JSX pero NO comprueba identificadores: una prop que se usa y no
 * se declara pasa el build y revienta en el navegador. Esta configuracion es
 * para atrapar exactamente eso antes de compilar. */
export default [
  {
    files: ["src/**/*.{js,jsx}"],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: "module",
      globals: { ...globals.browser },
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { "react-hooks": reactHooks },
    rules: {
      "no-undef": "error",
      "no-unused-vars": ["warn", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
      "react-hooks/rules-of-hooks": "error",
    },
  },
];
