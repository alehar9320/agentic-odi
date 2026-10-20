import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Studio render error", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="studio-app">
          <div className="studio-card" role="alert">
            <h2 className="section-title">The Studio hit an unexpected error</h2>
            <p className="caption">{this.state.error.message}</p>
            <button
              type="button"
              className="studio-button"
              onClick={() => window.location.reload()}
            >
              Reload the Studio
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
