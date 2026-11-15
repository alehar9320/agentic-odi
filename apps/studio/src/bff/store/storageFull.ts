import { StorageFullError, isQuotaExceededError } from "../errors";

/**
 * The pause a full disk puts on writes, and the one translation that turns a
 * browser quota failure into something a caller can act on.
 *
 * It lives at the store boundary because that is where a browser refuses a
 * write. Once one write is refused for space, every later write fails fast —
 * before it touches the database — so nothing piles up against a quota that
 * cannot clear itself on a timer. Reads are never routed through here, so the
 * work already stored stays readable and exportable while writes are paused.
 *
 * `Reuses:` the `subscribe`/listeners shape from `updater/service.ts`, and
 * `BffError`/`isQuotaExceededError` from `bff/errors.ts`.
 */
export class StorageWriteGuard {
  private full = false;
  private readonly listeners = new Set<() => void>();

  get storageFull(): boolean {
    return this.full;
  }

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  /**
   * Run one write. While paused it rejects without calling `write`; a quota
   * failure is translated to `StorageFullError` and pauses every later write.
   */
  async run<T>(write: () => Promise<T>): Promise<T> {
    if (this.full) {
      throw new StorageFullError();
    }
    try {
      return await write();
    } catch (error) {
      if (isQuotaExceededError(error)) {
        this.pause();
        throw new StorageFullError();
      }
      throw error;
    }
  }

  private pause(): void {
    if (this.full) {
      return;
    }
    this.full = true;
    for (const listener of this.listeners) {
      listener();
    }
  }
}
