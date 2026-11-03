/**
 * The rendered-contrast walker (issue #543, parent #331).
 *
 * axe skips `color-contrast` on any element whose background it cannot
 * resolve — anything painted over a gradient — and returns those as
 * `incomplete` instead of `violations`. That is exactly the code this product
 * leans on: the app shell paints a decorative radial wash over `--bg`, and the
 * composer, the hero, and the charts each paint their own. A gate that trusted
 * axe alone would skip most of the screen.
 *
 * So `contrastWalker` resolves the effective background itself. It walks the
 * ancestors, folds each `background-color` and each gradient's colour stops
 * together bottom-up, and judges the text against the worst stop it can sit on.
 * A pair it still cannot resolve (an image, a `backdrop-filter`) is reported as
 * `indeterminate` rather than skipped, so a new unreadable pair fails the build
 * instead of quietly leaving the gate.
 *
 * The function is self-contained on purpose: `e2e/a11y.spec.ts` serialises it
 * with `Function.prototype.toString` and installs it in the page, so it must
 * not close over anything. `contrast.test.ts` runs the same source in jsdom.
 */

export interface ContrastFinding {
  /** The screen under test, e.g. "home". */
  screen: string;
  theme: string;
  selector: string;
  text: string;
  foreground: string;
  /** The worst-case background the text sits on, or null when unresolved. */
  background: string | null;
  /** The measured ratio, or null when the background is indeterminate. */
  ratio: number | null;
  /** The ratio this element must clear, by size and weight. */
  required: number;
  reason: "ratio" | "indeterminate";
}

/** A colour as `[r, g, b, a]`, channels 0–255 and alpha 0–1. */
type Channels = [number, number, number, number];

