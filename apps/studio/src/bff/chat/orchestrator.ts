import type {
  CanvasData,
  ChatMessage,
  ChatStreamRequest,
  Observation,
  ObservationKind,
  Outcome,
} from "../../types";
import { asStudioError } from "../../api/studioApi";
import { isEndpointConfigured } from "../../lib/modelEndpoint";
import { BffError, notFound } from "../errors";
import type { LocalStore } from "../store/types";
import { LocalDataService } from "../data/localDataService";
import { LocalMemoryService } from "../memory/localMemoryService";
import { createSseParser, type RawSseEvent } from "../../api/sse";

type Provider = "endpoint" | "deterministic";

const TOOLS = [
  {
    name: "get_canvas",
    description: "Read the current ODI canvas: jobs, steps, and outcomes.",
    parameters: { type: "object", properties: {}, required: [] },
  },
  {
    name: "create_job",
    description: "Create a new job on the canvas.",
    parameters: {
      type: "object",
      properties: {
        name: { type: "string", description: "Job name." },
        description: { type: "string", description: "Optional job description." },
      },
      required: ["name"],
    },
  },
  {
    name: "update_job",
    description: "Rename or describe an existing job.",
    parameters: {
      type: "object",
      properties: {
        job_id: { type: "string" },
        name: { type: "string" },
        description: { type: "string" },
      },
      required: ["job_id"],
    },
  },
  {
    name: "delete_job",
    description: "Delete a job and its steps and outcomes.",
    parameters: {
      type: "object",
      properties: { job_id: { type: "string" } },
      required: ["job_id"],
    },
  },
  {
    name: "add_step",
    description: "Add a step to a job.",
    parameters: {
      type: "object",
      properties: {
        job_id: { type: "string" },
        name: { type: "string" },
        order: { type: "integer", minimum: 0 },
      },
      required: ["job_id", "name", "order"],
    },
  },
  {
    name: "update_step",
    description: "Rename or reorder a step.",
    parameters: {
      type: "object",
      properties: {
        step_id: { type: "string" },
        name: { type: "string" },
        order: { type: "integer", minimum: 0 },
      },
      required: ["step_id"],
    },
  },
  {
    name: "delete_step",
    description: "Delete a step and its outcomes.",
    parameters: {
      type: "object",
      properties: { step_id: { type: "string" } },
      required: ["step_id"],
    },
  },
  {
    name: "add_outcome",
    description: "Add an outcome to a job with importance and satisfaction scores.",
    parameters: {
      type: "object",
      properties: {
        job_id: { type: "string" },
        statement: { type: "string" },
        importance: { type: "number", minimum: 1, maximum: 10 },
        satisfaction: { type: "number", minimum: 1, maximum: 10 },
        step_id: { type: "string" },
      },
      required: ["job_id", "statement"],
    },
  },
  {
    name: "update_outcome",
    description: "Update an outcome statement or scores.",
    parameters: {
      type: "object",
      properties: {
        outcome_id: { type: "string" },
        statement: { type: "string" },
        importance: { type: "number", minimum: 1, maximum: 10 },
        satisfaction: { type: "number", minimum: 1, maximum: 10 },
      },
      required: ["outcome_id"],
    },
  },
  {
    name: "delete_outcome",
    description: "Delete an outcome.",
    parameters: {
      type: "object",
      properties: { outcome_id: { type: "string" } },
      required: ["outcome_id"],
    },
  },
  {
    name: "compute_opportunity",
    description: "Compute an ODI opportunity score from importance and satisfaction.",
    parameters: {
      type: "object",
      properties: {
        importance: { type: "number", minimum: 1, maximum: 10 },
        satisfaction: { type: "number", minimum: 1, maximum: 10 },
      },
      required: ["importance", "satisfaction"],
    },
  },
  {
    name: "evaluate_outcome",
    description: "Read an outcome and its opportunity score.",
    parameters: {
      type: "object",
      properties: { outcome_id: { type: "string" } },
      required: ["outcome_id"],
    },
  },
  {
    name: "remember",
    description: "Save an observation to local memory.",
    parameters: {
      type: "object",
      properties: {
        kind: {
          type: "string",
          enum: [
            "career",
            "opportunity",
            "business",
            "stakeholder",
            "constraint",
            "evidence",
            "preference",
          ],
        },
        text: { type: "string" },
      },
      required: ["text"],
    },
  },
  {
    name: "render_ui",
    description: "Render a UI surface for the current answer.",
    parameters: {
      type: "object",
      properties: {
        surface: {
          type: "string",
          enum: ["opportunity-board", "outcome-card", "job-map"],
        },
        outcome_id: { type: "string" },
      },
      required: ["surface"],
    },
  },
] as const;

