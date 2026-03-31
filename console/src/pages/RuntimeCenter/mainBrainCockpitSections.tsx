import { Button, Descriptions, Tag, Typography } from "antd";

import styles from "./index.module.less";
import {
  RUNTIME_CENTER_TEXT,
  formatRuntimeStatus,
  localizeRuntimeText,
} from "./text";
import { isRecord } from "./runtimeDetailPrimitives";

const { Text } = Typography;

function firstString(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
    if (typeof value === "number" && Number.isFinite(value)) {
      return String(value);
    }
    if (isRecord(value)) {
      const nested = firstString(
        value.title,
        value.name,
        value.label,
        value.summary,
        value.value,
        value.status,
        value.count,
        value.total,
      );
      if (nested) {
        return nested;
      }
    }
  }
  return null;
}

function toneFromStatus(value: unknown): "default" | "warning" | "error" | "success" {
  if (typeof value !== "string") {
    return "default";
  }
  const normalized = value.trim().toLowerCase();
  if (
    ["state-service", "success", "ready", "active", "clear", "proceed", "ok"].some(
      (token) => normalized.includes(token),
    )
  ) {
    return "success";
  }
  if (
    ["degraded", "warning", "caution", "pending"].some((token) =>
      normalized.includes(token),
    )
  ) {
    return "warning";
  }
  if (
    ["blocked", "error", "danger", "retry"].some((token) =>
      normalized.includes(token),
    )
  ) {
    return "error";
  }
  return "default";
}

function statusTagColor(value: unknown): "default" | "warning" | "error" | "success" {
  return toneFromStatus(value);
}

function recordTitle(record: Record<string, unknown>, fallback: string): string {
  const value =
    firstString(
      record.title,
      record.headline,
      record.label,
      record.name,
      record.id,
      record.assignment_id,
      record.report_id,
    ) ?? fallback;
  return localizeRuntimeText(value);
}

function recordSummary(record: Record<string, unknown>): string | null {
  const value = firstString(
    record.summary,
    record.description,
    record.reason,
    record.note,
    record.recommendation,
  );
  return value ? localizeRuntimeText(value) : null;
}

export function recordList(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is Record<string, unknown> => isRecord(item));
}
function recordRoute(
  record: Record<string, unknown>,
  fallbackRoute: string | null,
): string | null {
  return firstString(record.route) ?? fallbackRoute;
}

export function renderCompactRecordList(
  records: Record<string, unknown>[],
  options: {
    emptyLabel: string;
    fallbackRoute: string | null;
    fallbackRouteTitle: string;
    onOpenRoute: (route: string, title: string) => void;
  },
) {
  const { emptyLabel, fallbackRoute, fallbackRouteTitle, onOpenRoute } = options;
  if (records.length === 0) {
    return <Text type="secondary">{emptyLabel}</Text>;
  }
  return (
    <div className={styles.selectionList}>
      {records.map((record, index) => {
        const title = recordTitle(record, `Item ${index + 1}`);
        const summary = recordSummary(record);
        const status = firstString(record.status, record.runtime_status);
        const route = recordRoute(record, fallbackRoute);
        const needsFollowup = record.needs_followup === true;
        const processed = record.processed === true;
        return (
          <div key={`${title}:${index}`} className={styles.selectionRow}>
            <div className={styles.selectionBody}>
              <div className={styles.entryTitleRow}>
                {route ? (
                  <button
                    type="button"
                    className={styles.entryTitleButton}
                    onClick={() => {
                      onOpenRoute(route, title || fallbackRouteTitle);
                    }}
                  >
                    {title}
                  </button>
                ) : (
                  <div className={styles.entryTitle}>{title}</div>
                )}
                {status ? (
                  <Tag color={statusTagColor(status)}>{formatRuntimeStatus(status)}</Tag>
                ) : null}
                {needsFollowup ? <Tag color="warning">待跟进</Tag> : null}
                {processed ? <Tag color="success">已处理</Tag> : null}
              </div>
              {summary ? <p className={styles.selectionSummary}>{summary}</p> : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function renderOperatorBlock(
  options: {
    title: string;
    summary: string | null;
    status: unknown;
    route: string | null;
    routeTitle: string;
    details: Array<[string, string | null]>;
    onOpenRoute: (route: string, title: string) => void;
  },
) {
  const { title, summary, status, route, routeTitle, details, onOpenRoute } = options;
  const detailItems = details
    .filter(([, value]) => value && value !== RUNTIME_CENTER_TEXT.emptyValue)
    .map(([label, value]) => ({
      key: label,
      label,
      children: value,
    }));

  return (
    <div className={styles.controlCard}>
      <div className={styles.panelHeader} style={{ marginBottom: 12 }}>
        <div>
          <div className={styles.cardTitleRow}>
            <h3 className={styles.entryTitle}>{title}</h3>
            {typeof status === "string" && status ? (
              <Tag color={statusTagColor(status)}>{formatRuntimeStatus(status)}</Tag>
            ) : null}
          </div>
          {summary ? <p className={styles.selectionSummary}>{summary}</p> : null}
        </div>
        {route ? (
          <Button
            size="small"
            onClick={() => {
              onOpenRoute(route, routeTitle);
            }}
          >
            打开详情
          </Button>
        ) : null}
      </div>
      {detailItems.length > 0 ? (
        <Descriptions size="small" column={1} items={detailItems} />
      ) : (
        <Text type="secondary">{RUNTIME_CENTER_TEXT.emptyValue}</Text>
      )}
    </div>
  );
}

export function renderTraceBlock(
  options: {
    title: string;
    section: Record<string, unknown> | null;
    emptyLabel: string;
    onOpenRoute: (route: string, title: string) => void;
  },
) {
  const { title, section, emptyLabel, onOpenRoute } = options;
  const entries = Array.isArray(section?.entries)
    ? section!.entries.filter((item): item is Record<string, unknown> => isRecord(item))
    : [];
  const route = firstString(section?.route);
  const summary = firstString(section?.summary);
  const count = firstString(section?.count);

  return (
    <div className={styles.controlCard}>
      <div className={styles.panelHeader} style={{ marginBottom: 12 }}>
        <div>
          <div className={styles.cardTitleRow}>
            <h3 className={styles.entryTitle}>{title}</h3>
            {count ? <Tag>{count}</Tag> : null}
          </div>
          {summary ? <p className={styles.selectionSummary}>{summary}</p> : null}
        </div>
        {route ? (
          <Button
            size="small"
            onClick={() => {
              onOpenRoute(route, title);
            }}
          >
            打开详情
          </Button>
        ) : null}
      </div>
      {renderCompactRecordList(entries, {
        emptyLabel,
        fallbackRoute: route,
        fallbackRouteTitle: title,
        onOpenRoute,
      })}
    </div>
  );
}

export function renderCognitionBlock(
  options: {
    title: string;
    records: Record<string, unknown>[];
    emptyLabel: string;
    fallbackRoute: string | null;
    onOpenRoute: (route: string, title: string) => void;
  },
) {
  const { title, records, emptyLabel, fallbackRoute, onOpenRoute } = options;
  return (
    <div className={styles.controlCard}>
      <div className={styles.panelHeader} style={{ marginBottom: 12 }}>
        <div>
          <h3 className={styles.entryTitle}>{title}</h3>
        </div>
      </div>
      {renderCompactRecordList(records, {
        emptyLabel,
        fallbackRoute,
        fallbackRouteTitle: title,
        onOpenRoute,
      })}
    </div>
  );
}
