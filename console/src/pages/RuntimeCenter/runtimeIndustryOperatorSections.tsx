import { Button, Card, Empty, Space, Tag, Typography } from "antd";

import {
  analysisStatusColor,
  formatAnalysisMode,
  formatAnalysisStatus,
  formatAnalysisWritebackStatus,
  formatMediaType,
  mediaTypeColor,
  resolveMediaTitle,
} from "../../utils/mediaPresentation";
import {
  runtimeRiskColor,
  runtimeStatusColor,
} from "../../runtime/tagSemantics";
import styles from "./index.module.less";
import {
  formatPrimitiveValue,
  formatRuntimeSectionLabel as translateRuntimeSectionLabel,
  formatRuntimeStatus as translateRuntimeStatus,
  localizeRuntimeText,
} from "./text";
import { isRecord } from "./runtimeDetailPrimitives";

const { Text } = Typography;

function focusedSelectionId(
  focusSelection: Record<string, unknown> | null | undefined,
  kind: string,
  idKey: string,
): string | null {
  if (!focusSelection) {
    return null;
  }
  const selectionKind = typeof focusSelection.selection_kind === "string" ? focusSelection.selection_kind : null;
  if (selectionKind !== kind) {
    return null;
  }
  const value = focusSelection[idKey];
  return typeof value === "string" && value ? value : null;
}

function renderAssignmentSummaryTags(assignments: Record<string, unknown>[]) {
  const activeCount = assignments.filter(
    (assignment) => typeof assignment.status === "string" && assignment.status === "active",
  ).length;
  const readyCount = assignments.filter(
    (assignment) => typeof assignment.status === "string" && assignment.status === "ready",
  ).length;
  const completedCount = assignments.filter(
    (assignment) => typeof assignment.status === "string" && assignment.status === "completed",
  ).length;
  const evidenceCounts = assignments.map((assignment) =>
    Array.isArray(assignment.evidence_ids) ? assignment.evidence_ids.length : 0,
  );
  const maxEvidence = evidenceCounts.length > 0 ? Math.max(...evidenceCounts) : 0;

  return (
    <Space wrap size={[6, 6]} style={{ marginTop: 8 }}>
      {activeCount > 0 ? <Tag color="blue">{`进行中 ${activeCount}`}</Tag> : null}
      {readyCount > 0 ? <Tag>{`就绪 ${readyCount}`}</Tag> : null}
      {completedCount > 0 ? <Tag color="success">{`已完成 ${completedCount}`}</Tag> : null}
      {maxEvidence > 0 ? <Tag>{`最大证据 ${maxEvidence}`}</Tag> : null}
    </Space>
  );
}

