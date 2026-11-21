import type { ReactNode } from "react";

import { Markdown } from "../chat/Markdown";
import { StatValue } from "../../ui/primitives";

/**
 * One labelled block in a detail's body: an eyebrow, then its content.
 *
 * The body of a detail reads as a stack of these rather than a free-form panel
 * (#740). The eyebrow is the only thing this adds; the content is whatever
 * existing primitive the block needs, so no catalog entry is invented here.
 */
export function DetailBlock({ eyebrow, children }: { eyebrow: string; children: ReactNode }) {
  return (
    <section className="detail-block">
      <p className="detail-block__eyebrow">{eyebrow}</p>
      <div className="detail-block__body">{children}</div>
    </section>
  );
}

/**
 * The IMPACT block: the large numeral, its caption, and an optional delta.
 * Reuses `StatValue` so the headline number carries the display serif and looks
 * the same as it does wherever else a stat lands (#740).
 */
export function ImpactBlock({
  label,
  value,
  caption,
  tone = "neutral",
}: {
  label: string;
  value: string;
  caption?: string;
  tone?: "neutral" | "positive" | "warning" | "critical";
}) {
  return (
    <DetailBlock eyebrow={label}>
      <StatValue label={label} value={value} {...(caption ? { delta: caption } : {})} tone={tone} />
    </DetailBlock>
  );
}

/**
 * The WHAT'S HAPPENING block: one or two plain sentences, rendered through the
 * same Markdown primitive the transcript uses so the two cannot drift.
 */
export function ProseBlock({ label, text }: { label: string; text: string }) {
  return (
    <DetailBlock eyebrow={label}>
      <div className="ui-text detail-block__prose">
        <Markdown source={text} />
      </div>
    </DetailBlock>
  );
}
