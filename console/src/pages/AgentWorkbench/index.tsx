import React, { useMemo } from "react";
import {
  Alert,
  Button,
  Card,
  Empty,
  Space,
  Spin,
  Tabs,
  Tag,
  Typography,
  message,
} from "antd";
import {
  BarChartOutlined,
  CalendarOutlined,
  FolderOpenOutlined,
  ReloadOutlined,
  RiseOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  AgentDailyReport,
  AgentGrowthTrajectory,
  AgentWeeklyReport,
} from "./AgentReports";
import styles from "./index.module.less";
import {
  agentWorkbenchText,
  getIndustryRuntimeStatusLabel,
  runtimeCenterText,
} from "./copy";
import { localizeWorkbenchText } from "./localize";
import WorkspaceTab from "./WorkspaceTab";
import V7ExecutionSeatPanel from "./V7ExecutionSeatPanel";
import {
  type AgentProfile,
  useAgentWorkbench,
} from "./useAgentWorkbench";
import {
  buildAgentChatBinding,
  navigateToRuntimeChatEntry,
  openRuntimeChat,
} from "../../utils/runtimeChat";
import { presentExecutionActorName } from "../../runtime/executionPresentation";

import {
  TAB_KEYS,
  isExecutionCoreAgent,
  ProfileCard,
  CapabilityGovernancePanel,
  ActorRuntimePanel,
  EvidencePanel,
  statusColor,
} from "./pageSections";

const { Paragraph, Text } = Typography;

const AGENT_WORKBENCH_TAB_ALIASES: Record<string, string> = {
  workbench: "profile",
  workspace: "evidence",
  growth: "performance",
};

function normalizeAgentWorkbenchTab(rawTab: string | null): string {
  if (!rawTab) {
    return "daily";
  }
  const aliased = AGENT_WORKBENCH_TAB_ALIASES[rawTab] ?? rawTab;
  return TAB_KEYS.has(aliased) ? aliased : "daily";
}

function resolveExecutionSeatAgent(
  agents: AgentProfile[],
  candidate: AgentProfile | null | undefined,
): AgentProfile | null {
  if (!candidate || isExecutionCoreAgent(candidate)) {
    return null;
  }
  return agents.find((agent) => agent.agent_id === candidate.agent_id) || candidate;
}

function renderTabLabel(icon: React.ReactNode, label: string) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      {icon}
      <span>{label}</span>
    </span>
  );
}

