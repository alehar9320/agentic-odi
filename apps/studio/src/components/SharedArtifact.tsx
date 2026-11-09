import { useEffect, useState } from "react";

import { fetchSharedArtifact } from "../api/studioApi";
import { PRODUCT_NAME } from "../lib/brand";
import { formatOpportunityScore, isUnderserved } from "../lib/odi";
import { formatShareExpiry, isShareExpired } from "../lib/share";
import type { SharedArtifactPayload } from "../types";

/**
 * One shared artifact, read-only.
 *
 * This page is deliberately not the Studio with controls hidden. It holds no
 * workspace state and reads exactly one thing: the scoped payload a share token
 * returns. There is no rail, no composer, no navigation into the app, and no
 * control that implies the reader can edit — the only action on the page is the
 * browser's own print, which needs no code here. An expired or unknown token
 * shows one sentence and no data.
 */

type LoadState =
  | { kind: "loading" }
  | { kind: "ready"; payload: SharedArtifactPayload }
  | { kind: "expired" }
  | { kind: "unavailable" };

const TITLE: Record<SharedArtifactPayload["kind"], string> = {
  landscape: "Opportunity landscape",
  vision: "Vision",
};

/** Whether a payload names one of the artifact kinds this page can render. */
function isRenderable(payload: SharedArtifactPayload): boolean {
  return payload.kind === "landscape" || payload.kind === "vision";
}

export function SharedArtifact({ token }: { token: string }) {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetchSharedArtifact(token)
      .then((payload) => {
        if (cancelled) {
          return;
        }
        if (!isRenderable(payload)) {
          // A kind this build does not know is not something to guess at.
          setState({ kind: "unavailable" });
          return;
        }
        setState(
          isShareExpired(payload.expires_at)
            ? { kind: "expired" }
            : { kind: "ready", payload },
        );
      })
      .catch(() => {
        if (!cancelled) {
          setState({ kind: "unavailable" });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <main className="shared-page" tabIndex={-1}>
      {state.kind === "loading" ? (
        <p className="shared-page__status" role="status">
          Opening the shared artifact…
        </p>
      ) : state.kind === "expired" ? (
        <p className="shared-page__status" role="status">
          This shared link has expired.
        </p>
      ) : state.kind === "unavailable" ? (
        <p className="shared-page__status" role="status">
          This shared link is no longer available.
        </p>
      ) : (
        <SharedBody payload={state.payload} />
      )}
    </main>
  );
}

function SharedBody({ payload }: { payload: SharedArtifactPayload }) {
  const expiry = formatShareExpiry(payload.expires_at);
  const outcomes = payload.outcomes ?? [];
  const evidence = payload.evidence ?? [];

  return (
    <>
      <header className="shared-page__head">
        <p className="shared-page__eyebrow">{PRODUCT_NAME}</p>
        <h1 className="shared-page__title">{TITLE[payload.kind]}</h1>
        <p className="shared-page__expiry">
          Shared read-only{expiry ? ` · ${expiry}` : ""}
        </p>
      </header>

      {payload.source === "seed" ? (
        <p className="shared-page__sample" role="status">
          <strong>Sample data.</strong> Nothing here comes from the sender&apos;s own research.
        </p>
      ) : null}

      {payload.kind === "vision" ? (
        <section aria-label="Vision" className="shared-section">
          {payload.vision ? (
            <blockquote className="shared-vision">{payload.vision}</blockquote>
          ) : (
            <p className="shared-page__empty">This vision holds no words.</p>
          )}
        </section>
      ) : (
        <>
          <section aria-label="Opportunities" className="shared-section">
            <h2 className="shared-section__title">Opportunities</h2>
            {outcomes.length ? (
              <ul className="shared-outcomes">
                {outcomes.map((outcome) => (
                  <li
                    key={outcome.id}
                    className={`shared-outcome${isUnderserved(outcome.opportunity_score) ? " shared-outcome--hot" : ""}`}
                  >
                    <div className="shared-outcome__head">
                      <span className="shared-outcome__id">{outcome.id}</span>
                      <span className="badge badge--blue">
                        Opportunity {formatOpportunityScore(outcome.opportunity_score)}
                      </span>
                    </div>
                    <p className="shared-outcome__statement">
                      {outcome.statement ?? "Untitled outcome"}
                    </p>
                    <p className="shared-outcome__meta">
                      Importance <b>{outcome.importance ?? "—"}</b>
                      <span aria-hidden="true"> · </span>
                      Satisfaction <b>{outcome.satisfaction ?? "—"}</b>
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="shared-page__empty">No opportunities were shared.</p>
            )}
          </section>

          <section aria-label="Evidence" className="shared-section">
            <h2 className="shared-section__title">Evidence</h2>
            {evidence.length ? (
              <ul className="shared-evidence">
                {evidence.map((item) => (
                  <li key={item.id} className="shared-evidence__item">
                    <p className="shared-evidence__name">
                      {item.name ?? item.source_name ?? "Evidence"}
                    </p>
                    {item.content ? (
                      <p className="shared-evidence__content">{item.content}</p>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="shared-page__empty">No evidence was shared.</p>
            )}
          </section>
        </>
      )}
    </>
  );
}
