/**
 * The orientation tour.
 *
 * A short pass over the three rail destinations and the guild channel list,
 * aimed at someone who has just landed in the demo account and has never seen
 * the app. Each step points at a real element by its `data-tour` attribute
 * rather than at a coordinate, so the layout can change without breaking it.
 */

export type TourPlacement = "top" | "bottom" | "left" | "right";

export interface TourStep {
  id: string;
  /** Value of the `data-tour` attribute on the element to spotlight. */
  target: string;
  title: string;
  body: string;
  /** Preferred side for the tooltip; the overlay flips it if it will not fit. */
  placement?: TourPlacement;
  /**
   * Where this step needs the app to be. `":guild"` is replaced with the first
   * guild the account is in, and the step is skipped when there is none.
   *
   * Give every step one. A step that only moves the spotlight along the rail
   * while the page behind it stays put reads as the tour having frozen: the
   * app has to visibly arrive at whatever the step is describing.
   */
  route?: string;
  /**
   * Below `lg` the channel list is an off-canvas drawer, so a step pointing at
   * it has to open the drawer first or it would spotlight nothing.
   */
  needsPanel?: boolean;
}

export const TOUR_STEPS: TourStep[] = [
  {
    id: "home",
    target: "nav-home",
    title: "This is the rail",
    body:
      "Your three destinations live here. It is a column on a desktop and a bar along the bottom on a phone. You are on Home now, which summarises what is waiting for you.",
    placement: "right",
    route: "/home",
  },
  {
    id: "messages",
    target: "nav-messages",
    title: "Friends and direct messages",
    body:
      "This is where that button lands you. Everyone you are friends with, plus a conversation for each. A friend request that arrives while you are here shows up without a reload, and the badge counts the ones you have not answered.",
    placement: "right",
    route: "/dm",
  },
  {
    id: "guilds",
    target: "nav-guilds",
    title: "Guilds",
    body:
      "Servers, each with its own text and voice channels and its own member list. The demo account is already an admin of one, so you can create channels and invite people.",
    placement: "right",
    route: "/guild",
  },
  {
    id: "channels",
    target: "guild-channels",
    title: "Text and voice channels",
    body:
      "Text channels behave like the direct messages. Click a voice channel and you join a real call on the self-hosted SFU, with anyone already in it listed underneath.",
    placement: "right",
    route: "/guild/:guild",
    needsPanel: true,
  },
];
