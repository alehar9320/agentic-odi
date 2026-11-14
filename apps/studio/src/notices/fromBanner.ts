/**
 * Turning a banner into a notice.
 *
 * A banner is transient; a notice is its durable record. The resolution here
 * reuses the banner catalog's own defaults, so a notice's severity and copy are
 * always the same words the person saw on screen — never a second, drifting
 * description of the same event.
 */

import { resolveSpec } from "../banners/catalog";
import type { BannerSpec } from "../banners/types";
import type { NoticeInput } from "./types";

export function noticeFromBanner(spec: BannerSpec): Omit<NoticeInput, "at"> {
  const resolved = resolveSpec(spec);
  return {
    severity: resolved.severity,
    title: resolved.title,
    detail: resolved.body,
    context: `Banner: ${resolved.kind}`,
  };
}
