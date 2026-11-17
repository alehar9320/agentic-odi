/**
 * The generated contract guards the hand-written types (issue #1088).
 *
 * `schema.d.ts` is generated from `openapi.json`, which is generated from the
 * running FastAPI app. Before this file existed, nothing imported it: the
 * hand-written interfaces in `../types` were the only description of a
 * response, so a renamed or removed server field stayed `undefined` at runtime
 * instead of failing `tsc`.
 *
 * Each assertion below fails the build when the hand-written type no longer
 * satisfies the server's declared model — a required field renamed, removed, or
 * added. Optional fields are not compared, because a hand-written type is
 * allowed to be narrower than the wire shape; the point is that the server's
 * required shape is a checked fact, not a hope.
 *
 * When an assertion fails, read the field the compiler names in `schema.d.ts`,
 * update `../types` to match, and leave this file alone. To add coverage,
 * assert another pair. This module is type-only: it emits no JavaScript.
 */

import type { components } from "./schema";
import type { Conversation, ConversationSummary, Observation } from "../types";

type Schemas = components["schemas"];

/** True when `A` is assignable to `B` (every field `B` requires, `A` has). */
type Extends<A, B> = A extends B ? true : false;

/** Fails to compile unless the argument is exactly `true`. */
type Assert<T extends true> = T;

export type ObservationMatchesContract = Assert<Extends<Observation, Schemas["ObservationModel"]>>;

export type ConversationMatchesContract = Assert<
  Extends<Conversation, Schemas["ConversationModel"]>
>;

export type ConversationSummaryMatchesContract = Assert<
  Extends<ConversationSummary, Schemas["ConversationSummaryModel"]>
>;
