/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_GA4_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
