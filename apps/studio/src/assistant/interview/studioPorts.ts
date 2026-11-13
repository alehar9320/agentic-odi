/**
 * The interview's port into the Studio store (issue #397).
 *
 * The conductor never imports the store; it takes a small `InterviewPorts`
 * object. This hook is the one place that builds those ports from the actions
 * the Studio already exposes — `createJob` and `addOutcome` from
 * `StudioContext`, and `addEvidence` from the API client — so the interview
 * writes through the same paths as every other capture. No new route, no new
 * store.
 */

import { useMemo } from "react";

import { addEvidence as apiAddEvidence } from "../../api/studioApi";
import { useStudio, writeReceipt } from "../../state/StudioContext";
import type { InterviewPorts } from "./conductor";

export function useInterviewPorts(): InterviewPorts {
  const { createJob, addOutcome, settings, refreshCanvas, pushToast } = useStudio();
  const mcpUrl = settings.mcp_url;

  return useMemo<InterviewPorts>(
    () => ({
      createJob: (payload) => createJob(payload),
      addOutcome: async (payload) => {
        // The context action owns the write, the receipt, and the refresh. It
        // returns no id, so the conductor links evidence to the job until a
        // later slice threads the created outcome back (#400).
        await addOutcome(payload);
        return null;
      },
      addEvidence: async (payload) => {
        const result = await apiAddEvidence({ ...payload, mcp_url: mcpUrl });
        pushToast("success", writeReceipt(result, "Evidence captured."));
        await refreshCanvas();
      },
    }),
    [createJob, addOutcome, mcpUrl, refreshCanvas, pushToast],
  );
}
