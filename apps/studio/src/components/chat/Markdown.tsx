import { Fragment } from "react";

import { parseMarkdown, type MdBlock, type MdInline } from "../../lib/markdown";

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
      return (
        <pre className="md-pre">
          <code>{block.code}</code>
        </pre>
      );
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
