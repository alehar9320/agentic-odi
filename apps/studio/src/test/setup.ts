import "@testing-library/jest-dom/vitest";

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
