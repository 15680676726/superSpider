import { Button, Card, Skeleton, Space, Tag } from "antd";

import type { StartupRecoverySummary } from "../../api";
import styles from "./index.module.less";
import {
  type RuntimeCardStatus,
  type RuntimeOverviewCard,
  type RuntimeOverviewEntry,
} from "./useRuntimeCenter";
import {
  formatCnTimestamp as formatTimestamp,
  formatPrimitiveValue as primitiveValue,
  formatRecoveryFieldLabel,
  formatRouteTitle as routeTitle,
  formatRuntimeActionLabel as formatActionLabel,
  formatRuntimeCardSummary as translateRuntimeCardSummary,
  formatRuntimeCardTitle as translateRuntimeCardTitle,
  formatRuntimeEntryKind as translateRuntimeEntryKind,
  formatRuntimeEntrySummary as translateRuntimeEntrySummary,
  formatRuntimeEntryTitle as translateRuntimeEntryTitle,
  formatRuntimeFieldLabel as translateRuntimeFieldLabel,
  formatRuntimeSectionLabel as translateRuntimeSectionLabel,
  formatRuntimeSourceList as translateRuntimeSourceList,
  formatRuntimeStatus as translateRuntimeStatus,
  formatRuntimeSurfaceNote as translateRuntimeSurfaceNote,
  localizeRuntimeText,
} from "./text";
import {
  DETAIL_SECTION_ORDER,
  findChainNode,
  findIndustryAgentRoute,
  isIndustryExecutionSummary,
  isIndustryInstanceDetailPayload,
  isIndustryMainChainGraph,
  isIndustryMainChainNode,
  isRecord,
  isTaskReviewRecord,
  metaNumberValue,
  metaRows,
  metaStringValue,
  objectRows,
  primaryTitle,
  stringListValue,
} from "./runtimeDetailPrimitives";
import {
  renderIndustryExecutionFocusSection,
  renderIndustryMainChainSection,
  renderReviewListCard,
  renderTaskReviewSection,
} from "./runtimeIndustrySections";
import {
  renderDetailDrawer,
  renderDetailSection,
  renderRecordCard,
  renderRuntimeDetailDrawer,
} from "./runtimeDetailDrawer";
import { runtimeStatusColor } from "../../runtime/tagSemantics";

function surfaceTagColor(status: RuntimeCardStatus) {
  switch (status) {
    case "state-service":
      return "success";
    case "degraded":
      return "warning";
    default:
      return "default";
  }
}

function cardStatusColor(status: RuntimeCardStatus) {
  switch (status) {
    case "state-service":
      return "processing";
    case "degraded":
      return "warning";
    default:
      return "default";
  }
}

