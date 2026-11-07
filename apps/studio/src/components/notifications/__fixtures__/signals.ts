import type { Signal } from "../../../types";

/**
 * Example signals for tests and snapshots only. They are data a reviewer can
 * read, not a runtime path: nothing in the app imports this module, so no
 * fabricated card can reach a person's inbox.
 */
export const DEMO_SIGNALS: Signal[] = [
  {
    id: "demo-1",
    kind: "evidence_ingested",
    title: 'Evidence from "telemetry": cluster config friction',
    detail: "Analyzed workflow traces: 82% of users report friction during cluster config.",
    severity: "info",
    created_at: "2026-10-22T09:00:00+00:00",
    suppressed: false,
    fingerprint: "demo-fingerprint-1",
  },
  {
    id: "demo-2",
    kind: "opportunity_crossed",
    title: "Opportunity score crossed 10 (up): validation rules",
    detail: "Satisfaction fell to 3 while importance held at 9.",
    severity: "urgent",
    created_at: "2026-10-22T09:05:00+00:00",
    suppressed: false,
    fingerprint: "demo-fingerprint-2",
  },
  {
    id: "demo-3",
    kind: "job_map_completed",
    title: "Job map complete: Deploy a release covers all 8 stages",
    severity: "notice",
    created_at: "2026-10-22T09:10:00+00:00",
    suppressed: false,
    fingerprint: "demo-fingerprint-3",
  },
];
