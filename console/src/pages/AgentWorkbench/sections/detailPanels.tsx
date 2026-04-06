import {
  Card,
  Empty,
  Space,
  Tag,
  Typography,
} from "antd";

import {
  agentWorkbenchText,
} from "../copy";
import type {
  AgentProfile,
  EvidenceListItem,
} from "../useAgentWorkbench";
import {
  DELEGATE_TASK_CAPABILITY,
  delegationText,
} from "./shared";
import {
  EvidenceRow,
} from "./taskPanels";

const { Text } = Typography;

export function EvidencePanel({
  evidence,
  agents,
}: {
  evidence: EvidenceListItem[];
  agents: AgentProfile[];
}) {
  if (evidence.length === 0) {
    return (
      <Card className="baize-card" title={agentWorkbenchText.recentEvidenceTitle} style={{ marginBottom: 32 }}>
        <Empty
          description={agentWorkbenchText.noEvidenceRecords}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      </Card>
    );
  }

  const delegationEvidence = evidence.filter(
    (item) => item.capability_ref === DELEGATE_TASK_CAPABILITY,
  );
  const executionEvidence = evidence.filter(
    (item) => item.capability_ref !== DELEGATE_TASK_CAPABILITY,
  );

  return (
    <Card className="baize-card" title={agentWorkbenchText.recentEvidenceTitle} style={{ marginBottom: 32 }}>
      {delegationEvidence.length > 0 ? (
        <div style={{ marginBottom: executionEvidence.length > 0 ? 20 : 0 }}>
          <Space wrap style={{ marginBottom: 8 }}>
            <Text strong>{delegationText.delegationEvidenceTitle}</Text>
            <Tag color="purple">{delegationEvidence.length}</Tag>
          </Space>
          {delegationEvidence.slice(0, 6).map((item) => (
            <EvidenceRow key={item.id} item={item} agents={agents} />
          ))}
        </div>
      ) : null}

      {executionEvidence.length > 0 ? (
        <div>
          <Space wrap style={{ marginBottom: 8 }}>
            <Text strong>{delegationText.executionEvidenceTitle}</Text>
            <Tag>{executionEvidence.length}</Tag>
          </Space>
          {executionEvidence.slice(0, 10).map((item) => (
            <EvidenceRow key={item.id} item={item} agents={agents} />
          ))}
        </div>
      ) : null}
    </Card>
  );
}
