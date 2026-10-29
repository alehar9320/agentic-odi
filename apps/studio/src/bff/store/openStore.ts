import { IndexedDbLocalStore } from "./indexedDbStore";
import { MemoryLocalStore } from "./memoryStore";
import type { LocalStore } from "./types";

export async function openLocalStore(): Promise<LocalStore> {
  if (typeof indexedDB === "undefined") {
    return new MemoryLocalStore();
  }
  try {
    return await IndexedDbLocalStore.open();
  } catch {
    // Private browsing and hardened WebViews can deny IndexedDB. The studio
    // still works for the session, and the capability manifest says so.
    return new MemoryLocalStore();
  }
}
