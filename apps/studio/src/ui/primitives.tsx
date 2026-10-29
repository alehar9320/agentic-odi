import type { ReactNode } from "react";

import { readActions, useUiActions, type UiAction } from "./actions";
import type { UiNode } from "./protocol";
import { num, str, tone, type Tone } from "./props";
import { Markdown } from "../components/chat/Markdown";

export interface NodeProps {
  node: UiNode;
  renderChildren: (children: UiNode[]) => ReactNode;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/* ------------------------------------------------------------------ */
/* Shared pieces                                                       */
/* ------------------------------------------------------------------ */

export function ActionRow({ actions }: { actions: UiAction[] }) {
  const dispatcher = useUiActions();
  if (!dispatcher || actions.length === 0) {
    return null;
  }

  return (
    <div className="ui-actions">
      {actions.map((action, index) => (
        <button
          key={`${action.label}-${index}`}
          type="button"
          className={`ui-action ui-action--${action.tone}`}
          disabled={dispatcher.busy}
          onClick={() => dispatcher.onIntent(action.intent)}
        >
          {action.label}
        </button>
      ))}
    </div>
  );
}

export function MeterBar({
  label,
  value,
  max = 10,
  tone: barTone = "neutral",
}: {
  label: string;
  value: number;
  max?: number;
  tone?: Tone;
}) {
  const pct = clamp((value / max) * 100, 0, 100);
  return (
    <div className="ui-meter">
      <div className="ui-meter__head">
        <span>{label}</span>
        <span className="ui-meter__value">
          {value}/{max}
        </span>
      </div>
      <div
        className="ui-meter__track"
        role="meter"
        aria-label={label}
        aria-valuemax={max}
        aria-valuemin={0}
        aria-valuenow={value}
      >
        <span className={`ui-meter__fill ui-tone-bg--${barTone}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function ScorePill({ tone: pillTone, children }: { tone: Tone; children: ReactNode }) {
  return <span className={`ui-pill ui-pill--${pillTone}`}>{children}</span>;
}

/* ------------------------------------------------------------------ */
/* Layout                                                              */
/* ------------------------------------------------------------------ */

export function Stack({ node, renderChildren }: NodeProps) {
  const direction = str(node.props, "direction", "vertical");
  const gap = str(node.props, "gap", "md");
  return (
    <div className={`ui-stack ui-stack--${direction} ui-gap--${gap}`}>
      {renderChildren(node.children)}
      <ActionRow actions={readActions(node.props)} />
    </div>
  );
}

export function Grid({ node, renderChildren }: NodeProps) {
  const columns = num(node.props, "columns", 2);
  const gap = str(node.props, "gap", "md");
  return (
    <div className={`ui-grid ui-grid--${columns} ui-gap--${gap}`}>{renderChildren(node.children)}</div>
  );
}

/* ------------------------------------------------------------------ */
/* Atoms                                                               */
/* ------------------------------------------------------------------ */

export function Heading({ node }: NodeProps) {
  const text = str(node.props, "text");
  const level = num(node.props, "level", 2);
  const Tag = level <= 2 ? "h3" : "h4";
  return <Tag className="ui-heading">{text}</Tag>;
}

export function Text({ node }: NodeProps) {
  const text = str(node.props, "text");
  const textTone = str(node.props, "tone", "default");
  return (
    <div className={textTone === "default" ? "ui-text" : `ui-text ui-text--${textTone}`}>
      <Markdown source={text} />
    </div>
  );
}

export function ListBlock({ node }: NodeProps) {
  const raw = node.props.items;
  const items = Array.isArray(raw) ? raw.filter((item): item is string => typeof item === "string") : [];
  const marker = str(node.props, "marker", "dot");
  const Tag = marker === "number" ? "ol" : "ul";

  return (
    <Tag className={`ui-list ui-list--${marker}`}>
      {items.map((item, index) => (
        <li key={`${index}-${item.slice(0, 12)}`}>{item}</li>
      ))}
    </Tag>
  );
}

export function Stat({ node }: NodeProps) {
  const label = str(node.props, "label");
  const value = str(node.props, "value");
  const delta = str(node.props, "delta");
  const statTone = tone(node.props);
  return (
    <div className={`ui-stat ui-tone--${statTone}`}>
      <div className="ui-stat__label">{label}</div>
      <div className="ui-stat__value">{value}</div>
      {delta ? <div className="ui-stat__delta">{delta}</div> : null}
    </div>
  );
}

export function Meter({ node }: NodeProps) {
  const label = str(node.props, "label");
  const value = num(node.props, "value", 0);
  const max = num(node.props, "max", 10);
  return <MeterBar label={label} value={value} max={max} tone={tone(node.props)} />;
}

export function Callout({ node }: NodeProps) {
  const calloutTone = tone(node.props, "info");
  const title = str(node.props, "title");
  const body = str(node.props, "body");
  return (
    <aside className={`ui-callout ui-callout--${calloutTone}`}>
      {title ? <div className="ui-callout__title">{title}</div> : null}
      <div className="ui-callout__body">
        <Markdown source={body} />
      </div>
    </aside>
  );
}

export function Divider() {
  return <hr className="ui-divider" />;
}
