import { Fragment } from "react";

import { parseMarkdown, type MdBlock, type MdInline } from "../../lib/markdown";
import { useCopyConfirmation } from "../../lib/useCopyConfirmation";
import { CheckIcon, CopyIcon } from "../icons";

/**
 * A code block with a copy control that appears on hover and on focus-within.
 *
 * The control stays in the tab order — revealed by keyboard focus, not hidden
 * from it — and writes the exact code, so a snippet can be taken without
 * selecting it by hand. The tick holds for the shared confirmation window.
 */
export function CopyableCode({ code, className = "md-pre" }: { code: string; className?: string }) {
  const { copied, copy } = useCopyConfirmation();
  return (
    <div className="code-block">
      <pre className={className}>
        <code>{code}</code>
      </pre>
      <button
        type="button"
        className="code-block__copy quiet-action"
        aria-label={copied ? "Code copied" : "Copy code"}
        onClick={() => void copy(code)}
      >
        {copied ? <CheckIcon size={14} /> : <CopyIcon size={14} />}
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

function renderSpans(spans: MdInline[]) {
  return spans.map((span, index) => {
    switch (span.type) {
      case "strong":
        return <strong key={index}>{span.text}</strong>;
      case "em":
        return <em key={index}>{span.text}</em>;
      case "code":
        return (
          <code className="md-code" key={index}>
            {span.text}
          </code>
        );
      case "link": {
        const safe = /^(https?:\/\/|mailto:)/i.test(span.href);
        if (!safe) {
          return <Fragment key={index}>{span.text}</Fragment>;
        }
        return (
          <a key={index} href={span.href} target="_blank" rel="noreferrer noopener">
            {span.text}
          </a>
        );
      }
      case "text":
      default:
        return <Fragment key={index}>{span.text}</Fragment>;
    }
  });
}

function Block({ block }: { block: MdBlock }) {
  switch (block.type) {
    case "heading": {
      const Tag = (`h${block.level}` as "h1" | "h2" | "h3");
      return <Tag className="md-heading">{renderSpans(block.spans)}</Tag>;
    }
    case "code":
      return <CopyableCode code={block.code} />;
    case "list": {
      const items = block.items.map((item, index) => <li key={index}>{renderSpans(item)}</li>);
      return block.ordered ? (
        <ol className="md-list" start={block.start}>
          {items}
        </ol>
      ) : (
        <ul className="md-list">{items}</ul>
      );
    }
    case "quote":
      return <blockquote className="md-quote">{renderSpans(block.spans)}</blockquote>;
    case "rule":
      return <hr className="md-rule" />;
    case "paragraph":
    default:
      return <p className="md-paragraph">{renderSpans(block.spans)}</p>;
  }
}

export function Markdown({ source }: { source: string }) {
  const blocks = parseMarkdown(source);
  return (
    <div className="md">
      {blocks.map((block, index) => (
        <Block block={block} key={index} />
      ))}
    </div>
  );
}
