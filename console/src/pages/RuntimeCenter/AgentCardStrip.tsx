import { Card, Progress, Tag } from "antd";

import { normalizeDisplayChinese } from "../../text";
import { presentRuntimeStatusLabel } from "../../runtime/executionPresentation";
import { runtimeStatusColor } from "../../runtime/tagSemantics";
import styles from "./index.module.less";

export interface AgentCardStripItem {
  id: string;
  name: string;
  role: string;
  status: string;
  progress: number;
  needsAttention: boolean;
  isMainBrain?: boolean;
}

type AgentCardStripProps = {
  agents: AgentCardStripItem[];
  selectedId: string;
  onSelect: (id: string) => void;
};

function clampProgress(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round(value)));
}

function sortAgents(items: AgentCardStripItem[]): AgentCardStripItem[] {
  return [...items].sort((left, right) => {
    if (left.isMainBrain && !right.isMainBrain) {
      return -1;
    }
    if (!left.isMainBrain && right.isMainBrain) {
      return 1;
    }
    if (left.needsAttention !== right.needsAttention) {
      return left.needsAttention ? -1 : 1;
    }
    return left.name.localeCompare(right.name, "zh-CN");
  });
}

export default function AgentCardStrip({
  agents,
  selectedId,
  onSelect,
}: AgentCardStripProps) {
  const orderedAgents = sortAgents(agents);

  return (
    <div className={styles.agentCardStrip}>
      {orderedAgents.map((agent) => {
        const selected = agent.id === selectedId;
        return (
          <Card
            key={agent.id}
            className={`${styles.agentCard} ${
              selected ? styles.agentCardSelected : ""
            } ${agent.isMainBrain ? styles.agentCardMain : ""}`}
            bodyStyle={{ padding: 0 }}
          >
            <button
              type="button"
              className={styles.agentCardButton}
              onClick={() => onSelect(agent.id)}
            >
              <div className={styles.agentCardTop}>
                <div>
                  <div className={styles.agentCardName}>
                    {normalizeDisplayChinese(agent.name)}
                  </div>
                  <div className={styles.agentCardRole}>
                    {normalizeDisplayChinese(agent.role)}
                  </div>
                </div>
                <Tag color={runtimeStatusColor(agent.status)}>
                  {presentRuntimeStatusLabel(agent.status)}
                </Tag>
              </div>

              <div className={styles.agentCardProgressMeta}>
                <span>进度</span>
                <span>{`${clampProgress(agent.progress)}%`}</span>
              </div>
              <Progress
                percent={clampProgress(agent.progress)}
                showInfo={false}
                strokeColor={agent.needsAttention ? "#f59e0b" : "#1677ff"}
                trailColor="rgba(148, 163, 184, 0.18)"
              />

              <div className={styles.agentCardFooter}>
                {agent.needsAttention ? (
                  <span className={styles.agentCardAttention}>✋ 需要你决定</span>
                ) : (
                  <span className={styles.agentCardHint}>当前可继续自动推进</span>
                )}
              </div>
            </button>
          </Card>
        );
      })}
    </div>
  );
}
