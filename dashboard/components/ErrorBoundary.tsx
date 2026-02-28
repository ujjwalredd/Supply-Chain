"use client";

import { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

interface Props {
  children: ReactNode;
  label?: string; // panel name shown in fallback
}

interface State {
  hasError: boolean;
  message: string;
}

/**
 * Catches render errors in a dashboard panel and shows a minimal fallback,
 * preventing one broken panel from taking down the whole page.
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[ErrorBoundary:${this.props.label}]`, error, info);
  }

  handleRetry = () => {
    this.setState({ hasError: false, message: "" });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-6 flex flex-col items-center gap-3 text-center">
          <AlertTriangle className="h-5 w-5 text-destructive" />
          <div>
            <p className="text-sm font-medium text-destructive">
              {this.props.label ?? "Panel"} failed to render
            </p>
            <p className="text-xs text-mutedForeground mt-1 max-w-xs break-words">
              {this.state.message || "An unexpected error occurred."}
            </p>
          </div>
          <button
            type="button"
            onClick={this.handleRetry}
            className="px-3 py-1.5 rounded bg-destructive/15 text-destructive text-xs font-medium hover:bg-destructive/25 transition-colors"
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
