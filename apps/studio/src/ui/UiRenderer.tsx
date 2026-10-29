import { Component, type ErrorInfo, type ReactNode } from "react";

import { useStudio } from "../state/StudioContext";
import type { UiNode } from "./protocol";
import { NODE_COMPONENTS } from "./registry";

/**
 * One bad surface must never take down the conversation. Each node gets its own
 * boundary, so a card that throws degrades to a single quiet line and its
 * siblings keep rendering.
 */
export class NodeBoundary extends Component<
  { children: ReactNode; nodeType: string },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`Studio surface "${this.props.nodeType}" failed to render.`, error, info);
  }

  render() {
    if (this.state.failed) {
      return (
        <div className="ui-card ui-card--unknown" role="status">
          <p className="ui-caption">This surface could not be displayed.</p>
        </div>
      );
    }
    return this.props.children;
  }
}

function UnknownNode({ node }: { node: UiNode }) {
  const { pushToast } = useStudio();

  async function copySpec() {
    try {
      await navigator.clipboard.writeText(JSON.stringify(node, null, 2));
      pushToast("success", "Raw surface spec copied.");
    } catch {
      pushToast("error", "Could not copy the raw surface spec.");
    }
  }

  return (
    <div className="ui-card ui-card--unknown" role="status">
      <p className="ui-caption">Unavailable surface</p>
      <p className="ui-card__statement">
        This reply referenced <code className="ui-code">{node.type}</code>, which this version of
        Studio cannot render.
      </p>
      <button type="button" className="quiet-action" onClick={() => void copySpec()}>
        Copy raw spec
      </button>
    </div>
  );
}

function renderChildren(children: UiNode[]): ReactNode {
  return children.map((child, index) => renderNode(child, index));
}

function renderNode(node: UiNode, key?: string | number): ReactNode {
  const Component = NODE_COMPONENTS[node.type];
  if (node.unsupported || !Component) {
    return <UnknownNode key={key} node={node} />;
  }

  return (
    <NodeBoundary key={key} nodeType={node.type}>
      <Component node={node} renderChildren={renderChildren} />
    </NodeBoundary>
  );
}

export function UiRenderer({ node }: { node: UiNode }) {
  return <div className="ui-surface">{renderNode(node)}</div>;
}
