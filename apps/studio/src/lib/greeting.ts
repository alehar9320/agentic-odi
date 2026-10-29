/**
 * Headline copy for the conversational home screen.
 *
 * The hero line is the only "chrome" above the composer, so it has to earn its
 * space: it greets when it knows who you are, reflects what is already on the
 * canvas when there is data, and otherwise explains what the studio can do.
 * The lines rotate so the surface feels alive rather than static.
 */

export interface GreetingContext {
  now: Date;
  displayName?: string | null;
  jobCount: number;
  outcomeCount: number;
  underservedCount: number;
  llmHealthy?: boolean | null;
  productName?: string | null;
  jobStatement?: string | null;
}

export type GreetingKind = "greeting" | "insight" | "capability" | "status";

export interface Greeting {
  id: string;
  text: string;
  kind: GreetingKind;
}

/** Seconds between hero rotations. Exported so the UI and tests agree. */
export const GREETING_ROTATION_MS = 7000;

function cleanName(displayName?: string | null): string | null {
  const trimmed = displayName?.trim();
  if (!trimmed) {
    return null;
  }
  return trimmed.replace(/\s+/g, " ");
}

export function timeOfDayGreeting(now: Date): string {
  const hour = now.getHours();
  if (hour >= 5 && hour < 12) {
    return "Good morning";
  }
  if (hour >= 12 && hour < 18) {
    return "Good afternoon";
  }
  return "Good evening";
}

function plural(count: number, one: string, many = `${one}s`): string {
  return `${count} ${count === 1 ? one : many}`;
}

export function greetingCandidates(context: GreetingContext): Greeting[] {
  const name = cleanName(context.displayName);
  const greeting = timeOfDayGreeting(context.now);
  // The first frame is an invitation, not a clock. A greeting is warm but it
  // says nothing about why the person is here; the question does.
  const candidates: Greeting[] = [
    { id: "capability-win", text: "What do you want to win?", kind: "capability" },
    {
      id: "greeting",
      text: name ? `${greeting}, ${name}` : greeting,
      kind: "greeting",
    },
  ];

  if (context.outcomeCount > 0) {
    candidates.push({
      id: "insight-outcomes",
      text:
        context.underservedCount > 0
          ? `${plural(context.outcomeCount, "outcome")} mapped — ${context.underservedCount} underserved.`
          : `${plural(context.outcomeCount, "outcome")} mapped. Nothing is starving for attention.`,
      kind: "insight",
    });
  }

  if (context.jobCount > 0) {
    candidates.push({
      id: "insight-jobs",
      text:
        context.jobCount === 1
          ? "One job on the canvas. Want to break it into steps?"
          : `${plural(context.jobCount, "job")} on the canvas. Want to break one into steps?`,
      kind: "insight",
    });
  }

  candidates.push(
    {
      id: "capability-opportunity",
      text: "What opportunity is on your mind?",
      kind: "capability",
    },
    {
      id: "capability-bet",
      text: "Tell me the bet you're weighing. I'll tell you what would have to be true.",
      kind: "capability",
    },
  );

  const product = context.productName?.trim();
  if (product && context.jobStatement?.trim()) {
    candidates.push({
      id: "context-job",
      text: `${product} — ${context.jobStatement.trim()}`,
      kind: "insight",
    });
  } else if (product) {
    candidates.push({
      id: "context-product",
      text: `What job is ${product} hired to do?`,
      kind: "insight",
    });
  }

  if (context.llmHealthy === false) {
    candidates.push({
      id: "status-offline",
      text: "No model right now — the studio still works by hand.",
      kind: "status",
    });
  }

  return candidates;
}

/**
 * Pick the next headline in the rotation, never repeating the current one.
 */
export function nextGreeting(candidates: Greeting[], currentId?: string | null): Greeting | null {
  if (!candidates.length) {
    return null;
  }
  const currentIndex = candidates.findIndex((candidate) => candidate.id === currentId);
  return candidates[(currentIndex + 1) % candidates.length];
}
