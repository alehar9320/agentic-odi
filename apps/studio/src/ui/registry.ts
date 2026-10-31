import type { ComponentType } from "react";

import {
  Bet,
  DecisionRecord,
  DecisionReview,
  EvidenceQuote,
  ImpactSimulation,
  JobMap,
  OpportunityBoard,
  OpportunityBrief,
  OutcomeCompare,
  Roadmap,
  SegmentProfile,
  OpportunityThesis,
  OutcomeCard,
} from "./cards";
import {
  Callout,
  Divider,
  Grid,
  Heading,
  ListBlock,
  Meter,
  Stack,
  Stat,
  Text,
  type NodeProps,
} from "./primitives";

/**
 * The renderable half of the catalog. Kept separate from `catalog.ts` so the
 * wire manifest stays dependency-free and can be handed to the sidecar as plain
 * JSON.
 */
export const NODE_COMPONENTS: Record<string, ComponentType<NodeProps>> = {
  stack: Stack,
  grid: Grid,
  heading: Heading,
  text: Text,
  list: ListBlock,
  stat: Stat,
  meter: Meter,
  callout: Callout,
  divider: Divider,

  "outcome-card": OutcomeCard,
  "opportunity-board": OpportunityBoard,
  "opportunity-thesis": OpportunityThesis,
  "opportunity-brief": OpportunityBrief,
  "outcome-compare": OutcomeCompare,
  roadmap: Roadmap,
  "impact-simulation": ImpactSimulation,
  "evidence-quote": EvidenceQuote,
  "job-map": JobMap,
  "decision-record": DecisionRecord,
  "decision-review": DecisionReview,
  bet: Bet,
  "segment-profile": SegmentProfile,
};
