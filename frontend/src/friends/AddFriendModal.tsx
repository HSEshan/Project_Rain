import { useRef, useState } from "react";
import { FiAtSign } from "react-icons/fi";
import Modal from "../shared/Modal";
import { Button } from "../shared/Button";
import { Input } from "../shared/Input";
import { errorText } from "../shared/errors";
import { useFriendStore } from "./friendStore";
import { createFriendRequest } from "./apiClient";

type Result = { ok: boolean; text: string } | null;

export default function AddFriendModal() {
  const usernameRef = useRef<HTMLInputElement>(null);
  const { isModalOpen, setIsModalOpen } = useFriendStore();
  const [result, setResult] = useState<Result>(null);
  const [sending, setSending] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const username = usernameRef.current?.value.trim();
    if (!username) {
      setResult({ ok: false, text: "Enter a username first." });
      return;
    }

    setSending(true);
    try {
      await createFriendRequest(username);
      setResult({ ok: true, text: `Request sent to ${username}.` });
      if (usernameRef.current) usernameRef.current.value = "";
    } catch (err) {
      setResult({ ok: false, text: errorText(err, "Could not send that request.") });
    } finally {
      setSending(false);
    }
  };

  const handleClose = () => {
    setResult(null);
    setIsModalOpen(false);
  };

  return (
    <Modal
      isOpen={isModalOpen}
      onClose={handleClose}
      title="Add a friend"
      description="Send a request by username. A DM channel opens as soon as they accept."
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Username"
          name="username"
          ref={usernameRef}
          placeholder="Their exact username"
          icon={<FiAtSign size={15} />}
          autoFocus
        />

        {result && (
          <p
            className={`rounded-xl border px-3.5 py-2.5 text-sm ${
              result.ok
                ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300"
                : "border-red-500/25 bg-red-500/10 text-red-300"
            }`}
          >
            {result.text}
          </p>
        )}

        <div className="flex gap-3 pt-1">
          <Button type="button" onClick={handleClose} full>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={sending} full>
            Send request
          </Button>
        </div>
      </form>
    </Modal>
  );
}
