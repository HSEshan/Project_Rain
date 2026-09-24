/**
 * Turn an axios failure into something worth showing a person.
 *
 * `err.message` is "Request failed with status code 409", which tells the user
 * nothing. FastAPI puts the useful text in `detail`, and a 422 arrives as a
 * list of per-field validation errors instead of a string.
 *
 * **This only works on the original axios error.** An api client that catches
 * an `AxiosError` and rethrows `new Error("...")` throws away `.response`, and
 * everything below then falls through to the no-response branch — which is how
 * every failed signup and login came to say "Cannot reach the server", 409s and
 * 422s included. Let the axios error propagate; decide the wording here.
 */

type ApiError = {
  response?: {
    status?: number;
    data?: { detail?: unknown };
  };
};

/** FastAPI's 422 items. `loc` is like ["body", "password"]. */
type ValidationItem = {
  loc?: unknown[];
  msg?: string;
  type?: string;
};

const FIELD_LABELS: Record<string, string> = {
  username: "Username",
  email: "Email",
  password: "Password",
  name: "Name",
};

/**
 * Pydantic prefixes anything raised as a `ValueError` in a validator, so a
 * message the server wrote for a person arrives as "Value error, Password must
 * ...". Strip it rather than showing it.
 */
const stripPydanticPrefix = (msg: string) =>
  msg.replace(/^(Value error|Assertion failed),\s*/i, "");

function fieldOf(item: ValidationItem): string | undefined {
  const loc = item.loc;
  if (!Array.isArray(loc) || loc.length === 0) return undefined;
  const last = loc[loc.length - 1];
  return typeof last === "string" ? last : undefined;
}

function validationItemText(item: ValidationItem): string | null {
  const field = fieldOf(item);
  const msg = stripPydanticPrefix((item.msg ?? "").trim());
  if (!msg) return null;

  // EmailStr's own message ("value is not a valid email address: An email
  // address must have an @-sign.") explains RFC compliance to someone who
  // typed their address wrong. Say the useful half, matching the wording the
  // signup form's own client-side check already uses.
  if (field === "email") return "Enter a valid email address.";

  const label = field ? FIELD_LABELS[field] : undefined;
  if (!label) return sentence(msg);

  // Messages the server authored already name their field ("Password must
  // ..."), so prefixing would stutter. Pydantic's built-ins start with the
  // type instead ("String should have at least 3 characters") — swapping that
  // first word for the field name reads as though it were written on purpose.
  if (msg.toLowerCase().startsWith(label.toLowerCase())) return sentence(msg);
  if (/^(string|value|input|list|integer)\b/i.test(msg)) {
    return sentence(msg.replace(/^\w+/, label));
  }
  return sentence(`${label} ${msg.charAt(0).toLowerCase()}${msg.slice(1)}`);
}

const sentence = (text: string) => (/[.!?]$/.test(text) ? text : `${text}.`);

export function errorText(error: unknown, fallback: string): string {
  const response = (error as ApiError)?.response;
  const detail = response?.data?.detail;
  const status = response?.status;

  // No response at all: DNS, a dropped connection, CORS, or nothing listening.
  // This is the only case that is actually about reaching the server, and it is
  // checked first so that nothing else can claim it.
  if (!response) return "Cannot reach the server. Check your connection.";

  // Ahead of the detail check on purpose. A 500 says `detail: "Internal Server
  // Error"` and a proxy's 502 is an HTML page; neither is worth showing, and
  // whatever a 5xx does say is about the server's internals, not the user's
  // input.
  if (status && status >= 500) {
    return "The server is having trouble. Try again in a moment.";
  }

  if (typeof detail === "string" && detail.trim()) return sentence(detail.trim());

  if (Array.isArray(detail) && detail.length > 0) {
    // Every failing field, not just the first. Being told about the username
    // only to be told about the password on the next attempt is the same
    // guessing game the password rules avoid.
    const parts = (detail as ValidationItem[])
      .map(validationItemText)
      .filter((part): part is string => !!part);
    if (parts.length > 0) return [...new Set(parts)].join(" ");
  }

  if (status === 401) return "Incorrect email or password.";
  if (status === 429) return "Too many attempts. Wait a moment and try again.";
  return fallback;
}

/**
 * Sign-in copy, where being specific would be the wrong thing to do.
 *
 * The API answers 401 for both an unknown account and a bad password (it used
 * to answer 404 for the first, which let anyone test whether an email had an
 * account). 404 is still collapsed here so that an older server, or a proxy
 * that rewrites the status, cannot reintroduce the leak in the copy.
 */
export function loginErrorText(error: unknown): string {
  const status = (error as ApiError)?.response?.status;
  if (status === 401 || status === 404) return "Incorrect email or password.";
  return errorText(error, "Could not sign you in. Try again.");
}
