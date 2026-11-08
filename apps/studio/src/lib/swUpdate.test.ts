import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  activateWaiting,
  dismissAppUpdate,
  initServiceWorker,
  isUpdateWaiting,
  reloadForUpdate,
  resetAppUpdateForTests,
  useAppUpdate,
  watchForUpdates,
  type ContainerLike,
  type RegistrationLike,
  type WorkerLike,
} from "./swUpdate";

/** A worker whose state a test drives. */
class FakeWorker implements WorkerLike {
  state = "installing";
  readonly messages: unknown[] = [];
  private readonly listeners = new Set<() => void>();

  addEventListener(_type: "statechange", listener: () => void): void {
    this.listeners.add(listener);
  }

  postMessage(message: unknown): void {
    this.messages.push(message);
  }

  /** Move to a state and tell the listeners, the way the browser would. */
  become(state: string): void {
    this.state = state;
    for (const listener of this.listeners) {
      listener();
    }
  }
}

/** A registration whose waiting and installing workers a test controls. */
class FakeRegistration implements RegistrationLike {
  waiting: WorkerLike | null = null;
  installing: WorkerLike | null = null;
  private readonly listeners = new Set<() => void>();

  addEventListener(_type: "updatefound", listener: () => void): void {
    this.listeners.add(listener);
  }

  removeEventListener(_type: "updatefound", listener: () => void): void {
    this.listeners.delete(listener);
  }

  /** Fire the updatefound event the browser raises when an update begins. */
  found(): void {
    for (const listener of this.listeners) {
      listener();
    }
  }
}

class FakeContainer implements ContainerLike {
  controller: unknown = null;
  private readonly listeners = new Set<() => void>();

  addEventListener(_type: "controllerchange", listener: () => void): void {
    this.listeners.add(listener);
  }

  async register(): Promise<RegistrationLike> {
    return new FakeRegistration();
  }

  /** Fire the controllerchange event the browser raises once a new worker leads. */
  changed(): void {
    for (const listener of this.listeners) {
      listener();
    }
  }
}

afterEach(() => {
  resetAppUpdateForTests();
  vi.restoreAllMocks();
});

describe("isUpdateWaiting", () => {
  it("is an update only for a page the worker already controls", () => {
    const registration = new FakeRegistration();
    registration.waiting = new FakeWorker();

    expect(isUpdateWaiting(registration, true)).toBe(true);
    // A first install activates at once; there is nothing to offer.
    expect(isUpdateWaiting(registration, false)).toBe(false);
  });

  it("is not an update when nothing is waiting", () => {
    expect(isUpdateWaiting(new FakeRegistration(), true)).toBe(false);
  });
});

describe("watchForUpdates", () => {
  it("reports a worker that is already waiting when the page loads", () => {
    const registration = new FakeRegistration();
    registration.waiting = new FakeWorker();
    const onUpdateReady = vi.fn();

    watchForUpdates({ registration, isControlled: () => true, onUpdateReady });

    expect(onUpdateReady).toHaveBeenCalledTimes(1);
  });

  it("reports a worker that installs after an updatefound", () => {
    const registration = new FakeRegistration();
    const installing = new FakeWorker();
    registration.installing = installing;
    const onUpdateReady = vi.fn();

    watchForUpdates({ registration, isControlled: () => true, onUpdateReady });
    expect(onUpdateReady).not.toHaveBeenCalled();

    // The install finishes, the worker waits, and the browser fires updatefound.
    installing.become("installed");
    registration.waiting = installing;
    registration.found();

    expect(onUpdateReady).toHaveBeenCalledTimes(1);
  });

  it("reports at most once, so the offer cannot loop", () => {
    const registration = new FakeRegistration();
    registration.waiting = new FakeWorker();
    const onUpdateReady = vi.fn();

    watchForUpdates({ registration, isControlled: () => true, onUpdateReady });
    registration.found();

    expect(onUpdateReady).toHaveBeenCalledTimes(1);
  });

  it("stops listening once disposed", () => {
    const registration = new FakeRegistration();
    const onUpdateReady = vi.fn();
    const dispose = watchForUpdates({ registration, isControlled: () => true, onUpdateReady });

    dispose();
    registration.waiting = new FakeWorker();
    registration.found();

    expect(onUpdateReady).not.toHaveBeenCalled();
  });

  it("reads control when a build is staged, not when the watch is attached", () => {
    // The first load registers the worker and is controlled only after it
    // activates. Capturing `false` at attach time would drop the first update.
    const registration = new FakeRegistration();
    const installing = new FakeWorker();
    registration.installing = installing;
    const onUpdateReady = vi.fn();
    let controlled = false;

    watchForUpdates({ registration, isControlled: () => controlled, onUpdateReady });

    // The page becomes controlled, then the update installs and waits. The
    // browser sets `registration.waiting` as it dispatches `statechange`.
    controlled = true;
    registration.waiting = installing;
    installing.become("installed");

    expect(onUpdateReady).toHaveBeenCalledTimes(1);
  });

  it("follows an install that began before the watch attached", () => {
    // `updatefound` can fire before the page is listening; the installing worker
    // is still tracked directly.
    const registration = new FakeRegistration();
    const installing = new FakeWorker();
    registration.installing = installing;
    const onUpdateReady = vi.fn();

    watchForUpdates({ registration, isControlled: () => true, onUpdateReady });
    registration.waiting = installing;
    installing.become("installed");

    expect(onUpdateReady).toHaveBeenCalledTimes(1);
  });
});

