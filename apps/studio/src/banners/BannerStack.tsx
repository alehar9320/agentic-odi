import * as Toast from "@radix-ui/react-toast";

import { BannerRow } from "./Banner";
import { useBannerOptional } from "./BannerProvider";
import type { Banner } from "./types";

export interface BannerStackProps {
  /** Explicit data for tests and stories; otherwise the provider's view is used. */
  banners?: Banner[];
  overflow?: number;
  onDismiss?: (id: string) => void;
  onIntent?: (intent: string) => void;
}

/**
 * Both docks, one model. `top` banners are page strips that hold the layout
 * still; `corner` banners float bottom-right.
 *
 * Each dock is itself a Radix viewport, so the roots render inside the ordered
 * list the library expects for its keyboard and scroll behavior, and the two
 * docks never fight over one list.
 */
export function BannerStack(props: BannerStackProps) {
  const context = useBannerOptional();
  const banners = props.banners ?? context?.view.visible ?? [];
  const overflow = props.overflow ?? context?.view.overflow ?? 0;
  const onDismiss = props.onDismiss ?? context?.dismiss ?? (() => {});
  const onIntent = props.onIntent ?? (() => {});

  const top = banners.filter((banner) => banner.dock === "top");
  const corner = banners.filter((banner) => banner.dock === "corner");

  return (
    <Toast.Provider swipeDirection="right">
      <Toast.Viewport className="banner-dock banner-dock--top" label="Studio notices">
        {top.map((banner) => (
          <BannerRow key={banner.id} banner={banner} onDismiss={onDismiss} onIntent={onIntent} />
        ))}
        {overflow > 0 && (
          <li className="banner-overflow" role="status">
            +{overflow} more {overflow === 1 ? "notice" : "notices"}
          </li>
        )}
      </Toast.Viewport>

      <Toast.Viewport className="banner-dock banner-dock--corner" label="Studio notifications">
        {corner.map((banner) => (
          <BannerRow key={banner.id} banner={banner} onDismiss={onDismiss} onIntent={onIntent} />
        ))}
      </Toast.Viewport>
    </Toast.Provider>
  );
}
