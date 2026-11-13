import { Fragment, type ComponentPropsWithoutRef, type ReactElement } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { hideMarkers } from "../../assistant/claims";

/**
 * One Markdown engine for the studio.
 *
 * Prose, reasoning, the decision brief, the setup surfaces, and the ODI cards
 * all render through this component, so the transcript and the documents agree
 * on how Markdown looks. The class vocabulary is the `md-*` set in
 * `styles/theme.css`; a new Markdown feature adds a class here, not a second
 * parser.
 */

type MdProps<T extends keyof React.JSX.IntrinsicElements> = ComponentPropsWithoutRef<T> & {
  node?: unknown;
};

/** `react-markdown` passes the parsed node; a DOM element must not receive it. */
function domProps<T extends { node?: unknown }>(props: T): Omit<T, "node"> {
  const copy = { ...props };
  delete copy.node;
  return copy;
}

function Paragraph(props: MdProps<"p">): ReactElement {
  return <p className="md-paragraph" {...domProps(props)} />;
}

/** Headings keep their level and share one scale. */
function heading(level: 1 | 2 | 3 | 4 | 5 | 6) {
  return function Heading(props: MdProps<"h1">): ReactElement {
    const Tag = `h${level}` as "h1" | "h2" | "h3" | "h4" | "h5" | "h6";
    return <Tag className="md-heading" {...domProps(props)} />;
  };
}

/**
 * Inline code carries the `md-code` chip; a fenced block keeps its language
 * class and inherits `md-pre`'s typography instead.
 */
function Code(props: MdProps<"code">): ReactElement {
  const { className, children } = props;
  // A fenced block arrives with the newline that closed the fence; the reader
  // copies the code, not the line break after it.
  const body = typeof children === "string" && children.endsWith("\n") ? children.slice(0, -1) : children;
  return (
    <code {...domProps(props)} className={className ?? "md-code"}>
      {body}
    </code>
  );
}

/**
 * A link is only a link when the protocol is one a reader can trust.
 *
 * `react-markdown` blanks `javascript:` and `data:` URLs before they reach the
 * component, so an empty `href` here means the Markdown asked for an unsafe
 * link: render the text, not a dead anchor.
 */
function Anchor(props: MdProps<"a">): ReactElement {
  const { href, children } = props;
  const safe = typeof href === "string" && /^(https?:\/\/|mailto:)/i.test(href);
  if (!safe) {
    return <Fragment>{children}</Fragment>;
  }
  return (
    <a {...domProps(props)} href={href} target="_blank" rel="noreferrer noopener">
      {children}
    </a>
  );
}

/** The map every surface renders with. */
export const mdComponents: Components = {
  p: Paragraph,
  h1: heading(1),
  h2: heading(2),
  h3: heading(3),
  h4: heading(4),
  h5: heading(5),
  h6: heading(6),
  ul: (props) => <ul className="md-list" {...domProps(props)} />,
  ol: (props) => <ol className="md-list" {...domProps(props)} />,
  pre: (props) => <pre className="md-pre" {...domProps(props)} />,
  code: Code,
  blockquote: (props) => <blockquote className="md-quote" {...domProps(props)} />,
  hr: (props) => <hr className="md-rule" {...domProps(props)} />,
  a: Anchor,
  table: (props) => <table className="md-table" {...domProps(props)} />,
  th: (props) => <th className="md-table__cell md-table__head" {...domProps(props)} />,
  td: (props) => <td className="md-table__cell" {...domProps(props)} />,
};

/** Markdown as the studio renders it: one engine, one component map, markers hidden. */
export function Markdown({ source }: { source: string }): ReactElement {
  return (
    <div className="md">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
        {hideMarkers(source)}
      </ReactMarkdown>
    </div>
  );
}