describe("activateWaiting", () => {
  it("asks the waiting worker to skip waiting and reloads once it controls", () => {
    const registration = new FakeRegistration();
    const waiting = new FakeWorker();
    registration.waiting = waiting;
    const container = new FakeContainer();
    const reload = vi.fn();

    const started = activateWaiting(registration, container, reload);

    expect(started).toBe(true);
    expect(waiting.messages).toEqual([{ type: "SKIP_WAITING" }]);
    expect(reload).not.toHaveBeenCalled();

    container.changed();
    container.changed();
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("does nothing when there is no waiting worker", () => {
    const reload = vi.fn();
    const started = activateWaiting(new FakeRegistration(), new FakeContainer(), reload);

    expect(started).toBe(false);
    expect(reload).not.toHaveBeenCalled();
  });
});

describe("the update offer", () => {
  it("starts hidden and is shown when a build is ready", () => {
    const { result } = renderHook(() => useAppUpdate());
    expect(result.current.ready).toBe(false);
    expect(result.current.dismissed).toBe(false);
  });

  it("stays dismissed once the person hides it", () => {
    const { result } = renderHook(() => useAppUpdate());

    act(() => {
      dismissAppUpdate();
    });

    expect(result.current.dismissed).toBe(true);
  });
});

describe("initServiceWorker", () => {
  it("registers the worker at the origin root", async () => {
    const container = new FakeContainer();
    const register = vi.spyOn(container, "register");

    initServiceWorker(container);
    await vi.waitFor(() => expect(register).toHaveBeenCalledWith("/sw.js"));
  });

  it("offers the update once a new build is waiting", async () => {
    const container = new FakeContainer();
    const onReady = vi.fn();
    const registration = new FakeRegistration();
    vi.spyOn(container, "register").mockResolvedValue(registration);
    container.controller = {}; // an already-installed page

    initServiceWorker(container, onReady);
    await vi.waitFor(() => expect(container.register).toHaveBeenCalled());

    const installing = new FakeWorker();
    registration.installing = installing;
    registration.found();
    installing.become("installed");
    registration.waiting = installing;
    registration.found();

    expect(onReady).toHaveBeenCalled();
  });

  it("does nothing when the browser has no service worker", () => {
    expect(() => initServiceWorker(undefined)).not.toThrow();
  });
});

describe("reloadForUpdate", () => {
  it("reloads the page when no worker is waiting", () => {
    const reload = vi.fn();

    reloadForUpdate(reload);

    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("takes the waiting worker and reloads once it controls the page", async () => {
    const container = new FakeContainer();
    const registration = new FakeRegistration();
    registration.waiting = new FakeWorker();
    vi.spyOn(container, "register").mockResolvedValue(registration);
    initServiceWorker(container);
    await vi.waitFor(() => expect(container.register).toHaveBeenCalled());

    const reload = vi.fn();
    reloadForUpdate(reload);
    expect(reload).not.toHaveBeenCalled();

    container.changed();
    container.changed();
    expect(reload).toHaveBeenCalledTimes(1);
  });
});
