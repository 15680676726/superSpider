import React from "react";
import { Button, Result, Space, Typography } from "antd";
import {
  isChunkLoadError,
  reloadForChunkError,
} from "../runtime/chunkLoadRecovery";

const { Paragraph, Text } = Typography;

interface ChunkLoadBoundaryProps {
  children: React.ReactNode;
  resetKey?: string;
}

interface ChunkLoadBoundaryState {
  error: Error | null;
  autoReloadTriggered: boolean;
  recoveryAttempted: boolean;
}

export class ChunkLoadBoundary extends React.Component<
  ChunkLoadBoundaryProps,
  ChunkLoadBoundaryState
> {
  state: ChunkLoadBoundaryState = {
    error: null,
    autoReloadTriggered: false,
    recoveryAttempted: false,
  };

  static getDerivedStateFromError(error: Error): Partial<ChunkLoadBoundaryState> {
    return { error };
  }

  componentDidUpdate(prevProps: ChunkLoadBoundaryProps): void {
    if (prevProps.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({
        error: null,
        autoReloadTriggered: false,
        recoveryAttempted: false,
      });
      return;
    }
    if (
      this.state.error &&
      isChunkLoadError(this.state.error) &&
      !this.state.recoveryAttempted
    ) {
      const reloaded = reloadForChunkError();
      this.setState({
        autoReloadTriggered: reloaded,
        recoveryAttempted: true,
      });
    }
  }

  componentDidCatch(error: Error): void {
    console.error("Chunk load boundary caught render error", error);
  }

  render(): React.ReactNode {
    const { error, autoReloadTriggered } = this.state;
    if (!error) {
      return this.props.children;
    }

    const chunkLoadFailed = isChunkLoadError(error);
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "grid",
          placeItems: "center",
          padding: 24,
        }}
      >
        <Result
          status="warning"
          title={chunkLoadFailed ? "前端资源已更新" : "页面加载失败"}
          subTitle={
            chunkLoadFailed
              ? autoReloadTriggered
                ? "系统正在恢复最新页面资源。若长时间未恢复，可手动刷新一次。"
                : "当前页面引用的旧资源已经失效，请刷新页面加载最新版本。"
              : "页面运行时出现异常，请刷新后重试。"
          }
          extra={
            <Space>
              <Button type="primary" onClick={() => window.location.reload()}>
                刷新页面
              </Button>
            </Space>
          }
        >
          <Paragraph style={{ marginBottom: 0 }}>
            <Text type="secondary">
              {chunkLoadFailed
                ? "这通常发生在前端刚重新构建或服务刚重启，而你当前页面还停留在旧版本时。"
                : error.message || "未知错误"}
            </Text>
          </Paragraph>
        </Result>
      </div>
    );
  }
}
