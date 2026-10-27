import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useReducer,
  type ReactNode,
} from "react";

import {
  DEFAULT_MAX_VISIBLE,
  EMPTY_BANNER_STATE,
  dismissBanner,
  raiseBanner,
  resolveBanner,
  selectBanners,
  type BannerState,
} from "./store";
import type { Banner, BannerKind, BannerSpec } from "./types";

export interface BannerView {
  visible: Banner[];
  overflow: number;
}

export interface BannerApi {
  /** Raise a banner. The same kind raised again updates it in place. */
  raise: (spec: BannerSpec) => void;
  /** Clear a banner because its condition cleared. */
  resolve: (kind: BannerKind) => void;
  /** Clear a banner because the user dismissed it. */
  dismiss: (id: string) => void;
  view: BannerView;
}

type Action =
  | { type: "raise"; spec: BannerSpec }
  | { type: "resolve"; kind: BannerKind }
  | { type: "dismiss"; id: string };

function reducer(state: BannerState, action: Action): BannerState {
  switch (action.type) {
    case "raise":
      return raiseBanner(state, action.spec);
    case "resolve":
      return resolveBanner(state, action.kind);
    case "dismiss":
      return dismissBanner(state, action.id);
  }
}

const BannerContext = createContext<BannerApi | null>(null);

export function BannerProvider({
  children,
  maxVisible = DEFAULT_MAX_VISIBLE,
}: {
  children: ReactNode;
  maxVisible?: number;
}) {
  const [state, dispatch] = useReducer(reducer, EMPTY_BANNER_STATE);

  const raise = useCallback((spec: BannerSpec) => dispatch({ type: "raise", spec }), []);
  const resolve = useCallback((kind: BannerKind) => dispatch({ type: "resolve", kind }), []);
  const dismiss = useCallback((id: string) => dispatch({ type: "dismiss", id }), []);

  const view = useMemo(() => selectBanners(state, maxVisible), [state, maxVisible]);

  const api = useMemo<BannerApi>(
    () => ({ raise, resolve, dismiss, view }),
    [raise, resolve, dismiss, view],
  );

  return <BannerContext.Provider value={api}>{children}</BannerContext.Provider>;
}

export function useBanner(): BannerApi {
  const api = useContext(BannerContext);
  if (!api) {
    throw new Error("useBanner must be used inside a BannerProvider.");
  }
  return api;
}

/** For presentational components that accept an explicit api as a prop. */
export function useBannerOptional(): BannerApi | null {
  return useContext(BannerContext);
}
