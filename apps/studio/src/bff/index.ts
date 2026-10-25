import type { CanvasData } from "../types";
import type { LocalStore } from "./store/types";
import { openLocalStore } from "./store/openStore";
import { LocalDataService } from "./data/localDataService";
import { LocalMemoryService } from "./memory/localMemoryService";
import { ChatOrchestrator } from "./chat/orchestrator";
import { CapabilityRegistry, capabilityRegistry } from "./capabilities/registry";

export class StudioBff {
  readonly store: LocalStore;
  readonly data: LocalDataService;
  readonly memory: LocalMemoryService;
  readonly chat: ChatOrchestrator;
  readonly capabilities: CapabilityRegistry;

  constructor(store: LocalStore) {
    this.store = store;
    this.data = new LocalDataService(store);
    this.memory = new LocalMemoryService(store);
    this.chat = new ChatOrchestrator(store, this.data, this.memory);
    this.capabilities = capabilityRegistry;
  }

  async init(): Promise<void> {
    // Forces the store to open eagerly so later calls are not awaiting open.
    await this.store.nextSeq().catch(() => undefined);
  }

  async fetchCanvas(): Promise<CanvasData> {
    return this.data.fetchCanvas();
  }
}

let studioBffPromise: Promise<StudioBff> | null = null;

export async function getStudioBff(): Promise<StudioBff> {
  if (!studioBffPromise) {
    studioBffPromise = (async () => {
      const store = await openLocalStore();
      const bff = new StudioBff(store);
      await bff.init();
      return bff;
    })();
  }
  return studioBffPromise;
}

export async function resetStudioBffForTests(): Promise<void> {
  const current = studioBffPromise;
  studioBffPromise = null;
  if (current) {
    try {
      (await current).store.close();
    } catch {
      /* ignore */
    }
  }
}
