/// <reference types="vite/client" />

/** Build date (YYYY-MM-DD) injected by vite.config.ts at build time. */
declare const __STUDIO_BUILD_DATE__: string;

/** Git commit or build id injected at build time; "dev" in local builds. */
declare const __STUDIO_BUILD_COMMIT__: string;

/** App version injected from the release manifest at build time. */
declare const __STUDIO_APP_VERSION__: string;

interface ImportMetaEnv {
  /** `on` / `off` override for the first-run wizard feature flag. */
  readonly VITE_STUDIO_FIRST_RUN_WIZARD?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
