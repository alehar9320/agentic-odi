/**
 * The browser's cross-tab channel, small and synchronous.
 *
 * Tests that need to watch one tab react to another use this instead of the
 * real `BroadcastChannel`: delivery is immediate, so the assertions are about
 * what the ladder does with the news rather than about when the event loop
 * happens to run.
 */

class Channel {
  static open: Channel[] = [];

  onmessage: ((event: { data: unknown }) => void) | null = null;
  closed = false;

  constructor(readonly name: string) {
    Channel.open.push(this);
  }

  postMessage(data: unknown): void {
    // The spec's rule that matters here: a channel never receives its own
    // message. Two tabs echoing a notice back and forth would be a loop.
    for (const other of Channel.open) {
      if (other !== this && !other.closed && other.name === this.name) {
        other.onmessage?.({ data });
      }
    }
  }

  close(): void {
    this.closed = true;
  }
}

/** Put the fake where a browser keeps its own, and hand back the way to undo it. */
export function installFakeBroadcastChannel(): () => void {
  const real = globalThis.BroadcastChannel;
  Channel.open = [];
  globalThis.BroadcastChannel = Channel as unknown as typeof BroadcastChannel;
  return () => {
    globalThis.BroadcastChannel = real;
    Channel.open = [];
  };
}
