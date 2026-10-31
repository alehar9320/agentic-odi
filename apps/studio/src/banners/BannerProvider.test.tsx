import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BannerProvider, useBanner } from "./BannerProvider";

function useHarness() {
  return useBanner();
}

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <BannerProvider>{children}</BannerProvider>
);

describe("BannerProvider", () => {
  it("starts with nothing raised", () => {
    const { result } = renderHook(useHarness, { wrapper });
    expect(result.current.view.visible).toHaveLength(0);
    expect(result.current.view.overflow).toBe(0);
  });

  it("exposes a raised banner to consumers", () => {
    const { result } = renderHook(useHarness, { wrapper });
    act(() => result.current.raise({ kind: "sidecar-down" }));
    expect(result.current.view.visible[0].kind).toBe("sidecar-down");
  });

  it("updates one banner when the same persistent kind is raised twice", () => {
    const { result } = renderHook(useHarness, { wrapper });
    act(() => result.current.raise({ kind: "sidecar-down", body: "First." }));
    act(() => result.current.raise({ kind: "sidecar-down", body: "Second." }));
    expect(result.current.view.visible).toHaveLength(1);
    expect(result.current.view.visible[0].body).toBe("Second.");
  });

  it("keeps two transient banners of the same kind when their messages differ", () => {
    const { result } = renderHook(useHarness, { wrapper });
    act(() => result.current.raise({ kind: "success", body: "Added A." }));
    act(() => result.current.raise({ kind: "success", body: "Added B." }));
    expect(result.current.view.visible).toHaveLength(2);
  });

  it("resolves a banner when its condition clears", () => {
    const { result } = renderHook(useHarness, { wrapper });
    act(() => result.current.raise({ kind: "sidecar-down" }));
    act(() => result.current.resolve("sidecar-down"));
    expect(result.current.view.visible).toHaveLength(0);
  });

  it("dismisses a banner by id", () => {
    const { result } = renderHook(useHarness, { wrapper });
    act(() => result.current.raise({ kind: "sidecar-down" }));
    act(() => result.current.dismiss("sidecar-down"));
    expect(result.current.view.visible).toHaveLength(0);
  });
});
