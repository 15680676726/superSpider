import { Descriptions, Empty, List, Space, Tag, Typography } from "antd";

import type {
  IndustryInstanceDetail,
  IndustryRuntimeLane,
} from "../../api/modules/industry";
import {
  INDUSTRY_TEXT,
  formatTimestamp,
  presentIndustryRuntimeStatus,
  presentText,
  runtimeStatusColor,
} from "./pageHelpers";

const { Text, Paragraph } = Typography;

function nonEmpty(value: string | null | undefined): string | null {
  const normalized = value?.trim();
  return normalized ? normalized : null;
}

function isFocusedLane(
  lane: IndustryRuntimeLane,
  detail: IndustryInstanceDetail,
): boolean {
  const currentCycle = detail.current_cycle;
  if (!currentCycle) {
    return false;
  }
  return (currentCycle.focus_lane_ids || []).includes(lane.lane_id);
}

interface IndustryPlanningSurfaceProps {
  detail: IndustryInstanceDetail;
  locale: string;
}

export default function IndustryPlanningSurface({
  detail,
  locale,
}: IndustryPlanningSurfaceProps) {
  const hasCurrentCycle = Boolean(detail.current_cycle);
  const lanes = detail.lanes || [];
  const runtimeSignals = [
    { label: "Assignments", value: detail.assignments.length },
    { label: "Reports", value: detail.agent_reports.length },
    { label: "Evidence", value: detail.evidence.length },
    { label: "Decisions", value: detail.decisions.length },
    { label: "Patches", value: detail.patches.length },
  ];
  const synthesis = detail.current_cycle?.synthesis;
  const synthesisFindings = synthesis?.latest_findings || [];
  const synthesisFollowups = synthesisFindings.filter(
    (finding) => finding.needs_followup || nonEmpty(finding.followup_reason),
  );
  const recommendedActions = synthesis?.recommended_actions || [];
  const controlCoreContract = synthesis?.control_core_contract || [];
  const pendingProposalCount = detail.staffing?.pending_proposals.length || 0;
  const temporarySeatCount = detail.staffing?.temporary_seats.length || 0;
  const pendingSignalCount =
    typeof detail.staffing?.researcher?.pending_signal_count === "number"
      ? detail.staffing.researcher.pending_signal_count
      : 0;

  if (!hasCurrentCycle && lanes.length === 0) {
    return null;
  }

  return (
    <>
      <div>
        <Text
          strong
          style={{
            color: "var(--baize-text-muted)",
            fontSize: 12,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
          }}
        >
          Runtime Signals
        </Text>
        <Space wrap style={{ marginTop: 8 }}>
          {detail.current_cycle ? (
            <Tag color={runtimeStatusColor(detail.current_cycle.status)}>
              {presentIndustryRuntimeStatus(detail.current_cycle.status)}
            </Tag>
          ) : null}
          {detail.current_cycle?.focus_lane_ids.length ? (
            <Tag>{`Focus lanes ${detail.current_cycle.focus_lane_ids.length}`}</Tag>
          ) : null}
          {runtimeSignals.map((signal) => (
            <Tag key={signal.label}>
              {`${signal.label} ${signal.value}`}
            </Tag>
          ))}
        </Space>
      </div>

      {detail.current_cycle ? (
        <div>
          <Text
            strong
            style={{
              color: "var(--baize-text-muted)",
              fontSize: 12,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
            }}
          >
            {INDUSTRY_TEXT.detailCurrentCycle}
          </Text>
          <div style={{ marginTop: 8 }}>
            <Space wrap style={{ marginBottom: 8 }}>
              <Tag color={runtimeStatusColor(detail.current_cycle.status)}>
                {presentIndustryRuntimeStatus(detail.current_cycle.status)}
              </Tag>
              <Tag>
                {detail.current_cycle.cycle_kind === "weekly" ? "周周期" : "日周期"}
              </Tag>
              {detail.current_cycle.due_at ? (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {`到期 ${formatTimestamp(detail.current_cycle.due_at, locale)}`}
                </Text>
              ) : null}
            </Space>
            <Descriptions
              size="small"
              column={2}
              items={[
                {
                  key: "cycle-title",
                  label: "周期标题",
                  children: presentText(detail.current_cycle.title),
                },
                {
                  key: "cycle-summary",
                  label: "周期摘要",
                  children: presentText(detail.current_cycle.summary),
                },
                {
                  key: "focus-lanes",
                  label: "关注泳道",
                  children: `${detail.current_cycle.focus_lane_ids.length}`,
                },
                {
                  key: "backlog-count",
                  label: "待办",
                  children: `${detail.current_cycle.backlog_item_ids.length}`,
                },
                {
                  key: "assignment-count",
                  label: "派工",
                  children: `${detail.current_cycle.assignment_ids.length}`,
                },
                {
                  key: "report-count",
                  label: "汇报",
                  children: `${detail.current_cycle.report_ids.length}`,
                },
              ]}
            />
            {detail.current_cycle.synthesis ? (
              <>
                <Space wrap style={{ marginTop: 8 }}>
                  <Tag>{`发现 ${detail.current_cycle.synthesis.latest_findings.length}`}</Tag>
                  <Tag
                    color={
                      detail.current_cycle.synthesis.conflicts.length > 0
                        ? "error"
                        : "default"
                    }
                  >
                    {`冲突 ${detail.current_cycle.synthesis.conflicts.length}`}
                  </Tag>
                  <Tag
                    color={
                      detail.current_cycle.synthesis.holes.length > 0
                        ? "warning"
                        : "default"
                    }
                  >
                    {`缺口 ${detail.current_cycle.synthesis.holes.length}`}
                  </Tag>
                  {recommendedActions.length > 0 ? (
                    <Tag>{`建议动作 ${recommendedActions.length}`}</Tag>
                  ) : null}
                  {synthesisFollowups.length > 0 ? (
                    <Tag color="warning">{`待主脑跟进 ${synthesisFollowups.length}`}</Tag>
                  ) : null}
                  {detail.current_cycle.synthesis.needs_replan ? (
                    <Tag color="error">需要重规划</Tag>
                  ) : null}
                </Space>
                {(synthesisFollowups.length > 0 ||
                  recommendedActions.length > 0 ||
                  controlCoreContract.length > 0) ? (
                  <Space
                    direction="vertical"
                    size={6}
                    style={{ width: "100%", marginTop: 8 }}
                  >
                    {synthesisFollowups.length > 0 ? (
                      <div>
                        <Text strong style={{ fontSize: 12 }}>
                          监督闭环
                        </Text>
                        <Space direction="vertical" size={4} style={{ width: "100%", marginTop: 4 }}>
                          {synthesisFollowups.slice(0, 3).map((finding) => (
                            <Text key={finding.report_id} type="secondary">
                              {[
                                finding.headline || finding.summary || finding.report_id,
                                nonEmpty(finding.followup_reason),
                              ]
                                .filter(Boolean)
                                .join(" | ")}
                            </Text>
                          ))}
                        </Space>
                      </div>
                    ) : null}
                    {recommendedActions.length > 0 ? (
                      <div>
                        <Text strong style={{ fontSize: 12 }}>
                          建议动作
                        </Text>
                        <Space direction="vertical" size={4} style={{ width: "100%", marginTop: 4 }}>
                          {recommendedActions.slice(0, 3).map((action) => (
                            <Text key={action.action_id} type="secondary">
                              {String(action.title || action.summary || action.action_id)}
                            </Text>
                          ))}
                        </Space>
                      </div>
                    ) : null}
                    {controlCoreContract.length > 0 ? (
                      <div>
                        <Text strong style={{ fontSize: 12 }}>
                          控制契约
                        </Text>
                        <Space direction="vertical" size={4} style={{ width: "100%", marginTop: 4 }}>
                          {controlCoreContract.map((item) => (
                            <Text key={item} type="secondary">
                              {item}
                            </Text>
                          ))}
                        </Space>
                      </div>
                    ) : null}
                  </Space>
                ) : null}
              </>
            ) : null}
          </div>
        </div>
      ) : null}

      <div>
        <Text
          strong
          style={{
            color: "var(--baize-text-muted)",
            fontSize: 12,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
          }}
        >
          {INDUSTRY_TEXT.detailLanes}
        </Text>
        <Paragraph type="secondary" style={{ margin: "8px 0 0" }}>
          主脑按 lane 组织当前周期焦点、责任边界和后续汇报。
        </Paragraph>
        {(pendingProposalCount > 0 || temporarySeatCount > 0 || pendingSignalCount > 0) ? (
          <Space wrap style={{ marginTop: 8 }}>
            {pendingProposalCount > 0 ? <Tag>{`补位提案 ${pendingProposalCount}`}</Tag> : null}
            {temporarySeatCount > 0 ? <Tag>{`临时席位 ${temporarySeatCount}`}</Tag> : null}
            {pendingSignalCount > 0 ? (
              <Tag color="warning">{`待研判信号 ${pendingSignalCount}`}</Tag>
            ) : null}
          </Space>
        ) : null}
        {lanes.length === 0 ? (
          <Empty
            description="当前还没有正式工作泳道。"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            style={{ margin: "8px 0" }}
          />
        ) : (
          <List
            style={{ marginTop: 8 }}
            dataSource={lanes}
            renderItem={(lane) => {
              const focused = isFocusedLane(lane, detail);
              return (
                <List.Item>
                  <Space direction="vertical" size={4} style={{ width: "100%" }}>
                    <Space wrap>
                      <Text strong>{lane.title || lane.lane_id}</Text>
                      <Tag color={runtimeStatusColor(lane.status)}>
                        {presentIndustryRuntimeStatus(lane.status)}
                      </Tag>
                      <Tag>{`P${lane.priority}`}</Tag>
                      {focused ? <Tag color="blue">当前周期关注</Tag> : null}
                    </Space>
                    <Text type="secondary">
                      {lane.summary || lane.source_ref || "当前泳道还没有补充摘要。"}
                    </Text>
                  </Space>
                </List.Item>
              );
            }}
          />
        )}
      </div>
    </>
  );
}
