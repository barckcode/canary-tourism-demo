import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  /** Optional custom fallback UI to render when an error occurs */
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  retryCount: number;
}

const MAX_RETRIES = 3;

/**
 * Reusable error boundary that catches render errors in its subtree
 * and displays a user-friendly fallback UI with a retry button.
 * After MAX_RETRIES attempts, the retry button is replaced with a
 * link to navigate back to the dashboard.
 */
export default class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null, retryCount: 0 };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error("[ErrorBoundary] Caught error:", error, errorInfo);
  }

  handleRetry = (): void => {
    this.setState((prev) => ({
      hasError: false,
      error: null,
      retryCount: prev.retryCount + 1,
    }));
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      const exhaustedRetries = this.state.retryCount >= MAX_RETRIES;

      return (
        <div className="flex flex-col items-center justify-center gap-4 p-8 rounded-2xl bg-gray-900/60 border border-gray-700/40">
          <div className="w-12 h-12 rounded-full bg-volcanic-500/20 flex items-center justify-center">
            <svg
              className="w-6 h-6 text-volcanic-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z"
              />
            </svg>
          </div>
          <div className="text-center">
            <h3 className="text-sm font-semibold text-gray-200 mb-1">
              Something went wrong
            </h3>
            <p className="text-xs text-gray-400 max-w-xs">
              {this.state.error?.message || "An unexpected error occurred while rendering this component."}
            </p>
          </div>
          {exhaustedRetries ? (
            <a
              href="/"
              className="px-4 py-2 text-xs font-medium rounded-lg bg-ocean-600 hover:bg-ocean-500 text-white transition-colors"
            >
              Go to Dashboard
            </a>
          ) : (
            <button
              onClick={this.handleRetry}
              className="px-4 py-2 text-xs font-medium rounded-lg bg-ocean-600 hover:bg-ocean-500 text-white transition-colors"
            >
              Retry{this.state.retryCount > 0 ? ` (${this.state.retryCount}/${MAX_RETRIES})` : ""}
            </button>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}
