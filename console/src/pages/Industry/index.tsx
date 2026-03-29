import { useCallback } from "react";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Descriptions,
  Empty,
  Form,
  Input,
  List,
  Popconfirm,
  Row,
  Select,
  Space,
  Spin,
  Tag,
  Modal,
  Popover,
  Typography,
} from "antd";
import { DeleteOutlined, EditOutlined, PlusOutlined, ReloadOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import type {
  IndustryCapabilityRecommendationSection,
  IndustryDraftPlan,
  IndustryRuntimeAgentReport,
  IndustryRuntimeAssignment,
  IndustryRuntimeBacklogItem,
} from "../../api/modules/industry";
import type { MediaAnalysisSummary } from "../../api/modules/media";
import {
  localizeRemoteSkillText,
  presentRecommendationCapabilityFamily,
  presentRecommendationInstallKind,
  presentRecommendationRiskLevel,
  presentRecommendationSourceKind,
  presentRemoteSkillName,
  presentRemoteSkillSummary,
} from "../../utils/remoteSkillPresentation";
import { normalizeSpiderMeshBrand } from "../../utils/brand";
import { employmentModeColor } from "../../runtime/executionPresentation";
import { buildStaffingPresentation } from "../../runtime/staffingGapPresentation";
import {
  analysisStatusColor,
  buildAnalysisModeOptions,
  formatAnalysisMode,
  formatAnalysisStatus,
  formatAnalysisWritebackStatus,
  formatMediaType,
  mediaTypeColor,
  resolveMediaTitle,
} from "../../utils/mediaPresentation";

import {
  INDUSTRY_TEXT,
  INDUSTRY_EXPERIENCE_TEXT,
  formatCountLabel,
  formatIndustryDetailStats,
  uniqueStrings,
  CAPABILITY_FAMILY_OPTIONS,
  INSTALL_ASSIGNMENT_MODE_OPTIONS,
  LinesTextArea,
  type IndustryBriefFormValues,
  createBlankRole,
  createBlankGoal,
  createBlankSchedule,
  formatIndustryDisplayToken,
  presentIndustryEmploymentMode,
  presentIndustryReadinessStatus,
  presentIndustryRiskLevel,
  presentIndustryRoleClass,
  presentIndustryRuntimeStatus,
  readinessColor,
  roleColor,
  isSystemRole,
  formatTimestamp,
  presentText,
  presentList,
  runtimeStatusColor,
  deriveIndustryAgentStatus,
  deriveIndustryScheduleStatus,
  deriveIndustryTeamStatus,
} from "./pageHelpers";
import IndustryRuntimeCockpitPanel from "./IndustryRuntimeCockpitPanel";
import IndustryPlanningSurface from "./runtimePlanningSurface";
import { useIndustryPageState } from "./useIndustryPageState";

const { Paragraph, Text } = Typography;
const { TextArea } = Input;

function presentRecommendationSubsectionTitle(
  section: IndustryCapabilityRecommendationSection,
): string {
  if (section.section_kind === "execution-core") {
    return "编排能力";
  }
  if (section.section_kind === "system-baseline") {
    return "基础运行";
  }
  if (section.section_kind === "shared") {
    return "多人共用";
  }
  return normalizeSpiderMeshBrand(section.role_name || section.title) || section.title;
}

function isFocusedAssignment(
  assignment: IndustryRuntimeAssignment,
  selection: { selection_kind: "assignment" | "backlog"; assignment_id?: string | null } | null | undefined,
): boolean {
  return Boolean(
    assignment.selected ||
      (selection?.selection_kind === "assignment" &&
        selection.assignment_id === assignment.assignment_id),
  );
}

function isFocusedBacklog(
  backlogItem: IndustryRuntimeBacklogItem,
  selection: { selection_kind: "assignment" | "backlog"; backlog_item_id?: string | null } | null | undefined,
): boolean {
  return Boolean(
    backlogItem.selected ||
      (selection?.selection_kind === "backlog" &&
        selection.backlog_item_id === backlogItem.backlog_item_id),
  );
}

function resolveReportWorkContextId(report: IndustryRuntimeAgentReport): string | null {
  const workContextId = report.work_context_id?.trim();
  if (workContextId) {
    return workContextId;
  }
  const metadata = report.metadata;
  if (
    metadata &&
    typeof metadata === "object" &&
    typeof metadata.work_context_id === "string" &&
    metadata.work_context_id.trim()
  ) {
    return metadata.work_context_id.trim();
  }
  return null;
}

function runtimeSurfaceCardStyle(selected: boolean) {
  return {
    borderRadius: 12,
    border: `1px solid ${
      selected ? "var(--ant-primary-color, #1677ff)" : "var(--baize-border-color)"
    }`,
    background: selected ? "rgba(22,119,255,0.08)" : "rgba(255,255,255,0.02)",
    boxShadow: selected ? "0 0 0 1px rgba(22,119,255,0.12)" : "none",
  } as const;
}

export default function IndustryPage() {
  const navigate = useNavigate();
  const locale = "zh-CN";
  const [briefForm] = Form.useForm<IndustryBriefFormValues>();
  const [draftForm] = Form.useForm<IndustryDraftPlan>();
  const {
    allTeams,
    bootstrapLoading,
    briefMediaBusy,
    briefMediaItems,
    briefMediaLink,
    briefModalOpen,
    briefUploadInputRef,
    deletingInstanceId,
    detail,
    draftAgents,
    draftCounts,
    draftGenerationSummary,
    draftGoals,
    draftSchedules,
    draftTeamLabel,
    draftTeamSummary,
    error,
    handleAddBriefMediaLink,
    handleAddCustomInstallItem,
    handleBootstrap,
    handleBriefMediaModeChange,
    handleBriefUploadChange,
    handleChangeRecommendationReviewAcknowledgement,
    handleChangeRecommendationTargets,
    handleDeleteInstance,
    handleClearRuntimeFocus,
    handleOpenAgentReportChat,
    handleOpenExecutionCoreChat,
    handlePatchInstallPlanItem,
    handlePreview,
    handleRemoveBriefMediaItem,
    handleRemoveInstallPlanItem,
    handleSelectAssignmentFocus,
    handleSelectBacklogFocus,
    handleToggleRecommendation,
    hasCapabilityPlanning,
    installPlan,
    installPlanByRecommendationId,
    isEditing,
    isEditingExistingTeam,
    loadInstanceIntoDraft,
    loadInstances,
    loadingDetail,
    loadingInstances,
    preview,
    previewLoading,
    recommendationById,
    recommendationDisplayGroups,
    recommendationWarnings,
    retiredInstances,
    roleOptions,
    selectedExecutionCoreRole,
    selectedInstanceId,
    selectedSummary,
    setBriefMediaLink,
    setBriefModalOpen,
    setDraftSourceInstanceId,
    setError,
    setPreview,
    setSelectedInstanceId,
    watchedExperienceMode,
  } = useIndustryPageState({
    briefForm,
    draftForm,
    navigate,
  });
  const focusSelection = detail?.focus_selection || null;
  const staffingPresentation = buildStaffingPresentation(detail?.staffing);
  const renderMediaAnalysisList = useCallback(
    (
      analyses: MediaAnalysisSummary[],
      options?: {
        emptyText?: string;
        adoptedTag?: string;
        showWriteback?: boolean;
      },
    ) => {
      if (!analyses.length) {
        return (
          <Empty
            description={options?.emptyText || "暂无素材分析结果"}
            style={{ margin: "8px 0" }}
          />
        );
      }
      return (
        <List
          size="small"
          style={{ marginTop: 8 }}
          dataSource={analyses}
          renderItem={(analysis) => {
            const mediaType =
              analysis.detected_media_type || "unknown";
            const summary =
              analysis.summary ||
              analysis.key_points?.slice(0, 2).join(" / ") ||
              "暂无摘要";
            return (
              <List.Item style={{ padding: "10px 0" }}>
                <div style={{ width: "100%" }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      gap: 12,
                      alignItems: "flex-start",
                      flexWrap: "wrap",
                    }}
                  >
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <Space wrap>
                        <Text strong style={{ color: "var(--baize-text-main)" }}>
                          {resolveMediaTitle(analysis)}
                        </Text>
                        <Tag color={mediaTypeColor(mediaType)}>
                          {formatMediaType(mediaType)}
                        </Tag>
                        <Tag>{formatAnalysisMode(analysis.analysis_mode)}</Tag>
                        <Tag color={analysisStatusColor(analysis.status)}>
                          {formatAnalysisStatus(analysis.status)}
                        </Tag>
                        {options?.adoptedTag ? <Tag color="green">{options.adoptedTag}</Tag> : null}
                        {options?.showWriteback && analysis.strategy_writeback_status ? (
                          <Tag>{`策略 ${formatAnalysisWritebackStatus(analysis.strategy_writeback_status)}`}</Tag>
                        ) : null}
                        {options?.showWriteback && analysis.backlog_writeback_status ? (
                          <Tag>{`待办 ${formatAnalysisWritebackStatus(analysis.backlog_writeback_status)}`}</Tag>
                        ) : null}
                      </Space>
                      <Paragraph style={{ margin: "8px 0 0" }}>{summary}</Paragraph>
                      {analysis.key_points?.length ? (
                        <Text type="secondary" style={{ display: "block" }}>
                          {analysis.key_points.slice(0, 3).join(" / ")}
                        </Text>
                      ) : null}
                      {(analysis.warnings || []).map((warning) => (
                        <Alert
                          key={`${analysis.analysis_id}:${warning}`}
                          type="warning"
                          showIcon
                          message={warning}
                          style={{ marginTop: 8 }}
                        />
                      ))}
                    </div>
                  </div>
                </div>
              </List.Item>
            );
          }}
        />
      );
    },
    [],
  );

  return (
    <div className="page-container" style={{ display: "flex", flexDirection: "column", gap: 16, paddingBottom: 24 }}>
      <Card className="baize-page-header">
        <div className="baize-page-header-content">
          <div>
            <h1 className="baize-page-header-title">{INDUSTRY_TEXT.pageTitle}</h1>
            <p className="baize-page-header-description">{INDUSTRY_EXPERIENCE_TEXT.pageDescription}</p>
          </div>
          <div className="baize-page-header-actions">
            <Button icon={<ReloadOutlined />} onClick={() => void loadInstances()} className="baize-btn">刷新</Button>
          </div>
        </div>
      </Card>

      {error ? <Alert type="error" showIcon message={error} closable onClose={() => setError(null)} /> : null}

      {/* Brief Modal */}
      <Modal
        title={INDUSTRY_TEXT.prepareBrief}
        open={briefModalOpen}
        onCancel={() => setBriefModalOpen(false)}
        footer={null}
        width={640}
        destroyOnClose
      >
        <Paragraph type="secondary" style={{ marginBottom: 16 }}>{INDUSTRY_EXPERIENCE_TEXT.prepareBriefHint}</Paragraph>
        <Form form={briefForm} layout="vertical" initialValues={{ experience_mode: "system-led" }} onFinish={(values) => { void handlePreview(values).then(() => setBriefModalOpen(false)); }}>
          <Form.Item label={INDUSTRY_TEXT.formIndustry} name="industry" rules={[{ required: true, message: INDUSTRY_TEXT.formIndustryRequired }]}>
            <Input placeholder={INDUSTRY_TEXT.formIndustryPlaceholder} />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}><Form.Item label={INDUSTRY_TEXT.formCompany} name="company_name"><Input placeholder={INDUSTRY_TEXT.formCompanyPlaceholder} /></Form.Item></Col>
            <Col span={12}><Form.Item label={INDUSTRY_TEXT.formProduct} name="product"><Input placeholder={INDUSTRY_TEXT.formProductPlaceholder} /></Form.Item></Col>
          </Row>
          <Form.Item label={INDUSTRY_TEXT.formTargetCustomers} name="target_customers"><TextArea rows={2} placeholder={INDUSTRY_TEXT.formTargetCustomersPlaceholder} /></Form.Item>
          <Form.Item label={INDUSTRY_TEXT.formGoals} name="goals"><TextArea rows={2} placeholder={INDUSTRY_TEXT.formGoalsPlaceholder} /></Form.Item>
          <Form.Item label={INDUSTRY_TEXT.formConstraints} name="constraints"><TextArea rows={2} placeholder={INDUSTRY_TEXT.formConstraintsPlaceholder} /></Form.Item>
          <Form.Item label={INDUSTRY_EXPERIENCE_TEXT.formExperienceMode} name="experience_mode">
            <Select options={[{ label: INDUSTRY_EXPERIENCE_TEXT.formExperienceModeSystemLed, value: "system-led" }, { label: INDUSTRY_EXPERIENCE_TEXT.formExperienceModeOperatorGuided, value: "operator-guided" }]} />
          </Form.Item>
          <Form.Item label={INDUSTRY_EXPERIENCE_TEXT.formExperienceNotes} name="experience_notes">
            <TextArea rows={2} placeholder={watchedExperienceMode === "operator-guided" ? INDUSTRY_EXPERIENCE_TEXT.formExperienceNotesPlaceholder : "如果没有现成经验，可以留空，让系统先补齐完整执行闭环。"} />
          </Form.Item>
          <Form.Item label={INDUSTRY_EXPERIENCE_TEXT.formOperatorRequirements} name="operator_requirements"><TextArea rows={2} placeholder={INDUSTRY_EXPERIENCE_TEXT.formOperatorRequirementsPlaceholder} /></Form.Item>
          <Form.Item label={INDUSTRY_TEXT.formNotes} name="notes"><TextArea rows={2} placeholder={INDUSTRY_TEXT.formNotesPlaceholder} /></Form.Item>
          <div
            style={{
              marginBottom: 16,
              padding: 12,
              borderRadius: 12,
              border: "1px solid var(--baize-border-color)",
              background: "rgba(255,255,255,0.02)",
            }}
          >
            <Text strong style={{ color: "var(--baize-text-main)" }}>
              素材入口
            </Text>
            <Paragraph type="secondary" style={{ margin: "8px 0 12px" }}>
              支持链接、本地视频、音频和文档。视频可在这里切换分析模式，预览时会自动写回身份草案上下文。            </Paragraph>
            <Space.Compact style={{ width: "100%" }}>
              <Input
                placeholder="粘贴文章、视频、音频或文档链接"
                value={briefMediaLink}
                onChange={(event) => setBriefMediaLink(event.target.value)}
                onPressEnter={() => void handleAddBriefMediaLink()}
              />
              <Button
                onClick={() => void handleAddBriefMediaLink()}
                loading={briefMediaBusy}
              >
                添加链接
              </Button>
              <Button
                onClick={() => briefUploadInputRef.current?.click()}
                loading={briefMediaBusy}
              >
                上传文件
              </Button>
            </Space.Compact>
            <input
              ref={briefUploadInputRef}
              type="file"
              multiple
              hidden
              accept="video/*,audio/*,.pdf,.doc,.docx,.txt,.md,.markdown,.csv,.tsv,.json,.html,.htm,.xml,.yml,.yaml,.ppt,.pptx,.xlsx,.xls,.rtf"
              onChange={(event) => {
                void handleBriefUploadChange(event);
              }}
            />
            {briefMediaItems.length ? (
              <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 10 }}>
                {briefMediaItems.map((item) => {
                  const mediaType =
                    item.source.detected_media_type ||
                    item.source.media_type ||
                    "unknown";
                  const isVideo = mediaType === "video";
                  const modeOptions = buildAnalysisModeOptions(
                    mediaType,
                    item.analysis_mode_options,
                  );
                  return (
                    <div
                      key={item.id}
                      style={{
                        padding: 12,
                        borderRadius: 10,
                        border: "1px solid var(--baize-border-color)",
                        background: "rgba(255,255,255,0.03)",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "flex-start",
                          gap: 12,
                          flexWrap: "wrap",
                        }}
                      >
                        <div style={{ minWidth: 0, flex: 1 }}>
                          <Space wrap>
                            <Text strong style={{ color: "var(--baize-text-main)" }}>
                              {resolveMediaTitle(item.source)}
                            </Text>
                            <Tag color={mediaTypeColor(mediaType)}>
                              {formatMediaType(mediaType)}
                            </Tag>
                            <Tag>
                              {formatAnalysisMode(item.source.analysis_mode || "standard")}
                            </Tag>
                          </Space>
                          {(item.source.url || item.source.filename) ? (
                            <Text type="secondary" style={{ display: "block", marginTop: 6 }}>
                              {item.source.url || item.source.filename}
                            </Text>
                          ) : null}
                        </div>
                        <Button
                          type="text"
                          danger
                          icon={<DeleteOutlined />}
                          onClick={() => handleRemoveBriefMediaItem(item.id)}
                        />
                      </div>
                      {isVideo ? (
                        <div style={{ marginTop: 10 }}>
                          <Text type="secondary" style={{ display: "block", marginBottom: 6 }}>
                            视频分析模式
                          </Text>
                          <Select
                            value={item.source.analysis_mode || "video-lite"}
                            options={modeOptions}
                            style={{ width: 220 }}
                            onChange={(value) => handleBriefMediaModeChange(item.id, value)}
                          />
                          {!item.analysis_mode_options.includes("video-deep") ? (
                            <Text type="secondary" style={{ display: "block", marginTop: 6 }}>
                              当前运行时仅支持 `video-lite`，深度分析暂未开放。
                            </Text>
                          ) : null}
                        </div>
                      ) : null}
                      {(item.warnings || []).map((warning) => (
                        <Alert
                          key={`${item.id}:${warning}`}
                          type="warning"
                          showIcon
                          message={warning}
                          style={{ marginTop: 8 }}
                        />
                      ))}
                    </div>
                  );
                })}
              </div>
            ) : (
              <Paragraph type="secondary" style={{ margin: "12px 0 0" }}>
                还没有添加素材。预览后这里的素材会生成结构化摘要并写入身份草案上下文。              </Paragraph>
            )}
          </div>
          <Button type="primary" htmlType="submit" loading={previewLoading} block>{INDUSTRY_TEXT.previewPlan}</Button>
        </Form>
      </Modal>

      {/* Main Layout */}
      <div style={{ display: "grid", gridTemplateColumns: "340px minmax(0, 1fr)", gap: 16, minHeight: 0 }}>
        {/* Left: Team List */}
        <Card
          className="baize-card"
          title={<span style={{ color: "var(--baize-text-main)" }}>身份</span>}
          extra={<Button type="primary" size="small" onClick={() => setBriefModalOpen(true)}>创建身份</Button>}
          bodyStyle={{ padding: 0 }}
        >
          {loadingInstances ? (
            <div style={{ padding: 24, textAlign: "center" }}><Spin /></div>
          ) : allTeams.length === 0 ? (
            <Empty description={INDUSTRY_TEXT.noInstances} style={{ padding: 24 }} />
          ) : (
            <div style={{ maxHeight: "calc(100vh - 240px)", overflow: "auto" }}>
              {allTeams.map((item) => {
                const isSelected = item.instance_id === selectedInstanceId && !isEditing;
                const isRetired = retiredInstances.some((r) => r.instance_id === item.instance_id);
                return (
                  <div
                    key={item.instance_id}
                    onClick={() => { setSelectedInstanceId(item.instance_id); setPreview(null); setDraftSourceInstanceId(null); }}
                    style={{
                      padding: "12px 16px",
                      cursor: "pointer",
                      background: isSelected ? "var(--baize-selected-bg)" : undefined,
                      borderBottom: "1px solid var(--baize-border-color)",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "flex-start",
                      gap: 8,
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                        <Text strong style={{ color: "var(--baize-text-main)" }}>{item.label}</Text>
                        <Tag color={runtimeStatusColor(item.status)} style={{ margin: 0 }}>{presentIndustryRuntimeStatus(item.status)}</Tag>
                        {isRetired ? <Tag color="default" style={{ margin: 0 }}>已退役</Tag> : null}
                      </div>
                      <Text type="secondary" style={{ fontSize: 12 }}>{formatTimestamp(item.updated_at, locale)}</Text>
                    </div>
                    <Popconfirm
                      title="确认删除这个团队吗？"
                      description="删除后将移除该团队及其运行记录。"
                      okText="确认删除"
                      cancelText="取消"
                      onConfirm={(e) => { e?.stopPropagation(); void handleDeleteInstance(item.instance_id); }}
                    >
                      <Button type="text" danger size="small" icon={<DeleteOutlined />} loading={deletingInstanceId === item.instance_id} onClick={(e) => e.stopPropagation()} />
                    </Popconfirm>
                  </div>
                );
              })}
            </div>
          )}
        </Card>

        {/* Right: Detail or Preview */}
        <Card
          className="baize-card"
          title={
            <span style={{ color: "var(--baize-text-main)" }}>
              {isEditing
                ? (isEditingExistingTeam ? INDUSTRY_TEXT.updateTeam : INDUSTRY_TEXT.previewTitle)
                : (detail?.team?.label || selectedSummary?.label || INDUSTRY_TEXT.industryDetail)}
            </span>
          }
          extra={
            isEditing ? (
              <Space wrap>
                <Button onClick={() => setBriefModalOpen(true)}>{INDUSTRY_TEXT.regenerateDraft}</Button>
                <Button type="primary" disabled={!preview?.can_activate} loading={bootstrapLoading} onClick={() => void handleBootstrap()}>
                  {isEditingExistingTeam ? INDUSTRY_TEXT.updateTeam : INDUSTRY_TEXT.activateTeam}
                </Button>
                <Button onClick={() => { setPreview(null); setDraftSourceInstanceId(null); }}>取消</Button>
              </Space>
            ) : detail ? (
              <Space wrap>
                <Button size="small" type="primary" onClick={() => void handleOpenExecutionCoreChat()} disabled={!selectedExecutionCoreRole}>
                  {INDUSTRY_EXPERIENCE_TEXT.openExecutionCoreChat}
                </Button>
                <Button size="small" icon={<EditOutlined />} onClick={loadInstanceIntoDraft}>编辑</Button>
              </Space>
            ) : null
          }
        >
          {/* Right card body */}
          {isEditing ? (
            /* 编辑 / 预览模式 */
            <Form form={draftForm} layout="vertical">
              <Space direction="vertical" size={24} style={{ width: "100%" }}>
                {!preview?.can_activate ? <Alert type="warning" showIcon message={INDUSTRY_TEXT.previewBlockedWarning} /> : null}
                {/* Team info - flat, no nested card */}
                <div>
                  <Text strong style={{ color: "var(--baize-text-muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em" }}>基本信息</Text>
                  <div style={{ marginTop: 8 }}>
                    <Descriptions size="small" column={1} bordered items={[
                      { key: "label", label: INDUSTRY_TEXT.teamLabel, children: draftTeamLabel || preview?.draft.team.label },
                      { key: "summary", label: INDUSTRY_TEXT.summaryLabel, children: draftTeamSummary || preview?.draft.team.summary },
                      { key: "activate", label: INDUSTRY_TEXT.activationLabel, children: preview?.can_activate ? INDUSTRY_TEXT.readyToActivate : INDUSTRY_TEXT.blocked },
                      { key: "counts", label: INDUSTRY_TEXT.detailStats, children: [
                        formatCountLabel(INDUSTRY_TEXT.metricRoles, draftCounts.roles),
                        formatCountLabel(INDUSTRY_TEXT.metricGoals, draftCounts.goals),
                        formatCountLabel(INDUSTRY_TEXT.metricSchedules, draftCounts.schedules),
                      ].join(" / ") },
                    ]} />
                  </div>
                </div>

                <div>
                  <Text strong style={{ color: "var(--baize-text-muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                    ????
                  </Text>
                  <Paragraph type="secondary" style={{ margin: "8px 0 0" }}>
                    Preview-stage media analyses appear here and will remain available as shared context after the identity is created.                  </Paragraph>
                  {(preview?.media_warnings || []).map((warning) => (
                    <Alert
                      key={`preview-media-warning:${warning}`}
                      type="warning"
                      showIcon
                      message={warning}
                      style={{ marginTop: 8 }}
                    />
                  ))}
                  {renderMediaAnalysisList(preview?.media_analyses || [], {
                    emptyText: "No media analysis is available in this preview yet.",
                    adoptedTag: "Included",
                  })}
                </div>

                {recommendationWarnings.length ? (
                  <div>
                    <Text strong style={{ color: "var(--baize-text-muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                      能力配置
                    </Text>
                    {recommendationWarnings.map((warning) => (
                      <Alert
                        key={`preview-capability-warning:${warning}`}
                        type="info"
                        showIcon
                        message={warning}
                        style={{ marginTop: 8 }}
                      />
                    ))}
                  </div>
                ) : null}

                {/* Recommendations - simplified with Popover */}
                {recommendationDisplayGroups.length ? (
                  <div>
                    <Text strong style={{ color: "var(--baize-text-muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em" }}>{INDUSTRY_TEXT.capabilityRecommendations}</Text>
                    {preview?.recommendation_pack?.summary ? <Paragraph type="secondary" style={{ margin: "8px 0 0" }}>{preview.recommendation_pack.summary}</Paragraph> : null}
                    {(preview?.recommendation_pack?.warnings || []).map((w) => <Alert key={w} type="warning" showIcon message={w} style={{ marginTop: 8 }} />)}
                    <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 12 }}>
                      {recommendationDisplayGroups.map((group) => (
                        <div
                          key={group.group_id}
                          style={{
                            padding: 12,
                            borderRadius: 12,
                            border: "1px solid rgba(15, 23, 42, 0.08)",
                            background: "rgba(15, 23, 42, 0.02)",
                          }}
                        >
                          <Text strong style={{ fontSize: 13 }}>{group.title}</Text>
                          <Paragraph type="secondary" style={{ margin: "4px 0 0", fontSize: 12 }}>
                            {group.summary}
                          </Paragraph>
                          <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
                            {group.sections.map((section) => {
                              const showSubsectionTitle =
                                group.sections.length > 1 || section.section_kind !== "execution-core";
                              return (
                                <div key={section.section_id}>
                                  {showSubsectionTitle ? (
                                    <Text type="secondary" style={{ fontSize: 12, fontWeight: 700 }}>
                                      {presentRecommendationSubsectionTitle(section)}
                                    </Text>
                                  ) : null}
                                  <div
                                    style={{
                                      marginTop: showSubsectionTitle ? 4 : 0,
                                      display: "flex",
                                      flexDirection: "column",
                                      gap: 2,
                                    }}
                                  >
                                    {section.items.map((rec) => {
                                      const plan = installPlanByRecommendationId[rec.recommendation_id];
                                      const checked = Boolean(plan);
                                      return (
                                        <Popover
                                          key={rec.recommendation_id}
                                          placement="right"
                                          title={presentRemoteSkillName({ slug: rec.template_id, title: rec.title, description: rec.description })}
                                          content={
                                            <div style={{ maxWidth: 360 }}>
                                              <Paragraph style={{ margin: 0 }}>{presentRemoteSkillSummary({ slug: rec.template_id, title: rec.title, description: rec.description })}</Paragraph>
                                              <Space wrap style={{ marginTop: 8 }}>
                                                <Tag>{presentRecommendationSourceKind(rec.source_kind)}</Tag>
                                                <Tag>{presentRecommendationInstallKind(rec.install_kind)}</Tag>
                                                <Tag>{presentRecommendationRiskLevel(rec.risk_level)}</Tag>
                                                {(rec.capability_families || []).map((f) => <Tag key={f} color="cyan">{presentRecommendationCapabilityFamily(f)}</Tag>)}
                                              </Space>
                                              {(rec.discovery_queries || []).length ? (
                                                <div style={{ marginTop: 8 }}>
                                                  <Text type="secondary" style={{ fontSize: 12 }}>妫€绱㈣瘝</Text>
                                                  <Space wrap style={{ marginTop: 4 }}>
                                                    {(rec.discovery_queries || []).map((query) => (
                                                      <Tag key={`query-${rec.recommendation_id}-${query}`} color="blue">{query}</Tag>
                                                    ))}
                                                  </Space>
                                                </div>
                                              ) : null}
                                              {(rec.match_signals || []).length ? (
                                                <div style={{ marginTop: 8 }}>
                                                  <Text type="secondary" style={{ fontSize: 12 }}>匹配信号</Text>
                                                  <Space wrap style={{ marginTop: 4 }}>
                                                    {(rec.match_signals || []).map((signal) => (
                                                      <Tag key={`signal-${rec.recommendation_id}-${signal}`} color="geekblue">{localizeRemoteSkillText(signal)}</Tag>
                                                    ))}
                                                  </Space>
                                                </div>
                                              ) : null}
                                              {(rec.governance_path || []).length ? (
                                                <Paragraph type="secondary" style={{ margin: "8px 0 0", fontSize: 12 }}>
                                                  {`Governance path: ${(rec.governance_path || []).join(" -> ")}`}
                                                </Paragraph>
                                              ) : null}
                                              {(rec.notes || []).length ? (
                                                <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 4 }}>
                                                  <Text type="secondary" style={{ fontSize: 12 }}>Notes</Text>
                                                  {(rec.notes || []).slice(0, 4).map((note) => (
                                                    <Text key={`note-${rec.recommendation_id}-${note}`} style={{ fontSize: 12 }}>
                                                      {localizeRemoteSkillText(note)}
                                                    </Text>
                                                  ))}
                                                </div>
                                              ) : null}
                                              {rec.review_summary ? <Alert type="info" showIcon message={localizeRemoteSkillText(rec.review_summary)} style={{ marginTop: 8 }} /> : null}
                                              {rec.review_required && checked ? (
                                                <Checkbox
                                                  checked={Boolean(plan?.review_acknowledged)}
                                                  onChange={(e) => handleChangeRecommendationReviewAcknowledgement(rec.recommendation_id, e.target.checked)}
                                                  style={{ marginTop: 8 }}
                                                >我已审查该远程安装项</Checkbox>
                                              ) : null}
                                              <div style={{ marginTop: 8 }}>
                                                <Text type="secondary" style={{ fontSize: 12 }}>{INDUSTRY_TEXT.installTargets}</Text>
                                                <Select
                                                  mode="multiple" size="small" style={{ width: "100%", marginTop: 4 }}
                                                  value={plan?.target_agent_ids || rec.target_agent_ids || []}
                                                  options={roleOptions}
                                                  disabled={!checked || rec.installed}
                                                  onChange={(v) => handleChangeRecommendationTargets(rec.recommendation_id, v)}
                                                />
                                              </div>
                                            </div>
                                          }
                                        >
                                          <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 0" }}>
                                            <Checkbox checked={checked} disabled={rec.installed} onChange={(e) => handleToggleRecommendation(rec, e.target.checked)} />
                                            <Text style={{ flex: 1, color: "var(--baize-text-main)" }}>
                                              {presentRemoteSkillName({ slug: rec.template_id, title: rec.title, description: rec.description })}
                                            </Text>
                                            <Tag color={rec.installed ? "success" : "processing"} style={{ margin: 0 }}>
                                              {rec.installed ? INDUSTRY_TEXT.installed : INDUSTRY_TEXT.recommended}
                                            </Tag>
                                          </div>
                                        </Popover>
                                      );
                                    })}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
                {/* Install plan - simplified */}
                {hasCapabilityPlanning ? (
                  <div>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <Text strong style={{ color: "var(--baize-text-muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em" }}>安装计划</Text>
                      <Button size="small" icon={<PlusOutlined />} onClick={handleAddCustomInstallItem}>新增</Button>
                    </div>
                    {installPlan.length ? (
                      <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 2 }}>
                        {installPlan.map((item, index) => {
                          const rec = item.recommendation_id ? recommendationById.get(item.recommendation_id) : undefined;
                          const title = rec?.title || item.template_id || `自定义安装项 ${index + 1}`;
                          const isCustom = !rec;
                          return (
                            <Popover
                              key={item.plan_item_key}
                              placement="right"
                              title={presentRemoteSkillName({ slug: item.template_id, title, description: rec?.description || "" })}
                              content={
                                <div style={{ maxWidth: 360 }}>
                                  <Row gutter={[8, 8]}>
                                    <Col span={12}>
                                      <Text type="secondary" style={{ fontSize: 12 }}>安装类型</Text>
                                      <Select size="small" style={{ width: "100%" }} value={item.install_kind} disabled={!isCustom}
                                        options={[
                                          { label: "MCP / 安装模板", value: "mcp-template" },
                                          { label: "官方 MCP Registry", value: "mcp-registry" },
                                          { label: "系统内置能力", value: "builtin-runtime" },
                                          { label: "SkillHub 技能", value: "hub-skill" },
                                        ]}
                                        onChange={(v) => handlePatchInstallPlanItem(item.plan_item_key, {
                                          install_kind: v,
                                          source_kind:
                                            v === "hub-skill"
                                              ? "hub-search"
                                              : v === "mcp-registry"
                                                ? "mcp-registry"
                                                : "install-template",
                                        })}
                                      />
                                    </Col>
                                    <Col span={12}>
                                      <Text type="secondary" style={{ fontSize: 12 }}>挂载方式</Text>
                                      <Select size="small" style={{ width: "100%" }} value={item.capability_assignment_mode || "merge"} options={INSTALL_ASSIGNMENT_MODE_OPTIONS}
                                        onChange={(v) => handlePatchInstallPlanItem(item.plan_item_key, { capability_assignment_mode: v })}
                                      />
                                    </Col>
                                    <Col span={24}>
                                      <Text type="secondary" style={{ fontSize: 12 }}>{INDUSTRY_TEXT.installTargets}</Text>
                                      <Select mode="multiple" size="small" style={{ width: "100%" }} value={item.target_agent_ids || []} options={roleOptions}
                                        onChange={(v) => handlePatchInstallPlanItem(item.plan_item_key, { target_agent_ids: uniqueStrings(v) })}
                                      />
                                    </Col>
                                  </Row>
                                  {rec?.review_required ? (
                                    <Checkbox checked={Boolean(item.review_acknowledged)} style={{ marginTop: 8 }}
                                      onChange={(e) => handlePatchInstallPlanItem(item.plan_item_key, { review_acknowledged: e.target.checked })}
                                    >我已审查该远程安装项</Checkbox>
                                  ) : null}
                                </div>
                              }
                            >
                              <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 0" }}>
                                <Text style={{ flex: 1, color: "var(--baize-text-main)" }}>
                                  {presentRemoteSkillName({ slug: item.template_id, title, description: rec?.description || "" })}
                                </Text>
                                <Tag style={{ margin: 0 }}>{presentRecommendationInstallKind(item.install_kind)}</Tag>
                                <Button type="text" danger size="small" icon={<DeleteOutlined />} onClick={() => handleRemoveInstallPlanItem(item.plan_item_key)} />
                              </div>
                            </Popover>
                          );
                        })}
                      </div>
                    ) : (
                      <Empty description="还没有安装计划，可从推荐中勾选或手工新增。" style={{ margin: "8px 0" }} />
                    )}
                  </div>
                ) : null}

                {/* Team name / summary - flat fields */}
                <div>
                  <Text strong style={{ color: "var(--baize-text-muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em" }}>身份设置</Text>
                  <Row gutter={[16, 0]} style={{ marginTop: 8 }}>
                    <Col xs={24} md={12}><Form.Item label={INDUSTRY_TEXT.teamLabel} name={["team", "label"]}><Input /></Form.Item></Col>
                    <Col xs={24} md={12}><Form.Item label={INDUSTRY_TEXT.draftSummary} name="generation_summary"><Input /></Form.Item></Col>
                    <Col xs={24}><Form.Item label={INDUSTRY_TEXT.summaryLabel} name={["team", "summary"]}><TextArea rows={2} placeholder={INDUSTRY_TEXT.teamSummaryPlaceholder} /></Form.Item></Col>
                  </Row>
                </div>
                {/* Roles - flat list */}
                <div>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <Text strong style={{ color: "var(--baize-text-muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em" }}>{INDUSTRY_TEXT.teamRoles}</Text>
                    <Button
                      size="small"
                      htmlType="button"
                      onClick={() => {
                        draftForm.setFieldValue(["team", "agents"], [
                          ...draftAgents,
                          createBlankRole(),
                        ]);
                      }}
                    >
                      {INDUSTRY_TEXT.addRole}
                    </Button>
                  </div>
                  <Form.List name={["team", "agents"]}>
                    {(fields, { remove }) => (
                      <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 12 }}>
                        {fields.map((field, index) => {
                          const role = draftAgents[Number(field.name)];
                          const locked = isSystemRole(role);
                          const ref = role?.agent_id || role?.role_id || role?.role_name || role?.name;
                          return (
                            <div key={field.key} style={{ padding: 12, borderRadius: 8, border: "1px solid var(--baize-border-color)", background: "rgba(255,255,255,0.02)" }}>
                              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                                <Space wrap>
                                  <Text strong style={{ color: "var(--baize-text-main)" }}>{normalizeSpiderMeshBrand(role?.role_name || role?.name) || `${INDUSTRY_TEXT.roleFallback} ${index + 1}`}</Text>
                                  <Tag color={roleColor(role)}>{presentIndustryRoleClass(role?.agent_class)}</Tag>
                                  <Tag color={employmentModeColor(role?.employment_mode)}>{presentIndustryEmploymentMode(role?.employment_mode)}</Tag>
                                  <Tag>{role?.activation_mode === "on-demand" ? "按需唤起" : "常驻"}</Tag>
                                  <Tag>{presentIndustryRiskLevel(role?.risk_level)}</Tag>
                                </Space>
                                {locked ? <Text type="secondary" style={{ fontSize: 12 }}>{INDUSTRY_TEXT.systemRolesLockedHint}</Text> : <Button danger type="text" size="small" icon={<DeleteOutlined />} onClick={() => remove(field.name)} />}
                              </div>
                              <Row gutter={[12, 0]}>
                                <Col xs={24} md={8}><Form.Item label={INDUSTRY_TEXT.roleDisplayName} name={[field.name, "name"]} style={{ marginBottom: 8 }}><Input size="small" /></Form.Item></Col>
                                <Col xs={24} md={8}><Form.Item label={INDUSTRY_TEXT.roleTitle} name={[field.name, "role_name"]} style={{ marginBottom: 8 }}><Input size="small" /></Form.Item></Col>
                                <Col xs={24} md={8}><Form.Item label={INDUSTRY_TEXT.roleReportsTo} name={[field.name, "reports_to"]} style={{ marginBottom: 8 }}><Select size="small" allowClear options={roleOptions.filter((o) => o.value !== ref)} placeholder={INDUSTRY_TEXT.roleReportsToPlaceholder} /></Form.Item></Col>
                                <Col xs={24} md={8}><Form.Item label="雇佣方式" name={[field.name, "employment_mode"]} style={{ marginBottom: 8 }}><Select size="small" options={[{ label: "长期岗位", value: "career" }, { label: "临时岗位", value: "temporary" }]} /></Form.Item></Col>
                                <Col xs={24} md={8}><Form.Item label="激活方式" name={[field.name, "activation_mode"]} style={{ marginBottom: 8 }}><Select size="small" options={[{ label: "常驻", value: "persistent" }, { label: "按需唤起", value: "on-demand" }]} /></Form.Item></Col>
                                <Col xs={24}><Form.Item label={INDUSTRY_TEXT.roleMission} name={[field.name, "mission"]} style={{ marginBottom: 8 }}><TextArea rows={2} placeholder={INDUSTRY_TEXT.roleMissionPlaceholder} /></Form.Item></Col>
                                <Col xs={24} md={8}><Form.Item label={INDUSTRY_TEXT.roleEnvironment} name={[field.name, "environment_constraints"]} style={{ marginBottom: 8 }}><LinesTextArea rows={2} placeholder={INDUSTRY_TEXT.roleEnvironmentPlaceholder} /></Form.Item></Col>
                                <Col xs={24} md={8}><Form.Item label={INDUSTRY_TEXT.roleEvidence} name={[field.name, "evidence_expectations"]} style={{ marginBottom: 8 }}><LinesTextArea rows={2} placeholder={INDUSTRY_TEXT.roleEvidencePlaceholder} /></Form.Item></Col>
                                <Col xs={24} md={8}><Form.Item label="偏好能力族" name={[field.name, "preferred_capability_families"]} style={{ marginBottom: 8 }}><Select mode="multiple" size="small" options={CAPABILITY_FAMILY_OPTIONS} placeholder="选择更适合该岗位的能力族" /></Form.Item></Col>
                              </Row>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </Form.List>
                </div>

                {/* Goals - flat list */}
                <div>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <Text strong style={{ color: "var(--baize-text-muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em" }}>{INDUSTRY_TEXT.goalsTitle}</Text>
                    <Button
                      size="small"
                      htmlType="button"
                      onClick={() => {
                        draftForm.setFieldValue("goals", [
                          ...draftGoals,
                          createBlankGoal(roleOptions[0]?.value),
                        ]);
                      }}
                    >
                      {INDUSTRY_TEXT.addGoal}
                    </Button>
                  </div>
                  <Form.List name="goals">
                    {(fields, { remove }) => (
                      <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8 }}>
                        {fields.map((field, index) => (
                          <div key={field.key} style={{ padding: 12, borderRadius: 8, border: "1px solid var(--baize-border-color)", background: "rgba(255,255,255,0.02)" }}>
                            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                              <Text strong style={{ color: "var(--baize-text-main)" }}>{draftGoals[Number(field.name)]?.title || `${INDUSTRY_TEXT.goalTitle} ${index + 1}`}</Text>
                              <Button danger type="text" size="small" icon={<DeleteOutlined />} onClick={() => remove(field.name)} />
                            </div>
                            <Row gutter={[12, 0]}>
                              <Col xs={24} md={8}><Form.Item label={INDUSTRY_TEXT.goalOwner} name={[field.name, "owner_agent_id"]} style={{ marginBottom: 8 }}><Select size="small" options={roleOptions} /></Form.Item></Col>
                              <Col xs={24} md={8}><Form.Item label={INDUSTRY_TEXT.goalKind} name={[field.name, "kind"]} style={{ marginBottom: 8 }}><Input size="small" /></Form.Item></Col>
                              <Col xs={24} md={8}><Form.Item label={INDUSTRY_TEXT.goalTitle} name={[field.name, "title"]} style={{ marginBottom: 8 }}><Input size="small" /></Form.Item></Col>
                              <Col xs={24}><Form.Item label={INDUSTRY_TEXT.summaryLabel} name={[field.name, "summary"]} style={{ marginBottom: 8 }}><TextArea rows={1} placeholder={INDUSTRY_TEXT.goalSummaryPlaceholder} /></Form.Item></Col>
                              <Col xs={24}><Form.Item label={INDUSTRY_TEXT.planStepsLabel} name={[field.name, "plan_steps"]} style={{ marginBottom: 0 }}><LinesTextArea rows={2} placeholder={INDUSTRY_TEXT.goalPlanStepsPlaceholder} /></Form.Item></Col>
                            </Row>
                          </div>
                        ))}
                      </div>
                    )}
                  </Form.List>
                </div>
                {/* Schedules - flat list */}
                <div>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <Text strong style={{ color: "var(--baize-text-muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em" }}>{INDUSTRY_TEXT.schedulesTitle}</Text>
                    <Button
                      size="small"
                      htmlType="button"
                      onClick={() => {
                        draftForm.setFieldValue("schedules", [
                          ...draftSchedules,
                          createBlankSchedule(roleOptions[0]?.value),
                        ]);
                      }}
                    >
                      {INDUSTRY_TEXT.addSchedule}
                    </Button>
                  </div>
                  <Form.List name="schedules">
                    {(fields, { remove }) => (
                      <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8 }}>
                        {fields.map((field, index) => (
                          <div key={field.key} style={{ padding: 12, borderRadius: 8, border: "1px solid var(--baize-border-color)", background: "rgba(255,255,255,0.02)" }}>
                            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                              <Text strong style={{ color: "var(--baize-text-main)" }}>{draftSchedules[Number(field.name)]?.title || `${INDUSTRY_TEXT.scheduleTitle} ${index + 1}`}</Text>
                              <Button danger type="text" size="small" icon={<DeleteOutlined />} onClick={() => remove(field.name)} />
                            </div>
                            <Row gutter={[12, 0]}>
                              <Col xs={24} md={8}><Form.Item label={INDUSTRY_TEXT.scheduleOwner} name={[field.name, "owner_agent_id"]} style={{ marginBottom: 8 }}><Select size="small" options={roleOptions} /></Form.Item></Col>
                              <Col xs={24} md={8}><Form.Item label={INDUSTRY_TEXT.scheduleTitle} name={[field.name, "title"]} style={{ marginBottom: 8 }}><Input size="small" /></Form.Item></Col>
                              <Col xs={24} md={8}><Form.Item label={INDUSTRY_TEXT.cron} name={[field.name, "cron"]} style={{ marginBottom: 8 }}><Input size="small" /></Form.Item></Col>
                              <Col xs={24} md={8}><Form.Item label={INDUSTRY_TEXT.scheduleTimezone} name={[field.name, "timezone"]} style={{ marginBottom: 8 }}><Input size="small" /></Form.Item></Col>
                              <Col xs={24} md={8}><Form.Item label={INDUSTRY_TEXT.dispatchMode} name={[field.name, "dispatch_mode"]} style={{ marginBottom: 8 }}>
                                <Select size="small" options={[{ label: "流式", value: "stream" }, { label: "最终答复", value: "final" }]} />
                              </Form.Item></Col>
                              <Col xs={24} md={8}><Form.Item label={INDUSTRY_TEXT.summaryLabel} name={[field.name, "summary"]} style={{ marginBottom: 0 }}><Input size="small" placeholder={INDUSTRY_TEXT.scheduleSummaryPlaceholder} /></Form.Item></Col>
                            </Row>
                          </div>
                        ))}
                      </div>
                    )}
                  </Form.List>
                </div>

                {/* Readiness checks */}
                <div>
                  <Text strong style={{ color: "var(--baize-text-muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em" }}>{INDUSTRY_TEXT.readinessChecks}</Text>
                  <List
                    size="small"
                    style={{ marginTop: 8 }}
                    dataSource={preview?.readiness_checks || []}
                    renderItem={(item) => (
                      <List.Item style={{ padding: "6px 0" }}>
                        <Space wrap>
                          <Tag color={readinessColor(item.status)}>{presentIndustryReadinessStatus(item.status)}</Tag>
                          <Text style={{ color: "var(--baize-text-main)" }}>{item.title}</Text>
                          <Text type="secondary" style={{ fontSize: 12 }}>{item.detail}</Text>
                        </Space>
                      </List.Item>
                    )}
                  />
                </div>

                {draftGenerationSummary ? <Alert type="info" showIcon message={draftGenerationSummary} /> : null}
              </Space>
            </Form>
          ) : loadingDetail ? (
            <div style={{ padding: 48, textAlign: "center" }}><Spin /></div>
          ) : !detail ? (
            <Empty description={INDUSTRY_TEXT.selectTeamHint} />
          ) : true ? (
            <IndustryRuntimeCockpitPanel
              detail={detail}
              locale={locale}
              onClearRuntimeFocus={() => void handleClearRuntimeFocus()}
              onOpenAgentReportChat={(report) => void handleOpenAgentReportChat(report)}
              onSelectAssignmentFocus={(assignmentId) => void handleSelectAssignmentFocus(assignmentId)}
              onSelectBacklogFocus={(backlogItemId) => void handleSelectBacklogFocus(backlogItemId)}
            />
          ) : (
            /* 详情模式（只读） */
            <Space direction="vertical" size={24} style={{ width: "100%" }}>
              <Descriptions size="small" column={2} bordered items={[
                { key: "instance", label: INDUSTRY_TEXT.detailInstance, children: detail.instance_id },
                { key: "owner", label: INDUSTRY_TEXT.detailOwnerScope, children: detail.owner_scope },
                { key: "status", label: INDUSTRY_TEXT.detailStatus, children: presentIndustryRuntimeStatus(deriveIndustryTeamStatus(detail)) },
                { key: "stats", label: INDUSTRY_TEXT.statsLabel, children: formatIndustryDetailStats(detail.stats) },
              ]} />

              {focusSelection ? (
                <Alert
                  showIcon
                  type="info"
                  message={
                    focusSelection.selection_kind === "assignment"
                      ? "Focused Assignment"
                      : "Focused Backlog"
                  }
                  description={[
                    focusSelection.summary || focusSelection.title || "Runtime detail is scoped to a selected subview.",
                    focusSelection.status
                      ? `Status ${presentIndustryRuntimeStatus(focusSelection.status)}`
                      : null,
                  ]
                    .filter(Boolean)
                    .join(" | ")}
                  action={
                    <Button size="small" onClick={() => void handleClearRuntimeFocus()}>
                      Show full surface
                    </Button>
                  }
                />
              ) : null}

              {detail.execution ? (
                <div>
                  <Text strong style={{ color: "var(--baize-text-muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em" }}>执行面板</Text>
                  <div style={{ marginTop: 8 }}>
                    <Space wrap style={{ marginBottom: 8 }}>
                      <Tag color={runtimeStatusColor(detail.execution.status)}>{presentIndustryRuntimeStatus(detail.execution.status)}</Tag>
                      {detail.execution.current_owner ? <Tag>{detail.execution.current_owner}</Tag> : null}
                      {detail.execution.current_stage ? <Tag>{formatIndustryDisplayToken(detail.execution.current_stage)}</Tag> : null}
                      {detail.execution.updated_at ? <Text type="secondary" style={{ fontSize: 12 }}>{formatTimestamp(detail.execution.updated_at, locale)}</Text> : null}
                    </Space>
                    <Descriptions size="small" column={2} items={[
                      { key: "focus", label: "当前焦点", children: detail.execution.current_focus || "-" },
                      { key: "owner", label: "当前负责人", children: detail.execution.current_owner || "-" },
                      { key: "risk", label: "当前风险", children: detail.execution.current_risk ? presentIndustryRiskLevel(detail.execution.current_risk) : "-" },
                      { key: "evidence", label: "最新证据", children: detail.execution.latest_evidence_summary || (detail.execution.evidence_count > 0 ? `共 ${detail.execution.evidence_count} 条证据` : "暂无证据") },
                      { key: "next", label: "下一步", children: detail.execution.next_step || "-" },
                      { key: "trigger", label: "触发来源", children: detail.execution.trigger_reason || detail.execution.trigger_source || "-" },
                    ]} />
                    {detail.execution.blocked_reason || detail.execution.stuck_reason ? (
                      <Alert showIcon type={detail.execution.status === "failed" || detail.execution.status === "idle-loop" ? "warning" : "info"} message={detail.execution.blocked_reason || detail.execution.stuck_reason || ""} style={{ marginTop: 8 }} />
                    ) : null}
                  </div>
                </div>
              ) : null}
              {detail.execution_core_identity || detail.strategy_memory ? (
                <div>
                  <Text strong style={{ color: "var(--baize-text-muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                    执行中枢身份
                  </Text>
                  <div style={{ marginTop: 8 }}>
                    <Space wrap style={{ marginBottom: 8 }}>
                      {detail.strategy_memory?.status ? (
                        <Tag color={runtimeStatusColor(String(detail.strategy_memory.status))}>
                          {presentIndustryRuntimeStatus(String(detail.strategy_memory.status))}
                        </Tag>
                      ) : null}
                      {detail.execution_core_identity?.role_name ? (
                        <Tag>{normalizeSpiderMeshBrand(String(detail.execution_core_identity.role_name))}</Tag>
                      ) : null}
                      {detail.execution_core_identity?.operating_mode ? (
                        <Tag>
                          {String(detail.execution_core_identity.operating_mode) === "control-core"
                            ? "主脑中控"
                            : formatIndustryDisplayToken(
                                detail.execution_core_identity.operating_mode as string | undefined,
                              )}
                        </Tag>
                      ) : null}
                    </Space>
                    <Descriptions
                      size="small"
                      column={2}
                      items={[
                        {
                          key: "mission",
                          label: "长期使命",
                          children: presentText(detail.execution_core_identity?.mission as string | undefined),
                        },
                        {
                          key: "north-star",
                          label: "北极星",
                          children: presentText(
                            (detail.strategy_memory?.north_star as string | undefined) ||
                              (detail.strategy_memory?.summary as string | undefined),
                          ),
                        },
                        {
                          key: "focuses",
                          label: "当前关注",
                          children: presentList(detail.strategy_memory?.current_focuses as string[] | undefined),
                        },
                        {
                          key: "priorities",
                          label: "优先顺序",
                          children: presentList(detail.strategy_memory?.priority_order as string[] | undefined),
                        },
                        {
                          key: "thinking-axes",
                          label: "思考轴",
                          children: presentList(detail.execution_core_identity?.thinking_axes as string[] | undefined),
                        },
                        {
                          key: "delegation-policy",
                          label: "分派原则",
                          children: presentList(detail.execution_core_identity?.delegation_policy as string[] | undefined),
                        },
                      ]}
                    />
                  </div>
                </div>
              ) : null}

              <div>
                <Text strong style={{ color: "var(--baize-text-muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                  素材分析
                </Text>
                <Paragraph type="secondary" style={{ margin: "8px 0 0" }}>
                  这里只保留已经写回行业实例的素材分析结果，供主脑聊天和后续执行复用。
                </Paragraph>
                {renderMediaAnalysisList(detail.media_analyses || [], {
                  emptyText: "当前行业实例还没有写回的素材分析。",
                  adoptedTag: "已接入身份",
                  showWriteback: true,
                })}
              </div>

              <IndustryPlanningSurface detail={detail} locale={locale} />

              {staffingPresentation.hasAnyState ? (
                <div>
                  <Text strong style={{ color: "var(--baize-text-muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                    Staffing Closure
                  </Text>
                  <div style={{ marginTop: 8 }}>
                    <Space wrap style={{ marginBottom: 8 }}>
                      {staffingPresentation.activeGap ? <Tag color="warning">Active gap</Tag> : null}
                      {staffingPresentation.pendingProposals.length ? (
                        <Tag>{`Pending proposals ${staffingPresentation.pendingProposals.length}`}</Tag>
                      ) : null}
                      {staffingPresentation.temporarySeats.length ? (
                        <Tag>{`Temporary seats ${staffingPresentation.temporarySeats.length}`}</Tag>
                      ) : null}
                      {staffingPresentation.researcher ? <Tag>Researcher active</Tag> : null}
                    </Space>
                    <Space direction="vertical" size={10} style={{ width: "100%" }}>
                      {staffingPresentation.activeGap ? (
                        <Alert
                          showIcon
                          type={
                            staffingPresentation.activeGap.badges.includes("Needs approval")
                              ? "warning"
                              : "info"
                          }
                          message={staffingPresentation.activeGap.title}
                          description={[
                            staffingPresentation.activeGap.detail,
                            staffingPresentation.activeGap.meta.join(" / "),
                          ]
                            .filter(Boolean)
                            .join(" | ")}
                        />
                      ) : null}
                      {staffingPresentation.pendingProposals.length ? (
                        <Card size="small" title="Pending Proposals">
                          <Space direction="vertical" size={6} style={{ width: "100%" }}>
                            {staffingPresentation.pendingProposals.map((item) => (
                              <Text key={item}>{item}</Text>
                            ))}
                          </Space>
                        </Card>
                      ) : null}
                      {staffingPresentation.temporarySeats.length ? (
                        <Card size="small" title="Temporary Seats">
                          <Space direction="vertical" size={6} style={{ width: "100%" }}>
                            {staffingPresentation.temporarySeats.map((item) => (
                              <Text key={item}>{item}</Text>
                            ))}
                          </Space>
                        </Card>
                      ) : null}
                      {staffingPresentation.researcher ? (
                        <Card size="small" title="Researcher">
                          <Space direction="vertical" size={6} style={{ width: "100%" }}>
                            <Text strong>{staffingPresentation.researcher.headline}</Text>
                            <Text type="secondary">{staffingPresentation.researcher.detail}</Text>
                            <Space wrap>
                              {staffingPresentation.researcher.badges.map((badge) => (
                                <Tag key={badge}>{badge}</Tag>
                              ))}
                            </Space>
                          </Space>
                        </Card>
                      ) : null}
                    </Space>
                  </div>
                </div>
              ) : null}

              <div>
                <Text strong style={{ color: "var(--baize-text-muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                  {INDUSTRY_TEXT.detailBacklog}
                </Text>
                {detail.backlog.length === 0 ? (
                  <Empty description="No backlog is active yet." style={{ margin: "8px 0" }} />
                ) : (
                  <List
                    size="small"
                    style={{ marginTop: 8 }}
                    dataSource={detail.backlog}
                    renderItem={(backlogItem) => {
                      const selected = isFocusedBacklog(backlogItem, focusSelection);
                      return (
                        <List.Item style={{ padding: "8px 0" }}>
                          <Card
                            size="small"
                            style={{ width: "100%", ...runtimeSurfaceCardStyle(selected) }}
                            extra={
                              <Button
                                size="small"
                                type={selected ? "primary" : "default"}
                                onClick={() => void handleSelectBacklogFocus(backlogItem.backlog_item_id)}
                              >
                                {selected ? "Focused" : "Focus backlog"}
                              </Button>
                            }
                          >
                            <Space direction="vertical" size={8} style={{ width: "100%" }}>
                              <Space wrap>
                                <Text strong style={{ color: "var(--baize-text-main)" }}>
                                  {backlogItem.title || backlogItem.backlog_item_id}
                                </Text>
                                <Tag color={runtimeStatusColor(backlogItem.status)}>
                                  {presentIndustryRuntimeStatus(backlogItem.status)}
                                </Tag>
                                <Tag>{`P${backlogItem.priority}`}</Tag>
                                <Tag>{backlogItem.source_kind}</Tag>
                                {selected ? <Tag color="blue">Selected</Tag> : null}
                              </Space>
                              <Text type="secondary">
                                {backlogItem.summary || backlogItem.source_ref || "No summary captured yet."}
                              </Text>
                              <Space wrap>
                                {backlogItem.assignment_id ? (
                                  <Tag>{`Assignment ${backlogItem.assignment_id}`}</Tag>
                                ) : null}
                                <Tag>{`Evidence ${backlogItem.evidence_ids.length}`}</Tag>
                                {backlogItem.updated_at ? (
                                  <Text type="secondary" style={{ fontSize: 12 }}>
                                    {formatTimestamp(backlogItem.updated_at, locale)}
                                  </Text>
                                ) : null}
                              </Space>
                            </Space>
                          </Card>
                        </List.Item>
                      );
                    }}
                  />
                )}
              </div>

              <div>
                <Text strong style={{ color: "var(--baize-text-muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                  {INDUSTRY_TEXT.detailAssignments}
                </Text>
                {detail.assignments.length === 0 ? (
                  <Empty description="No live assignments yet." style={{ margin: "8px 0" }} />
                ) : (
                  <List
                    size="small"
                    style={{ marginTop: 8 }}
                    dataSource={detail.assignments}
                    renderItem={(assignment) => {
                      const selected = isFocusedAssignment(assignment, focusSelection);
                      return (
                        <List.Item style={{ padding: "8px 0" }}>
                          <Card
                            size="small"
                            style={{ width: "100%", ...runtimeSurfaceCardStyle(selected) }}
                            extra={
                              <Button
                                size="small"
                                type={selected ? "primary" : "default"}
                                onClick={() => void handleSelectAssignmentFocus(assignment.assignment_id)}
                              >
                                {selected ? "Focused" : "Focus assignment"}
                              </Button>
                            }
                          >
                            <Space direction="vertical" size={8} style={{ width: "100%" }}>
                              <Space wrap>
                                <Text strong style={{ color: "var(--baize-text-main)" }}>
                                  {assignment.title || assignment.assignment_id}
                                </Text>
                                <Tag color={runtimeStatusColor(assignment.status)}>
                                  {presentIndustryRuntimeStatus(assignment.status)}
                                </Tag>
                                {assignment.report_back_mode ? (
                                  <Tag>{assignment.report_back_mode}</Tag>
                                ) : null}
                                {selected ? <Tag color="blue">Selected</Tag> : null}
                              </Space>
                              <Text type="secondary">
                                {assignment.summary || "No assignment summary captured yet."}
                              </Text>
                              <Space wrap>
                                {assignment.backlog_item_id ? (
                                  <Tag>{`Backlog ${assignment.backlog_item_id}`}</Tag>
                                ) : null}
                                {assignment.goal_id ? <Tag>{`Goal ${assignment.goal_id}`}</Tag> : null}
                                <Tag>{`Evidence ${assignment.evidence_ids.length}`}</Tag>
                                {assignment.updated_at ? (
                                  <Text type="secondary" style={{ fontSize: 12 }}>
                                    {formatTimestamp(assignment.updated_at, locale)}
                                  </Text>
                                ) : null}
                              </Space>
                            </Space>
                          </Card>
                        </List.Item>
                      );
                    }}
                  />
                )}
              </div>

              <div>
                <Text strong style={{ color: "var(--baize-text-muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                  {INDUSTRY_TEXT.detailAgentReports}
                </Text>
                {detail.agent_reports.length === 0 ? (
                  <Empty description="No agent reports yet." style={{ margin: "8px 0" }} />
                ) : (
                  <List
                    size="small"
                    style={{ marginTop: 8 }}
                    dataSource={detail.agent_reports}
                    renderItem={(report) => {
                      const workContextId = resolveReportWorkContextId(report);
                      const summary =
                        report.summary ||
                        report.recommendation ||
                        report.findings[0] ||
                        "No report summary captured yet.";
                      return (
                        <List.Item style={{ padding: "8px 0" }}>
                          <Card
                            size="small"
                            style={{ width: "100%", ...runtimeSurfaceCardStyle(false) }}
                            extra={
                              <Space wrap>
                                {report.assignment_id ? (
                                  <Button
                                    size="small"
                                    onClick={() => void handleSelectAssignmentFocus(report.assignment_id!)}
                                  >
                                    Focus linked assignment
                                  </Button>
                                ) : null}
                                <Button
                                  size="small"
                                  type="primary"
                                  onClick={() => void handleOpenAgentReportChat(report)}
                                >
                                  Open report chat
                                </Button>
                              </Space>
                            }
                          >
                            <Space direction="vertical" size={8} style={{ width: "100%" }}>
                              <Space wrap>
                                <Text strong style={{ color: "var(--baize-text-main)" }}>
                                  {report.headline || report.report_id}
                                </Text>
                                <Tag color={runtimeStatusColor(report.status)}>
                                  {presentIndustryRuntimeStatus(report.status)}
                                </Tag>
                                <Tag>{report.report_kind}</Tag>
                                {report.result ? <Tag>{report.result}</Tag> : null}
                                {report.processed ? <Tag color="green">Processed</Tag> : null}
                                {report.needs_followup ? <Tag color="orange">Follow-up</Tag> : null}
                                {workContextId ? <Tag color="blue">{workContextId}</Tag> : null}
                              </Space>
                              <Text type="secondary">{summary}</Text>
                              <Space wrap>
                                {report.followup_reason ? <Tag>{report.followup_reason}</Tag> : null}
                                <Tag>{`Findings ${report.findings.length}`}</Tag>
                                <Tag>{`Evidence ${report.evidence_ids.length}`}</Tag>
                                {report.updated_at ? (
                                  <Text type="secondary" style={{ fontSize: 12 }}>
                                    {formatTimestamp(report.updated_at, locale)}
                                  </Text>
                                ) : null}
                              </Space>
                            </Space>
                          </Card>
                        </List.Item>
                      );
                    }}
                  />
                )}
              </div>

              {/* Agents */}
              <div>
                <Text strong style={{ color: "var(--baize-text-muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em" }}>{INDUSTRY_TEXT.detailAgents}</Text>
                <List size="small" style={{ marginTop: 8 }} dataSource={detail.agents} renderItem={(agent) => (
                  <List.Item style={{ padding: "6px 0" }}>
                    <Space direction="vertical" size={2}>
                      <Space wrap>
                        <Text strong style={{ color: "var(--baize-text-main)" }}>{normalizeSpiderMeshBrand(String(agent.role_name || agent.name))}</Text>
                        <Tag color={runtimeStatusColor(deriveIndustryAgentStatus(agent))}>{presentIndustryRuntimeStatus(deriveIndustryAgentStatus(agent))}</Tag>
                        {agent.agent_class ? <Tag>{presentIndustryRoleClass(agent.agent_class)}</Tag> : null}
                        {agent.employment_mode ? (
                          <Tag color={employmentModeColor(agent.employment_mode)}>
                            {presentIndustryEmploymentMode(agent.employment_mode)}
                          </Tag>
                        ) : null}
                        {agent.activation_mode ? <Tag>{agent.activation_mode === "on-demand" ? "按需唤起" : "常驻"}</Tag> : null}
                      </Space>
                      <Text type="secondary" style={{ fontSize: 12 }}>{normalizeSpiderMeshBrand(String(agent.role_summary || agent.environment_summary || ""))}</Text>
                    </Space>
                  </List.Item>
                )} />
              </div>

              {/* Goals */}
              <div>
                <Text strong style={{ color: "var(--baize-text-muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em" }}>{INDUSTRY_TEXT.goalsTitle}</Text>
                <List size="small" style={{ marginTop: 8 }} dataSource={detail.goals} renderItem={(goal) => (
                  <List.Item style={{ padding: "6px 0" }}>
                    <Space direction="vertical" size={2}>
                      <Space wrap>
                        <Text strong style={{ color: "var(--baize-text-main)" }}>{String(goal.title || goal.kind || "未命名目标")}</Text>
                        <Tag>{presentIndustryRuntimeStatus(goal.status || "active")}</Tag>
                        {goal.role_name ? <Tag>{normalizeSpiderMeshBrand(String(goal.role_name))}</Tag> : null}
                      </Space>
                      <Text type="secondary" style={{ fontSize: 12 }}>{String(goal.summary || "")}</Text>
                    </Space>
                  </List.Item>
                )} />
              </div>

              {/* Schedules */}
              <div>
                <Text strong style={{ color: "var(--baize-text-muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em" }}>{INDUSTRY_TEXT.schedulesTitle}</Text>
                {detail.schedules.length === 0 ? <Empty description={INDUSTRY_TEXT.noSchedules} style={{ margin: "8px 0" }} /> : (
                  <List size="small" style={{ marginTop: 8 }} dataSource={detail.schedules} renderItem={(schedule) => (
                    <List.Item style={{ padding: "6px 0" }}>
                      <Space wrap>
                        <Text strong style={{ color: "var(--baize-text-main)" }}>{String(schedule.title || schedule.schedule_id)}</Text>
                        <Tag color={runtimeStatusColor(deriveIndustryScheduleStatus(schedule))}>{presentIndustryRuntimeStatus(deriveIndustryScheduleStatus(schedule))}</Tag>
                        <Tag>{String(schedule.cron || "-")}</Tag>
                        <Tag>{String(schedule.timezone || "UTC")}</Tag>
                      </Space>
                    </List.Item>
                  )} />
                )}
              </div>

              {/* 日报 */}
              <div>
                <Text strong style={{ color: "var(--baize-text-muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em" }}>{INDUSTRY_TEXT.dailyReport}</Text>
                <Space wrap style={{ marginTop: 8 }}>
                  <Tag>{INDUSTRY_TEXT.reportEvidence} {detail.reports.daily.evidence_count}</Tag>
                  <Tag>{INDUSTRY_TEXT.reportDecisions} {detail.reports.daily.decision_count}</Tag>
                  <Tag>{INDUSTRY_TEXT.reportProposals} {detail.reports.daily.proposal_count}</Tag>
                  <Tag>{INDUSTRY_TEXT.reportPatches} {detail.reports.daily.patch_count}</Tag>
                </Space>
                {detail.reports.daily.highlights.length === 0 ? <Empty description={INDUSTRY_TEXT.noHighlights} style={{ margin: "8px 0" }} /> : (
                  <List size="small" style={{ marginTop: 8 }} dataSource={detail.reports.daily.highlights} renderItem={(item) => <List.Item style={{ padding: "4px 0" }}>{item}</List.Item>} />
                )}
              </div>
            </Space>
          )}
        </Card>
      </div>
    </div>
  );
}



