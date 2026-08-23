import { defineConfig } from "vitest/config";

// Unit tests run in a plain Node environment (no DOM needed for the manifest /
// resolver contract tests). Add jsdom + @testing-library later for component tests.
export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