function emit(event: RawSseEvent, onEvent: (event: RawSseEvent) => void): void {
  onEvent(event);
}

function toolEvent(name: string, status: string, preview?: string): RawSseEvent {
  return { event: "tool", data: { name, status, preview } };
}

function toolResultEvent(name: string, output: unknown): RawSseEvent {
  return { event: "tool_result", data: { name, output } };
}

interface ToolCall {
  id: string;
  type: string;
  name: string;
  arguments: string;
  argumentsObj: Record<string, unknown>;
  output?: unknown;
}

export class ChatOrchestrator {
  constructor(
    private readonly store: LocalStore,
    private readonly data: LocalDataService,
    private readonly memory: LocalMemoryService,
  ) {}

  async stream(
    request: ChatStreamRequest,
    onEvent: (event: RawSseEvent) => void,
    signal?: AbortSignal,
  ): Promise<void> {
    const provider: Provider = isEndpointConfigured(request)
      ? "endpoint"
      : "deterministic";
    // "offline" is the sidecar's own word for an answer no model produced, so a
    // browser-only turn and a local turn are labeled the same way in the transcript.
    emit(
      {
        event: "status",
        data: { phase: provider === "endpoint" ? "streaming" : "offline" },
      },
      onEvent,
    );

    const conversation = await this.ensureConversation(request.conversation_id);
    emit({ event: "conversation", data: { id: conversation.id } }, onEvent);

    const lastMessage = request.messages[request.messages.length - 1];
    const userMessage =
      lastMessage && lastMessage.role === "user" ? lastMessage : undefined;
    if (userMessage) {
      await this.memory.appendTurn(
        conversation.id,
        "user",
        userMessage.content,
        userMessage.id,
        userMessage.parentId,
      );
    }

    if (provider === "endpoint") {
      await this.streamEndpoint(request, conversation, onEvent, signal);
    } else {
      await this.streamDeterministic(userMessage, onEvent);
    }
  }

  private async ensureConversation(
    conversationId: string | undefined | null,
  ): Promise<StoredConversationLike> {
    if (conversationId) {
      const existing = await this.store.getConversation(conversationId);
      if (existing) {
        return existing;
      }
    }
    const latest = await this.memory.latestConversation();
    if (latest.conversation) {
      return latest.conversation;
    }
    return this.memory.createConversation("New conversation");
  }

  private async streamDeterministic(
    userMessage: ChatMessage | undefined,
    onEvent: (event: RawSseEvent) => void,
  ): Promise<void> {
    const message = userMessage ? userMessage.content : "";
    const canvas = await this.data.fetchCanvas();
    emit(toolEvent("get_canvas", "running"), onEvent);
    await this.executeDeterministicCommand(message, canvas, onEvent);
    emit(toolEvent("get_canvas", "ok"), onEvent);
  }

