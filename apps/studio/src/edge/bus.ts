/**
 * One sentence between tabs: the ladder moved.
 *
 * IndexedDB already holds the shared truth; what a tab cannot learn by itself
 * is that the truth changed while it was not looking. Without this, a "yes" in
 * one tab leaves the offer standing in another until that tab's next turn
 * happens to re-read storage — and Settings keeps showing a tier that stopped
 * existing a moment ago.
 */

const CHANNEL_NAME = "agentic-odi-edge-ladder";

export interface LadderBus {
  /** Tell the other tabs to go and look for themselves. */
  publish(): void;
  /** Stop listening. A page-level owner that was reset never leaks a listener. */
  close(): void;
}

/**
 * Deliberately contentless. Which tier landed, and whether the person consented,
 * is storage's answer and each tab reads it its own way — so no tab can pick up
 * another's download and announce it as the model it fetched. A browser without
 * `BroadcastChannel` (or one that refuses it, as private browsing does) gets a
 * silent bus: the ladder still works alone in a single tab.
 */
export function createLadderBus(onChange: () => void): LadderBus {
  let channel: BroadcastChannel | null = null;
  try {
    if (typeof BroadcastChannel !== "undefined") {
      channel = new BroadcastChannel(CHANNEL_NAME);
      channel.onmessage = () => onChange();
    }
  } catch {
    channel = null;
  }
  return {
    publish() {
      channel?.postMessage("changed");
    },
    close() {
      if (channel) {
        channel.onmessage = null;
        channel.close();
      }
      channel = null;
    },
  };
}
