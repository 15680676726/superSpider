import {
  Alert,
  Button,
  Descriptions,
  Drawer,
  Empty,
  Spin,
  Tag,
  Typography,
} from "antd";

import RuntimeCapabilitySurfaceCard, {
  isRuntimeCapabilitySurface,
} from "../../components/RuntimeCapabilitySurfaceCard";
import styles from "./index.module.less";
import {
  type RuntimeCenterDetailState,
} from "./useRuntimeCenter";
import {
  formatPrimitiveValue as primitiveValue,
  formatRuntimeSectionLabel as translateRuntimeSectionLabel,
  localizeRuntimeText,
  RUNTIME_CENTER_TEXT,
} from "./text";
import {
  DETAIL_SECTION_ORDER,
  isIndustryInstanceDetailPayload,
  isIndustryMainChainGraph,
  isRecord,
  isTaskReviewRecord,
  objectRows,
  primaryTitle,
} from "./runtimeDetailPrimitives";
import {
  renderIndustryExecutionFocusSection,
  renderIndustryMainChainSection,
  renderOperatorAgentReportsSection,
  renderOperatorBacklogSection,
  renderOperatorAssignmentsSection,
  renderOperatorMediaAnalysesSection,
  renderTaskReviewSection,
} from "./runtimeIndustrySections";
import { renderHostTwinSection } from "./runtimeEnvironmentSections";

const { Text } = Typography;

export function renderRecordCard(
  key: string,
  record: Record<string, unknown>,
  openRoute: (route: string, title: string) => void,
  selected = false,
) {
  const rows = objectRows(record).slice(0, 8);
  const nestedEntries = Object.entries(record).filter(([, value]) => {
    if (value === null || value === undefined || value === "") {
      return false;
    }
    if (Array.isArray(value)) {
      return value.some((item) => typeof item === "object" && item !== null);
    }
    return isRecord(value);
  });

  return (
    <div
      key={key}
      className={styles.detailItem}
      style={
        selected
          ? {
              border: "1px solid rgba(22, 119, 255, 0.35)",
              boxShadow: "0 0 0 1px rgba(22, 119, 255, 0.08)",
            }
          : undefined
      }
    >
      {selected ? (
        <div style={{ marginBottom: 8 }}>
          <Tag color="blue">Focused</Tag>
        </div>
      ) : null}
      {rows.length > 0 ? (
        <Descriptions
          size="small"
          column={1}
          bordered
          items={rows.map(([label, value]) => ({
            key: `${key}:${label}`,
            label,
            children:
              value.length > 140 ? (
                <pre className={styles.detailPre}>{value}</pre>
              ) : (
                <span>{value}</span>
              ),
          }))}
        />
      ) : null}

      {nestedEntries.length > 0 ? (
        <div className={styles.detailNested}>
          {nestedEntries.map(([nestedKey, nestedValue]) => (
            <div key={`${key}:${nestedKey}`} className={styles.detailNestedBlock}>
              <div className={styles.detailSectionTitle}>
                {translateRuntimeSectionLabel(nestedKey)}
              </div>
              {Array.isArray(nestedValue) ? (
                <div className={styles.detailArray}>
                  {nestedValue.map((item, index) =>
                    isRecord(item)
                      ? renderRecordCard(`${key}:${nestedKey}:${index}`, item, openRoute)
                      : (
                          <pre
                            key={`${key}:${nestedKey}:${index}`}
                            className={styles.detailPre}
                          >
                            {primitiveValue(item)}
                          </pre>
                        ),
                  )}
                </div>
              ) : isRecord(nestedValue) ? (
                renderRecordCard(`${key}:${nestedKey}`, nestedValue, openRoute)
              ) : (
                <pre className={styles.detailPre}>{primitiveValue(nestedValue)}</pre>
              )}
            </div>
          ))}
        </div>
      ) : null}

      {isRecord(record.routes) ? (
        <div className={styles.routeActions}>
          {Object.entries(record.routes)
            .filter(([, route]) => typeof route === "string" && route)
            .map(([routeKey, route]) => (
              <Button
                key={`${key}:${routeKey}`}
                size="small"
                onClick={() => {
                  openRoute(
                    route as string,
                    `${translateRuntimeSectionLabel(routeKey)} 详情`,
                  );
                }}
              >
                {translateRuntimeSectionLabel(routeKey)}
              </Button>
            ))}
        </div>
      ) : null}
    </div>
  );
}

