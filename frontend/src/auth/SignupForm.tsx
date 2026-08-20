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
 * Client-side rules mirror the backend `UserCreate` model. They exist to give
 * instant feedback, not to enforce anything — the server still validates.
 */
function validate(values: Fields): Partial<Fields> {
  const errors: Partial<Fields> = {};
  if (values.username.trim().length < 3)
    errors.username = "At least 3 characters.";
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(values.email))
    errors.email = "Enter a valid email address.";
  if (values.password.length < 8)
    errors.password = "At least 8 characters.";
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
        setFormError(errorText(err, "Could not create that account."));
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
