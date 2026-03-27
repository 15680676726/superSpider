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
  workspaceText,
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
  openRuntimeChat,
} from "../../utils/runtimeChat";
import { presentExecutionActorName } from "../../runtime/executionPresentation";

import {
  TAB_KEYS,
  GoalSelector,
  isExecutionCoreAgent,
  ProfileCard,
  CapabilityGovernancePanel,
  ActorRuntimePanel,
  GoalDetailPanel,
  EvidencePanel,
  statusColor,
} from "./pageSections";

const { Paragraph, Text } = Typography;

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
    goals,
    selectedGoalId,
    setSelectedGoalId,
    goalDetail,
    loading,
    agentDetailLoading,
    industryDetailLoading,
    capabilityCatalogLoading,
    goalLoading,
    dashboardError,
    agentDetailError,
    industryDetailError,
    goalError,
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
  const activeTab = TAB_KEYS.has(requestedTab ?? "") ? requestedTab ?? "workbench" : "workbench";
  const executionCoreAgent = useMemo(
    () =>
      agents.find((agent) => isExecutionCoreAgent(agent)) ||
      selectedAgent ||
      agents[0] ||
      null,
    [agents, selectedAgent],
  );
  const executionSeatAgents = useMemo(
    () =>
      executionCoreAgent
        ? agents.filter((agent) => agent.agent_id !== executionCoreAgent.agent_id)
        : agents,
    [agents, executionCoreAgent],
  );
  const defaultFocusedAgent = useMemo(
    () => executionSeatAgents[0] || executionCoreAgent || agents[0] || null,
    [agents, executionCoreAgent, executionSeatAgents],
  );
  const displayedAgent = agentDetail?.agent ?? selectedAgent ?? defaultFocusedAgent;
  const displayedGoals = agentDetail ? agentDetail.goals : goals;
  const displayedEvidence = agentDetail ? agentDetail.evidence : evidence;

  React.useEffect(() => {
    if (agents.length === 0) {
      return;
    }
    const matchedAgent = requestedAgentId
      ? agents.find((item) => item.agent_id === requestedAgentId) || null
      : null;
    const persistedSelection = selectedAgent
      ? agents.find((item) => item.agent_id === selectedAgent.agent_id) || null
      : null;
    const nextAgent = matchedAgent || persistedSelection || defaultFocusedAgent;
    if (!nextAgent || selectedAgent?.agent_id === nextAgent.agent_id) {
      return;
    }
    setSelectedAgent(nextAgent);
  }, [
    agents,
    defaultFocusedAgent,
    requestedAgentId,
    selectedAgent?.agent_id,
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

  const selectedGoal = useMemo(() => {
    if (!selectedGoalId) {
      return null;
    }
    return displayedGoals.find((goal) => goal.id === selectedGoalId) ?? null;
  }, [displayedGoals, selectedGoalId]);

  const handleTabChange = (nextTab: string) => {
    const nextParams = new URLSearchParams(searchParams);
    if (nextTab === "workbench") {
      nextParams.delete("tab");
    } else {
      nextParams.set("tab", nextTab);
    }
    if (selectedAgent?.agent_id) {
      nextParams.set("agent", selectedAgent.agent_id);
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
        navigate("/chat");
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
            <p className="baize-page-header-description">管理智能体职责、任务执行与成长轨迹。</p>
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
              <Tag color="blue">Spider Mesh 主脑</Tag>
              <Tag color={statusColor(executionCoreAgent.status)}>
                {getIndustryRuntimeStatusLabel(executionCoreAgent.status)}
              </Tag>
              {executionSeatAgents.length > 0 ? (
                <Tag>{`执行位 ${executionSeatAgents.length}`}</Tag>
              ) : null}
            </Space>
            <Paragraph style={{ marginBottom: 0 }}>
              Spider Mesh 主脑保留长期使命与派工权；下方面板聚焦当前所选执行位的
              assignment、report、escalation 与回主脑确认事项。
            </Paragraph>
            <div className={styles.agentSwitcherGrid}>
              <Card
                className={[
                  "baize-card",
                  styles.agentSwitcherCard,
                  displayedAgent?.agent_id === executionCoreAgent.agent_id
                    ? styles.agentSwitcherCardSelected
                    : "",
                ].filter(Boolean).join(" ")}
                hoverable
                size="small"
                onClick={() => handleSelectAgent(executionCoreAgent)}
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
                <Paragraph hidden type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>
                  {localizeWorkbenchText(
                    executionCoreAgent.role_summary ||
                      executionCoreAgent.current_goal ||
                      executionCoreAgent.mission,
                  ) || "负责拆解目标、分派执行位、回收证据并监督结果。"}
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
                        agent.current_goal ||
                          agent.role_summary ||
                          agent.environment_summary,
                      ) || "由 Spider Mesh 主脑统一分派任务。"}
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
            key: "workbench",
            label: (
              <span>
                <UserOutlined /> {agentWorkbenchText.tabWorkbench}
              </span>
            ),
            children: (
              <>
                {displayedAgent ? (
                  <ProfileCard
                    agent={displayedAgent}
                    linkedGoal={selectedGoal}
                    onOpenChat={() => {
                      void handleOpenChat(displayedAgent);
                    }}
                  />
                ) : null}
                {displayedAgent ? (
                  <V7ExecutionSeatPanel
                    agent={displayedAgent}
                    agents={agents}
                    agentDetail={agentDetail}
                    industryDetail={industryDetail}
                    industryDetailLoading={industryDetailLoading}
                    industryDetailError={industryDetailError}
                  />
                ) : null}
                {displayedAgent ? (
                  <CapabilityGovernancePanel
                    agent={displayedAgent}
                    detail={agentDetail}
                    capabilityCatalog={capabilityCatalog}
                    capabilityCatalogLoading={capabilityCatalogLoading}
                    capabilityActionKey={capabilityActionKey}
                    onRefresh={refreshAgentDetail}
                    onSubmitGovernedChange={submitGovernedCapabilityAssignment}
                    onResolveDecision={resolveCapabilityDecision}
                  />
                ) : null}
                <ActorRuntimePanel
                  detail={agentDetail}
                  actorActionKey={actorActionKey}
                  onPauseActor={pauseActorRuntime}
                  onResumeActor={resumeActorRuntime}
                  onRetryMailbox={retryActorMailboxRuntime}
                  onCancelActor={cancelActorRuntime}
                />
                <GoalSelector
                  goals={displayedGoals}
                  selectedGoalId={selectedGoalId}
                  onSelect={setSelectedGoalId}
                />
                <GoalDetailPanel
                  detail={goalDetail}
                  loading={goalLoading}
                  error={goalError}
                />
                <EvidencePanel evidence={displayedEvidence} agents={agents} />
              </>
            ),
          },
          {
            key: "workspace",
            label: (
              <span>
                <FolderOpenOutlined /> {workspaceText.tabTitle}
              </span>
            ),
            children: (
              <>
                <WorkspaceTab
                  agent={displayedAgent}
                  agentDetail={agentDetail}
                  loading={agentDetailLoading}
                  error={agentDetailError}
                />
              </>
            ),
          },
          {
            key: "daily",
            label: (
              <span>
                <CalendarOutlined /> {agentWorkbenchText.tabDaily}
              </span>
            ),
            children: (
              <AgentDailyReport
                agentId={displayedAgent?.agent_id ?? null}
                agentName={displayedAgent?.name ?? null}
              />
            ),
          },
          {
            key: "weekly",
            label: (
              <span>
                <BarChartOutlined /> {agentWorkbenchText.tabWeekly}
              </span>
            ),
            children: (
              <AgentWeeklyReport
                agentId={displayedAgent?.agent_id ?? null}
                agentName={displayedAgent?.name ?? null}
              />
            ),
          },
          {
            key: "growth",
            label: (
              <span>
                <RiseOutlined /> {agentWorkbenchText.tabGrowth}
              </span>
            ),
            children: <AgentGrowthTrajectory />,
          },
        ]}
      />
    </div>
  );
}