export function renderOperatorBacklogSection(
  sectionKey: string,
  sectionValue: unknown,
  openRoute: (route: string, title: string) => void,
  focusSelection?: Record<string, unknown> | null,
) {
  if (!Array.isArray(sectionValue)) {
    return null;
  }
  const backlogItems = sectionValue.filter(isRecord);
  const focusedBacklogId = focusedSelectionId(focusSelection, "backlog", "backlog_item_id");
  const openCount = backlogItems.filter(
    (item) => typeof item.status === "string" && item.status === "open",
  ).length;
  const queuedCount = backlogItems.filter(
    (item) => typeof item.status === "string" && item.status === "queued",
  ).length;

  return (
    <section key={sectionKey} className={styles.detailSection}>
      <div className={styles.detailSectionTitle}>
        {translateRuntimeSectionLabel(sectionKey)} <Tag>{sectionValue.length}</Tag>
      </div>

      {backlogItems.length > 0 ? (
        <Space wrap size={[6, 6]} style={{ marginTop: 8 }}>
          {openCount > 0 ? <Tag color="blue">{`开放 ${openCount}`}</Tag> : null}
          {queuedCount > 0 ? <Tag>{`排队 ${queuedCount}`}</Tag> : null}
        </Space>
      ) : null}

      {sectionValue.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无内容" />
      ) : (
        <div className={styles.detailArray}>
          {sectionValue.map((item, index) => {
            if (!isRecord(item)) {
              return (
                <pre key={`${sectionKey}:${index}`} className={styles.detailPre}>
                  {formatPrimitiveValue(item)}
                </pre>
              );
            }
            const backlogId =
              typeof item.backlog_item_id === "string" && item.backlog_item_id
                ? item.backlog_item_id
                : null;
            const title =
              (typeof item.title === "string" && item.title) ||
              (typeof item.summary === "string" && item.summary) ||
              backlogId ||
              `待办 ${index + 1}`;
            const summary = typeof item.summary === "string" ? item.summary : null;
            const status = typeof item.status === "string" && item.status ? item.status : "unknown";
            const sourceKind =
              typeof item.source_kind === "string" && item.source_kind ? item.source_kind : null;
            const route = typeof item.route === "string" && item.route ? item.route : null;
            const selected =
              item.selected === true || (backlogId && backlogId === focusedBacklogId);
            const laneId = typeof item.lane_id === "string" && item.lane_id ? item.lane_id : null;
            const cycleId =
              typeof item.cycle_id === "string" && item.cycle_id ? item.cycle_id : null;
            const assignmentId =
              typeof item.assignment_id === "string" && item.assignment_id
                ? item.assignment_id
                : null;
            const evidenceCount = Array.isArray(item.evidence_ids) ? item.evidence_ids.length : 0;
            return (
              <Card
                key={backlogId || `${sectionKey}:${index}`}
                size="small"
                style={
                  selected
                    ? {
                        border: "1px solid rgba(22, 119, 255, 0.35)",
                        boxShadow: "0 0 0 1px rgba(22, 119, 255, 0.08)",
                      }
                    : undefined
                }
              >
                <Space wrap size={[6, 6]} style={{ marginBottom: summary ? 6 : 0 }}>
                  <Text strong>{title}</Text>
                  <Tag color={runtimeStatusColor(status)}>{translateRuntimeStatus(status)}</Tag>
                  {selected ? <Tag color="blue">已聚焦</Tag> : null}
                  {sourceKind ? <Tag>{sourceKind}</Tag> : null}
                  {evidenceCount > 0 ? <Tag>{`证据 ${evidenceCount}`}</Tag> : null}
                </Space>
                {summary ? <Text type="secondary">{summary}</Text> : null}
                <Space wrap size={[8, 6]} className={styles.selectionMeta}>
                  {laneId ? <span>{`泳道 ${laneId}`}</span> : null}
                  {cycleId ? <span>{`周期 ${cycleId}`}</span> : null}
                  {assignmentId ? <span>{`派单 ${assignmentId}`}</span> : null}
                </Space>
                {route ? (
                  <div className={styles.routeActions}>
                    <Button
                      size="small"
                      onClick={() => {
                        openRoute(route, title);
                      }}
                    >
                      打开待办
                    </Button>
                  </div>
                ) : null}
              </Card>
            );
          })}
        </div>
      )}
    </section>
  );
}

export function renderOperatorAssignmentsSection(
  sectionKey: string,
  sectionValue: unknown,
  openRoute: (route: string, title: string) => void,
  focusSelection?: Record<string, unknown> | null,
) {
  if (!Array.isArray(sectionValue)) {
    return null;
  }
  const assignments = sectionValue.filter(isRecord);
  const focusedAssignmentId = focusedSelectionId(focusSelection, "assignment", "assignment_id");

  return (
    <section key={sectionKey} className={styles.detailSection}>
      <div className={styles.detailSectionTitle}>
        {translateRuntimeSectionLabel(sectionKey)} <Tag>{sectionValue.length}</Tag>
      </div>

      {assignments.length > 0 ? renderAssignmentSummaryTags(assignments) : null}

      {sectionValue.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无内容" />
      ) : (
        <div className={styles.detailArray}>
          {sectionValue.map((item, index) => {
            if (!isRecord(item)) {
              return (
                <pre key={`${sectionKey}:${index}`} className={styles.detailPre}>
                  {formatPrimitiveValue(item)}
                </pre>
              );
            }

            const assignmentId =
              typeof item.assignment_id === "string" && item.assignment_id ? item.assignment_id : null;
            const title =
              (typeof item.title === "string" && item.title) ||
              (typeof item.summary === "string" && item.summary) ||
              assignmentId ||
              `派工 ${index + 1}`;
            const summary = typeof item.summary === "string" ? item.summary : null;
            const status = typeof item.status === "string" && item.status ? item.status : "unknown";
            const route = typeof item.route === "string" && item.route ? item.route : null;
            const focused =
              item.selected === true || (assignmentId && assignmentId === focusedAssignmentId);
            const ownerAgentId =
              typeof item.owner_agent_id === "string" && item.owner_agent_id
                ? item.owner_agent_id
                : null;
            const laneId =
              typeof item.lane_id === "string" && item.lane_id ? item.lane_id : null;
            const cycleId =
              typeof item.cycle_id === "string" && item.cycle_id ? item.cycle_id : null;
            const evidenceCount = Array.isArray(item.evidence_ids) ? item.evidence_ids.length : 0;
            const lastReportId =
              typeof item.last_report_id === "string" && item.last_report_id
                ? item.last_report_id
                : null;

            return (
              <Card
                key={assignmentId || `${sectionKey}:${index}`}
                size="small"
                style={
                  focused
                    ? {
                        border: "1px solid rgba(22, 119, 255, 0.35)",
                        boxShadow: "0 0 0 1px rgba(22, 119, 255, 0.08)",
                      }
                    : undefined
                }
              >
                <Space wrap size={[6, 6]} style={{ marginBottom: summary ? 6 : 0 }}>
                  <Text strong>{title}</Text>
                  <Tag color={runtimeStatusColor(status)}>{translateRuntimeStatus(status)}</Tag>
                  {focused ? <Tag color="blue">已聚焦</Tag> : null}
                  {evidenceCount > 0 ? <Tag>{`证据 ${evidenceCount}`}</Tag> : null}
                </Space>
                {summary ? <Text type="secondary">{summary}</Text> : null}
                <Space wrap size={[8, 6]} className={styles.selectionMeta}>
                  {ownerAgentId ? <span>{`负责人 ${ownerAgentId}`}</span> : null}
                  {laneId ? <span>{`泳道 ${laneId}`}</span> : null}
                  {cycleId ? <span>{`周期 ${cycleId}`}</span> : null}
                  {lastReportId ? <span>{`最新汇报 ${lastReportId}`}</span> : null}
                </Space>
                {route ? (
                  <div className={styles.routeActions}>
                    <Button
                      size="small"
                      onClick={() => {
                        openRoute(route, title);
                      }}
                    >
                      打开派工
                    </Button>
                  </div>
                ) : null}
              </Card>
            );
          })}
        </div>
      )}
    </section>
  );
}

