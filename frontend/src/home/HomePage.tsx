import Card from "./Card";
import { useFriendRequestStore } from "../friends/friendRequestStore";
import GuildCreateModal from "../guild/GuildCreateModal";
import AddFriendModal from "../friends/AddFriendModal";
import { useGuildStore } from "../guild/guildStore";
import { PiUserCirclePlus } from "react-icons/pi";
import { PiShieldPlus } from "react-icons/pi";
import { PiUserGear } from "react-icons/pi";

export default function HomePage() {
  const { setIsModalOpen: setIsModalOpenFriendRequest } =
    useFriendRequestStore();
  const { setModalOpen: setIsModalOpenGuildCreate } = useGuildStore();
  return (
    <div className="flex flex-col items-center justify-top h-screen w-[90%]">
      <AddFriendModal />
      <GuildCreateModal />
      <h1 className="text-4xl text-white font-bold mt-10">Welcome to Rain</h1>
      <div className="flex flex-row items-center justify-center gap-8 mt-10">
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
          title="Customize Profile"
          image={<PiUserGear size={100} />}
          onClick={() => {}}
        />
      </div>
    </div>
  );
}
