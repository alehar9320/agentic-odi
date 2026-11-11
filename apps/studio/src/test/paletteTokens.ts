/**
 * Reading the tokens a document carries inline.
 *
 * Two pages have to ship the palette before any bundle runs — `index.html`'s
 * bootstrap shell and `public/offline.html`, which paints without a server.
 * Both are therefore a *copy* of `src/styles/theme.css`, and a copy is exactly
 * the thing that drifts. These readers exist so each page's guard compares the
 * copy against the source rather than against a literal typed into the test.
 */

/** The text of a document's first inline `<style>` or `<script>`. */
export function inlineTag(html: string, tag: "style" | "script"): string {
  const match = html.match(new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`));
  if (!match) {
    throw new Error(`missing inline <${tag}>`);
  }
  return match[1];
}

function block(css: string, selector: string): string | null {
  const start = css.indexOf(selector);
  if (start < 0) {
    return null;
  }
  const open = css.indexOf("{", start);
  const close = css.indexOf("}", open);
  return css.slice(open + 1, close);
}

/** The value of `--token` inside the first block matching `selector`. */
export function tokenValue(css: string, selector: string, token: string): string | null {
  const body = block(css, selector);
  if (body === null) {
    return null;
  }
  return body.match(new RegExp(`--${token}:\\s*([^;]+);`))?.[1].trim() ?? null;
}

const COLOR = /^(#[0-9a-fA-F]{3,8}|rgba?\()/;

/**
 * Every custom property in the block whose value is a colour, by name.
 *
 * Font stacks, radii, and `var()` aliases are deliberately not colours: a page
 * that invents a `--font` is not a page that invented a palette.
 */
export function colorTokens(css: string, selector: string): Record<string, string> {
  const body = block(css, selector);
  if (body === null) {
    return {};
  }
  const declared = Array.from(body.matchAll(/--([a-z0-9-]+):\s*([^;]+);/g), (match) => [
    match[1],
    match[2].trim(),
  ]);
  return Object.fromEntries(declared.filter(([, value]) => COLOR.test(value)));
}
