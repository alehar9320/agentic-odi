import { useMemo, useState } from "react";

/** What a field or section says after a save was attempted. */
export type FieldSaveStatus =
  | { kind: "idle" }
  | { kind: "saved" }
  | { kind: "error"; reason: string };

/**
 * What a section says after its fields have been touched: the first refusal, so
 * a section never claims "Saved" while any field is still refused; otherwise
 * "Saved" once any field landed.
 */
export function summarizeSaves(statuses: FieldSaveStatus[]): FieldSaveStatus {
  const failed = statuses.find((status) => status.kind === "error");
  if (failed) {
    return failed;
  }
  if (statuses.some((status) => status.kind === "saved")) {
    return { kind: "saved" };
  }
  return { kind: "idle" };
}

/** Collect each field's outcome and reduce them to one line for the section. */
export function useSectionSaves() {
  const [statuses, setStatuses] = useState<Record<string, FieldSaveStatus>>({});

  const report = useMemo(
    () => (field: string, status: FieldSaveStatus) => {
      setStatuses((previous) => {
        if (previous[field] === status) {
          return previous;
        }
        return { ...previous, [field]: status };
      });
    },
    [],
  );

  const summary = useMemo(() => summarizeSaves(Object.values(statuses)), [statuses]);

  return { report, summary };
}
