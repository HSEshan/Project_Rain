import GuildSelectionBar from "./GuildSelectionBar";
import GuildInviteList from "./GuildInviteList";
import EmptyState from "../shared/EmptyState";

/** Route element for /guild — the guild picker with nothing selected yet. */
export default function GuildsHome() {
  return (
    <div className="flex flex-1">
      <GuildSelectionBar />
      <div className="flex-1 flex flex-col items-center justify-center gap-8 p-6">
        <EmptyState
          title="No guild selected"
          hint="Pick a guild on the left, or create one."
        />
        {/* Renders nothing when there are no invites */}
        <GuildInviteList />
      </div>
    </div>
  );
}
