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

const HISTORY_HEADER = "\u5f53\u524d\u7ebf\u7a0b\u63d0\u4ea4\u8bb0\u5f55";
const APPROVE_LABEL = "\u6279\u51c6";
const REJECT_LABEL = "\u62d2\u7edd";

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
                header={HISTORY_HEADER}
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
                {APPROVE_LABEL}
              </Button>
              <Button
                danger
                size="small"
                loading={rejectBusy}
                onClick={() => onReject(current.decisionIds)}
              >
                {REJECT_LABEL}
              </Button>
            </Space>
          ) : null
        }
      />
    </div>
  );
}
