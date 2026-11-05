/**
 * The colours a rendered subtree paints with a literal instead of a class.
 *
 * A themed surface must reach the palette through a class name, so the theme,
 * the printer and the offline page can all follow it. jsdom has no cascade for
 * `var()`, which makes a computed-style check useless here; what it *can* see
 * is the markup the component wrote. Anything this returns is a colour that
 * will not move when the theme does.
 */

/** Attributes that carry a paint when a component colours by hand. */
const PAINT_ATTRIBUTES = ["fill", "stroke", "stop-color", "style"] as const;

const LITERAL = /#[0-9a-fA-F]{3,8}\b|\brgba?\([^)]*\)/g;

/** One `TAG #literal` line per colour written into the markup, so a failure
 * names the element rather than just a count. */
export function literalPaint(root: Element): string[] {
  const painted: string[] = [];
  const selectors = PAINT_ATTRIBUTES.map((name) => `[${name}]`).join(", ");
  for (const element of Array.from(root.querySelectorAll(selectors))) {
    const value = PAINT_ATTRIBUTES.map((name) => element.getAttribute(name))
      .filter((attribute: string | null): attribute is string => attribute !== null)
      .join(" ");
    for (const literal of value.match(LITERAL) ?? []) {
      painted.push(`${element.tagName} ${literal}`);
    }
  }
  return painted;
}
