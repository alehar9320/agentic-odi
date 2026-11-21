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

import { useEffect, useMemo, useState } from "react";

import { addEvidence as apiAddEvidence } from "../../api/studioApi";
import { useStudio, writeReceipt } from "../../state/StudioContext";
import type { InterviewPorts } from "./conductor";
import type { InterviewDraftOptions } from "./Interview";
import type { DraftStore } from "./persistence";

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

/**
 * The interview's draft store, read from the local BFF (#402).
 *
 * `getStudioBff()` opens the same store every other Studio write uses, so the
 * draft lands beside the records rather than in a second store. It is opened in
 * an effect, not during render, because the store is a promise and a render must
 * stay synchronous; until it resolves the interview runs without a draft and
 * starts persisting as soon as it does. A store that never opens leaves the
 * interview fully usable in memory — the fail-soft rule of #402.
 */
export function useInterviewDraft(jobId: string | null): InterviewDraftOptions | undefined {
  const [store, setStore] = useState<DraftStore | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const { getStudioBff } = await import("../../bff/index");
        const bff = await getStudioBff();
        if (!cancelled) {
          setStore(bff.store);
        }
      } catch {
        // Fail soft: no store, no draft, and the interview still works.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return useMemo(() => (jobId && store ? { store, jobId } : undefined), [jobId, store]);
}