  private async executeDeterministicCommand(
    message: string,
    canvas: CanvasData,
    onEvent: (event: RawSseEvent) => void,
  ): Promise<void> {
    const trimmed = message.trim();
    const lower = trimmed.toLowerCase();

    if (lower.startsWith("add job")) {
      const name = trimmed.replace(/^add job\s+/i, "").trim().replace(/^["“]|["”]$/g, "");
      if (!name) {
        emit({ event: "delta", data: { text: "Please tell me the job name." } }, onEvent);
        emit({ event: "message", data: { content: "Please tell me the job name." } }, onEvent);
        return;
      }
      const job = await this.data.createJob({ name });
      emit(toolEvent("create_job", "running", name), onEvent);
      emit(toolEvent("create_job", "ok", JSON.stringify(job)), onEvent);
      emit({ event: "canvas_dirty", data: {} }, onEvent);
      emit({ event: "delta", data: { text: `Job “${job.name}” created.` } }, onEvent);
      emit({ event: "message", data: { content: `Job “${job.name}” created.` } }, onEvent);
      return;
    }

    if (lower.startsWith("add outcome")) {
      const rest = trimmed.replace(/^add outcome\s+/i, "").trim();
      const match = rest.match(/^(.+?)(?:\s+importance\s+(\d+(?:\.\d+)?))?(?:\s+satisfaction\s+(\d+(?:\.\d+)?))?$/);
      if (!match) {
        emit(
          {
            event: "delta",
            data: {
              text: "Say “add outcome <statement> importance N satisfaction N”.",
            },
          },
          onEvent,
        );
        emit(
          {
            event: "message",
            data: { content: "Say “add outcome <statement> importance N satisfaction N”." },
          },
          onEvent,
        );
        return;
      }
      const statement = match[1].trim().replace(/^["“]|["”]$/g, "");
      const importance = match[2] ? Number(match[2]) : 5;
      const satisfaction = match[3] ? Number(match[3]) : 5;
      const job = canvas.jobs[0];
      if (!job) {
        emit(
          {
            event: "delta",
            data: { text: "Add a job first, then I can capture an outcome." },
          },
          onEvent,
        );
        emit(
          {
            event: "message",
            data: { content: "Add a job first, then I can capture an outcome." },
          },
          onEvent,
        );
        return;
      }
      const outcome = await this.data.addOutcome({
        job_id: job.id,
        statement,
        importance,
        satisfaction,
      });
      emit(toolEvent("add_outcome", "running", statement), onEvent);
      emit(toolEvent("add_outcome", "ok", JSON.stringify(outcome)), onEvent);
      emit({ event: "canvas_dirty", data: {} }, onEvent);
      emit(
        {
          event: "delta",
          data: {
            text: `Outcome captured: “${outcome.statement}” (opportunity ${outcome.opportunity_score ?? 0}).`,
          },
        },
        onEvent,
      );
      emit(
        {
          event: "message",
          data: {
            content: `Outcome captured: “${outcome.statement}” (opportunity ${outcome.opportunity_score ?? 0}).`,
          },
        },
        onEvent,
      );
      return;
    }

    if (lower.startsWith("remember")) {
      const text = trimmed.replace(/^remember\b\s*/i, "").trim();
      if (!text) {
        emit(
          { event: "delta", data: { text: "What would you like me to remember?" } },
          onEvent,
        );
        emit(
          { event: "message", data: { content: "What would you like me to remember?" } },
          onEvent,
        );
        return;
      }
      const observation = await this.memory.addObservation({
        kind: "evidence",
        text,
        confirmed: true,
      });
      emit(toolEvent("remember", "running", text.slice(0, 60)), onEvent);
      emit(toolEvent("remember", "ok", JSON.stringify(observation)), onEvent);
      emit({ event: "memory", data: { observation } }, onEvent);
      emit({ event: "delta", data: { text: "Saved to memory." } }, onEvent);
      emit({ event: "message", data: { content: "Saved to memory." } }, onEvent);
      return;
    }

    if (lower.includes("render") || lower.includes("board") || lower.includes("show")) {
      const outcomes = canvas.outcomes.slice(0, 12);
      if (!outcomes.length) {
        emit(
          {
            event: "delta",
            data: { text: "Add an outcome first, then I can render the opportunity board." },
          },
          onEvent,
        );
        emit(
          {
            event: "message",
            data: {
              content: "Add an outcome first, then I can render the opportunity board.",
            },
          },
          onEvent,
        );
        return;
      }
      emit(toolEvent("render_ui", "running", "opportunity-board"), onEvent);
      const board = this.renderOpportunityBoard(outcomes);
      emit(
        {
          event: "ui",
          data: { id: `ui-board-${canvas.outcomes.length}`, spec: board },
        },
        onEvent,
      );
      emit(toolEvent("render_ui", "ok", "opportunity-board"), onEvent);
      emit(
        {
          event: "delta",
          data: {
            text: "Here is your opportunity board, ranked by ODI opportunity score.",
          },
        },
        onEvent,
      );
      emit(
        {
          event: "message",
          data: {
            content: "Here is your opportunity board, ranked by ODI opportunity score.",
          },
        },
        onEvent,
      );
      return;
    }

    const jobs = canvas.jobs.length;
    const steps = canvas.steps.length;
    const outcomes = canvas.outcomes.length;
    const scored = canvas.outcomes.filter((o) => o.opportunity_score !== null);
    const top = scored
      .slice()
      .sort((a, b) => (b.opportunity_score ?? 0) - (a.opportunity_score ?? 0))
      .slice(0, 3);
    const lines: string[] = [
      `Your canvas has ${jobs} job${jobs !== 1 ? "s" : ""}, ${steps} step${
        steps !== 1 ? "s" : ""
      }, and ${outcomes} outcome${outcomes !== 1 ? "s" : ""}.`,
    ];
    if (top.length) {
      lines.push(
        "Top opportunities: " +
          top.map((o) => `"${o.statement}" (${o.opportunity_score ?? 0})`).join("; "),
      );
    }
    lines.push(
      "Try: “add job Onboard customers”, “add outcome Reduce setup time importance 8 satisfaction 3”, or “remember the customer hates long setup.”",
    );
    const content = lines.join("\n");
    emit({ event: "delta", data: { text: content } }, onEvent);
    emit({ event: "message", data: { content } }, onEvent);
  }

