import { useMemo, useState } from "react";
import { Button, Card, Empty, Input, Select, Statistic, Tag } from "antd";
import { RefreshCw } from "lucide-react";
import type { CapabilityMount, CapabilitySummary } from "../../../api/types";
import { runtimeRiskColor, runtimeRiskLabel } from "../../../runtime/tagSemantics";
import { normalizeDisplayChinese } from "../../../text";
import { useCapabilities } from "./useCapabilities";
import styles from "./index.module.less";

type CapabilityStatusFilter = "all" | "enabled" | "disabled";

const KIND_ORDER = [
  "local-tool",
  "remote-mcp",
  "skill-bundle",
  "provider-admin",
  "system-op",
];

const KIND_LABELS: Record<string, string> = {
  "local-tool": "本地工具",
  "remote-mcp": "远程模型上下文协议",
  "skill-bundle": "技能包",
  "provider-admin": "提供方管理",
  "system-op": "系统操作",
  unknown: "未知",
};

const TEXT = {
  title: "能力总览",
  description:
    "查看当前已挂载能力的状态、类型、风险和执行要求。",
  refresh: "刷新",
  searchPlaceholder:
    "搜索能力名称、编号、摘要或类型",
  kindFilter: "能力类型",
  statusFilter: "启用状态",
  kindAll: "全部类型",
  statusAll: "全部状态",
  statusEnabled: "已启用",
  statusDisabled: "已停用",
  summaryTotal: "能力总数",
  summaryEnabled: "已启用",
  summaryKinds: "按类型统计",
  emptyKinds: "暂无类型数据",
  loading: "加载中...",
  empty: "暂无能力数据",
  metaEnvironment: "环境要求",
  metaEvidence: "证据约定",
  metaRoles: "角色访问",
  metaExecutor: "执行器",
  metaNone: "未设置",
} as const;

function formatKind(kind: string) {
  return KIND_LABELS[kind] || normalizeDisplayChinese(kind.replace(/-/g, " "));
}

function formatRiskLevel(risk: string) {
  return runtimeRiskLabel(risk) || risk;
}

function capabilityDisplayName(
  capability: Partial<Pick<CapabilityMount, "id" | "name">> | null | undefined,
) {
  if (typeof capability?.name === "string" && capability.name.trim().length > 0) {
    return normalizeDisplayChinese(capability.name);
  }
  if (typeof capability?.id === "string" && capability.id.trim().length > 0) {
    return capability.id;
  }
  return "unknown-capability";
}

function capabilityKind(capability: Partial<CapabilityMount> | null | undefined) {
  if (typeof capability?.kind === "string" && capability.kind.trim().length > 0) {
    return capability.kind;
  }
  return "unknown";
}

function capabilitySummary(capability: Partial<CapabilityMount> | null | undefined) {
  if (typeof capability?.summary === "string" && capability.summary.trim().length > 0) {
    return normalizeDisplayChinese(capability.summary);
  }
  return "";
}

function capabilityStatus(capability: Partial<CapabilityMount> | null | undefined) {
  return capability?.enabled === true;
}

function deriveSummary(capabilities: CapabilityMount[]): CapabilitySummary {
  const by_kind: Record<string, number> = {};
  const by_source: Record<string, number> = {};
  let enabled = 0;
  capabilities.forEach((capability) => {
    const kind = capabilityKind(capability);
    const sourceKind =
      typeof capability.source_kind === "string" && capability.source_kind.trim().length > 0
        ? capability.source_kind
        : "unknown";
    by_kind[kind] = (by_kind[kind] ?? 0) + 1;
    by_source[sourceKind] = (by_source[sourceKind] ?? 0) + 1;
    if (capabilityStatus(capability)) {
      enabled += 1;
    }
  });
  return {
    total: capabilities.length,
    enabled,
    by_kind,
    by_source,
  };
}

function riskColor(risk: string) {
  return runtimeRiskColor(risk);
}

function statusColor(enabled: boolean) {
  return enabled ? "success" : "default";
}

function capabilityTags(value: string[] | null | undefined): string[] {
  return Array.isArray(value) ? value.filter((item) => typeof item === "string") : [];
}

function renderTags(items: string[], emptyLabel: string) {
  if (!items.length) {
    return <span className={styles.metaEmpty}>{emptyLabel}</span>;
  }
  return items.map((item) => (
    <Tag key={item} color="default">
      {normalizeDisplayChinese(item)}
    </Tag>
  ));
}

