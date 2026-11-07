/// <reference types="vite/client" />

/** Build date (YYYY-MM-DD) injected by vite.config.ts at build time. */
declare const __STUDIO_BUILD_DATE__: string;

/** App version from the build-info source, injected by vite.config.ts. */
declare const __STUDIO_APP_VERSION__: string;

/** Git commit sha injected at build time; "dev" in a source checkout. */
declare const __STUDIO_BUILD_COMMIT__: string;
/** Build version injected by vite.config.ts from apps/studio/package.json. */
declare const __STUDIO_VERSION__: string;

interface ImportMetaEnv {
  /** `on` / `off` override for the first-run wizard feature flag. */
  readonly VITE_STUDIO_FIRST_RUN_WIZARD?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
