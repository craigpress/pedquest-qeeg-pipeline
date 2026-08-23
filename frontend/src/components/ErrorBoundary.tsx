import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  /** If true, shows a compact inline error for individual panels */
  panel?: boolean;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
    this.props.onReset?.();
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      if (this.props.panel) {
        return (
          <div className="flex items-center justify-between px-4 py-3 rounded border border-red-500/30 bg-red-500/5 text-xs text-red-400">
            <span>Panel failed to load: {this.state.error?.message ?? "Unknown error"}</span>
            <button
              onClick={this.handleRetry}
              className="ml-3 px-2 py-1 rounded bg-red-500/20 hover:bg-red-500/30 text-red-300 transition-colors"
            >
              Retry
            </button>
          </div>
        );
      }

      return (
        <div className="flex flex-col items-center justify-center h-full gap-4 p-8 text-center">
          <div className="text-red-400 text-sm font-medium">Something went wrong</div>
          <div className="text-muted-foreground text-xs max-w-md">
            {this.state.error?.message ?? "An unexpected error occurred"}
          </div>
          <button
            onClick={this.handleRetry}
            className="px-4 py-2 rounded bg-primary/20 hover:bg-primary/30 text-primary text-xs transition-colors"
          >
            Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
