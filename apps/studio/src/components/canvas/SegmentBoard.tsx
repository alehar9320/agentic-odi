import { useEffect, useMemo, useState } from "react";

import { asStudioError, proposeStrategy as apiProposeStrategy } from "../../api/studioApi";
import { useStudio } from "../../state/StudioContext";
import type { Segment, Strategy } from "../../types";
import type { UiNode } from "../../ui/protocol";
import { UiRenderer } from "../../ui/UiRenderer";
import { FailurePanel } from "../FailurePanel";

/**
 * The cards the chat renders are the cards the lens renders: one catalog, one
 * renderer, so a segment never looks different depending on how you got there.
 */
function segmentNode(segment: Segment): UiNode {
  return {
    type: "segment-card",
    props: {
      id: segment.id,
      name: segment.name,
      people: segment.people,
      peopleInferred: segment.people_inferred ?? false,
      jobStatement: segment.job_statement,
      verdict: segment.verdict ?? "unknown",
      confidence: segment.confidence,
      outcomeIds: segment.outcome_ids,
      rationale: segment.rationale,
    },
    children: [],
  };
}

function strategyNode(strategy: Strategy): UiNode {
  return {
    type: "strategy-card",
    props: {
      id: strategy.id,
      kind: strategy.kind,
      segmentId: strategy.segment_id ?? undefined,
      thesis: strategy.thesis,
      bets: strategy.bets,
      rejected: strategy.rejected,
    },
    children: [],
  };
}

function byConfidence(a: Segment, b: Segment): number {
  return b.confidence - a.confidence;
}

/**
 * Stage 5 and stage 6 on one board: who the outcomes point at, then the bet that
 * follows from it. Both halves read the store, so nothing here is a guess the
 * conversation has not already made.
 */
export function SegmentBoard() {
  const {
    segments,
    strategy,
    segmentsError,
    refreshSegments,
    canvas,
    settings,
    pushToast,
    sendMessage,
    closePanel,
  } = useStudio();
  const [busy, setBusy] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);

  useEffect(() => {
    void refreshSegments();
  }, [refreshSegments]);

  const outcomes = useMemo(() => canvas?.outcomes ?? [], [canvas]);
  const unclustered = useMemo(() => {
    const clustered = new Set(segments.flatMap((segment) => segment.outcome_ids));
    return outcomes.filter((outcome) => outcome.id && !clustered.has(outcome.id));
  }, [outcomes, segments]);

  const ordered = useMemo(() => [...segments].sort(byConfidence), [segments]);

  function askForSegments() {
    closePanel();
    void sendMessage(
      "Segment the outcomes I have scored and tell me who this is for, with the confidence behind it.",
    );
  }

  async function propose() {
    setBusy(true);
    setRefusal(null);
    try {
      await apiProposeStrategy(settings.mcp_url);
      await refreshSegments();
      pushToast("success", "Recorded the path the segments support.");
    } catch (error) {
      // A refused bet says what is missing. Show that instead of a generic
      // failure, because it is the answer to "so what do we do?".
      const problem = asStudioError(error);
      setRefusal(problem.message);
    } finally {
      setBusy(false);
    }
  }

  if (segmentsError && segments.length === 0) {
    return <FailurePanel error={segmentsError} retryText="Segments" onRetry={() => void refreshSegments()} />;
  }

  return (
    <section className="fade-in segments-board">
      {ordered.length === 0 ? (
        <div className="segments-board__empty">
          <p className="empty-note">
            No segments yet. A segment is a group of people plus the job they are doing, and it
            only exists once two or more scored outcomes cluster together — never from a
            demographic guess.
          </p>
          <button type="button" className="button button--block" onClick={askForSegments}>
            Cluster my scored outcomes
          </button>
        </div>
      ) : (
        <div className="segments-board__list">
          {ordered.map((segment) => (
            <UiRenderer key={segment.id} node={segmentNode(segment)} />
          ))}
        </div>
      )}

      {unclustered.length > 0 ? (
        <div className="segments-board__unclustered">
          <p className="caption">
            {`Unclustered — ${unclustered.length} outcome(s) joined no segment. One outcome is a hypothesis, not a market.`}
          </p>
          <ul>
            {unclustered.slice(0, 8).map((outcome) => (
              <li key={outcome.id}>{outcome.statement ?? outcome.id}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="segments-board__strategy">
        {strategy ? (
          <UiRenderer node={strategyNode(strategy)} />
        ) : (
          <p className="empty-note">
            No strategy recorded. The recommended path only exists once the segments support one —
            ask the studio what to do and it names the paths it beat.
          </p>
        )}
        <button
          type="button"
          className="quiet-action"
          onClick={() => void propose()}
          disabled={busy || ordered.length === 0}
        >
          {busy ? "Proposing…" : "Propose the path"}
        </button>
        {ordered.length === 0 ? (
          <p className="empty-note">Segmentation comes first: a bet needs a segment to aim at.</p>
        ) : null}
        {refusal ? <p className="segments-board__refusal">{refusal}</p> : null}
      </div>
    </section>
  );
}
