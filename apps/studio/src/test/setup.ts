import "@testing-library/jest-dom/vitest";

// assistant-ui's viewport measures the scroll container. jsdom has no layout,
// so the observer only needs to exist and to be inert.
class ResizeObserverMock {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

Object.defineProperty(globalThis, "ResizeObserver", {
  value: ResizeObserverMock,
  configurable: true,
});

// Node exposes an experimental localStorage global that shadows jsdom's and
// lacks clear/removeItem. Replace it with a small deterministic store so the
// app and the tests share one working implementation.
class MemoryStorage implements Storage {
  private readonly store = new Map<string, string>();

  get length(): number {
    return this.store.size;
  }

  clear(): void {
    this.store.clear();
  }

  getItem(key: string): string | null {
    return this.store.has(key) ? (this.store.get(key) as string) : null;
  }

  key(index: number): string | null {
    return Array.from(this.store.keys())[index] ?? null;
  }

  removeItem(key: string): void {
    this.store.delete(key);
  }

  setItem(key: string, value: string): void {
    this.store.set(key, String(value));
  }
}

Object.defineProperty(globalThis, "localStorage", {
  value: new MemoryStorage(),
  configurable: true,
});

// jsdom does not implement ResizeObserver, which the assistant-ui viewport
// primitives subscribe to. Provide a no-op stub so the studio shell can render.
if (typeof globalThis.ResizeObserver === "undefined") {
  class ResizeObserver {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  Object.defineProperty(globalThis, "ResizeObserver", {
    value: ResizeObserver,
    configurable: true,
    writable: true,
  });
}

// jsdom 31 does not implement object URLs. Node's `URL.createObjectURL` is still
// reachable and looks callable, but it reads a Node `Blob`'s internal buffer and
// throws on jsdom's `Blob` ("Cannot read properties of undefined (reading
// '_buffer')"), so a `typeof` guard in the component cannot detect it. Give the
// environment a working pair; tests that assert on downloads stub these
// themselves and `vi.unstubAllGlobals()` restores this pair afterwards.
let objectUrlCount = 0;

Object.defineProperty(globalThis.URL, "createObjectURL", {
  value: () => `blob:jsdom/${++objectUrlCount}`,
  configurable: true,
  writable: true,
});

Object.defineProperty(globalThis.URL, "revokeObjectURL", {
  value: () => {},
  configurable: true,
  writable: true,
});
