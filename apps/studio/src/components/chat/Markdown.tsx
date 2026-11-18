import { createElement } from "react";
import type { ComponentPropsWithoutRef, ElementType, JSX, ReactNode } from "react";
import ReactMarkdown, { type Components, type ExtraProps } from "react-markdown";
import remarkGfm from "remark-gfm";

import { hideMarkers } from "../../assistant/claims";

/**
 * Markdown rendering, owned by `react-markdown` + `remark-gfm`.
 *
 * This replaced a hand-written 169-line subset (#394). The product's class
 * vocabulary lives in one shared map so prose, reasoning, brief, setup, and
 * intro surfaces read the same. Raw HTML stays inert: `react-markdown` turns a
 * raw node into text, and the link override refuses unsafe protocols.
 */

const SAFE_HREF = /^(https?:\/\/|mailto:)/i;
const UNSAFE_HREF = /^(javascript:|data:|vbscript:|file:)/i;

type TagProps<Tag extends keyof JSX.IntrinsicElements> = ComponentPropsWithoutRef<Tag> &
  ExtraProps;

/**
 * One element of the class vocabulary. `node` is react-markdown's hast node:
 * it carries the source position, not an attribute, so it is dropped before
 * the props reach the DOM.
 */
function mdElement<Tag extends keyof JSX.IntrinsicElements>(Tag: Tag, className: string) {
  return function MdElement({ node, ...props }: TagProps<Tag>) {
    void node;
    return createElement(Tag as ElementType, { className, ...props });
  };
}

function MarkdownLink({ node, href, children, ...rest }: TagProps<"a">) {
  void node;
  const safe = typeof href === "string" && SAFE_HREF.test(href) && !UNSAFE_HREF.test(href);
  if (!safe) {
    return <span>{children}</span>;
  }
  return (
    <a href={href} target="_blank" rel="noreferrer noopener" {...rest}>
      {children}
    </a>
  );
}

/** GFM tables are wrapped so a wide table scrolls instead of widening a reply. */
function MarkdownTable({ node, children, ...rest }: TagProps<"table">) {
  void node;
  return (
    <div className="md-table-wrap">
      <table className="md-table" {...rest}>
        {children}
      </table>
    </div>
  );
}

/** The one class vocabulary every markdown surface renders through. */
export const mdComponents: Components = {
  p: mdElement("p", "md-paragraph"),
  h1: mdElement("h1", "md-heading"),
  h2: mdElement("h2", "md-heading"),
  h3: mdElement("h3", "md-heading"),
  h4: mdElement("h4", "md-heading"),
  h5: mdElement("h5", "md-heading"),
  h6: mdElement("h6", "md-heading"),
  ul: mdElement("ul", "md-list"),
  ol: mdElement("ol", "md-list"),
  code: mdElement("code", "md-code"),
  pre: mdElement("pre", "md-pre"),
  blockquote: mdElement("blockquote", "md-quote"),
  hr: mdElement("hr", "md-rule"),
  table: MarkdownTable,
  a: MarkdownLink,
};

export const mdRemarkPlugins = [remarkGfm];

/**
 * A standalone string of markdown. `hideMarkers` is applied here so no caller
 * has to remember it: a claim marker is syntax, never prose.
 */
export function Markdown({ source }: { source: string }): ReactNode {
  return (
    <div className="md">
      <ReactMarkdown remarkPlugins={mdRemarkPlugins} components={mdComponents}>
        {hideMarkers(source)}
      </ReactMarkdown>
    </div>
  );
}
