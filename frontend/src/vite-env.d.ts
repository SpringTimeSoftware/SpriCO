/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare const __SPRICO_FRONTEND_BUILD_TIMESTAMP__: string
declare const __SPRICO_FRONTEND_PACKAGE_VERSION__: string
declare const __SPRICO_FRONTEND_BUILD_MARKER__: string