export function renderOperatorAgentReportsSection(
  sectionKey: string,
  sectionValue: unknown,
  openRoute: (route: string, title: string) => void,
  focusSelection?: Record<string, unknown> | null,
) {
  if (!Array.isArray(sectionValue)) {
    return null;
  }

  const reports = sectionValue.filter(isRecord);
  const focusedReportId = focusedSelectionId(focusSelection, "agent_report", "report_id");
  const unconsumedCount = reports.filter((report) => report.processed !== true).length;
  const followupCount = reports.filter((report) => report.needs_followup === true).length;

  return (
    <section key={sectionKey} className={styles.detailSection}>
      <div className={styles.detailSectionTitle}>
        {translateRuntimeSectionLabel(sectionKey)} <Tag>{sectionValue.length}</Tag>
      </div>

      {reports.length > 0 ? (
        <Space wrap size={[6, 6]} style={{ marginTop: 8 }}>
          {unconsumedCount > 0 ? <Tag color="warning">{`未消费 ${unconsumedCount}`}</Tag> : <Tag color="success">已全部消费</Tag>}
          {followupCount > 0 ? <Tag color="warning">{`跟进 ${followupCount}`}</Tag> : null}
        </Space>
      ) : null}

      {sectionValue.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无内容" />
      ) : (
        <div className={styles.detailArray}>
          {sectionValue.map((item, index) => {
            if (!isRecord(item)) {
              return (
                <pre key={`${sectionKey}:${index}`} className={styles.detailPre}>
                  {formatPrimitiveValue(item)}
                </pre>
              );
            }

            const reportId =
              typeof item.report_id === "string" && item.report_id ? item.report_id : null;
            const headline =
              (typeof item.headline === "string" && item.headline) ||
              (typeof item.summary === "string" && item.summary) ||
              reportId ||
              `Report ${index + 1}`;
            const summary = typeof item.summary === "string" ? item.summary : null;
            const status = typeof item.status === "string" && item.status ? item.status : "unknown";
            const processed = item.processed === true;
            const needsFollowup = item.needs_followup === true;
            const route = typeof item.route === "string" && item.route ? item.route : null;
            const focused =
              item.selected === true || (reportId && reportId === focusedReportId);
            const reportKind =
              typeof item.report_kind === "string" && item.report_kind ? item.report_kind : null;
            const riskLevel =
              typeof item.risk_level === "string" && item.risk_level ? item.risk_level : null;
            const ownerAgentId =
              typeof item.owner_agent_id === "string" && item.owner_agent_id
                ? item.owner_agent_id
                : null;
            const laneId = typeof item.lane_id === "string" && item.lane_id ? item.lane_id : null;
            const assignmentId =
              typeof item.assignment_id === "string" && item.assignment_id ? item.assignment_id : null;
            const evidenceCount = Array.isArray(item.evidence_ids) ? item.evidence_ids.length : 0;

            return (
              <Card
                key={reportId || `${sectionKey}:${index}`}
                size="small"
                style={
                  focused
                    ? {
                        border: "1px solid rgba(22, 119, 255, 0.35)",
                        boxShadow: "0 0 0 1px rgba(22, 119, 255, 0.08)",
                      }
                    : undefined
                }
              >
                <Space wrap size={[6, 6]} style={{ marginBottom: summary ? 6 : 0 }}>
                  <Text strong>{headline}</Text>
                  <Tag color={runtimeStatusColor(status)}>{translateRuntimeStatus(status)}</Tag>
                  {focused ? <Tag color="blue">已聚焦</Tag> : null}
                  {processed ? <Tag color="success">已处理</Tag> : <Tag color="warning">未处理</Tag>}
                  {needsFollowup ? <Tag color="warning">待跟进</Tag> : null}
                  {evidenceCount > 0 ? <Tag>{`证据 ${evidenceCount}`}</Tag> : null}
                  {riskLevel ? <Tag color={runtimeRiskColor(riskLevel)}>{riskLevel}</Tag> : null}
                  {reportKind ? <Tag>{reportKind}</Tag> : null}
                </Space>
                {summary ? <Text type="secondary">{summary}</Text> : null}
                <Space wrap size={[8, 6]} className={styles.selectionMeta}>
                  {ownerAgentId ? <span>{`负责人 ${ownerAgentId}`}</span> : null}
                  {laneId ? <span>{`泳道 ${laneId}`}</span> : null}
                  {assignmentId ? <span>{`派工 ${assignmentId}`}</span> : null}
                </Space>
                {route ? (
                  <div className={styles.routeActions}>
                    <Button
                      size="small"
                      onClick={() => {
                        openRoute(route, headline);
                      }}
                    >
                      打开汇报
                    </Button>
                  </div>
                ) : null}
              </Card>
            );
          })}
        </div>
      )}
    </section>
  );
}

