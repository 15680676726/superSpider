import { Button, Empty, List, Space, Tag, Tooltip, Typography } from "antd";
import { useMemo, type ReactNode } from "react";
import type {
  AgentCapabilityDecision,
  AgentCapabilitySurface,
  AgentCapabilitySurfaceItem,
} from "../pages/AgentWorkbench/useAgentWorkbench";
import {
  CAPABILITY_SURFACE_TEXT,
  formatCapabilityAssignmentSource,
  formatCapabilityMode,
  formatRiskLevel,
  formatRuntimeStatus,
} from "../pages/RuntimeCenter/text";
import {
  runtimeRiskColor,
  runtimeStatusColor,
} from "../runtime/tagSemantics";
import styles from "./RuntimeCapabilitySurfaceCard.module.less";

const { Paragraph, Text } = Typography;

const SYSTEM_DISPATCH_CAPABILITIES = new Set([
  "system:dispatch_query",
  "system:dispatch_command",
  "system:delegate_task",
]);

interface RuntimeCapabilitySurfaceCardProps {
  surface: AgentCapabilitySurface | null | undefined;
  className?: string;
  onOpenRoute?: (route: string, title: string) => void;
}

function formatCapabilityLabel(item: AgentCapabilitySurfaceItem): string {
  if (item.name && item.name !== item.id) {
    return item.id;
  }
  return item.id;
}

function formatAssignmentSourceList(values: string[]): string {
  return values.map((value) => formatCapabilityAssignmentSource(value)).join(" / ");
}

function uniqueStrings(lists: Array<string[] | undefined>): string[] {
  const seen = new Set<string>();
  const output: string[] = [];
  lists.forEach((list) => {
    (list || []).forEach((value) => {
      const normalized = value.trim();
      if (!normalized || seen.has(normalized)) {
        return;
      }
      seen.add(normalized);
      output.push(normalized);
    });
  });
  return output;
}

function isDispatchCapability(item: AgentCapabilitySurfaceItem): boolean {
  if (item.source_kind !== "system") {
    return false;
  }
  return (
    SYSTEM_DISPATCH_CAPABILITIES.has(item.id) || item.id.startsWith("system:dispatch_")
  );
}

function isGovernanceCapability(item: AgentCapabilitySurfaceItem): boolean {
  return item.source_kind === "system" && !isDispatchCapability(item);
}

function CapabilityTagGroup({
  title,
  items,
  emptyText,
}: {
  title: string;
  items: AgentCapabilitySurfaceItem[];
  emptyText: string;
}) {
  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader}>
        <Text strong className={styles.panelTitle}>
          {title}
        </Text>
        <Tag>{items.length}</Tag>
      </div>
      {items.length === 0 ? (
        <Text type="secondary" className={styles.emptyText}>
          {emptyText}
        </Text>
      ) : (
        <div className={styles.chips}>
          {items.map((item) => (
            <Tooltip
              key={item.id}
              title={
                item.summary
                  ? `${item.summary}${
                      item.assignment_sources.length > 0
                        ? `\n${formatAssignmentSourceList(item.assignment_sources)}`
                        : ""
                    }`
                  : formatAssignmentSourceList(item.assignment_sources)
              }
            >
              <Tag color={runtimeRiskColor(item.risk_level)} className={styles.capabilityTag}>
                {formatCapabilityLabel(item)}
              </Tag>
            </Tooltip>
          ))}
        </div>
      )}
    </div>
  );
}

function StringTagGroup({
  title,
  values,
  emptyText,
  color,
}: {
  title: string;
  values: string[];
  emptyText: string;
  color?: string;
}) {
  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader}>
        <Text strong className={styles.panelTitle}>
          {title}
        </Text>
        <Tag>{values.length}</Tag>
      </div>
      {values.length === 0 ? (
        <Text type="secondary" className={styles.emptyText}>
          {emptyText}
        </Text>
      ) : (
        <div className={styles.chips}>
          {values.map((value) => (
            <Tag key={value} color={color} className={styles.capabilityTag}>
              {value}
            </Tag>
          ))}
        </div>
      )}
    </div>
  );
}

