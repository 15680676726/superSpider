import { Alert, Button, List, Space, Tag } from "antd";

import type {
  RuntimeCommitStatusKind,
  RuntimeSidecarState,
} from "./runtimeSidecarEvents";

type ChatCommitConfirmationCardProps = {
  state: RuntimeSidecarState;
  approveBusy: boolean;
  rejectBusy: boolean;
  onApprove: (decisionIds: string[]) => void;
  onReject: (decisionIds: string[]) => void;
};

function resolveAlertType(kind: RuntimeCommitStatusKind) {
  switch (kind) {
    case "committed":
      return "success" as const;
    case "confirm_required":
    case "environment_unavailable":
      return "warning" as const;
    case "governance_denied":
    case "failed":
      return "error" as const;
    case "started":
    case "deferred":
    default:
      return "info" as const;
  }
}

export function ChatCommitConfirmationCard({
  state,
  approveBusy,
  rejectBusy,
  onApprove,
  onReject,
}: ChatCommitConfirmationCardProps) {
  const current = state.currentCommitStatus;
  if (!current) {
    return null;
  }

  const canConfirm =
    current.kind === "confirm_required" && current.decisionIds.length > 0;
  const historyItems = state.history.slice().reverse();

  return (
    <div style={{ marginBottom: 12 }}>
      <Alert
        showIcon
        type={resolveAlertType(current.kind)}
        message={current.title}
        description={
          <Space direction="vertical" size={10} style={{ width: "100%" }}>
            {current.summary ? <div>{current.summary}</div> : null}
            {current.reason ? (
              <Tag bordered={false} color="default">
                {current.reason}
              </Tag>
            ) : null}
            {historyItems.length > 1 ? (
              <List
                size="small"
                header="当前线程提交记录"
                dataSource={historyItems}
                renderItem={(item) => (
                  <List.Item>
                    <Space size={8}>
                      <span>{item.title}</span>
                      {item.summary ? (
                        <span style={{ color: "rgba(0, 0, 0, 0.65)" }}>
                          {item.summary}
                        </span>
                      ) : null}
                    </Space>
                  </List.Item>
                )}
              />
            ) : null}
          </Space>
        }
        action={
          canConfirm ? (
            <Space>
              <Button
                type="primary"
                size="small"
                loading={approveBusy}
                onClick={() => onApprove(current.decisionIds)}
              >
                批准
              </Button>
              <Button
                danger
                size="small"
                loading={rejectBusy}
                onClick={() => onReject(current.decisionIds)}
              >
                拒绝
              </Button>
            </Space>
          ) : null
        }
      />
    </div>
  );
}
