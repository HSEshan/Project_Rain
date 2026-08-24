/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Public repository, linked from the landing page. */
  readonly VITE_GIT_REPO_URL?: string;
  /** Swagger UI path. rest_api runs with root_path=/api, so it is /api/docs. */
  readonly VITE_API_DOCS_PATH?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
