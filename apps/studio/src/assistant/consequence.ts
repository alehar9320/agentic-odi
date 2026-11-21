/**
 * What a write approval will actually do, in one sentence.
 *
 * The approval card used to ask `Run <tool>?`, which is a question about a
 * tool name rather than about an action. This module turns the name into the
 * effect it has — and, when the name is one it does not know, says so plainly
 * ("runs make_coffee") instead of inventing an effect the tool may not have.
 *
 * The noun is derived from the tool name, never guessed. Only the article is
 * corrected, and only for the few nouns where English needs it.
 */

/** Nouns the tool vocabulary uses that do not take "a" before them. */
const UNCOUNTABLE = new Set(["evidence", "work", "data"]);

function noun(rest: string): string {
  return rest.replace(/_/g, " ");
}

function article(rest: string, nounText: string): string {
  if (UNCOUNTABLE.has(rest)) {
    return "";
  }
  return /^[aeiou]/.test(nounText) ? "an " : "a ";
}

/**
 * The consequence of running `tool`, as one sentence fragment.
 *
 * `add_*` and `create_*` create, `update_*` changes, `delete_*` removes.
 * Anything else is reported as running the tool, unchanged.
 */
export function describeConsequence(tool: string): string {
  const match = /^(add|create|update|delete)_(.+)$/.exec(tool);
  if (!match) {
    return `runs ${tool}`;
  }
  const [, verb, rest] = match;
  const nounText = noun(rest);
  const articleText = article(rest, nounText);
  if (verb === "update") {
    return `changes an existing ${nounText}`;
  }
  if (verb === "delete") {
    return `removes ${articleText}${nounText}`.replace("  ", " ");
  }
  return `creates ${articleText}${nounText}`.replace("  ", " ");
}
