import Card from "./Card";
import { useFriendStore } from "../friends/friendStore";
import { useGuildStore } from "../guild/guildStore";
import { PiUserCirclePlus } from "react-icons/pi";
import { PiShieldPlus } from "react-icons/pi";
import { PiUsersThree } from "react-icons/pi";
import { PiEnvelopeOpen } from "react-icons/pi";

export default function HomePage() {
  const {
    setIsModalOpen: setIsModalOpenFriendRequest,
    friendRequests,
  } = useFriendStore();
  const {
    setModalOpen: setIsModalOpenGuildCreate,
    invites,
    setInviteInboxOpen,
  } = useGuildStore();

  return (
    <div className="flex flex-col items-center justify-top h-screen w-[90%]">
      <h1 className="text-4xl text-white font-bold mt-10">Welcome to Rain</h1>
      {/* Wraps: a fourth card overflows a narrow window otherwise */}
      <div className="flex flex-row flex-wrap items-center justify-center gap-8 mt-10">
        <Card
          title="Add Friends"
          image={<PiUserCirclePlus size={100} />}
          onClick={() => {
            setIsModalOpenFriendRequest(true);
          }}
        />
        <Card
          title="Create a Guild"
          image={<PiShieldPlus size={100} />}
          onClick={() => {
            setIsModalOpenGuildCreate(true);
          }}
        />
        <Card
          title="Friend Requests"
          image={<PiUsersThree size={100} />}
          badge={friendRequests.length}
          onClick={() => {
            setIsModalOpenFriendRequest(true);
          }}
        />
        <Card
          title="Guild Invites"
          image={<PiEnvelopeOpen size={100} />}
          badge={invites.length}
          onClick={() => {
            setInviteInboxOpen(true);
          }}
        />
      </div>
    </div>
  );
}
