import {
  Alert,
  Button,
  Card,
  Checkbox,
  Descriptions,
  Empty,
  Input,
  Space,
  Spin,
  Switch,
  Tabs,
  Row,
  Col,
  Tag,
  Typography,
} from "antd";
import { useCallback, useMemo } from "react";
import {
  Activity,
  Bot,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Waypoints,
} from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";
import AutomationTab from "./AutomationTab";
import CapabilityOptimizationPanel from "./CapabilityOptimizationPanel";
import styles from "./index.module.less";
import { useRuntimeCenter } from "./useRuntimeCenter";
import { localizeRuntimeText, RUNTIME_CENTER_TEXT } from "./text";
import {
  type RuntimeCenterTab,
  useRuntimeCenterAdminState,
} from "./useRuntimeCenterAdminState";
import {
  surfaceTagColor,
  cardStatusColor,
  translateRuntimeStatus,
  translateRuntimeEntryKind,
  translateRuntimeCardTitle,
  translateRuntimeCardSummary,
  translateRuntimeSourceList,
  translateRuntimeEntryTitle,
  translateRuntimeEntrySummary,
  translateRuntimeFieldLabel,
  formatTimestamp,
  primitiveValue,
  routeTitle,
  renderDetailDrawer,
  renderEntry,
  summaryRows,
  toggleSelection,
} from "./viewHelpers";
import MainBrainCockpitPanel from "./MainBrainCockpitPanel";
import { runtimeStatusColor } from "../../runtime/tagSemantics";

const { Text } = Typography;
const { TextArea } = Input;

