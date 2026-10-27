import { apiUrl } from "../bridge/desktopBridge";
import { nowIso } from "./id";
import type { CanvasData, ChangelogData, Observation } from "../types";
import type { LocalStore } from "./store/types";
import type { WorkspaceSnapshot } from "./store/types";
import { openLocalStore } from "./store/openStore";
import { LocalDataService } from "./data/localDataService";
import { LocalMemoryService } from "./memory/localMemoryService";
import { ChatOrchestrator } from "./chat/orchestrator";
import { CapabilityRegistry, capabilityRegistry } from "./capabilities/registry";
import { BffError } from "./errors";

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

  /**
   * Release notes are read from `CHANGELOG.md` by the sidecar, so the local
   * backend has none of its own and says so rather than inventing a release.
   * The modal renders an empty state for this.
   */
  async fetchChangelog(): Promise<ChangelogData> {
    return { releases: [] };
  }

  /** Serialize the whole local workspace (canvas, memory, conversations) to JSON. */
  async exportWorkspace(): Promise<string> {
    const snapshot = await this.store.snapshot();
    return JSON.stringify({ ...snapshot, exported_at: nowIso() }, null, 2);
  }

  /** Replace the whole local workspace with an imported JSON snapshot. */
  async importWorkspace(json: string): Promise<void> {
    let snapshot: WorkspaceSnapshot;
    try {
      snapshot = JSON.parse(json) as WorkspaceSnapshot;
    } catch {
      throw new BffError(
        "validation",
        "The workspace file is not valid JSON.",
        { suggestion: "Export the workspace again and try importing the file unchanged." },
      );
    }
    if (!snapshot || snapshot.version !== 1) {
      throw new BffError(
        "validation",
        `Unsupported workspace version ${snapshot?.version}.`,
        { suggestion: "Export the workspace again and try importing the file unchanged." },
      );
    }
    await this.store.restore(snapshot);
  }

  /**
   * One-time import from a reachable sidecar. Only imports when the local store
   * is empty, so an existing local workspace is never overwritten. Returns true
   * when data was imported, false when the local store already had data.
   */
  async importFromSidecar(mcpUrl: string): Promise<boolean> {
    const existing = await this.store.listJobs();
    if (existing.length > 0) {
      return false;
    }

    const canvas = (await fetch(
      apiUrl(`/api/canvas?mcp_url=${encodeURIComponent(mcpUrl)}`),
    ).then((response) => response.json())) as CanvasData;

    const observationPage = (await fetch(
      apiUrl("/api/memory/observations"),
    ).then((response) => response.json())) as {
      observations: Observation[];
    };

    const jobIdMap = new Map<string, string>();
    for (const job of canvas.jobs ?? []) {
      const id = job.id;
      const name = job.name;
      if (!id || !name) {
        continue;
      }
      const local = await this.data.createJob({
        name,
        description: job.description ?? "",
      });
      jobIdMap.set(id, local.id);
    }

    const steps = (canvas.steps ?? []).slice().sort(
      (left, right) => (left.order ?? 0) - (right.order ?? 0),
    );
    for (const step of steps) {
      const stepJobId = step.job_id;
      if (!stepJobId) {
        continue;
      }
      const localJobId = jobIdMap.get(stepJobId);
      if (!localJobId) {
        continue;
      }
      await this.data.addStep({
        job_id: localJobId,
        name: step.name ?? "",
        order: step.order ?? 0,
      });
    }

    for (const outcome of canvas.outcomes ?? []) {
      const outcomeJobId = outcome.job_id;
      if (!outcomeJobId) {
        continue;
      }
      const localJobId = jobIdMap.get(outcomeJobId);
      if (!localJobId) {
        continue;
      }
      await this.data.addOutcome({
        job_id: localJobId,
        statement: outcome.statement ?? "",
        importance: outcome.importance ?? 5,
        satisfaction: outcome.satisfaction ?? 5,
      });
    }

    for (const observation of observationPage.observations ?? []) {
      await this.memory.addObservation({
        kind: observation.kind,
        text: observation.text,
        data: observation.data ?? {},
        confidence: observation.confidence ?? 0.5,
        confirmed: observation.status === "confirmed",
      });
    }

    return true;
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
