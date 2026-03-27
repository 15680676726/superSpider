import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button, Result } from "antd";
import {
  isChunkLoadError,
  reloadForChunkError,
} from "../runtime/chunkLoadRecovery";
import { isApiError } from "../api";

interface Props {
  children: ReactNode;
  /** Key to reset the boundary (e.g. route path). */
  resetKey?: string;
  /** Custom fallback renderer. */
  fallback?: (error: Error, reset: () => void) => ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Page-level error boundary that handles:
 * - Chunk load failures → auto-reload
 * - API errors → friendly message with retry
 * - Generic errors → fallback UI with reset
 */
export class PageErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Chunk load errors → auto-reload
    if (isChunkLoadError(error)) {
      reloadForChunkError();
      return;
    }

    // Log for debugging
    console.error("[PageErrorBoundary]", error, info.componentStack);
  }

  componentDidUpdate(prevProps: Props): void {
    // Reset error state when resetKey changes (e.g. route navigation)
    if (this.state.error && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ error: null });
    }
  }

  private handleReset = (): void => {
    this.setState({ error: null });
  };

  render(): ReactNode {
    const { error } = this.state;

    if (!error) {
      return this.props.children;
    }

    // Custom fallback
    if (this.props.fallback) {
      return this.props.fallback(error, this.handleReset);
    }

    // API error — show structured message
    if (isApiError(error)) {
      return (
        <Result
          status={error.isServerError ? "500" : "error"}
          title={error.isServerError ? "服务器错误" : "请求失败"}
          subTitle={error.detail || `错误码：${error.status}`}
          extra={
            <Button type="primary" onClick={this.handleReset}>
              重试
            </Button>
          }
        />
      );
    }

    // Generic error
    return (
      <Result
        status="error"
        title="页面出错了"
        subTitle={error.message || "发生了未知错误，请重试。"}
        extra={[
          <Button key="retry" type="primary" onClick={this.handleReset}>
            重试
          </Button>,
          <Button key="home" onClick={() => (window.location.href = "/")}>
            返回首页
          </Button>,
        ]}
      />
    );
  }
}