export function renderOperatorMediaAnalysesSection(
  sectionKey: string,
  sectionValue: unknown,
  openRoute: (route: string, title: string) => void,
) {
  if (!Array.isArray(sectionValue)) {
    return null;
  }

  const analyses = sectionValue.filter(isRecord);
  return (
    <section key={sectionKey} className={styles.detailSection}>
      <div className={styles.detailSectionTitle}>
        媒体分析 <Tag>{sectionValue.length}</Tag>
      </div>

      {sectionValue.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无内容" />
      ) : (
        <div className={styles.detailArray}>
          {analyses.map((analysis, index) => {
            const analysisId =
              typeof analysis.analysis_id === "string" && analysis.analysis_id
                ? analysis.analysis_id
                : `analysis-${index + 1}`;
            const title = localizeRuntimeText(resolveMediaTitle(analysis));
            const summary =
              (typeof analysis.summary === "string" && analysis.summary) ||
              (Array.isArray(analysis.key_points)
                ? analysis.key_points
                    .filter((item) => typeof item === "string" && item.trim())
                    .slice(0, 3)
                    .join(" / ")
                : "") ||
              "暂无摘要";
            const mediaType =
              typeof analysis.detected_media_type === "string" && analysis.detected_media_type
                ? analysis.detected_media_type
                : "unknown";
            const status =
              typeof analysis.status === "string" && analysis.status ? analysis.status : "unknown";
            const analysisMode =
              typeof analysis.analysis_mode === "string" && analysis.analysis_mode
                ? analysis.analysis_mode
                : "standard";
            const workContextId =
              typeof analysis.work_context_id === "string" && analysis.work_context_id
                ? analysis.work_context_id
                : null;
            const route = `/api/media/analyses/${analysisId}`;
            return (
              <Card key={analysisId} size="small">
                <Space wrap size={[6, 6]} style={{ marginBottom: 6 }}>
                  <Text strong>{title}</Text>
                  <Tag color={mediaTypeColor(mediaType)}>{formatMediaType(mediaType)}</Tag>
                  <Tag>{formatAnalysisMode(analysisMode)}</Tag>
                  <Tag color={analysisStatusColor(status)}>{formatAnalysisStatus(status)}</Tag>
                  {typeof analysis.strategy_writeback_status === "string" &&
                  analysis.strategy_writeback_status ? (
                    <Tag>{`策略 ${formatAnalysisWritebackStatus(analysis.strategy_writeback_status)}`}</Tag>
                  ) : null}
                  {typeof analysis.backlog_writeback_status === "string" &&
                  analysis.backlog_writeback_status ? (
                    <Tag>{`待办 ${formatAnalysisWritebackStatus(analysis.backlog_writeback_status)}`}</Tag>
                  ) : null}
                </Space>
                <Text type="secondary">{summary}</Text>
                <Space wrap size={[8, 6]} className={styles.selectionMeta}>
                  {workContextId ? <span>{`工作上下文 ${workContextId}`}</span> : null}
                  {typeof analysis.thread_id === "string" && analysis.thread_id ? (
                    <span>{`线程 ${analysis.thread_id}`}</span>
                  ) : null}
                </Space>
                <div className={styles.routeActions}>
                  <Button
                    size="small"
                    onClick={() => {
                      openRoute(route, title);
                    }}
                  >
                    打开分析
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </section>
  );
}