  private renderOpportunityBoard(outcomes: Outcome[]): Record<string, unknown> {
    const boardOutcomes = outcomes.map((o) => ({
      id: o.id,
      statement: o.statement ?? "",
      importance: o.importance ?? 0,
      satisfaction: o.satisfaction ?? 0,
      opportunityScore: o.opportunity_score ?? 0,
    }));
    return {
      type: "opportunity-board",
      props: {
        title: "Opportunity board",
        outcomes: boardOutcomes,
      },
    };
  }

  private async streamEndpoint(
    request: ChatStreamRequest,
    conversation: StoredConversationLike,
    onEvent: (event: RawSseEvent) => void,
    signal?: AbortSignal,
  ): Promise<void> {
    let assistantTurn: string;
    // A saved address the browser cannot reach — mixed-content blocked, refused by
    // CORS, a laptop moved off the network its Ollama lives on — should not cost the
    // person the answer they asked for. Nothing may have reached the transcript or the
    // canvas yet, so a failure that early is answered locally instead of reported.
    let started = false;
    const watched = (event: RawSseEvent): void => {
      if (
        event.event === "delta" ||
        event.event === "message" ||
        event.event === "tool_result"
      ) {
        started = true;
      }
      onEvent(event);
    };

    try {
      const history: Array<Record<string, unknown>> = [
        {
          role: "system",
          content:
            "You are a helpful ODI assistant. Use the tools to read and update the local canvas. " +
            "When the user asks to show something, prefer render_ui with a supported surface. " +
            "Keep answers short and practical.",
        },
      ];
      for (const message of request.messages) {
        if (message.role === "notice") {
          continue;
        }
        history.push({ role: message.role, content: message.content });
      }

      const first = await this.callOpenAI(
        request,
        history,
        TOOLS,
        true,
        watched,
        signal,
      );
      if (first.toolCalls.length) {
        await this.executeToolCalls(first.toolCalls, watched);
        const second = await this.callOpenAI(
          request,
          [
            ...history,
            { role: "assistant", content: null, tool_calls: first.toolCalls },
            ...first.toolCalls.map((call) => ({
              role: "tool",
              tool_call_id: call.id,
              content: JSON.stringify(call.output),
            })),
          ],
          TOOLS,
          true,
          watched,
          signal,
        );
        assistantTurn = second.content;
      } else {
        assistantTurn = first.content;
      }
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") {
        throw error;
      }
      if (started) {
        // Some of the answer, or some of the work, is already in front of them.
        emit({ event: "error", data: { error: asStudioError(error) } }, onEvent);
        return;
      }
      if (error instanceof BffError && error.studioError.code === "provider_error") {
        // The endpoint answered — badly. A rejected key or a model that does not exist
        // is a thing the person can fix, so it gets said rather than hidden behind a
        // local draft that looks like a reply from the model they asked for.
        emit({ event: "error", data: { error: asStudioError(error) } }, onEvent);
        return;
      }
      // The request never left the browser: mixed content blocked, CORS refused, a
      // laptop off the network its model lives on. Their question is still worth an
      // answer, and the local responder has one.
      emit({ event: "status", data: { phase: "offline" } }, onEvent);
      const lastMessage = request.messages[request.messages.length - 1];
      await this.streamDeterministic(
        lastMessage && lastMessage.role === "user" ? lastMessage : undefined,
        onEvent,
      );
      return;
    }