export function renderDetailSection(
  sectionKey: string,
  sectionValue: unknown,
  openRoute: (route: string, title: string) => void,
) {
  if (sectionValue === null || sectionValue === undefined || sectionValue === "") {
    return null;
  }

  if (sectionKey === "routes" && isRecord(sectionValue)) {
    const routes = Object.entries(sectionValue).filter(
      ([, route]) => typeof route === "string" && route,
    );
    if (routes.length === 0) {
      return null;
    }
    return (
      <section key={sectionKey} className={styles.detailSection}>
        <div className={styles.detailSectionTitle}>路由</div>
        <div className={styles.routeActions}>
          {routes.map(([routeKey, route]) => (
            <Button
              key={`${sectionKey}:${routeKey}`}
              onClick={() => {
                openRoute(
                  route as string,
                  `${translateRuntimeSectionLabel(routeKey)} 详情`,
                );
              }}
            >
              {translateRuntimeSectionLabel(routeKey)}
            </Button>
          ))}
        </div>
      </section>
    );
  }

  if (sectionKey === "capability_surface" && isRuntimeCapabilitySurface(sectionValue)) {
    return (
      <section key={sectionKey} className={styles.detailSection}>
        <div className={styles.detailSectionTitle}>
          {RUNTIME_CENTER_TEXT.capabilitySurfaceSectionTitle}
        </div>
        <RuntimeCapabilitySurfaceCard
          surface={sectionValue}
          onOpenRoute={openRoute}
        />
      </section>
    );
  }

  if (sectionKey === "review" && isTaskReviewRecord(sectionValue)) {
    return renderTaskReviewSection(sectionKey, sectionValue, openRoute);
  }

  if (sectionKey === "task_subgraph" && isRecord(sectionValue)) {
    return (
      <section key={sectionKey} className={styles.detailSection}>
        <div className={styles.detailSectionTitle}>任务子图</div>
        {renderRecordCard(sectionKey, sectionValue, openRoute)}
      </section>
    );
  }

  if (sectionKey === "host_twin" && isRecord(sectionValue)) {
    return renderHostTwinSection(sectionKey, sectionValue);
  }

  if (sectionKey === "assignments") {
    const rendered = renderOperatorAssignmentsSection(
      sectionKey,
      sectionValue,
      openRoute,
    );
    if (rendered) {
      return rendered;
    }
  }

  if (sectionKey === "backlog") {
    const rendered = renderOperatorBacklogSection(
      sectionKey,
      sectionValue,
      openRoute,
    );
    if (rendered) {
      return rendered;
    }
  }

  if (sectionKey === "agent_reports") {
    const rendered = renderOperatorAgentReportsSection(
      sectionKey,
      sectionValue,
      openRoute,
    );
    if (rendered) {
      return rendered;
    }
  }

  if (sectionKey === "media_analyses") {
    const rendered = renderOperatorMediaAnalysesSection(
      sectionKey,
      sectionValue,
      openRoute,
    );
    if (rendered) {
      return rendered;
    }
  }

  if (Array.isArray(sectionValue)) {
    const isFocusableSection = sectionKey === "assignments" || sectionKey === "backlog";
    const orderedItems =
      isFocusableSection && sectionValue.length > 1
        ? [...sectionValue].sort((left, right) => {
            const leftSelected = isRecord(left) && left.selected === true ? 1 : 0;
            const rightSelected = isRecord(right) && right.selected === true ? 1 : 0;
            return rightSelected - leftSelected;
          })
        : sectionValue;
    return (
      <section key={sectionKey} className={styles.detailSection}>
        <div className={styles.detailSectionTitle}>
          {translateRuntimeSectionLabel(sectionKey)} <Tag>{sectionValue.length}</Tag>
        </div>
        {sectionValue.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂无内容"
          />
        ) : (
          <div className={styles.detailArray}>
            {orderedItems.map((item, index) =>
              isRecord(item) ? (
                renderRecordCard(
                  `${sectionKey}:${index}`,
                  item,
                  openRoute,
                  item.selected === true,
                )
              ) : (
                <pre key={`${sectionKey}:${index}`} className={styles.detailPre}>
                  {primitiveValue(item)}
                </pre>
              ),
            )}
          </div>
        )}
      </section>
    );
  }

  if (isRecord(sectionValue)) {
    return (
      <section key={sectionKey} className={styles.detailSection}>
        <div className={styles.detailSectionTitle}>
          {translateRuntimeSectionLabel(sectionKey)}
        </div>
        {renderRecordCard(
          sectionKey,
          sectionValue,
          openRoute,
          sectionValue.selected === true,
        )}
      </section>
    );
  }

  return (
    <section key={sectionKey} className={styles.detailSection}>
      <div className={styles.detailSectionTitle}>
        {translateRuntimeSectionLabel(sectionKey)}
      </div>
      <pre className={styles.detailPre}>{primitiveValue(sectionValue)}</pre>
    </section>
  );
}

