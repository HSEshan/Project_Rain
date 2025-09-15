import { useRef, useState } from "react";
import Modal from "../shared/Modal";
import { useFriendRequestStore } from "./friendRequestStore";
import FriendRequestList from "./FriendRequestList";
import { createFriendRequest } from "./apiClient";

export default function AddFriendModal() {
  const usernameRef = useRef<HTMLInputElement>(null);
  const { isModalOpen, setIsModalOpen } = useFriendRequestStore();
  const [response, setResponse] = useState<string>("");
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!usernameRef.current?.value) {
      setResponse("Please enter a username");
      return;
    }
    await createFriendRequest(usernameRef.current?.value)
      .then(() => {
        setResponse(`Friend request sent to ${usernameRef.current?.value}`);
      })
      .catch((err: Error) => {
        setResponse(err.message);
      });
  };
  const handleClose = () => {
    setResponse("");
    setIsModalOpen(false);
  };

  return (
    <Modal isOpen={isModalOpen} onClose={handleClose} title="Add Friend">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label
            htmlFor="username"
            className="block text-sm font-medium text-gray-300 mb-2"
          >
            Username *
          </label>
          <input
            id="username"
            ref={usernameRef}
            type="text"
            placeholder="Enter username"
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        <div className="flex flex-col gap-2">
          <h4 className="text-sm font-medium text-gray-300">Friend Requests</h4>
          <FriendRequestList />
        </div>

        <div className="flex gap-3 pt-4">
          <button
            type="button"
            onClick={handleClose}
            className="flex-1 px-4 py-2 text-gray-300 bg-gray-700 hover:bg-gray-600 rounded-md transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-md transition-colors"
          >
            Add Friend
          </button>
        </div>
        {response && <p className="text-center text-sm">{response}</p>}
      </form>
    </Modal>
  );
}
