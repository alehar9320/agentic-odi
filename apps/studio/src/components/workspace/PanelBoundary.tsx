import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  /** The lens's name, so the log says which one broke. */
  name: string;
  children: ReactNode;
}

interface State {
  error: Error | null;
  /** Bumped on Retry so the lens is rendered from scratch. */
  attempt: number;
}

/**
 * Keeps a broken lens inside its own panel.
 *
 * A lens is a view onto the conversation, not the conversation itself: when it
 * throws, the user must still be able to read the thread, ask a question, and
 * try the lens again. The app-level boundary stays for the cases where the
 * studio itself is unusable.
 */
export class PanelBoundary extends Component<Props, State> {
  state: State = { error: null, attempt: 0 };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Panel render error", this.props.name, error, info.componentStack);
  }

  private retry = () => {
    this.setState((prev) => ({ error: null, attempt: prev.attempt + 1 }));
  };

  render() {
    if (this.state.error) {
      return (
        <div className="panel-failure" role="alert">
          <p className="panel-failure__message">
            This view could not be drawn. The conversation is untouched.
          </p>
          <p className="panel-failure__detail">{this.state.error.message}</p>
          <button type="button" className="quiet-action" onClick={this.retry}>
            Retry
          </button>
        </div>
      );
    }

    return <div key={this.state.attempt}>{this.props.children}</div>;
  }
}