function DecisionList({
  decisions,
  onOpenRoute,
}: {
  decisions: AgentCapabilityDecision[];
  onOpenRoute?: (route: string, title: string) => void;
}) {
  return (
    <List
      dataSource={decisions}
      locale={{
        emptyText: CAPABILITY_SURFACE_TEXT.noCapabilityGovernance,
      }}
      renderItem={(decision) => {
        const actions: ReactNode[] = [];
        if (decision.route && onOpenRoute) {
          actions.push(
            <Button
              key={`decision:${decision.id}`}
              size="small"
              onClick={() => {
                onOpenRoute(decision.route!, CAPABILITY_SURFACE_TEXT.capabilityDecisionTitle);
              }}
            >
              {CAPABILITY_SURFACE_TEXT.openCapabilityDecision}
            </Button>,
          );
        }
        if (decision.task_route && onOpenRoute) {
          actions.push(
            <Button
              key={`task:${decision.id}`}
              size="small"
              onClick={() => {
                onOpenRoute(
                  decision.task_route!,
                  CAPABILITY_SURFACE_TEXT.capabilityDecisionTaskTitle,
                );
              }}
            >
              {CAPABILITY_SURFACE_TEXT.openCapabilityTask}
            </Button>,
          );
        }
        return (
          <List.Item key={decision.id} actions={actions}>
            <div className={styles.decisionItem}>
              <Space wrap>
                <Text strong>{decision.summary || decision.id}</Text>
                {decision.status ? (
                  <Tag color={runtimeStatusColor(decision.status)}>
                    {formatRuntimeStatus(decision.status)}
                  </Tag>
                ) : null}
                {decision.risk_level ? (
                  <Tag color={runtimeRiskColor(decision.risk_level)}>
                    {formatRiskLevel(decision.risk_level)}
                  </Tag>
                ) : null}
                <Tag>
                  {formatCapabilityMode(decision.capability_assignment_mode || "replace")}
                </Tag>
              </Space>
              {decision.capabilities.length > 0 ? (
                <div className={styles.chips}>
                  {decision.capabilities.map((capability) => (
                    <Tag key={`${decision.id}:${capability}`} className={styles.capabilityTag}>
                      {capability}
                    </Tag>
                  ))}
                </div>
              ) : null}
              <div className={styles.decisionMeta}>
                {decision.actor ? <span>{decision.actor}</span> : null}
                {decision.created_at ? <span>{decision.created_at}</span> : null}
                {decision.expires_at ? (
                  <span>
                    {CAPABILITY_SURFACE_TEXT.capabilityDecisionExpires(decision.expires_at)}
                  </span>
                ) : null}
              </div>
              {decision.reason ? (
                <Paragraph className={styles.decisionReason}>{decision.reason}</Paragraph>
              ) : null}
            </div>
          </List.Item>
        );
      }}
    />
  );
}

export function isRuntimeCapabilitySurface(value: unknown): value is AgentCapabilitySurface {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }
  const record = value as Record<string, unknown>;
  return (
    typeof record.agent_id === "string" &&
    Array.isArray(record.items) &&
    Array.isArray(record.effective_capabilities) &&
    Array.isArray(record.recommended_capabilities)
  );
}

