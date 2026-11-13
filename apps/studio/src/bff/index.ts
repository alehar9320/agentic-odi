import { apiUrl } from "../bridge/desktopBridge";
import { newId, nowIso } from "./id";
import type { CanvasData, ChangelogData, Evidence, Job, Observation, Outcome, Step } from "../types";
import type { LocalStore, OutboxEntity, OutboxKind, OutboxRecord } from "./store/types";
import { authHeaders } from "../api/studioApi";
import type { WorkspaceSnapshot } from "./store/types";
import { openLocalStore } from "./store/openStore";
import { LocalDataService } from "./data/localDataService";
import { ReceiptService } from "./data/receiptService";
import { LocalMemoryService } from "./memory/localMemoryService";
import { ChatOrchestrator } from "./chat/orchestrator";
import { CapabilityRegistry, capabilityRegistry } from "./capabilities/registry";
import { BffError } from "./errors";
import { storageFacts } from "./storageFacts";

/** One queued write, as the caller describes it before the store assigns an id. */
interface QueuedWriteInput {
  kind: OutboxKind;
  entity: OutboxEntity;
  local_id: string | null;
  payload: unknown;
}

export class StudioBff {
  readonly store: LocalStore;
  readonly data: LocalDataService;
  readonly receipts: ReceiptService;
  readonly memory: LocalMemoryService;
  readonly chat: ChatOrchestrator;
  readonly capabilities: CapabilityRegistry;

  constructor(store: LocalStore) {
    this.store = store;
    this.data = new LocalDataService(store);
    this.receipts = new ReceiptService(store);
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

  /** The queued writes still waiting for the sidecar, oldest first. */
  async listOutbox(): Promise<OutboxRecord[]> {
    return this.store.listOutbox();
  }

  /** Storage facts for the local store. */
  async storageFacts(): Promise<Awaited<ReturnType<typeof storageFacts>>> {
    return storageFacts(this.store);
  }

  private async enqueue(input: QueuedWriteInput): Promise<OutboxRecord> {
    const record: OutboxRecord = {
      id: newId(),
      kind: input.kind,
      entity: input.entity,
      local_id: input.local_id,
      server_id: null,
      payload: input.payload,
      depends_on: [],
      state: "pending",
      attempts: 0,
      last_error: null,
      created_at: nowIso(),
      acknowledged_at: null,
    };
    await this.store.enqueueOutbox(record);
    return record;
  }

  /**
   * Apply a write to the local store and queue it for the sidecar. The local
   * record comes back so the caller can show it now; the outbox record is what
   * says the sidecar has not seen it yet.
   */
  async createJob(payload: { name: string; description?: string }): Promise<Job> {
    const job = await this.data.createJob(payload);
    await this.enqueue({
      kind: "create",
      entity: "job",
      local_id: job.id,
      payload: { name: job.name, description: job.description },
    });
    return job;
  }

  async updateJob(
    jobId: string,
    payload: { name?: string; description?: string },
  ): Promise<Job> {
    const job = await this.data.updateJob(jobId, payload);
    await this.enqueue({ kind: "update", entity: "job", local_id: jobId, payload });
    return job;
  }

  async deleteJob(jobId: string): Promise<{ deleted: string }> {
    const result = await this.data.deleteJob(jobId);
    await this.enqueue({ kind: "delete", entity: "job", local_id: jobId, payload: {} });
    return result;
  }

  async addStep(input: { job_id: string; name: string; order: number }): Promise<Step> {
    const step = await this.data.addStep(input);
    await this.enqueue({
      kind: "create",
      entity: "step",
      local_id: step.id ?? null,
      payload: { job_id: input.job_id, name: step.name, order: step.order },
    });
    return step;
  }

  async updateStep(
    stepId: string,
    payload: { name?: string; order?: number },
  ): Promise<Step> {
    const step = await this.data.updateStep(stepId, payload);
    await this.enqueue({ kind: "update", entity: "step", local_id: stepId, payload });
    return step;
  }

  async deleteStep(stepId: string): Promise<{ deleted: string }> {
    const result = await this.data.deleteStep(stepId);
    await this.enqueue({ kind: "delete", entity: "step", local_id: stepId, payload: {} });
    return result;
  }

  async addOutcome(input: {
    job_id: string;
    statement: string;
    importance: number | null;
    satisfaction: number | null;
    step_id?: string | null;
  }): Promise<Outcome> {
    const outcome = await this.data.addOutcome(input);
    await this.enqueue({
      kind: "create",
      entity: "outcome",
      local_id: outcome.id ?? null,
      payload: {
        job_id: input.job_id,
        statement: outcome.statement,
        importance: outcome.importance,
        satisfaction: outcome.satisfaction,
        step_id: input.step_id ?? null,
      },
    });
    return outcome;
  }

  async updateOutcome(
    outcomeId: string,
    payload: {
      statement?: string;
      importance?: number | null;
      satisfaction?: number | null;
    },
  ): Promise<Outcome> {
    const outcome = await this.data.updateOutcome(outcomeId, payload);
    await this.enqueue({ kind: "update", entity: "outcome", local_id: outcomeId, payload });
    return outcome;
  }

  async deleteOutcome(outcomeId: string): Promise<{ deleted: string }> {
    const result = await this.data.deleteOutcome(outcomeId);
    await this.enqueue({
      kind: "delete",
      entity: "outcome",
      local_id: outcomeId,
      payload: {},
    });
    return result;
  }

  async addEvidence(input: {
    source_name?: string;
    source_kind?: string;
    item_type?: string;
    name: string;
    content: string;
    url?: string;
    job_id?: string;
    step_id?: string;
    outcome_id?: string;
  }): Promise<Evidence> {
    const record = await this.data.addEvidence(input);
    await this.enqueue({
      kind: "create",
      entity: "evidence",
      local_id: record.id ?? null,
      payload: {
        source_name: input.source_name,
        source_kind: input.source_kind,
        item_type: input.item_type,
        name: record.name,
        content: record.content,
        url: input.url,
        job_id: input.job_id ?? null,
        step_id: input.step_id ?? null,
        outcome_id: input.outcome_id ?? null,
      },
    });
    return record;
  }

  async deleteEvidence(evidenceId: string): Promise<{ deleted: string }> {
    const result = await this.data.deleteEvidence(evidenceId);
    await this.enqueue({
      kind: "delete",
      entity: "evidence",
      local_id: evidenceId,
      payload: {},
    });
    return result;
  }

  /**
   * The changelog comes from the sidecar's release data. Without it there is
   * nothing honest to show, so return an empty list rather than inventing notes.
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
      { headers: authHeaders() },
    ).then((response) => response.json())) as CanvasData;

    const observationPage = (await fetch(
      apiUrl("/api/memory/observations"),
      { headers: authHeaders() },
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
        subject_type: observation.subject_type ?? null,
        subject_id: observation.subject_id ?? null,
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
