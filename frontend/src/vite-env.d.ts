/// <reference types="vite/client" />

interface ImportMetaEnv {
  // 打包（Tauri / vite build）时由 .env.production 注入，指向本地后端；开发期为空走 vite proxy。
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