export function contrastWalker(root: Element, screen: string, theme: string): ContrastFinding[] {
  const TRANSPARENT: Channels = [0, 0, 0, 0];
  const UNREADABLE: Channels = [Number.NaN, Number.NaN, Number.NaN, 0];
  const MAX_NODES = 2000;
  const MAX_CANDIDATES = 16;

  function parseColor(value: string): Channels | null {
    const match = value.match(/^rgba?\(([^)]+)\)$/);
    if (!match) {
      return null;
    }
    const parts = match[1]
      .split(/[\s,/]+/)
      .filter(Boolean)
      .map(Number);
    if (parts.length < 3 || parts.slice(0, 3).some((part) => Number.isNaN(part))) {
      return null;
    }
    const alpha = parts.length >= 4 && !Number.isNaN(parts[3]) ? parts[3] : 1;
    return [parts[0], parts[1], parts[2], alpha];
  }

  function luminance(color: Channels): number {
    const channel = (value: number) => {
      const scaled = value / 255;
      return scaled <= 0.04045 ? scaled / 12.92 : ((scaled + 0.055) / 1.055) ** 2.4;
    };
    return 0.2126 * channel(color[0]) + 0.7152 * channel(color[1]) + 0.0722 * channel(color[2]);
  }

  function contrastRatio(foreground: Channels, background: Channels): number {
    const [lighter, darker] = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
    return (lighter + 0.05) / (darker + 0.05);
  }

  function composite(top: Channels, bottom: Channels): Channels {
    const alpha = top[3] + bottom[3] * (1 - top[3]);
    if (alpha === 0) {
      return TRANSPARENT;
    }
    const blend = (index: number) =>
      (top[index] * top[3] + bottom[index] * bottom[3] * (1 - top[3])) / alpha;
    return [blend(0), blend(1), blend(2), alpha];
  }

  function isUnreadable(color: Channels): boolean {
    return Number.isNaN(color[0]);
  }

  /** The opaque colours one element can paint, gradient stops included. */
  function nodeLayers(style: CSSStyleDeclaration): Channels[] {
    const color = parseColor(style.backgroundColor) ?? TRANSPARENT;
    const image = style.backgroundImage;
    if (!image || image === "none") {
      return [color];
    }
    if (/^(linear|radial|conic)-gradient\(/.test(image.trim())) {
      const stops = (image.match(/rgba?\([^)]*\)/g) ?? [])
        .map((token) => parseColor(token))
        .filter((stop): stop is Channels => stop !== null);
      if (stops.length > 0) {
        return stops.map((stop) => composite(stop, color));
      }
    }
    return [color, UNREADABLE];
  }

  function dedupe(colors: Channels[]): Channels[] {
    const seen = new Set<string>();
    const out: Channels[] = [];
    for (const color of colors) {
      const key = color.map((value) => Math.round(value * 1000)).join(",");
      if (!seen.has(key)) {
        seen.add(key);
        out.push(color);
      }
    }
    return out;
  }

  /** The colours behind `element`, or null when one cannot be resolved.
   *
   * The stack holds what is painted *on top* at the current point; each
   * ancestor is composited underneath it, so a translucent child is folded
   * over its opaque parent rather than the other way round. */
  function effectiveBackgrounds(element: Element): Channels[] | null {
    let stack: Channels[] = [TRANSPARENT];
    let node: Element | null = element;
    while (node) {
      const style = getComputedStyle(node);
      const layers = nodeLayers(style);
      if (layers.some((layer) => isUnreadable(layer))) {
        return null;
      }
      const next: Channels[] = [];
      for (const layer of layers) {
        for (const top of stack) {
          next.push(composite(top, layer));
        }
      }
      stack = dedupe(next).slice(0, MAX_CANDIDATES);
      if (stack.every((candidate) => candidate[3] === 1)) {
        return stack;
      }
      node = node.parentElement;
    }
    const bodyColor = parseColor(getComputedStyle(document.body).backgroundColor);
    const floor: Channels = bodyColor && bodyColor[3] === 1 ? bodyColor : [255, 255, 255, 1];
    const resolved = stack.map((candidate) =>
      candidate[3] === 1 ? candidate : composite(candidate, floor),
    );
    return resolved.every((color) => color[3] === 1) ? resolved : null;
  }

  /** The colour text actually renders in. SVG text paints with `fill`, not
   * `color`, so reading `color` there would measure the inherited value and
   * miss the ink on the screen. */
  function textColor(element: Element, style: CSSStyleDeclaration): string {
    if (element.namespaceURI === "http://www.w3.org/2000/svg") {
      const fill = style.fill;
      if (fill && fill !== "none" && /^rgba?\(/.test(fill)) {
        return fill;
      }
    }
    return style.color;
  }

  function requiredRatio(element: Element): number {
    const style = getComputedStyle(element);
    const size = parseFloat(style.fontSize);
    const weight = parseInt(style.fontWeight, 10) || 400;
    const bold = weight >= 700;
    return size >= 24 || (bold && size >= 18.66) ? 3 : 4.5;
  }

  function cssPath(element: Element): string {
    const parts: string[] = [];
    let node: Element | null = element;
    while (node && node !== document.body && parts.length < 5) {
      const id = node.id ? `#${node.id}` : "";
      const cls = Array.from(node.classList)
        .slice(0, 2)
        .map((name) => `.${name}`)
        .join("");
      parts.unshift(`${node.tagName.toLowerCase()}${id}${cls}`);
      node = node.parentElement;
    }
    return parts.join(" > ") || element.tagName.toLowerCase();
  }

  function hasDirectText(element: Element): boolean {
    for (const child of Array.from(element.childNodes)) {
      if (child.nodeType === 3 && (child.textContent ?? "").trim().length > 0) {
        return true;
      }
    }
    return false;
  }

  function isVisible(element: Element): boolean {
    const style = getComputedStyle(element);
    if (style.visibility === "hidden" || style.display === "none" || Number(style.opacity) === 0) {
      return false;
    }
    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function format(color: Channels): string {
    return `rgb(${Math.round(color[0])}, ${Math.round(color[1])}, ${Math.round(color[2])})`;
  }

  const findings: ContrastFinding[] = [];
  const candidates = [root, ...Array.from(root.querySelectorAll("*"))].slice(0, MAX_NODES);
  for (const element of candidates) {
    if (!hasDirectText(element) || !isVisible(element)) {
      continue;
    }
    const style = getComputedStyle(element);
    const foreground = parseColor(textColor(element, style));
    if (!foreground) {
      continue;
    }
    const backgrounds = effectiveBackgrounds(element);
    const required = requiredRatio(element);
    const text = (element.textContent ?? "").trim().slice(0, 80);
    if (!backgrounds || backgrounds.length === 0) {
      findings.push({
        screen,
        theme,
        selector: cssPath(element),
        text,
        foreground: textColor(element, style),
        background: null,
        ratio: null,
        required,
        reason: "indeterminate",
      });
      continue;
    }
    // The text can sit anywhere the gradient covers, so the gate is the worst
    // stop, not the average.
    let worstRatio = Number.POSITIVE_INFINITY;
    let worstBackground = backgrounds[0];
    for (const background of backgrounds) {
      const ratio = contrastRatio(foreground, background);
      if (ratio < worstRatio) {
        worstRatio = ratio;
        worstBackground = background;
      }
    }
    if (worstRatio < required) {
      findings.push({
        screen,
        theme,
        selector: cssPath(element),
        text,
        foreground: style.color,
        background: format(worstBackground),
        ratio: worstRatio,
        required,
        reason: "ratio",
      });
    }
  }
  return findings;
}

/** One readable block per failure: unmeasurable pairs first, then worst ratio. */
export function formatFindings(findings: ContrastFinding[]): string {
  return findings
    .slice()
    // A pair the walker could not resolve is the most urgent: it needs a human
    // before it can be judged, so it sorts ahead of any measured ratio.
    .sort((a, b) => (a.ratio ?? -1) - (b.ratio ?? -1))
    .map(
      (finding) =>
        `screen=${finding.screen} theme=${finding.theme} selector=${finding.selector} ` +
        `text=${JSON.stringify(finding.text)} fg=${finding.foreground} ` +
        `bg=${finding.background ?? "unknown"} ` +
        `ratio=${finding.ratio === null ? "indeterminate" : finding.ratio.toFixed(2)} ` +
        `required=${finding.required}`,
    )
    .join("\n");
}

/**
 * A pair the gate already knows about, with the slice that will fix it.
 *
 * The gate is only as good as this list's honesty: every entry names an issue,
 * and `staleKnownPairs` fails the build when one stops failing, so the list can
 * only shrink.
 */
export interface KnownPair {
  theme: string;
  foreground: string;
  background: string | null;
  required: number;
  issue: number;
  note: string;
}

/** A pair is identified by the colours and the threshold, not by the screen. */
function pairKey(theme: string, foreground: string, background: string | null, required: number): string {
  return `${theme}|${foreground}|${background ?? "unresolved"}|${required}`;
}

/** The findings that are not on the known-pairs list. */
export function unlistedFindings(
  findings: ContrastFinding[],
  known: KnownPair[],
): ContrastFinding[] {
  const allowed = new Set(
    known.map((entry) => pairKey(entry.theme, entry.foreground, entry.background, entry.required)),
  );
  return findings.filter(
    (finding) => !allowed.has(pairKey(finding.theme, finding.foreground, finding.background, finding.required)),
  );
}

/** The known pairs that no longer fail, i.e. the entries that are now stale. */
export function staleKnownPairs(known: KnownPair[], findings: ContrastFinding[]): KnownPair[] {
  const seen = new Set(
    findings.map((finding) => pairKey(finding.theme, finding.foreground, finding.background, finding.required)),
  );
  return known.filter(
    (entry) => !seen.has(pairKey(entry.theme, entry.foreground, entry.background, entry.required)),
  );
}
