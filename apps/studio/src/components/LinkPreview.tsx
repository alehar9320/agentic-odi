import type { Link } from "../types";
import { RouteIcon } from "./icons";

const RELATIONSHIP_LABELS: Record<string, string> = {
  evidence_for: "evidence for",
  outcome_of: "outcome of",
  blocked_by: "blocked by",
  duplicates: "duplicates",
  relates_to: "relates to",
};

function relationshipLabel(type: string): string {
  const label = RELATIONSHIP_LABELS[type];
  return label ?? type.replaceAll(/_/g, " ");
}

function shortId(id: string): string {
  return id.length > 12 ? `${id.slice(0, 12)}…` : id;
}

/**
 * A presentational chip that makes a stored link readable. It is a pure
 * function of its props: no fetching, no app state, no new dependency.
 */
export function LinkPreview({ link }: { link: Link }) {
  const {
    relationship_type,
    target_type,
    target_id,
    external_system,
    external_id,
    preview,
  } = link;
  const label = relationshipLabel(relationship_type);
  const target = preview?.title ?? shortId(target_id);
  const badge = `${external_system} · ${external_id ?? ""}`;

  return (
    <span className="link-preview" aria-label={label}>
      <RouteIcon size={14} />
      <span className="link-preview__relationship">{label}</span>
      <span className="link-preview__target">
        <span className="link-preview__type">{target_type}</span>{" · "}
        <span className="link-preview__id">{target}</span>
      </span>
      {external_system ? (
        <span className="link-preview__badge">
          {preview && preview.url ? (
            <a href={preview.url} className="link-preview__badgeLink">
              {badge}
            </a>
          ) : (
            badge
          )}
        </span>
      ) : null}
    </span>
  );
}
