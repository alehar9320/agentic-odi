import { configure } from "@chromatic-com/vitest";
import type { ReactNode } from "react";
import { expect, it } from "vitest";
import { render } from "vitest-browser-react";

import { Button } from "@/components/ui/button";

// The whole cascade, in the order the app loads it.
import "../styles/entry.css";

/**
 * The product stylesheet must sit in a layer, below Tailwind's utilities.
 *
 * An unlayered rule beats every layered one, specificity included, so while
 * `src/styles/theme.css` is unlayered a copied component's utilities lose: the
 * vendored button gets `button { color: inherit }` instead of its `text-white`,
 * which is why components from `src/vendor` look half-restyled inside the
 * Studio. Both directions are asserted, because a "fix" that puts the product
 * sheet below everything else would only pass the first.
 *
 * Computed styles are read from a real browser: jsdom has no cascade for
 * `@layer`, so a unit run of this file would prove nothing.
 */

// The frame is the document the app renders into, so the stylesheets above are
// the ones under test and nothing here narrows them.
function Stage({ children }: { children: ReactNode }) {
  return <div style={{ padding: 24, display: "grid", gap: 16, width: 360 }}>{children}</div>;
}

configure({ title: "Layering" });

it("lets a vendored utility override a product element rule", async () => {
  const { container } = await render(
    <Stage>
      <Button variant="destructive" data-testid="vendored">
        Delete the evidence
      </Button>
    </Stage>,
  );

  const vendored = container.querySelector<HTMLElement>('[data-testid="vendored"]');
  expect(vendored, "the vendored button did not render").not.toBeNull();
  // `text-white` is the utility `button.tsx` asks for; theme.css's
  // `button { color: inherit }` would resolve to the body's #f1f2f4 instead.
  expect(getComputedStyle(vendored as HTMLElement).color).toBe("rgb(255, 255, 255)");
});

it("keeps a product rule ahead of the browser default", async () => {
  const { container } = await render(
    <Stage>
      <a href="#canvas" data-testid="product-link">
        Open the canvas
      </a>
    </Stage>,
  );

  const link = container.querySelector<HTMLElement>('[data-testid="product-link"]');
  expect(link, "the product link did not render").not.toBeNull();
  // No browser sets a text-underline-offset, so 2px can only come from the
  // product sheet — proof that layering it did not disarm it.
  expect(getComputedStyle(link as HTMLElement).textUnderlineOffset).toBe("2px");
});
