import { Alert } from "antd";
import { useNetworkStatus } from "../hooks/useNetworkStatus";

/**
 * Renders a fixed banner at the top of the viewport when the browser is offline.
 * Mount once in the root layout.
 */
export function NetworkOfflineBanner() {
  const online = useNetworkStatus();

  if (online) return null;

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        zIndex: 9999,
      }}
    >
      <Alert
        type="warning"
        message="网络连接已断开"
        description="请检查网络连接，恢复后将自动重连。"
        banner
        showIcon
        closable={false}
      />
    </div>
  );
}
