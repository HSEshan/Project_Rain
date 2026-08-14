import GuildSelectionBar from "./GuildSelectionBar";
import EmptyState from "../shared/EmptyState";

/** Route element for /guild — the guild picker with nothing selected yet. */
export default function GuildsHome() {
  return (
    <div className="flex flex-1">
      <GuildSelectionBar />
      <EmptyState
        title="No guild selected"
        hint="Pick a guild on the left, or create one."
      />
    </div>
  );
}