export default function RuntimeCapabilitySurfaceCard({
  surface,
  className,
  onOpenRoute,
}: RuntimeCapabilitySurfaceCardProps) {
  const effectiveItems = useMemo(
    () => surface?.items.filter((item) => item.assignment_sources.includes("effective")) ?? [],
    [surface],
  );
  const dispatchItems = useMemo(
    () => effectiveItems.filter((item) => isDispatchCapability(item)),
    [effectiveItems],
  );
  const governanceItems = useMemo(
    () => effectiveItems.filter((item) => isGovernanceCapability(item)),
    [effectiveItems],
  );
  const toolItems = useMemo(
    () => effectiveItems.filter((item) => item.source_kind === "tool"),
    [effectiveItems],
  );
  const skillItems = useMemo(
    () => effectiveItems.filter((item) => item.source_kind === "skill"),
    [effectiveItems],
  );
  const mcpItems = useMemo(
    () => effectiveItems.filter((item) => item.source_kind === "mcp"),
    [effectiveItems],
  );
  const otherItems = useMemo(
    () =>
      effectiveItems.filter(
        (item) =>
          item.source_kind !== "tool" &&
          item.source_kind !== "skill" &&
          item.source_kind !== "mcp" &&
          item.source_kind !== "system",
      ),
    [effectiveItems],
  );
  const environmentRequirements = useMemo(
    () => uniqueStrings(effectiveItems.map((item) => item.environment_requirements)),
    [effectiveItems],
  );
  const evidenceContract = useMemo(
    () => uniqueStrings(effectiveItems.map((item) => item.evidence_contract)),
    [effectiveItems],
  );
  const riskMix = useMemo(() => {
    const counts = { auto: 0, guarded: 0, confirm: 0 };
    effectiveItems.forEach((item) => {
      if (item.risk_level === "confirm") {
        counts.confirm += 1;
        return;
      }
      if (item.risk_level === "guarded") {
        counts.guarded += 1;
        return;
      }
      counts.auto += 1;
    });
    return counts;
  }, [effectiveItems]);
  const recommendedMissing = useMemo(() => {
    const effective = new Set(surface?.effective_capabilities || []);
    return (surface?.recommended_capabilities || []).filter((item) => !effective.has(item));
  }, [surface]);
  const explicitAdditions = useMemo(() => {
    const recommended = new Set(surface?.recommended_capabilities || []);
    return (surface?.explicit_capabilities || []).filter((item) => !recommended.has(item));
  }, [surface]);
  const visibleDecisions = useMemo(
    () =>
      surface?.pending_decisions.length
        ? surface.pending_decisions
        : (surface?.recent_decisions || []).slice(0, 5),
    [surface],
  );

  if (!surface) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={CAPABILITY_SURFACE_TEXT.capabilitySurfaceUnavailable}
      />
    );
  }

  return (
    <div className={[styles.surface, className].filter(Boolean).join(" ")}>
      <div className={styles.hero}>
        <Text className={styles.eyebrow}>
          {CAPABILITY_SURFACE_TEXT.capabilitySurfaceEyebrow}
        </Text>
        <Space wrap className={styles.heroTags}>
          <Tag color="gold">
            {CAPABILITY_SURFACE_TEXT.capabilityModeTag(surface.default_mode)}
          </Tag>
          <Tag color={surface.actor_present ? "green" : "default"}>
            {surface.actor_present
              ? CAPABILITY_SURFACE_TEXT.capabilityActorMounted
              : CAPABILITY_SURFACE_TEXT.capabilityProfileOnly}
          </Tag>
          <Tag
            color={
              surface.effective_capabilities.includes("system:apply_role")
                ? "blue"
                : "default"
            }
          >
            {surface.effective_capabilities.includes("system:apply_role")
              ? CAPABILITY_SURFACE_TEXT.capabilityApplyRoleMounted
              : CAPABILITY_SURFACE_TEXT.capabilityApplyRoleMissing}
          </Tag>
          <Tag color={surface.drift_detected ? "orange" : "green"}>
            {surface.drift_detected
              ? CAPABILITY_SURFACE_TEXT.capabilityDriftDetected
              : CAPABILITY_SURFACE_TEXT.capabilityAligned}
          </Tag>
          {surface.routes.actor_governed_assign || surface.routes.governed_assign ? (
            <Tag color="cyan">
              {CAPABILITY_SURFACE_TEXT.capabilityGovernedWritePath}
            </Tag>
          ) : null}
          {surface.routes.actor_direct_assign || surface.routes.direct_assign ? (
            <Tag color="purple">
              {CAPABILITY_SURFACE_TEXT.capabilityDirectWritePath}
            </Tag>
          ) : null}
        </Space>
        <Paragraph type="secondary" className={styles.heroSummary}>
          {CAPABILITY_SURFACE_TEXT.capabilitySurfaceSummary}
        </Paragraph>
      </div>

      <div className={styles.metricGrid}>
        <div className={styles.metricCard}>
          <div className={styles.metricLabel}>
            {CAPABILITY_SURFACE_TEXT.capabilityEffectiveCount}
          </div>
          <div className={styles.metricValue}>{surface.stats.effective_count}</div>
        </div>
        <div className={styles.metricCard}>
          <div className={styles.metricLabel}>
            {CAPABILITY_SURFACE_TEXT.capabilityDispatchCount}
          </div>
          <div className={styles.metricValue}>{dispatchItems.length}</div>
        </div>
        <div className={styles.metricCard}>
          <div className={styles.metricLabel}>
            {CAPABILITY_SURFACE_TEXT.capabilityGovernanceCount}
          </div>
          <div className={styles.metricValue}>{governanceItems.length}</div>
        </div>
        <div className={styles.metricCard}>
          <div className={styles.metricLabel}>
            {CAPABILITY_SURFACE_TEXT.capabilityPendingDecisionCount}
          </div>
          <div className={styles.metricValue}>{surface.stats.pending_decision_count}</div>
        </div>
      </div>

      <div className={styles.section}>
        <Text strong className={styles.sectionTitle}>
          {CAPABILITY_SURFACE_TEXT.capabilityRightsTitle}
        </Text>
        <div className={styles.grid}>
          <CapabilityTagGroup
            title={CAPABILITY_SURFACE_TEXT.capabilityDispatchTitle}
            items={dispatchItems}
            emptyText={CAPABILITY_SURFACE_TEXT.noDispatchCapabilities}
          />
          <CapabilityTagGroup
            title={CAPABILITY_SURFACE_TEXT.capabilityGovernanceTitle}
            items={governanceItems}
            emptyText={CAPABILITY_SURFACE_TEXT.noGovernanceCapabilities}
          />
        </div>
      </div>

      <div className={styles.section}>
        <Text strong className={styles.sectionTitle}>
          {CAPABILITY_SURFACE_TEXT.capabilityCompositionTitle}
        </Text>
        <div className={styles.grid}>
          <CapabilityTagGroup
            title={CAPABILITY_SURFACE_TEXT.capabilityToolsTitle}
            items={toolItems}
            emptyText={CAPABILITY_SURFACE_TEXT.noToolCapabilities}
          />
          <CapabilityTagGroup
            title={CAPABILITY_SURFACE_TEXT.capabilitySkillsTitle}
            items={skillItems}
            emptyText={CAPABILITY_SURFACE_TEXT.noSkillCapabilities}
          />
          <CapabilityTagGroup
            title={CAPABILITY_SURFACE_TEXT.capabilityMcpTitle}
            items={mcpItems}
            emptyText={CAPABILITY_SURFACE_TEXT.noMcpCapabilities}
          />
          <CapabilityTagGroup
            title={CAPABILITY_SURFACE_TEXT.capabilityOtherTitle}
            items={otherItems}
            emptyText={CAPABILITY_SURFACE_TEXT.noOtherCapabilities}
          />
        </div>
      </div>

      <div className={styles.section}>
        <Text strong className={styles.sectionTitle}>
          {CAPABILITY_SURFACE_TEXT.capabilityDriftTitle}
        </Text>
        <div className={styles.grid}>
          <StringTagGroup
            title={CAPABILITY_SURFACE_TEXT.capabilityRecommendedMissingTitle}
            values={recommendedMissing}
            emptyText={CAPABILITY_SURFACE_TEXT.capabilityRecommendedMissingEmpty}
            color="orange"
          />
          <StringTagGroup
            title={CAPABILITY_SURFACE_TEXT.capabilityExplicitAdditionTitle}
            values={explicitAdditions}
            emptyText={CAPABILITY_SURFACE_TEXT.capabilityExplicitAdditionEmpty}
            color="blue"
          />
        </div>
      </div>

      <div className={styles.section}>
        <Text strong className={styles.sectionTitle}>
          {CAPABILITY_SURFACE_TEXT.capabilityRuntimeContractTitle}
        </Text>
        <div className={styles.grid}>
          <StringTagGroup
            title={CAPABILITY_SURFACE_TEXT.capabilityEnvironmentTitle}
            values={environmentRequirements}
            emptyText={CAPABILITY_SURFACE_TEXT.capabilityEnvironmentEmpty}
            color="cyan"
          />
          <StringTagGroup
            title={CAPABILITY_SURFACE_TEXT.capabilityEvidenceTitle}
            values={evidenceContract}
            emptyText={CAPABILITY_SURFACE_TEXT.capabilityEvidenceEmpty}
            color="green"
          />
        </div>
      </div>

      <div className={styles.section}>
        <Text strong className={styles.sectionTitle}>
          {CAPABILITY_SURFACE_TEXT.capabilityRiskMixTitle}
        </Text>
        <div className={styles.chips}>
          <Tag color="green">
            {CAPABILITY_SURFACE_TEXT.capabilityRiskAuto(riskMix.auto)}
          </Tag>
          <Tag color="orange">
            {CAPABILITY_SURFACE_TEXT.capabilityRiskGuarded(riskMix.guarded)}
          </Tag>
          <Tag color="red">
            {CAPABILITY_SURFACE_TEXT.capabilityRiskConfirm(riskMix.confirm)}
          </Tag>
        </div>
      </div>

      <div className={styles.section}>
        <Text strong className={styles.sectionTitle}>
          {CAPABILITY_SURFACE_TEXT.capabilityDecisionQueueTitle}
        </Text>
        <div className={styles.panel}>
          <DecisionList decisions={visibleDecisions} onOpenRoute={onOpenRoute} />
        </div>
      </div>
    </div>
  );
}
