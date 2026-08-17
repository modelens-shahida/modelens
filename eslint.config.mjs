import { defineConfig } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";

const eslintConfig = [
  {
    ignores: [".venv/**", "node_modules/**", ".next/**"]
  },
  ...nextVitals,
  {
    rules: {
      "react-hooks/exhaustive-deps": "warn",
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/immutability": "off",
      "react/no-unescaped-entities": "off",
      "react/jsx-no-undef": "warn",
      "@next/next/no-img-element": "off"
    }
  }
];

export default eslintConfig;
