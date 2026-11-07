import { apiUrl } from "../bridge/desktopBridge";
import { authHeaders } from "../api/studioApi";
import { nowIso } from "./id";
import type { CanvasData, ChangelogData, Evidence, Observation } from "../types";
import type {
  LocalStore,
  StoredConversation,
  StoredJob,
  StoredOutcome,
  StoredStep,
  StoredTurn,
  WorkspaceSnapshot,
  WorkspaceSummary,
} from "./store/types";
import { WORKSPACE_SNAPSHOT_VERSION } from "./store/types";
import { openLocalStore } from "./store/openStore";
import { LocalDataService } from "./data/localDataService";
import { LocalMemoryService } from "./memory/localMemoryService";
import { ChatOrchestrator } from "./chat/orchestrator";
import { CapabilityRegistry, capabilityRegistry } from "./capabilities/registry";
import { BffError } from "./errors";

const EXPORT_HINT =
  "Export the workspace again and try importing the file unchanged.";

/** The list fields a snapshot carries, read defensively. */
function readList<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

/**
 * Turn a version 1 payload into a version 2 snapshot.
 *
 * Version 1 had no `evidence`; every other list is carried across untouched, so
 * an old file keeps every record it held.
 */
function migrateFromV1(raw: Record<string, unknown>): WorkspaceSnapshot {
  return {
    version: WORKSPACE_SNAPSHOT_VERSION,
    jobs: readList<StoredJob>(raw.jobs),
    steps: readList<StoredStep>(raw.steps),
    outcomes: readList<StoredOutcome>(raw.outcomes),
    observations: readList<Observation>(raw.observations),
    evidence: [],
    conversations: readList<StoredConversation>(raw.conversations),
    turns: readList<StoredTurn>(raw.turns),
  };
}

/**
 * Read an exported workspace file into a snapshot this build can restore.
 *
 * Accepts the current version and migrates version 1 on the way in. Any other
 * version is refused with the version it found, because silently ignoring the
 * parts a newer file carries would be a backup that drops records.
 */
export function parseWorkspaceSnapshot(json: string): WorkspaceSnapshot {
  let raw: unknown;
  try {
    raw = JSON.parse(json);
  } catch {
    throw new BffError("validation", "The workspace file is not valid JSON.", {
      suggestion: EXPORT_HINT,
    });
  }
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new BffError(
      "validation",
      "The workspace file is not a workspace snapshot.",
      { suggestion: EXPORT_HINT },
    );
  }
  const record = raw as Record<string, unknown>;
  const version = record.version;
  if (version === 1) {
    return migrateFromV1(record);
  }
  if (version === WORKSPACE_SNAPSHOT_VERSION) {
    return {
      version: WORKSPACE_SNAPSHOT_VERSION,
      jobs: readList<StoredJob>(record.jobs),
      steps: readList<StoredStep>(record.steps),
      outcomes: readList<StoredOutcome>(record.outcomes),
      observations: readList<Observation>(record.observations),
      evidence: readList<Evidence>(record.evidence),
      conversations: readList<StoredConversation>(record.conversations),
      turns: readList<StoredTurn>(record.turns),
    };
  }
  const found = version === undefined ? "none" : String(version);
  throw new BffError(
    "validation",
    `This workspace file is version ${found}, but this build reads up to version ${WORKSPACE_SNAPSHOT_VERSION}.`,
    {
      suggestion:
        typeof version === "number" && version > WORKSPACE_SNAPSHOT_VERSION
          ? "Update the studio, then import the file again."
          : EXPORT_HINT,
    },
  );
}

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
   * The changelog comes from the sidecar's release data. Without it there is
   * nothing honest to show, so return an empty list rather than inventing notes.
   */
  async fetchChangelog(): Promise<ChangelogData> {
    return { releases: [] };
  }

  /**
   * Serialize the whole local workspace (canvas, memory, conversations) to a
   * readable JSON snapshot at the current version.
   *
   * Queued-but-unsent intents are not portable, so they are excluded and their
   * presence is recorded in the file rather than silently dropped.
   */
  async exportWorkspace(): Promise<string> {
    const snapshot = await this.store.snapshot();
    const outbox = await this.store.listOutbox();
    const pending = outbox.some(
      (record) => record.state === "pending" || record.state === "sending",
    );
    return JSON.stringify(
      { ...snapshot, exported_at: nowIso(), pending_writes_excluded: pending },
      null,
      2,
    );
  }

  /** What the workspace holds, so a caller can name it before replacing it. */
  async workspaceSummary(): Promise<WorkspaceSummary> {
    const snapshot = await this.store.snapshot();
    const counts = {
      jobs: snapshot.jobs.length,
      steps: snapshot.steps.length,
      outcomes: snapshot.outcomes.length,
      observations: snapshot.observations.length,
      evidence: snapshot.evidence.length,
      conversations: snapshot.conversations.length,
      turns: snapshot.turns.length,
    };
    const records = Object.values(counts).reduce((total, count) => total + count, 0);
    return { records, counts, empty: records === 0 };
  }

  /**
   * Replace the whole local workspace with an imported JSON snapshot.
   *
   * A version 1 file is migrated on the way in; a version this build cannot read
   * is refused with the version it found, so the mismatch is explained rather
   * than swallowed. Restoring is destructive by nature — the caller confirms
   * first, and this method never asks.
   */
  async importWorkspace(json: string): Promise<void> {
    const snapshot = parseWorkspaceSnapshot(json);
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