export default function RuntimeCenterPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const {
    data,
    loading,
    refreshing,
    error,
    mainBrainData,
    mainBrainError,
    mainBrainLoading,
    mainBrainUnavailable,
    busyActionId,
    detail,
    detailLoading,
    detailError,
    reload,
    invokeAction,
    openDetail,
    closeDetail,
  } = useRuntimeCenter();

  const rawTab = searchParams.get("tab");
  const activeTab: RuntimeCenterTab =
    rawTab === "governance" || rawTab === "recovery" || rawTab === "automation"
      ? rawTab
      : "overview";
  const focusScope = searchParams.get("scope");
  const surface = data?.surface;

  const decisionEntries = useMemo(
    () => data?.cards.find((card) => card.key === "decisions")?.entries ?? [],
    [data],
  );
  const patchEntries = useMemo(
    () => data?.cards.find((card) => card.key === "patches")?.entries ?? [],
    [data],
  );
  const {
    governanceStatus,
    governanceLoading,
    governanceError,
    governanceBusyKey,
    capabilityOptimizationOverview,
    capabilityOptimizationLoading,
    capabilityOptimizationError,
    capabilityOptimizationBusyId,
    recoverySummary,
    selfCheck,
    recoveryLoading,
    recoveryError,
    recoveryBusyKey,
    operatorActor,
    setOperatorActor,
    governanceResolution,
    setGovernanceResolution,
    emergencyReason,
    setEmergencyReason,
    resumeReason,
    setResumeReason,
    executeApprovedDecisions,
    setExecuteApprovedDecisions,
    selectedDecisionIds,
    setSelectedDecisionIds,
    selectedPatchIds,
    setSelectedPatchIds,
    handleDecisionBatch,
    handlePatchBatch,
    handleCapabilityOptimizationExecute,
    handleEmergencyStop,
    handleResumeRuntime,
    handleRecoveryRefresh,
    handleSelfCheck,
    refreshActiveTabData,
  } = useRuntimeCenterAdminState({
    activeTab,
    dataGeneratedAt: data?.generated_at,
    decisionEntries,
    patchEntries,
    reload,
    navigate,
  });

  const handleTabChange = (nextTab: string) => {
    const nextParams = new URLSearchParams(searchParams);
    if (nextTab === "overview") {
      nextParams.delete("tab");
      nextParams.delete("scope");
    } else {
      nextParams.set("tab", nextTab);
      if (nextTab !== "automation") {
        nextParams.delete("scope");
      }
    }
    setSearchParams(nextParams, { replace: true });
  };

  const openSurfaceRoute = useCallback(
    async (route: string, title: string) => {
      if (route.startsWith("/api/")) {
        await openDetail(route, title);
        return;
      }
      navigate(route);
    },
    [navigate, openDetail],
  );

  const recoveryRows = summaryRows(recoverySummary);
  const healthHighlights = useMemo(
    () => (selfCheck?.checks ?? []).slice(0, 4),
    [selfCheck],
  );

  return (
    <div className={`${styles.page} page-container`}>
      <Card className="baize-page-header">
        <div className="baize-page-header-content">
          <div>
            <h1 className="baize-page-header-title">{RUNTIME_CENTER_TEXT.pageTitle}</h1>
            <p className="baize-page-header-description">
              {activeTab === "governance"
                ? RUNTIME_CENTER_TEXT.tabGovernanceDescription
                : activeTab === "recovery"
                  ? RUNTIME_CENTER_TEXT.tabRecoveryDescription
                  : activeTab === "automation"
                    ? RUNTIME_CENTER_TEXT.automationPageDescription
                    : RUNTIME_CENTER_TEXT.pageDescription}
            </p>
          </div>
          <div className="baize-page-header-actions">
            <Space size={12} wrap>
              <Tag
                color={surfaceTagColor(surface?.status ?? "unavailable")}
                style={{ borderRadius: "8px", fontWeight: 700, padding: "4px 12px" }}
              >
                {translateRuntimeStatus(surface?.status ?? "unavailable")}
              </Tag>
              <Button
                className="baize-btn baize-btn-primary"
                icon={<RefreshCw size={16} />}
                loading={refreshing || governanceLoading || recoveryLoading}
                onClick={() => {
                  void refreshActiveTabData();
                }}
              >
                刷新
              </Button>
            </Space>
          </div>
        </div>
        <div style={{ marginTop: 8, fontSize: "12px", color: "var(--baize-text-muted)" }}>
          {data?.generated_at
            ? RUNTIME_CENTER_TEXT.generatedAt(formatTimestamp(data.generated_at))
            : RUNTIME_CENTER_TEXT.waitingForData}
        </div>
      </Card>

      <section className={styles.tabBar}>
        <Tabs
          activeKey={activeTab}
          onChange={handleTabChange}
          items={[
            { key: "overview", label: RUNTIME_CENTER_TEXT.tabOverview },
            { key: "governance", label: RUNTIME_CENTER_TEXT.tabGovernance },
            { key: "recovery", label: RUNTIME_CENTER_TEXT.tabRecovery },
            { key: "automation", label: RUNTIME_CENTER_TEXT.tabAutomation },
          ]}
        />
      </section>

      {activeTab === "overview" ? (
        <>
          <Space direction="vertical" size={24} style={{ width: "100%", marginBottom: 32 }}>
          <MainBrainCockpitPanel
            data={data}
            loading={loading}
            refreshing={refreshing}
            error={error}
            mainBrainData={mainBrainData}
            mainBrainError={mainBrainError}
            mainBrainLoading={mainBrainLoading}
            mainBrainUnavailable={mainBrainUnavailable}
            onRefresh={() => {
              void refreshActiveTabData();
            }}
            onOpenRoute={(route, title) => {
                void openSurfaceRoute(route, title);
              }}
            />
          </Space>
          {data ? (
            <section className={styles.grid}>
              {data.cards.map((card) => (
                <Card key={card.key} className="baize-card">
                  <div className={styles.cardHeader}>
                    <div>
                      <div className={styles.cardTitleRow}>
                        <h2 className={styles.cardTitle}>{translateRuntimeCardTitle(card.key, card.title)}</h2>
                        <Tag color={cardStatusColor(card.status)}>{translateRuntimeStatus(card.status)}</Tag>
                      </div>
                      <p className={styles.cardSummary}>{translateRuntimeCardSummary(card.key, card.summary)}</p>
                    </div>
                    <div className={styles.cardSide}><Tag>{card.count}</Tag><span className={styles.cardSource}>{translateRuntimeSourceList(card.source)}</span></div>
                  </div>
                  {card.entries.length > 0 ? (
                    <div className={styles.entryList}>
                      {card.entries.map((entry) => renderEntry(card, entry, busyActionId, invokeAction, openDetail))}
                    </div>
                  ) : (
                    <div className={styles.emptyWrap}><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={RUNTIME_CENTER_TEXT.cardEmpty(translateRuntimeCardTitle(card.key, card.title))} /></div>
                  )}
                </Card>
                ))}
            </section>
          ) : null}
        </>
      ) : null}

      {activeTab === "governance" ? (
        <div className={styles.tabStack}>
          <section className={styles.metrics}>
            <Card className={styles.metricCard}><div className={styles.metricIcon}>{governanceStatus?.emergency_stop_active ? <ShieldAlert size={18} /> : <ShieldCheck size={18} />}</div><div><div className={styles.metricLabel}>{RUNTIME_CENTER_TEXT.governanceState}</div><div className={styles.metricValueSmall}>{governanceStatus?.emergency_stop_active ? RUNTIME_CENTER_TEXT.runtimePaused : RUNTIME_CENTER_TEXT.runtimeAccepting}</div></div></Card>
            <Card className={styles.metricCard}><div className={styles.metricIcon}><Waypoints size={18} /></div><div><div className={styles.metricLabel}>{RUNTIME_CENTER_TEXT.pendingDecisions}</div><div className={styles.metricValue}>{governanceStatus?.pending_decisions ?? decisionEntries.length}</div></div></Card>
            <Card className={styles.metricCard}><div className={styles.metricIcon}><RotateCcw size={18} /></div><div><div className={styles.metricLabel}>{RUNTIME_CENTER_TEXT.pendingPatches}</div><div className={styles.metricValue}>{governanceStatus?.pending_patches ?? patchEntries.length}</div></div></Card>
            <Card className={styles.metricCard}><div className={styles.metricIcon}><Bot size={18} /></div><div><div className={styles.metricLabel}>{RUNTIME_CENTER_TEXT.pausedSchedules}</div><div className={styles.metricValue}>{governanceStatus?.paused_schedule_ids.length ?? 0}</div></div></Card>
            <Card className={styles.metricCard}><div className={styles.metricIcon}><RefreshCw size={18} /></div><div><div className={styles.metricLabel}>待处理优化</div><div className={styles.metricValue}>{capabilityOptimizationOverview?.summary.actionable_count ?? 0}</div></div></Card>
          </section>
          <section className={styles.panelGrid}>
            <Card className="baize-card">
              <div className={styles.panelHeader}><div><h2 className={styles.cardTitle}>{RUNTIME_CENTER_TEXT.governanceControls}</h2><p className={styles.cardSummary}>{RUNTIME_CENTER_TEXT.governanceControlsSummary}</p></div><Tag color={governanceStatus?.emergency_stop_active ? "error" : "success"}>{governanceStatus?.emergency_stop_active ? RUNTIME_CENTER_TEXT.runtimePaused : RUNTIME_CENTER_TEXT.runtimeAccepting}</Tag></div>
              {governanceError ? <Alert showIcon type="error" message={governanceError} style={{ marginBottom: 24 }} /> : null}
              <Row gutter={[24, 24]}>
                <Col xs={24} lg={12}>
                  <div className={styles.controlCard} style={{ height: "100%" }}>
                    <Space direction="vertical" size={16} style={{ width: "100%" }}>
                      <div className={styles.fieldStack}><Text strong>{RUNTIME_CENTER_TEXT.operatorActor}</Text><Input value={operatorActor} onChange={(event) => setOperatorActor(event.target.value)} /></div>
                      <div className={styles.fieldStack}><Text strong>{RUNTIME_CENTER_TEXT.emergencyReason}</Text><TextArea rows={3} value={emergencyReason} onChange={(event) => setEmergencyReason(event.target.value)} /></div>
                      <div className={styles.actionStrip}>
                        <Button danger type="primary" loading={governanceBusyKey === "emergency-stop"} onClick={() => { void handleEmergencyStop(); }}>{RUNTIME_CENTER_TEXT.emergencyStop}</Button>
                        <Button loading={governanceBusyKey === "resume"} onClick={() => { void handleResumeRuntime(); }}>{RUNTIME_CENTER_TEXT.resumeRuntime}</Button>
                      </div>
                    </Space>
                  </div>
                </Col>
                <Col xs={24} lg={12}>
                  <div className={styles.controlCard} style={{ height: "100%" }}>
                    <Space direction="vertical" size={16} style={{ width: "100%" }}>
                      <div className={styles.fieldStack}><Text strong>{RUNTIME_CENTER_TEXT.resumeReason}</Text><TextArea rows={3} value={resumeReason} onChange={(event) => setResumeReason(event.target.value)} /></div>
                      <Descriptions size="small" column={1} bordered items={[
                        { key: "blocked", label: RUNTIME_CENTER_TEXT.blockedCapabilities, children: (governanceStatus?.blocked_capability_refs ?? []).join(", ") || "-" },
                        { key: "shutdown", label: RUNTIME_CENTER_TEXT.channelShutdown, children: String(governanceStatus?.channel_shutdown_applied ?? false) },
                        { key: "updated", label: RUNTIME_CENTER_TEXT.updatedAt, children: formatTimestamp(governanceStatus?.updated_at) },
                      ]} />
                    </Space>
                  </div>
                </Col>
              </Row>
            </Card>
            <CapabilityOptimizationPanel
              loading={capabilityOptimizationLoading}
              error={capabilityOptimizationError}
              overview={capabilityOptimizationOverview}
              busyRecommendationId={capabilityOptimizationBusyId}
              onExecute={(item) => {
                void handleCapabilityOptimizationExecute(item);
              }}
              onOpenRoute={(route, title) => {
                void openSurfaceRoute(route, title || routeTitle(route));
              }}
            />
            <Card className="baize-card">
              <div className={styles.panelHeader}><div><h2 className={styles.cardTitle}>{RUNTIME_CENTER_TEXT.decisionBatchTitle}</h2><p className={styles.cardSummary}>{RUNTIME_CENTER_TEXT.decisionBatchSummary}</p></div><Tag>{decisionEntries.length}</Tag></div>
              <div className={styles.fieldStack}><Text strong>{RUNTIME_CENTER_TEXT.batchResolution}</Text><TextArea rows={3} value={governanceResolution} onChange={(event) => setGovernanceResolution(event.target.value)} /><div className={styles.inlineControl}><Switch checked={executeApprovedDecisions} onChange={setExecuteApprovedDecisions} /><span>{RUNTIME_CENTER_TEXT.executeApprovedDecisions}</span></div></div>
              <div className={styles.actionStrip}>
                <Button size="small" onClick={() => setSelectedDecisionIds(decisionEntries.map((entry) => entry.id))}>{RUNTIME_CENTER_TEXT.selectAll}</Button>
                <Button size="small" onClick={() => setSelectedDecisionIds([])}>{RUNTIME_CENTER_TEXT.clearSelection}</Button>
                <Button type="primary" loading={governanceBusyKey === "decisions-approve"} onClick={() => { void handleDecisionBatch("approve"); }}>{RUNTIME_CENTER_TEXT.batchApprove}</Button>
                <Button danger loading={governanceBusyKey === "decisions-reject"} onClick={() => { void handleDecisionBatch("reject"); }}>{RUNTIME_CENTER_TEXT.batchReject}</Button>
              </div>
              {governanceLoading && !governanceStatus ? <Spin /> : decisionEntries.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={RUNTIME_CENTER_TEXT.noPendingDecisions} /> : <div className={styles.selectionList}>{decisionEntries.map((entry) => { const localizedTitle = translateRuntimeEntryTitle("decisions", entry.title); const localizedSummary = translateRuntimeEntrySummary("decisions", entry.summary); return <div key={entry.id} className={styles.selectionRow}><Checkbox checked={selectedDecisionIds.includes(entry.id)} onChange={() => toggleSelection(selectedDecisionIds, entry.id, setSelectedDecisionIds)} /><div className={styles.selectionBody}><button type="button" className={styles.entryTitleButton} onClick={() => { if (entry.route) { void openSurfaceRoute(entry.route, localizedTitle); } }}>{localizedTitle}</button><div className={styles.selectionMeta}><Tag color={runtimeStatusColor(entry.status)}>{translateRuntimeStatus(entry.status)}</Tag>{entry.owner ? <span>{localizeRuntimeText(entry.owner)}</span> : null}<span>{formatTimestamp(entry.updated_at)}</span></div>{localizedSummary ? <p className={styles.selectionSummary}>{localizedSummary}</p> : null}</div></div>; })}</div>}
            </Card>
            <Card className="baize-card">
              <div className={styles.panelHeader}><div><h2 className={styles.cardTitle}>{RUNTIME_CENTER_TEXT.patchBatchTitle}</h2><p className={styles.cardSummary}>{RUNTIME_CENTER_TEXT.patchBatchSummary}</p></div><Tag>{patchEntries.length}</Tag></div>
              <div className={styles.actionStrip}>
                <Button size="small" onClick={() => setSelectedPatchIds(patchEntries.map((entry) => entry.id))}>{RUNTIME_CENTER_TEXT.selectAll}</Button>
                <Button size="small" onClick={() => setSelectedPatchIds([])}>{RUNTIME_CENTER_TEXT.clearSelection}</Button>
                <Button type="primary" loading={governanceBusyKey === "patches-approve"} onClick={() => { void handlePatchBatch("approve"); }}>{RUNTIME_CENTER_TEXT.batchApprove}</Button>
                <Button loading={governanceBusyKey === "patches-apply"} onClick={() => { void handlePatchBatch("apply"); }}>{RUNTIME_CENTER_TEXT.batchApply}</Button>
                <Button loading={governanceBusyKey === "patches-rollback"} onClick={() => { void handlePatchBatch("rollback"); }}>{RUNTIME_CENTER_TEXT.batchRollback}</Button>
                <Button danger loading={governanceBusyKey === "patches-reject"} onClick={() => { void handlePatchBatch("reject"); }}>{RUNTIME_CENTER_TEXT.batchReject}</Button>
              </div>
              {patchEntries.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={RUNTIME_CENTER_TEXT.noVisiblePatches} /> : <div className={styles.selectionList}>{patchEntries.map((entry) => { const localizedTitle = translateRuntimeEntryTitle("patches", entry.title); const localizedSummary = translateRuntimeEntrySummary("patches", entry.summary); return <div key={entry.id} className={styles.selectionRow}><Checkbox checked={selectedPatchIds.includes(entry.id)} onChange={() => toggleSelection(selectedPatchIds, entry.id, setSelectedPatchIds)} /><div className={styles.selectionBody}><button type="button" className={styles.entryTitleButton} onClick={() => { if (entry.route) { void openSurfaceRoute(entry.route, localizedTitle); } }}>{localizedTitle}</button><div className={styles.selectionMeta}><Tag color={runtimeStatusColor(entry.status)}>{translateRuntimeStatus(entry.status)}</Tag><Tag>{translateRuntimeEntryKind(entry.kind)}</Tag>{entry.owner ? <span>{localizeRuntimeText(entry.owner)}</span> : null}<span>{formatTimestamp(entry.updated_at)}</span></div>{localizedSummary ? <p className={styles.selectionSummary}>{localizedSummary}</p> : null}</div></div>; })}</div>}
            </Card>
          </section>
        </div>
      ) : null}

      {activeTab === "recovery" ? (
        <div className={styles.tabStack}>
          <section className={styles.metrics}>
            <Card className={styles.metricCard}><div className={styles.metricIcon}><RotateCcw size={18} /></div><div><div className={styles.metricLabel}>{RUNTIME_CENTER_TEXT.recoveryReason}</div><div className={styles.metricValueSmall}>{localizeRuntimeText(String(recoverySummary?.reason ?? "startup"))}</div></div></Card>
            <Card className={styles.metricCard}><div className={styles.metricIcon}><ShieldCheck size={18} /></div><div><div className={styles.metricLabel}>{RUNTIME_CENTER_TEXT.selfCheckStatus}</div><div className={styles.metricValueSmall}>{translateRuntimeStatus(selfCheck?.overall_status ?? "pending")}</div></div></Card>
            <Card className={styles.metricCard}><div className={styles.metricIcon}><Activity size={18} /></div><div><div className={styles.metricLabel}>{RUNTIME_CENTER_TEXT.recoveryItems}</div><div className={styles.metricValue}>{recoveryRows.length}</div></div></Card>
            <Card className={styles.metricCard}><div className={styles.metricIcon}><Bot size={18} /></div><div><div className={styles.metricLabel}>{RUNTIME_CENTER_TEXT.selfCheckChecks}</div><div className={styles.metricValue}>{selfCheck?.checks.length ?? 0}</div></div></Card>
          </section>
          {recoveryError ? <Alert showIcon type="error" message={recoveryError} /> : null}
          <section className={styles.panelGrid}>
            <Row gutter={[24, 24]}>
              <Col xs={24} lg={10}>
                <Card className="baize-card" style={{ height: "100%" }}>
                  <div className={styles.panelHeader}><div><h2 className={styles.cardTitle}>{RUNTIME_CENTER_TEXT.recoveryLedger}</h2><p className={styles.cardSummary}>{RUNTIME_CENTER_TEXT.recoveryLedgerSummary}</p></div><Space size={8}><Button size="small" loading={recoveryBusyKey === "recovery-refresh"} onClick={() => { void handleRecoveryRefresh(); }}>{"刷新"}</Button><Button size="small" onClick={() => { void openSurfaceRoute("/api/runtime-center/recovery/latest", RUNTIME_CENTER_TEXT.recoveryLedger); }}>{RUNTIME_CENTER_TEXT.openDetail}</Button></Space></div>
                  {recoveryLoading && !recoverySummary ? <Spin /> : recoveryRows.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={RUNTIME_CENTER_TEXT.noRecoverySummary} /> : <Descriptions size="small" column={1} bordered items={recoveryRows.map(([label, value]) => ({ key: label, label, children: value }))} />}
                </Card>
              </Col>
              <Col xs={24} lg={14}>
                <Card className="baize-card" style={{ height: "100%" }}>
                  <div className={styles.panelHeader}><div><h2 className={styles.cardTitle}>{RUNTIME_CENTER_TEXT.selfCheckPanel}</h2><p className={styles.cardSummary}>{RUNTIME_CENTER_TEXT.selfCheckPanelSummary}</p></div><Space size={8}><Tag color={runtimeStatusColor(selfCheck?.overall_status ?? "pending")}>{translateRuntimeStatus(selfCheck?.overall_status ?? "pending")}</Tag><Button size="small" loading={recoveryBusyKey === "self-check"} onClick={() => { void handleSelfCheck(); }}>{RUNTIME_CENTER_TEXT.runSelfCheck}</Button></Space></div>
                  {!selfCheck ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={RUNTIME_CENTER_TEXT.noSelfCheck} /> : <><div className={styles.metrics} style={{ marginBottom: 16 }}>{healthHighlights.map((check) => <Card key={check.name} className={styles.metricCard}><div className={styles.metricIcon}><ShieldCheck size={18} /></div><div><div className={styles.metricLabel}>{translateRuntimeFieldLabel(check.name)}</div><div className={styles.metricValueSmall}>{translateRuntimeStatus(check.status)}</div><div className={styles.selectionSummary}>{localizeRuntimeText(check.summary)}</div></div></Card>)}</div><div className={styles.checkList}>{selfCheck.checks.map((check) => <div key={check.name} className={styles.checkRow}><div className={styles.checkHeader}><div><div className={styles.checkTitle}>{translateRuntimeFieldLabel(check.name)}</div><div className={styles.selectionSummary}>{localizeRuntimeText(check.summary)}</div></div><Tag color={runtimeStatusColor(check.status)}>{translateRuntimeStatus(check.status)}</Tag></div>{Object.keys(check.meta).length > 0 ? <pre className={styles.detailPre}>{primitiveValue(check.meta)}</pre> : null}</div>)}</div></>}
                </Card>
              </Col>
            </Row>
          </section>
        </div>
      ) : null}

      {activeTab === "automation" ? (
        <AutomationTab
          focusScope={focusScope}
          refreshSignal={data?.generated_at}
          openDetail={(route, title) => openSurfaceRoute(route, title || routeTitle(route))}
          onRuntimeChanged={() => reload()}
        />
      ) : null}

      {renderDetailDrawer(
        detail,
        detailLoading,
        detailError,
        closeDetail,
        (route, title) => {
          void openSurfaceRoute(route, title || routeTitle(route));
        },
      )}
    </div>
  );
}