    if (assistantTurn) {
      const assistantId = request.assistant_id ?? crypto.randomUUID();
      const userMessageId =
        request.messages[request.messages.length - 1]?.id ?? null;
      await this.memory.appendTurn(
        conversation.id,
        "assistant",
        assistantTurn,
        assistantId,
        userMessageId,
      );
      emit({ event: "delta", data: { text: assistantTurn } }, onEvent);
      emit({ event: "message", data: { content: assistantTurn } }, onEvent);
    }
  }

  private async callOpenAI(
    request: {
      base_url: string;
      api_key: string;
      model: string;
    },
    messages: Array<Record<string, unknown>>,
    tools: readonly (typeof TOOLS)[number][],
    stream: boolean,
    onEvent: (event: RawSseEvent) => void,
    signal?: AbortSignal,
  ): Promise<{ content: string; toolCalls: ToolCall[] }> {
    const url = `${request.base_url.replace(/\/$/, "")}/chat/completions`;
    const body: Record<string, unknown> = {
      model: request.model,
      messages,
      stream,
    };
    if (tools.length) {
      body.tools = tools;
      body.tool_choice = "auto";
    }

    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        // A private server with no key needs no header; "Bearer " alone makes
        // some local runtimes reject the request.
        ...(request.api_key ? { Authorization: `Bearer ${request.api_key}` } : {}),
      },
      body: JSON.stringify(body),
      signal,
    });

    if (!response.ok || !response.body) {
      let detail: string | undefined;
      try {
        const parsed = (await response.json()) as {
          error?: { message?: string };
        };
        detail = parsed.error?.message;
      } catch {
        /* ignore */
      }
      throw new BffError(
        "provider_error",
        detail || `Model endpoint returned ${response.status}.`,
        { retryable: true },
      );
    }

    const content: string[] = [];
    const toolCalls: Map<number, ToolCall> = new Map();
    let finished = false;
    const parser = createSseParser();

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    for (;;) {
      if (finished || (signal && signal.aborted)) {
        break;
      }
      const { value, done } = await reader.read();
      if (done) {
        break;
      }
      for (const event of parser.push(decoder.decode(value, { stream: true }))) {
        const chunk = event.data as Record<string, unknown>;
        const choices = chunk.choices as Array<Record<string, unknown>> | undefined;
        const choice = choices?.[0];
        const delta = choice?.delta as Record<string, unknown> | undefined;
        if (delta && typeof delta.content === "string" && stream) {
          content.push(delta.content);
          emit({ event: "delta", data: { text: delta.content } }, onEvent);
        }
        const calls = delta?.tool_calls as
          | Array<Record<string, unknown>>
          | undefined;
        if (calls) {
          for (const call of calls) {
            const index = Number(call.index);
            let existing = toolCalls.get(index);
            if (!existing) {
              existing = {
                id: String(call.id ?? ""),
                type: String(call.type ?? "function"),
                name: String(
                  (call.function as Record<string, unknown> | undefined)?.name ?? "",
                ),
                arguments: "",
                argumentsObj: {},
              };
              toolCalls.set(index, existing);
            }
            const args = String(
              (call.function as Record<string, unknown> | undefined)?.arguments ?? "",
            );
            existing.arguments += args;
          }
        }
        if (choice?.finish_reason) {
          finished = true;
          break;
        }
      }
    }

    for (const call of toolCalls.values()) {
      try {
        call.argumentsObj = JSON.parse(call.arguments || "{}");
      } catch {
        call.argumentsObj = {};
      }
    }

    return {
      content: content.join(""),
      toolCalls: [...toolCalls.values()].filter((call) => call.name),
    };
  }

  private async executeToolCalls(
    calls: ToolCall[],
    onEvent: (event: RawSseEvent) => void,
  ): Promise<void> {
    for (const call of calls) {
      emit(toolEvent(call.name, "running"), onEvent);
      let output: unknown;
      let canvasDirty = false;
      let observation: Observation | undefined;

      try {
        switch (call.name) {
          case "get_canvas": {
            const canvas = await this.data.fetchCanvas();
            output = {
              jobs: canvas.jobs.length,
              steps: canvas.steps.length,
              outcomes: canvas.outcomes.length,
            };
            break;
          }
          case "create_job": {
            const job = await this.data.createJob({
              name: String(call.argumentsObj.name ?? ""),
              description: String(call.argumentsObj.description ?? ""),
            });
            output = job;
            canvasDirty = true;
            break;
          }
          case "update_job": {
            const job = await this.data.updateJob(String(call.argumentsObj.job_id), {
              name: call.argumentsObj.name as string | undefined,
              description: call.argumentsObj.description as string | undefined,
            });
            output = job;
            canvasDirty = true;
            break;
          }
          case "delete_job": {
            await this.data.deleteJob(String(call.argumentsObj.job_id));
            output = { deleted: call.argumentsObj.job_id };
            canvasDirty = true;
            break;
          }
          case "add_step": {
            const step = await this.data.addStep({
              job_id: String(call.argumentsObj.job_id),
              name: String(call.argumentsObj.name ?? ""),
              order: Number(call.argumentsObj.order ?? 0),
            });
            output = step;
            canvasDirty = true;
            break;
          }
          case "update_step": {
            const step = await this.data.updateStep(String(call.argumentsObj.step_id), {
              name: call.argumentsObj.name as string | undefined,
              order: call.argumentsObj.order as number | undefined,
            });
            output = step;
            canvasDirty = true;
            break;
          }
          case "delete_step": {
            await this.data.deleteStep(String(call.argumentsObj.step_id));
            output = { deleted: call.argumentsObj.step_id };
            canvasDirty = true;
            break;
          }
          case "add_outcome": {
            const outcome = await this.data.addOutcome({
              job_id: String(call.argumentsObj.job_id),
              statement: String(call.argumentsObj.statement ?? ""),
              importance: Number(call.argumentsObj.importance),
              satisfaction: Number(call.argumentsObj.satisfaction),
              step_id: call.argumentsObj.step_id as string | undefined,
            });
            output = outcome;
            canvasDirty = true;
            break;
          }
          case "update_outcome": {
            const outcome = await this.data.updateOutcome(
              String(call.argumentsObj.outcome_id),
              {
                statement: call.argumentsObj.statement as string | undefined,
                importance: call.argumentsObj.importance as number | undefined,
                satisfaction: call.argumentsObj.satisfaction as number | undefined,
              },
            );
            output = outcome;
            canvasDirty = true;
            break;
          }
          case "delete_outcome": {
            await this.data.deleteOutcome(String(call.argumentsObj.outcome_id));
            output = { deleted: call.argumentsObj.outcome_id };
            canvasDirty = true;
            break;
          }
          case "compute_opportunity": {
            const importance = Number(call.argumentsObj.importance);
            const satisfaction = Number(call.argumentsObj.satisfaction);
            output = {
              score: importance + Math.max(importance - satisfaction, 0),
            };
            break;
          }
          case "evaluate_outcome": {
            const outcome = await this.store.getOutcome(
              String(call.argumentsObj.outcome_id),
            );
            if (!outcome) {
              throw notFound("Outcome", String(call.argumentsObj.outcome_id));
            }
            output = outcome;
            break;
          }
          case "remember": {
            observation = await this.memory.addObservation({
              kind: (call.argumentsObj.kind as ObservationKind) ?? "evidence",
              text: String(call.argumentsObj.text ?? ""),
              confirmed: true,
            });
            output = observation;
            break;
          }
          case "render_ui": {
            const surface = String(call.argumentsObj.surface ?? "opportunity-board");
            const outcomeId = call.argumentsObj.outcome_id as string | undefined;
            const spec = this.renderUiSpec(surface, outcomeId);
            output = { surface, spec };
            emit({ event: "ui", data: { id: `ui-${Date.now()}`, spec } }, onEvent);
            break;
          }
          default: {
            output = { error: `Unknown tool: ${call.name}` };
          }
        }
      } catch (error) {
        output = { error: asStudioError(error) };
      }

      call.output = output;
      emit(toolEvent(call.name, "ok"), onEvent);
      emit(toolResultEvent(call.name, output), onEvent);
      if (canvasDirty) {
        emit({ event: "canvas_dirty", data: {} }, onEvent);
      }
      if (observation) {
        emit({ event: "memory", data: { observation } }, onEvent);
      }
    }
  }

  private renderUiSpec(
    surface: string,
    outcomeId?: string,
  ): Record<string, unknown> {
    if (surface === "outcome-card") {
      return {
        type: "outcome-card",
        props: {
          id: outcomeId ?? "",
          statement: "",
          importance: 0,
          satisfaction: 0,
          opportunityScore: 0,
        },
      };
    }
    return {
      type: "stack",
      props: { direction: "vertical", gap: "md" },
      children: [],
    };
  }
}

interface StoredConversationLike {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}
