/**
 * Turn an axios failure into something worth showing a person.
 *
 * `err.message` is "Request failed with status code 409", which tells the user
 * nothing. FastAPI puts the useful text in `detail`, and a 422 arrives as a
 * list of validation errors instead of a string.
 */
export function errorText(error: unknown, fallback: string): string {
  const response = (
    error as { response?: { status?: number; data?: { detail?: unknown } } }
  )?.response;
  const detail = response?.data?.detail;

  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]) {
    const first = detail[0] as { msg?: string };
    if (first.msg) return String(first.msg);
  }
  if (response?.status === 401) return "Incorrect email or password.";
  if (!response) return "Cannot reach the server. Check your connection.";
  return fallback;
}
