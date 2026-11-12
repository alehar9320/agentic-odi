import { useEffect, useState } from "react";

import { fetchLatestBriefing } from "../../api/studioApi";
import { isBriefingDismissed, markBriefingDismissed } from "../../lib/briefingDismissed";
import { formatRelativeTime } from "../../lib/relativeTime";
import { useStudio } from "../../state/StudioContext";
import type { Briefing, BriefingItem, SignalSubjectKind } from "../../types";

/** The kinds the studio can actually open; anything else is shown as plain text. */
const OPENABLE: ReadonlySet<string> = new Set<SignalSubjectKind>([
  "job",
  "step",
  "outcome",
  "evidence",
  "segment",
  "strategy",
]);

function isOpenable(kind: string): kind is SignalSubjectKind {
  return OPENABLE.has(kind);
}

function KindTag({ kind }: { kind: BriefingItem["kind"] }) {
  if (kind === "failed") {
    return <span className="badge badge--amber">Failed</span>;
  }
  if (kind === "added") {
    return <span className="badge badge--green">New</span>;
  }
  return <span className="badge badge--blue">Changed</span>;
}

/**
 * The one readable briefing the overnight run left behind.
 *
 * Every line is a link to the record it describes: activating it opens that
 * record through the studio's single open-record path. A briefing with no lines
 * is a real answer — the run finished and changed nothing — so it says so
 * rather than showing an empty box.
 */
export function BriefingCard() {
  const { openRecord } = useStudio();
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const load = () => {
      fetchLatestBriefing()
        .then((latest) => {
          if (cancelled) {
            return;
          }
          setBriefing(latest);
          setDismissed(
            latest ? isBriefingDismissed(latest.run_id, latest.created_at) : false
          );
        })
        .catch(() => {
          // A briefing is a morning convenience, not a gate: a failed read shows
          // nothing rather than an error the reader cannot act on.
          if (!cancelled) {
            setBriefing(null);
          }
        });
    };

    load();

    // Reload when the window becomes visible again: the latest finished run may
    // have changed while the tab was backgrounded.
    if (typeof document !== "undefined" && document.addEventListener) {
      const onVisibilityChange = () => {
        if (document.visibilityState === "visible") {
          load();
        }
      };
      document.addEventListener("visibilitychange", onVisibilityChange);
      return () => {
        cancelled = true;
        document.removeEventListener("visibilitychange", onVisibilityChange);
      };
    }

    return () => {
      cancelled = true;
    };
  }, []);

  if (!briefing || dismissed) {
    return null;
  }

  function dismiss() {
    if (briefing) {
      markBriefingDismissed(briefing.run_id, briefing.created_at);
    }
    setDismissed(true);
  }

  // At most four lines, and every displayed line opens its record: non-openable
  // kinds are excluded so no line lacks an open action.
  const items = briefing.items.filter((item) => isOpenable(item.record_kind)).slice(0, 4);

  return (
    <section className="card briefing-card" aria-label="Since you were away">
      <div className="card__head">
        <div>
          <span className="hero__eyebrow">Latest finished run</span>
          <h2 className="briefing-card__title">Since you were away</h2>
        </div>
        <div className="briefing-card__actions">
          <time className="briefing-card__time" dateTime={briefing.created_at}>
            {formatRelativeTime(briefing.created_at)}
          </time>
          <button
            type="button"
            className="button button--ghost"
            onClick={dismiss}
            title="Hide this briefing"
          >
            Dismiss
          </button>
        </div>
      </div>

      {items.length === 0 ? (
        <p className="briefing-card__empty">
          The run finished and found nothing that needs your attention.
        </p>
      ) : (
        <ul className="briefing-card__items">
          {items.map((item) => (
            <li key={`${item.record_kind}:${item.record_id}`} className="briefing-card__item">
              <KindTag kind={item.kind} />
              <button
                type="button"
                className="briefing-card__link"
                onClick={() => openRecord(item.record_kind as SignalSubjectKind, item.record_id)}
              >
                {item.text}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
