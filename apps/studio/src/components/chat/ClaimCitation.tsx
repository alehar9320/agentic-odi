import { HoverCard } from "@/components/ui/hover-card"
import type { Claim } from "../../types"

/** A cited claim that opens its provenance in place. */
export function ClaimCitation({
  claim,
  onOpenRecord,
}: {
  claim: Claim
  /** Called with the evidence record id when the person opens a source from the popover. */
  onOpenRecord?: (citationId: string) => void
}) {
  const hasSource = claim.evidence.length > 0

  return (
    <HoverCard
      children={claim.text}
      content={
        <div className="claim-citation">
          {hasSource ? (
            <>
              <p className="claim-citation__quote">{claim.text}</p>
              {claim.evidence.map((citation) => {
                const label = citation.source_name
                  ? `${citation.source_name} · ${citation.name}`
                  : citation.name
                return (
                  <button
                    key={citation.id}
                    type="button"
                    className="claim-citation__source"
                    title="Open this record"
                    onClick={() => onOpenRecord?.(citation.id)}
                  >
                    {label}
                  </button>
                )
              })}
            </>
          ) : (
            <p className="claim-citation__empty">No source recorded</p>
          )}
        </div>
      }
    />
  )
}
