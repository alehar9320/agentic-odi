import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import vendorCss from "./index.css?inline";
import { Button } from "@/components/ui/button";

/**
 * Tailwind is installed for `src/vendor` alone.
 *
 * The compiled stylesheet is the evidence: a utility the copied component uses
 * must be generated, a utility only product code uses must not be, and the
 * preflight reset must stay out of the bundle entirely — it would restyle every
 * element the product renders from `src/styles/theme.css`.
 */
describe("vendor tailwind scope", () => {
  it("generates the utilities the copied components use", () => {
    expect(vendorCss).toContain(".inline-flex");
  });

  it("does not generate utilities that only product code uses", () => {
    expect(vendorCss).not.toContain(".sr-only");
  });

  it("leaves the preflight reset out of the product document", () => {
    // Preflight's universal selector is the first rule it emits.
    expect(vendorCss).not.toMatch(/\*,\s*::after/);
  });

  it("renders the copied button with its utility classes", () => {
    render(<Button variant="outline">Save the evidence</Button>);
    const button = screen.getByRole("button", { name: "Save the evidence" });
    expect(button.className.split(" ")).toContain("inline-flex");
    expect(button.className.split(" ")).toContain("rounded-md");
  });
});
