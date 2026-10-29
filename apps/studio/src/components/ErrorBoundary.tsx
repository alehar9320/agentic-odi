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
        <div className="error-page">
          <div className="error-page__card" role="alert">
            <p className="hero__eyebrow">Living Studio</p>
            <h1 className="error-page__title">Something broke on the way to the canvas.</h1>
            <p className="hero__sub">{this.state.error.message}</p>
            <button type="button" className="button" onClick={() => window.location.reload()}>
              Reload the studio
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
