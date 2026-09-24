import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { FiAtSign, FiLock, FiMail } from "react-icons/fi";
import type { AxiosResponse } from "axios";
import { Button } from "../shared/Button";
import { Input } from "../shared/Input";
import { errorText } from "../shared/errors";
import { postSignup } from "./apiClient";

type Fields = { username: string; email: string; password: string };

/**
 * The backend's `UserCreate` rules, restated.
 *
 * They exist for instant feedback and enforce nothing — the server validates
 * again and is the only thing that decides. What matters is that they do not
 * *disagree*: this used to check length alone, so a username with a space or a
 * password with no digit passed here and failed there, and the person was
 * corrected twice, differently, for one mistake. The wording below is the
 * wording the server would have used.
 *
 * If a rule changes in `rest_api/src/auth/schemas.py`, change it here too.
 */
const USERNAME_MIN_LENGTH = 3;
const PASSWORD_MIN_LENGTH = 8;
const PASSWORD_MAX_LENGTH = 20;

function passwordProblem(password: string): string | undefined {
  const clauses: string[] = [];
  if (
    password.length < PASSWORD_MIN_LENGTH ||
    password.length > PASSWORD_MAX_LENGTH
  ) {
    clauses.push(
      `be between ${PASSWORD_MIN_LENGTH} and ${PASSWORD_MAX_LENGTH} characters`
    );
  }

  const missing = [
    !/[A-Z]/.test(password) && "an uppercase letter",
    !/[a-z]/.test(password) && "a lowercase letter",
    !/[0-9]/.test(password) && "a number",
    !/[!@#$%^&*()_+\-=[\]{}|;:,.<>?/]/.test(password) && "a special character",
  ].filter((item): item is string => !!item);

  // Everything at once, like the server: revealing one rule per attempt turns
  // choosing a password into a guessing game.
  if (missing.length > 0) {
    const last = missing.pop() as string;
    clauses.push(
      "contain " + (missing.length ? `${missing.join(", ")} and ${last}` : last)
    );
  }
  if (clauses.length === 0) return undefined;
  return `Password must ${clauses.join(", and ")}.`;
}

function validate(values: Fields): Partial<Fields> {
  const errors: Partial<Fields> = {};

  if (values.username.length < USERNAME_MIN_LENGTH) {
    errors.username = `Username must be at least ${USERNAME_MIN_LENGTH} characters.`;
  } else if (!/^[a-zA-Z0-9_]+$/.test(values.username)) {
    errors.username =
      "Username can only contain letters, numbers and underscores.";
  }

  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(values.email)) {
    errors.email = "Enter a valid email address.";
  }

  const password = passwordProblem(values.password);
  if (password) errors.password = password;

  return errors;
}

export default function SignupForm({ onDone }: { onDone: () => void }) {
  const navigate = useNavigate();

  const usernameRef = useRef<HTMLInputElement>(null);
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);

  const [errors, setErrors] = useState<Partial<Fields>>({});
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");

    const values: Fields = {
      username: usernameRef.current?.value || "",
      email: emailRef.current?.value || "",
      password: passwordRef.current?.value || "",
    };
    const found = validate(values);
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    setSubmitting(true);
    await postSignup(values.username, values.email, values.password)
      .then((res: AxiosResponse) => {
        if (res.status === 201) {
          navigate("/login?signup=true");
          onDone();
        }
      })
      .catch((err: unknown) => {
        setFormError(
          errorText(err, "Could not create that account. Try again.")
        );
      })
      .finally(() => setSubmitting(false));
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5" noValidate>
      <div>
        <h2 className="text-2xl font-bold text-white">Create your account</h2>
        <p className="mt-1.5 text-sm text-ink-400">
          Free, and takes about ten seconds.
        </p>
      </div>

      <Input
        label="Username"
        name="username"
        type="text"
        autoComplete="username"
        placeholder="How people will find you"
        icon={<FiAtSign size={15} />}
        error={errors.username}
        ref={usernameRef}
      />
      <Input
        label="Email"
        name="email"
        type="email"
        autoComplete="email"
        placeholder="you@example.com"
        icon={<FiMail size={15} />}
        error={errors.email}
        ref={emailRef}
      />
      <Input
        label="Password"
        name="password"
        type="password"
        autoComplete="new-password"
        placeholder="At least 8 characters"
        icon={<FiLock size={15} />}
        error={errors.password}
        ref={passwordRef}
      />

      {formError && (
        <p className="rounded-xl border border-red-500/25 bg-red-500/10 px-3.5 py-2.5 text-sm text-red-300">
          {formError}
        </p>
      )}

      <Button type="submit" variant="primary" size="lg" full loading={submitting}>
        {submitting ? "Creating…" : "Create account"}
      </Button>
    </form>
  );
}
