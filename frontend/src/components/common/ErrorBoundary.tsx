/**
 * ErrorBoundary — catches render-time errors in the component subtree and
 * displays a safe fallback UI instead of crashing the entire page.
 *
 * Usage:
 *   <ErrorBoundary fallback={<p>Something went wrong.</p>}>
 *     <ChildThatMightThrow />
 *   </ErrorBoundary>
 *
 * If no `fallback` prop is provided a default message is shown.
 */

import { Component, type ReactNode, type ErrorInfo } from "react";

interface Props {
  /** Content to render when no error has occurred. */
  children: ReactNode;
  /** Optional custom fallback UI to display on error. */
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(_error: Error): State {
    // Update state so the next render shows the fallback UI.
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // TODO: send error + info to a logging/monitoring service
    console.error("[ErrorBoundary] Caught error:", error, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <p className="text-lg font-semibold text-red-600">
              Something went wrong.
            </p>
            <p className="text-sm text-gray-500">
              Please refresh the page or try again later.
            </p>
          </div>
        )
      );
    }

    return this.props.children;
  }
}