export default function CapabilitiesPage() {
  const { capabilities, summary, loading, reload } = useCapabilities();
  const [kindFilter, setKindFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<CapabilityStatusFilter>("all");
  const [query, setQuery] = useState("");

  const summaryData = summary ?? deriveSummary(capabilities);
  const kindOptions = [
    { value: "all", label: TEXT.kindAll },
    ...KIND_ORDER.map((kind) => ({
      value: kind,
      label: formatKind(kind),
    })),
  ];

  const filtered = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return [...capabilities]
      .filter((capability) => {
        if (kindFilter !== "all" && capabilityKind(capability) !== kindFilter) {
          return false;
        }
        if (statusFilter === "enabled" && !capabilityStatus(capability)) {
          return false;
        }
        if (statusFilter === "disabled" && capabilityStatus(capability)) {
          return false;
        }
        if (!normalizedQuery) {
          return true;
        }
        const haystack = [
          capabilityDisplayName(capability),
          capability.id || "",
          capabilitySummary(capability),
          capabilityKind(capability),
        ]
          .join(" ")
          .toLowerCase();
        return haystack.includes(normalizedQuery);
      })
      .sort((left, right) => {
        if (capabilityStatus(left) !== capabilityStatus(right)) {
          return capabilityStatus(left) ? -1 : 1;
        }
        return String(capabilityDisplayName(left)).localeCompare(
          String(capabilityDisplayName(right)),
          undefined,
          { sensitivity: "base" },
        );
      });
  }, [capabilities, kindFilter, statusFilter, query]);

  return (
    <div className={styles.capabilitiesPage}>
      <div className={styles.header}>
        <div className={styles.headerInfo}>
          <h1 className={styles.title}>{TEXT.title}</h1>
          <p className={styles.description}>{TEXT.description}</p>
        </div>
        <Button icon={<RefreshCw size={14} />} onClick={() => void reload()}>
          {TEXT.refresh}
        </Button>
      </div>

      <div className={styles.filters}>
        <Input
          allowClear
          placeholder={TEXT.searchPlaceholder}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          style={{ width: 260 }}
        />
        <div>
          <div className={styles.filterLabel}>{TEXT.kindFilter}</div>
          <Select
            value={kindFilter}
            onChange={setKindFilter}
            options={kindOptions}
            style={{ width: 200 }}
          />
        </div>
        <div>
          <div className={styles.filterLabel}>{TEXT.statusFilter}</div>
          <Select
            value={statusFilter}
            onChange={(value) => setStatusFilter(value as CapabilityStatusFilter)}
            options={[
              { value: "all", label: TEXT.statusAll },
              { value: "enabled", label: TEXT.statusEnabled },
              { value: "disabled", label: TEXT.statusDisabled },
            ]}
            style={{ width: 160 }}
          />
        </div>
      </div>

      <div className={styles.summaryGrid}>
        <Card className={styles.summaryCard}>
          <Statistic title={TEXT.summaryTotal} value={summaryData.total} />
        </Card>
        <Card className={styles.summaryCard}>
          <Statistic title={TEXT.summaryEnabled} value={summaryData.enabled} />
        </Card>
        <Card className={styles.summaryCard}>
          <Statistic title={TEXT.summaryKinds} value="" />
          <div className={styles.summaryTags}>
            {Object.keys(summaryData.by_kind).length === 0
              ? TEXT.emptyKinds
              : Object.entries(summaryData.by_kind)
                  .sort(
                    ([left], [right]) =>
                      KIND_ORDER.indexOf(left) - KIND_ORDER.indexOf(right),
                  )
                  .map(([kind, count]) => (
                    <Tag key={kind} color="default">
                      {`${formatKind(kind)} / ${count}`}
                    </Tag>
                  ))}
          </div>
        </Card>
      </div>

      {loading ? (
        <div className={styles.emptyState}>
          <Empty description={TEXT.loading} />
        </div>
      ) : filtered.length === 0 ? (
        <div className={styles.emptyState}>
          <Empty description={TEXT.empty} />
        </div>
      ) : (
        <div className={styles.cardGrid}>
          {filtered.map((capability) => (
            <Card
              key={capability.id}
              className={styles.capabilityCard}
              bodyStyle={{ padding: 18 }}
            >
              <div className={styles.cardHeader}>
                <div>
                  <h3 className={styles.cardTitle}>
                    {capabilityDisplayName(capability)}
                  </h3>
                  <div className={styles.cardSubtitle}>{capability.id}</div>
                </div>
                <div>
                  <Tag color={statusColor(capabilityStatus(capability))}>
                    {capabilityStatus(capability)
                      ? TEXT.statusEnabled
                      : TEXT.statusDisabled}
                  </Tag>
                  <Tag color={riskColor(capability.risk_level || "auto")}>
                    {formatRiskLevel(capability.risk_level || "auto")}
                  </Tag>
                  <Tag color="blue">
                    {formatKind(capabilityKind(capability))}
                  </Tag>
                </div>
              </div>
              <p className={styles.cardSummary}>{capabilitySummary(capability)}</p>
              <div className={styles.metaBlock}>
                <div className={styles.metaRow}>
                  <span className={styles.metaLabel}>{TEXT.metaEnvironment}</span>
                  {renderTags(
                    capabilityTags(capability.environment_requirements),
                    TEXT.metaNone,
                  )}
                </div>
                <div className={styles.metaRow}>
                  <span className={styles.metaLabel}>{TEXT.metaEvidence}</span>
                  {renderTags(
                    capabilityTags(capability.evidence_contract),
                    TEXT.metaNone,
                  )}
                </div>
                <div className={styles.metaRow}>
                  <span className={styles.metaLabel}>{TEXT.metaRoles}</span>
                  {renderTags(
                    capabilityTags(capability.role_access_policy),
                    TEXT.metaNone,
                  )}
                </div>
                <div className={styles.metaRow}>
                  <span className={styles.metaLabel}>{TEXT.metaExecutor}</span>
                  <span className={styles.metaEmpty}>
                    {capability.executor_ref
                      ? normalizeDisplayChinese(capability.executor_ref)
                      : TEXT.metaNone}
                  </span>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
