/**
 * The single screen-reader announcer (#701 D47).
 *
 * Outcome announcements — copy, export, save, connect, mark-read — all used to
 * render their own `role="status"` region, so a burst of three actions spoke
 * over one another and the last one won. One hook, one live region: a burst is
 * three sentences in order, never three overlapping regions, and a region that
 * stays mounted can never be missed by a reader that arrived late.
 */

export type Announce = (message: string) => void;

/** No-op for components rendered outside a provider (SSR, unit tests). */
export const noopAnnounce: Announce = () => {};