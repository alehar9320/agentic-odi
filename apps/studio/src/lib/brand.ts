/**
 * One source of truth for the product's name and the copy built from it.
 *
 * Every surface used to invent its own variant ("The Living Studio", "Agentic
 * ODI Living Studio", "Living Studio 0.14.0 is ready"), so the chrome repeated
 * the name instead of saying what it does. Components import from here, and
 * `brandCopy.test.ts` fails if a literal returns.
 */

export const PRODUCT_NAME = "Living Studio";
export const COMPANY_NAME = "Agentic ODI";

/** The one document title, used by the shell and the desktop bundle. */
export function productTitle(): string {
  return PRODUCT_NAME;
}

/**
 * The window title: it says what the window holds.
 *
 * Home names the product and the company; a thread names itself and says the
 * product once; unread signals come first, the way a mailbox counts before the
 * subject. The shell sets this and nothing else does (#695).
 */
export function studioWindowTitle(options: {
  threadTitle?: string | null;
  unreadSignals?: number;
}): string {
  const unread = options.unreadSignals ?? 0;
  const prefix = unread > 0 ? `(${unread}) ` : "";
  const thread = options.threadTitle?.trim();
  return thread
    ? `${prefix}${thread} — ${PRODUCT_NAME}`
    : `${prefix}The ${PRODUCT_NAME} | ${COMPANY_NAME}`;
}

/** The version, named without the product: the banner is already inside it. */
export function versionLabel(version: string): string {
  return `Version ${version}`;
}

export type UpdateTitleState = "downloading" | "installing" | "ready";

/** Update copy that says what is happening, not who is doing it. */
export function updateTitle(version: string, state: UpdateTitleState): string {
  switch (state) {
    case "downloading":
      return `Downloading version ${version}`;
    case "installing":
      return `Installing version ${version}`;
    case "ready":
      return `Version ${version} is ready. Restart to finish.`;
  }
}
