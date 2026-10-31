import type { Signal } from "../../../types";

/**
 * The three example signals the old developer simulator fabricated, kept as
 * test data only. They are imported by test files and never by the application,
 * so Vite keeps them out of the production bundle. No runtime path renders them.
 */
export const DEMO_SIGNALS: Signal[] = [
  {
    id: "demo-1",
    kind: "evidence_ingested",
    title: 'Evidence from "telemetry": cluster config friction',
    detail: "Analyzed workflow traces: 82% of users report friction during cluster config.",
    subject_kind: "evidence",
    subject_id: "EV-DEMO-1",
    severity: "info",
    created_at: "2026-10-01T09:00:00+00:00",
    suppressed: false,
    fingerprint: "demo-fp-1",
  },
  {
    id: "demo-2",
    kind: "opportunity_crossed",
    title: "Opportunity score crossed 10 (up): validation rules",
    detail: "Satisfaction fell to 3 while importance held at 9.",
    subject_kind: "outcome",
    subject_id: "O-DEMO-2",
    severity: "urgent",
    created_at: "2026-10-01T09:05:00+00:00",
    suppressed: false,
    fingerprint: "demo-fp-2",
  },
  {
    id: "demo-3",
    kind: "job_map_completed",
    title: "Job map complete: Deploy a release covers all 8 stages",
    subject_kind: "job",
    subject_id: "JOB-DEMO-3",
    severity: "notice",
    created_at: "2026-10-01T09:10:00+00:00",
    suppressed: false,
    fingerprint: "demo-fp-3",
  },
];