export function renderRuntimeDetailDrawer(
  detail: RuntimeCenterDetailState | null,
  detailLoading: boolean,
  detailError: string | null,
  closeDetail: () => void,
  openDetail: (route: string, title: string) => void,
) {
  const payload = detail?.payload;
  const payloadRecord = isRecord(payload) ? payload : null;
  const title = payloadRecord
    ? localizeRuntimeText(primaryTitle(payloadRecord, detail?.title ?? "运行详情"))
    : localizeRuntimeText(detail?.title ?? "运行详情");
  const capabilitySurfacePayload =
    payloadRecord && isRuntimeCapabilitySurface(payloadRecord)
      ? payloadRecord
      : null;
  const industryDetailPayload =
    payloadRecord && isIndustryInstanceDetailPayload(payloadRecord)
      ? payloadRecord
      : null;
  const industryMainChain =
    industryDetailPayload && isIndustryMainChainGraph(industryDetailPayload.main_chain)
      ? industryDetailPayload.main_chain
      : null;
  const sectionEntries = payloadRecord
    ? [
        ...DETAIL_SECTION_ORDER.map((key) => [key, payloadRecord[key]] as const),
        ...Object.entries(payloadRecord).filter(
          ([key]) =>
            !DETAIL_SECTION_ORDER.includes(key as (typeof DETAIL_SECTION_ORDER)[number]),
        ),
      ]
    : [];
  const visibleSectionEntries = industryDetailPayload
    ? sectionEntries.filter(
        ([sectionKey]) =>
          ![
            "execution",
            "main_chain",
            "strategy_memory",
            "lanes",
            "current_cycle",
          ].includes(sectionKey),
      )
    : sectionEntries;

  return (
    <Drawer
      width={640}
      open={detail !== null || detailLoading}
      onClose={closeDetail}
      title={title || "运行详情"}
      className={styles.detailDrawer}
      extra={
        detail?.route ? (
          <Text type="secondary" className={styles.drawerRoute}>
            {detail.route}
          </Text>
        ) : null
      }
    >
      {detailError ? (
        <Alert
          showIcon
          type="error"
          message="详情加载失败"
          description={detailError}
          style={{ marginBottom: 32 }}
        />
      ) : null}

      {detailLoading ? (
        <div className={styles.detailLoading}>
          <Spin />
        </div>
      ) : capabilitySurfacePayload ? (
        <div className={styles.detailBody}>
          <RuntimeCapabilitySurfaceCard
            surface={capabilitySurfacePayload}
            onOpenRoute={openDetail}
          />
        </div>
      ) : payloadRecord ? (
        <div className={styles.detailBody}>
          {industryDetailPayload
            ? renderIndustryExecutionFocusSection(industryDetailPayload, openDetail)
            : null}
          {industryMainChain
            ? renderIndustryMainChainSection(industryMainChain, openDetail)
            : null}
          {visibleSectionEntries.map(([sectionKey, sectionValue]) =>
            renderDetailSection(
              sectionKey,
              sectionValue,
              openDetail,
            ),
          )}
        </div>
      ) : (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="暂无详情数据"
        />
      )}
    </Drawer>
  );
}

export const renderDetailDrawer = renderRuntimeDetailDrawer;
