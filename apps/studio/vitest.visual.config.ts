import { chromaticPlugin } from "@chromatic-com/vitest/plugin";
import { playwright } from "@vitest/browser-playwright";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/**
 * Chromatic's visual tests run in Vitest Browser Mode, so they get their own
 * config: the unit suite in `vite.config.ts` stays on jsdom and never needs a
 * browser.
 *
 * Two deliberate limits keep the monthly snapshot bill small. Chromatic bills
 * `tests × builds × browsers × viewports`, so browser mode only picks up
 * `*.visual.test.tsx` files, and every one of them renders in the same single
 * Chromium instance at the same viewport. Adding a component to visual review
 * is therefore an explicit, reviewable act: one new file, not a wider glob.
 */
export default defineConfig({
  plugins: [
    react(),
    chromaticPlugin({
      // Pausing animations at their end frame means shimmer and fade-in
      // components diff on real changes instead of on capture timing.
      pauseAnimationAtEnd: true,
    }),
  ],
  test: {
    include: ["src/**/*.visual.test.tsx"],
    browser: {
      enabled: true,
      headless: true,
      provider: playwright(),
      instances: [{ browser: "chromium", viewport: { width: 900, height: 700 } }],
    },
  },
});
