import { vi } from "vitest";

/**
 * A `localStorage` that refuses one operation, which is what a browser with
 * storage disabled or a full quota actually does: the method throws rather than
 * handing back `null`. The other methods keep working off a plain map, so a test
 * that refuses the write can still assert what the app painted during the
 * session, and `attempts()` proves the stub was the one that answered.
 */
export function refusingStorage(
  failing: "getItem" | "setItem" | "removeItem",
): { attempts: () => number; restore: () => void } {
  const store = new Map<string, string>();
  for (let index = 0; index < window.localStorage.length; index += 1) {
    const key = window.localStorage.key(index);
    if (key !== null) {
      store.set(key, window.localStorage.getItem(key) ?? "");
    }
  }
  const calls = { getItem: 0, setItem: 0, removeItem: 0 };

  const fake: Storage = {
    get length() {
      return store.size;
    },
    key: (index: number) => [...store.keys()][index] ?? null,
    getItem: (key: string) => {
      calls.getItem += 1;
      if (failing === "getItem") {
        throw new Error("SecurityError: the browser will not hand out storage");
      }
      return store.get(key) ?? null;
    },
    setItem: (key: string, value: string) => {
      calls.setItem += 1;
      if (failing === "setItem") {
        throw new Error("QuotaExceededError: the browser will not keep this");
      }
      store.set(key, value);
    },
    removeItem: (key: string) => {
      calls.removeItem += 1;
      if (failing === "removeItem") {
        throw new Error("SecurityError: the browser will not forget this");
      }
      store.delete(key);
    },
    clear: () => {
      store.clear();
    },
  };

  vi.stubGlobal("localStorage", fake);

  return {
    attempts: () => calls[failing],
    restore: () => {
      vi.unstubAllGlobals();
    },
  };
}
