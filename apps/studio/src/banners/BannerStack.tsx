import * as Toast from "@radix-ui/react-toast";

import { BannerRow } from "./Banner";
import { useBannerOptional } from "./BannerProvider";
import type { Banner, BannerActionId, BannerDock } from "./types";

export interface BannerStackProps {
  /** Explicit data for tests and stories; otherwise the provider's view is used. */
  banners?: Banner[];
  overflow?: number;
  onDismiss?: (id: string) => void;
  onAction?: (action: BannerActionId) => void;
  onIntent?: (intent: string) => void;
}

/**
 * One dock: its own provider, its own viewport, its own ordered list.
 *
 * Radix portals every toast root into the single viewport registered on its
 * provider, so sharing one provider across both docks would send every banner
 * to whichever dock mounted last — the corner stack — no matter which list
 * rendered it.
 */
function Dock({
  dock,
  label,
  banners,
  overflow = 0,
  onDismiss,
  onAction,
  onIntent,
}: {
  dock: BannerDock;
  label: string;
  banners: Banner[];
  overflow?: number;
  onDismiss: (id: string) => void;
  onAction: (action: BannerActionId) => void;
  onIntent: (intent: string) => void;
}) {
  return (
    <Toast.Provider swipeDirection="right">
      <Toast.Viewport className={`banner-dock banner-dock--${dock}`} label={label}>
        {banners.map((banner) => (
          <BannerRow
            key={banner.id}
            banner={banner}
            onDismiss={onDismiss}
            onAction={onAction}
            onIntent={onIntent}
          />
        ))}
        {overflow > 0 && (
          <li className="banner-overflow" role="status">
            +{overflow} more {overflow === 1 ? "notice" : "notices"}
          </li>
        )}
      </Toast.Viewport>
    </Toast.Provider>
  );
}

/**
 * Both docks, one model. `top` banners are page strips that hold the layout
 * still; `corner` banners float bottom-right.
 */
export function BannerStack(props: BannerStackProps) {
  const context = useBannerOptional();
  const banners = props.banners ?? context?.view.visible ?? [];
  const overflow = props.overflow ?? context?.view.overflow ?? 0;
  const onDismiss = props.onDismiss ?? context?.dismiss ?? (() => {});
  const onAction = props.onAction ?? (() => {});
  const onIntent = props.onIntent ?? (() => {});

  return (
    <>
      <Dock
        dock="top"
        label="Studio notices"
        banners={banners.filter((banner) => banner.dock === "top")}
        overflow={overflow}
        onDismiss={onDismiss}
        onAction={onAction}
        onIntent={onIntent}
      />
      <Dock
        dock="corner"
        label="Studio notifications"
        banners={banners.filter((banner) => banner.dock === "corner")}
        onDismiss={onDismiss}
        onAction={onAction}
        onIntent={onIntent}
      />
    </>
  );
}
