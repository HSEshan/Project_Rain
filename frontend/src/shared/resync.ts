/**
 * "Your state may be stale, refetch."
 *
 * A dead gateway, a crashed consumer, a Redis outage and a closed laptop lid all
 * produce the same symptom: the client is behind the database and does not know
 * it. One signal repairs all of them, because refetching does not care *why*
 * state drifted.
 *
 * `AppInitializer` already does this work, but only on mount. Nothing ran it
 * when the websocket came back, so every event published during a disconnect
 * was lost until the user reloaded the page.
 *
 * Stores subscribe at module scope, the same way they subscribe to the event
 * bus, so a refetch happens whether or not the relevant view is mounted.
 *
 * The industrial version of this is Discord's sequence number plus RESUME,
 * where the server replays only the gap. This is that design's fallback path —
 * what it does when the gap is too old to replay — which is why it is the right
 * thing to build first. See devnotes.md, Appendix D6.
 */

type ResyncHandler = () => void;

const handlers = new Set<ResyncHandler>();

/** Subscribe a store to resync. Returns an unsubscribe, mostly for tests. */
export function onResync(handler: ResyncHandler): () => void {
  handlers.add(handler);
  return () => handlers.delete(handler);
}

/**
 * Fired by `WebSocketProvider` when a connection is re-established, never on
 * the first connect: `AppInitializer` has just fetched everything.
 */
export function emitResync(): void {
  handlers.forEach((handler) => {
    try {
      handler();
    } catch (error) {
      // One store failing to refetch must not stop the others
      console.error("Resync handler failed", error);
    }
  });
}
