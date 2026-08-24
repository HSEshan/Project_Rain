/**
 * Outbound links shown on the landing page.
 *
 * Read from the Vite env (`frontend/.env`, written by `generate_env_files.py`)
 * so a fork points at its own repository without editing a component. The
 * fallbacks keep the buttons working when the file is missing, which is the
 * difference between a stale link and one that reads "undefined".
 */

const DEFAULT_GIT_REPO_URL = "https://github.com/HSEshan/Project_Rain";
const DEFAULT_API_DOCS_PATH = "/api/docs";

export const GIT_REPO_URL =
  import.meta.env.VITE_GIT_REPO_URL?.trim() || DEFAULT_GIT_REPO_URL;

/**
 * Same origin as the app: Caddy proxies `/api/*` to rest_api, which serves
 * Swagger UI under its `root_path`. Only reachable while the backend runs with
 * `DOCS=true`.
 */
export const API_DOCS_URL =
  import.meta.env.VITE_API_DOCS_PATH?.trim() || DEFAULT_API_DOCS_PATH;
