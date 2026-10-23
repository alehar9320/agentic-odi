import { useState } from "react";
import { useStudio } from "../../state/StudioContext";

export function EvidenceStream() {
  const { canvas, deleteEvidence, promoteEvidence } = useStudio();
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const items = canvas?.evidence ?? [];

  return (
    <section className="stack">
      <p className="notice">
        Signals & Evidence captured from external connectors (Gong, Slack, Notion, Jira) or manual research. Knowledge remains stored in external tools while Agentic ODI orchestrates links to Jobs, Steps, and Outcomes.
      </p>

      {items.length === 0 ? (
        <p className="empty-state">No evidence or research signals captured yet.</p>
      ) : (
        items.map((item) => {
          const hasLinks = item.job_id || item.outcome_id || item.step_id;
          return (
            <figure className="evidence" key={item.id}>
              <figcaption style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span>
                  <strong>{item.name}</strong> · {item.source_name} ({item.source_kind})
                </span>
                {item.url && (
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="quiet-action"
                    style={{ textDecoration: "underline" }}
                  >
                    Open in {item.source_name} ↗
                  </a>
                )}
              </figcaption>
              <blockquote>“{item.content}”</blockquote>
              <div
                className="evidence__meta"
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginTop: "0.5rem",
                }}
              >
                <span>
                  {hasLinks ? (
                    <>
                      Linked to: {[item.job_id, item.step_id, item.outcome_id].filter(Boolean).join(" / ")}
                    </>
                  ) : (
                    <em>Unlinked research signal</em>
                  )}
                </span>
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <button
                    type="button"
                    className="quiet-action"
                    onClick={() => {
                      void promoteEvidence(item.id, { target: "outcome" });
                    }}
                  >
                    Promote to Outcome
                  </button>
                  <button
                    type="button"
                    className="quiet-action quiet-action--danger"
                    disabled={deletingId === item.id}
                    onClick={() => {
                      setDeletingId(item.id);
                      void deleteEvidence(item.id).finally(() => setDeletingId(null));
                    }}
                  >
                    {deletingId === item.id ? "Removing…" : "Remove"}
                  </button>
                </div>
              </div>
            </figure>
          );
        })
      )}
    </section>
  );
}