function renderEntry(
  card: RuntimeOverviewCard,
  entry: RuntimeOverviewEntry,
  busyActionId: string | null,
  invokeAction: (
    cardKey: string,
    entryId: string,
    actionKey: string,
    actionPath: string,
  ) => void,
  openDetail: (route: string, title: string) => void,
  options?: {
    userFacing?: boolean;
  },
) {
  const localizedTitle = translateRuntimeEntryTitle(card.key, entry.title);
  const localizedSummary = translateRuntimeEntrySummary(card.key, entry.summary);
  const userFacing = options?.userFacing === true;
  const visibleMeta =
    card.key === "tasks"
      ? Object.fromEntries(
          Object.entries(entry.meta).filter(
            ([key]) => !["parent_task_id", "child_task_count"].includes(key),
          ),
        )
      : entry.meta;
  const parentTaskId =
    card.key === "tasks"
      ? metaStringValue(entry.meta, "parent_task_id")
      : null;
  const childTaskCount =
    card.key === "tasks"
      ? metaNumberValue(entry.meta, "child_task_count")
      : null;

  return (
    <div key={entry.id} className={styles.entry}>
      <div className={styles.entryTop}>
        <div className={styles.entryTitleBlock}>
          <div className={styles.entryTitleRow}>
            {entry.route ? (
              <button
                type="button"
                className={styles.entryTitleButton}
                onClick={() => {
                  void openDetail(entry.route!, localizedTitle);
                }}
              >
                {localizedTitle}
              </button>
            ) : (
              <h3 className={styles.entryTitle}>{localizedTitle}</h3>
            )}
            <Tag color={runtimeStatusColor(entry.status)}>
              {translateRuntimeStatus(entry.status)}
            </Tag>
            {!userFacing ? <Tag>{translateRuntimeEntryKind(entry.kind)}</Tag> : null}
            {!userFacing && childTaskCount && childTaskCount > 0 ? (
              <Tag color="purple">{`委派主任务 ${childTaskCount}`}</Tag>
            ) : null}
            {!userFacing && parentTaskId ? <Tag color="geekblue">委派子任务</Tag> : null}
          </div>
          <div className={styles.entryMetaLine}>
            {entry.owner ? <span>{localizeRuntimeText(entry.owner)}</span> : null}
            <span>{formatTimestamp(entry.updated_at)}</span>
          </div>
        </div>
      </div>

      {localizedSummary ? <p className={styles.entrySummary}>{localizedSummary}</p> : null}

      {!userFacing && metaRows(visibleMeta).length > 0 ? (
        <div className={styles.metaGrid}>
          {metaRows(visibleMeta).map(([label, value]) => (
            <div key={`${entry.id}:${label}`} className={styles.metaItem}>
              <span className={styles.metaLabel}>{label}</span>
              <span className={styles.metaValue}>{value}</span>
            </div>
          ))}
        </div>
      ) : null}

      <div className={styles.entryFooter}>
        {entry.route ? (
          <button
            type="button"
            className={styles.routeButton}
            onClick={() => {
              void openDetail(entry.route!, localizedTitle);
            }}
          >
            {userFacing ? "查看详情" : <code className={styles.route}>{entry.route}</code>}
          </button>
        ) : (
          <span />
        )}
        {Object.keys(entry.actions).length > 0 ? (
          <Space size={8} wrap>
            {Object.entries(entry.actions).map(([actionKey, actionPath]) => {
              const id = `${card.key}:${entry.id}:${actionKey}`;
              return (
                <Button
                  key={actionKey}
                  size="small"
                  type={
                    actionKey === "approve" || actionKey === "apply"
                      ? "primary"
                      : "default"
                  }
                  loading={busyActionId === id}
                  onClick={() => {
                    if (actionKey === "diagnosis") {
                      void openDetail(actionPath, routeTitle(actionPath));
                      return;
                    }
                    void invokeAction(card.key, entry.id, actionKey, actionPath);
                  }}
                >
                  {formatActionLabel(actionKey)}
                </Button>
              );
            })}
          </Space>
        ) : null}
      </div>
    </div>
  );
}

function summaryRows(
  summary: StartupRecoverySummary | null,
): Array<[string, string]> {
  if (!summary) {
    return [];
  }
  return Object.entries(summary)
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .map(([key, value]) => [formatRecoveryFieldLabel(key), primitiveValue(value)]);
}

function toggleSelection(
  current: string[],
  value: string,
  update: (next: string[]) => void,
) {
  if (current.includes(value)) {
    update(current.filter((item) => item !== value));
    return;
  }
  update([...current, value]);
}

function renderLoading() {
  return (
    <div className={styles.grid}>
      {Array.from({ length: 6 }).map((_, index) => (
        <Card key={index} className={styles.card}>
          <Skeleton active paragraph={{ rows: 4 }} />
        </Card>
      ))}
    </div>
  );
}

export {
  DETAIL_SECTION_ORDER,
  surfaceTagColor,
  cardStatusColor,
  formatActionLabel,
  translateRuntimeStatus,
  translateRuntimeEntryKind,
  translateRuntimeCardTitle,
  translateRuntimeCardSummary,
  translateRuntimeSourceList,
  translateRuntimeSurfaceNote,
  translateRuntimeEntryTitle,
  translateRuntimeEntrySummary,
  translateRuntimeSectionLabel,
  translateRuntimeFieldLabel,
  formatTimestamp,
  metaRows,
  isRecord,
  primitiveValue,
  metaStringValue,
  metaNumberValue,
  primaryTitle,
  routeTitle,
  objectRows,
  stringListValue,
  isTaskReviewRecord,
  isIndustryExecutionSummary,
  isIndustryMainChainNode,
  isIndustryMainChainGraph,
  isIndustryInstanceDetailPayload,
  findIndustryAgentRoute,
  findChainNode,
  renderIndustryExecutionFocusSection,
  renderIndustryMainChainSection,
  renderReviewListCard,
  renderTaskReviewSection,
  renderRecordCard,
  renderDetailSection,
  renderDetailDrawer,
  renderRuntimeDetailDrawer,
  renderEntry,
  summaryRows,
  toggleSelection,
  renderLoading,
};