export default function AgentWorkbenchPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedIndustryId = searchParams.get("industry");
  const requestedAgentId = searchParams.get("agent");
  const {
    agents,
    selectedAgent,
    setSelectedAgent,
    agentDetail,
    industryDetail,
    capabilityCatalog,
    evidence,
    loading,
    agentDetailLoading,
    industryDetailLoading,
    capabilityCatalogLoading,
    dashboardError,
    agentDetailError,
    industryDetailError,
    capabilityActionKey,
    actorActionKey,
    refresh,
    refreshAgentDetail,
    submitGovernedCapabilityAssignment,
    resolveCapabilityDecision,
    pauseActorRuntime,
    resumeActorRuntime,
    retryActorMailboxRuntime,
    cancelActorRuntime,
  } = useAgentWorkbench({
    industryInstanceId: requestedIndustryId,
  });

  const requestedTab = searchParams.get("tab");
  const activeTab = normalizeAgentWorkbenchTab(requestedTab);
  const executionCoreAgent = useMemo(
    () => agents.find((agent) => isExecutionCoreAgent(agent)) || null,
    [agents],
  );
  const executionSeatAgents = useMemo(
    () => agents.filter((agent) => !isExecutionCoreAgent(agent)),
    [agents],
  );
  const requestedExecutionSeat = useMemo(
    () =>
      requestedAgentId
        ? executionSeatAgents.find((agent) => agent.agent_id === requestedAgentId) || null
        : null,
    [executionSeatAgents, requestedAgentId],
  );
  const selectedExecutionSeat = useMemo(
    () => resolveExecutionSeatAgent(executionSeatAgents, selectedAgent),
    [executionSeatAgents, selectedAgent],
  );
  const defaultFocusedAgent = useMemo(
    () => requestedExecutionSeat || selectedExecutionSeat || executionSeatAgents[0] || null,
    [executionSeatAgents, requestedExecutionSeat, selectedExecutionSeat],
  );
  const displayedAgent = defaultFocusedAgent;
  const displayedAgentDetail = useMemo(
    () => {
      if (!displayedAgent || !agentDetail?.agent) {
        return null;
      }
      if (isExecutionCoreAgent(agentDetail.agent)) {
        return null;
      }
      return agentDetail.agent.agent_id === displayedAgent.agent_id ? agentDetail : null;
    },
    [agentDetail, displayedAgent],
  );
  const displayedEvidence = displayedAgentDetail ? displayedAgentDetail.evidence : evidence;

  React.useEffect(() => {
    if (agents.length === 0) {
      return;
    }
    const nextAgent = requestedExecutionSeat || selectedExecutionSeat || executionSeatAgents[0] || null;
    if (!nextAgent || selectedAgent?.agent_id === nextAgent.agent_id) {
      return;
    }
    setSelectedAgent(nextAgent);
  }, [
    executionSeatAgents,
    requestedExecutionSeat,
    selectedAgent?.agent_id,
    selectedExecutionSeat,
    setSelectedAgent,
  ]);

  const handleSelectAgent = React.useCallback((agent: AgentProfile | null) => {
    if (!agent) {
      return;
    }
    if (selectedAgent?.agent_id !== agent.agent_id) {
      setSelectedAgent(agent);
    }
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("agent", agent.agent_id);
    if (nextParams.toString() !== searchParams.toString()) {
      setSearchParams(nextParams, { replace: true });
    }
  }, [
    searchParams,
    selectedAgent?.agent_id,
    setSearchParams,
    setSelectedAgent,
  ]);

  const handleTabChange = (nextTab: string) => {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("tab", nextTab);
    if (displayedAgent?.agent_id) {
      nextParams.set("agent", displayedAgent.agent_id);
    }
    setSearchParams(nextParams, { replace: true });
  };

  const handleClearIndustryScope = () => {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("industry");
    setSearchParams(nextParams, { replace: true });
  };

  const handleOpenChat = async (agent: AgentProfile | null) => {
    if (!agent) {
      return;
    }
    try {
      if (!agent.industry_instance_id) {
        navigateToRuntimeChatEntry(navigate);
        message.info("当前前台只保留主脑聊天入口，已切换到主脑聊天。");
        return;
      }
      await openRuntimeChat(buildAgentChatBinding(agent), navigate);
    } catch (err) {
      message.error(
        err instanceof Error ? err.message : agentWorkbenchText.chatOpenFailed,
      );
      }
  };

  const handleOpenRuntimeCenter = React.useCallback(() => {
    navigate("/runtime-center");
  }, [navigate]);

  if (loading) {
    return (
      <div style={{ textAlign: "center", paddingTop: 120 }}>
        <Spin size="large" />
        <br />
        <Text type="secondary">{agentWorkbenchText.loading}</Text>
      </div>
    );
  }

  if (agents.length === 0) {
    return (
      <div style={{ padding: 24 }}>
        <Empty description={agentWorkbenchText.noAgents} />
      </div>
    );
  }

  return (
    <div style={{ padding: 24, width: "100%" }}>
      {requestedIndustryId ? (
        <Alert
          type="info"
          showIcon
          closable
          onClose={handleClearIndustryScope}
          style={{ marginBottom: 32 }}
          message={agentWorkbenchText.scopeMessage}
          description={
            <Space wrap>
              <Tag>{requestedIndustryId}</Tag>
              <Button className="baize-btn" size="small" type="link" onClick={handleClearIndustryScope}>
                {agentWorkbenchText.clearScope}
              </Button>
            </Space>
          }
        />
      ) : null}
      <Card className="baize-page-header">
        <div className="baize-page-header-content">
          <div>
            <h1 className="baize-page-header-title">{agentWorkbenchText.pageTitle}</h1>
            <p className="baize-page-header-description">{agentWorkbenchText.pageDescription}</p>
          </div>
          <div className="baize-page-header-actions">
            <Button
              icon={<ReloadOutlined />}
              onClick={() => {
                void refresh();
              }}
              className="baize-btn"
            >
              刷新
            </Button>
          </div>
        </div>
      </Card>
      {executionCoreAgent ? (
        <Card className="baize-card" style={{ marginBottom: 32 }}>
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <Space wrap>
              <Text strong>主脑与执行位</Text>
              <Tag color="blue">超级伙伴主脑</Tag>
              <Tag color={statusColor(executionCoreAgent.status)}>
                {getIndustryRuntimeStatusLabel(executionCoreAgent.status)}
              </Tag>
              {executionSeatAgents.length > 0 ? (
                <Tag>{`执行位 ${executionSeatAgents.length}`}</Tag>
              ) : null}
            </Space>
            <Paragraph style={{ marginBottom: 0 }}>
              超级伙伴主脑保留长期使命与派工权；下方面板只聚焦当前所选执行位的
              执行、回流、升级与待主脑裁决事项。
            </Paragraph>
            <div className={styles.agentSwitcherGrid}>
              <Card
                className={[
                  "baize-card",
                  styles.agentSwitcherCard,
                ].filter(Boolean).join(" ")}
                hoverable
                size="small"
                onClick={handleOpenRuntimeCenter}
              >
                <div className={styles.agentSwitcherHeader}>
                  <UserOutlined className={styles.agentSwitcherIcon} />
                  <div
                    className={styles.agentSwitcherName}
                    title={presentExecutionActorName(
                      executionCoreAgent.agent_id,
                      executionCoreAgent.name,
                    )}
                  >
                    {presentExecutionActorName(
                      executionCoreAgent.agent_id,
                      executionCoreAgent.name,
                    )}
                  </div>
                  <Tag color="blue">主脑</Tag>
                </div>
                <Space wrap size={[6, 6]}>
                  <Tag color={statusColor(executionCoreAgent.status)}>
                    {getIndustryRuntimeStatusLabel(executionCoreAgent.status)}
                  </Tag>
                  {executionSeatAgents.length > 0 ? (
                    <Tag>{`执行位 ${executionSeatAgents.length}`}</Tag>
                  ) : null}
                </Space>
                <Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>
                  {localizeWorkbenchText(
                    executionCoreAgent.role_summary ||
                      executionCoreAgent.current_focus ||
                      executionCoreAgent.mission,
                  ) || "负责拆解目标、分派执行位、回收证据并监督结果。点击返回主脑驾驶舱查看全局运行。"}
                </Paragraph>
              </Card>
              {executionSeatAgents.map((agent) => (
                <Card
                  className={[
                    "baize-card",
                    styles.agentSwitcherCard,
                    displayedAgent?.agent_id === agent.agent_id
                      ? styles.agentSwitcherCardSelected
                      : "",
                  ].filter(Boolean).join(" ")}
                  key={agent.agent_id}
                  hoverable
                  size="small"
                  onClick={() => handleSelectAgent(agent)}
                >
                  <Space wrap>
                    <UserOutlined />
                    <Text strong>{presentExecutionActorName(agent.agent_id, agent.name)}</Text>
                    <Tag color="default">执行位</Tag>
                    <Tag color={statusColor(agent.status)}>
                      {getIndustryRuntimeStatusLabel(agent.status)}
                    </Tag>
                  </Space>
                  <div hidden style={{ marginTop: 8 }}>
                    <Text type="secondary">
                      {localizeWorkbenchText(agent.role_name) || agentWorkbenchText.unassignedRole}
                    </Text>
                  </div>
                  <div hidden style={{ marginTop: 4 }}>
                    <Text type="secondary">
                      {localizeWorkbenchText(
                        agent.current_focus ||
                          agent.role_summary ||
                          agent.environment_summary,
                      ) || "由超级伙伴主脑统一分派任务。"}
                    </Text>
                  </div>
                  {false ? (
                    <div style={{ marginTop: 8 }}>
                      <Tag color="green">当前聚焦</Tag>
                    </div>
                  ) : null}
                </Card>
              ))}
            </div>
          </Space>
        </Card>
      ) : null}

      {dashboardError ? (
        <Alert
          showIcon
          type="error"
          message={agentWorkbenchText.dataUnavailable}
          description={dashboardError}
          style={{ marginBottom: 32 }}
        />
      ) : null}
      {agentDetailError ? (
        <Alert
          showIcon
          type="warning"
          message={runtimeCenterText.agentDetail}
          description={agentDetailError}
          style={{ marginBottom: 32 }}
        />
      ) : null}

      <Tabs
        activeKey={activeTab}
        destroyInactiveTabPane={false}
        onChange={handleTabChange}
        items={[
          {
            key: "daily",
            label: renderTabLabel(<CalendarOutlined />, agentWorkbenchText.tabDaily),
            children: (
              <AgentDailyReport
                agentId={displayedAgent?.agent_id ?? null}
                agentName={displayedAgent?.name ?? null}
              />
            ),
          },
          {
            key: "weekly",
            label: renderTabLabel(<BarChartOutlined />, agentWorkbenchText.tabWeekly),
            children: (
              <AgentWeeklyReport
                agentId={displayedAgent?.agent_id ?? null}
                agentName={displayedAgent?.name ?? null}
              />
            ),
          },
          {
            key: "profile",
            label: renderTabLabel(<UserOutlined />, agentWorkbenchText.tabProfile),
            children: (
              <>
                {displayedAgent ? (
                  <ProfileCard
                    agent={displayedAgent}
                    onOpenChat={() => {
                      void handleOpenChat(displayedAgent);
                    }}
                  />
                ) : null}
                {displayedAgent ? (
                  <V7ExecutionSeatPanel
                    agent={displayedAgent}
                    agents={agents}
                    agentDetail={displayedAgentDetail}
                    industryDetail={industryDetail}
                    industryDetailLoading={industryDetailLoading}
                    industryDetailError={industryDetailError}
                  />
                ) : null}
                {displayedAgent ? (
                  <CapabilityGovernancePanel
                    agent={displayedAgent}
                    detail={displayedAgentDetail}
                    capabilityCatalog={capabilityCatalog}
                    capabilityCatalogLoading={capabilityCatalogLoading}
                    capabilityActionKey={capabilityActionKey}
                    onRefresh={refreshAgentDetail}
                    onSubmitGovernedChange={submitGovernedCapabilityAssignment}
                    onResolveDecision={resolveCapabilityDecision}
                  />
                ) : null}
                <ActorRuntimePanel
                  detail={displayedAgentDetail}
                  actorActionKey={actorActionKey}
                  onPauseActor={pauseActorRuntime}
                  onResumeActor={resumeActorRuntime}
                  onRetryMailbox={retryActorMailboxRuntime}
                  onCancelActor={cancelActorRuntime}
                />
              </>
            ),
          },
          {
            key: "performance",
            label: renderTabLabel(<RiseOutlined />, agentWorkbenchText.tabPerformance),
            children: <AgentGrowthTrajectory />,
          },
          {
            key: "evidence",
            label: renderTabLabel(<FolderOpenOutlined />, agentWorkbenchText.tabEvidence),
            children: (
              <>
                <WorkspaceTab
                  agent={displayedAgent}
                  agentDetail={displayedAgentDetail}
                  loading={agentDetailLoading}
                  error={agentDetailError}
                />
                <EvidencePanel evidence={displayedEvidence} agents={agents} />
              </>
            ),
          },
        ]}
      />
    </div>
  );
}
