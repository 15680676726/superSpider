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
  IndustryDraftPlan,
} from "../../api/modules/industry";
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
import {
  buildAnalysisModeOptions,
  formatAnalysisMode,
  formatMediaType,
  mediaTypeColor,
  resolveMediaTitle,
} from "../../utils/mediaPresentation";

import {
  INDUSTRY_TEXT,
  INDUSTRY_EXPERIENCE_TEXT,
  formatCountLabel,
  uniqueStrings,
  CAPABILITY_FAMILY_OPTIONS,
  INSTALL_ASSIGNMENT_MODE_OPTIONS,
  LinesTextArea,
  type IndustryBriefFormValues,
  createBlankRole,
  createBlankGoal,
  createBlankSchedule,
  presentIndustryEmploymentMode,
  presentIndustryReadinessStatus,
  presentIndustryRiskLevel,
  presentIndustryRoleClass,
  presentIndustryRuntimeStatus,
  readinessColor,
  roleColor,
  isSystemRole,
  formatTimestamp,
  runtimeStatusColor,
} from "./pageHelpers";
import IndustryRuntimeCockpitPanel from "./IndustryRuntimeCockpitPanel";
import {
  presentRecommendationSubsectionTitle,
  renderMediaAnalysisList,
} from "./runtimePresentation";
import { useIndustryPageState } from "./useIndustryPageState";

const { Paragraph, Text } = Typography;
const { TextArea } = Input;

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
                    素材分析
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
                                                  <Text type="secondary" style={{ fontSize: 12 }}>检索词</Text>
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
          ) : (
            <IndustryRuntimeCockpitPanel
              detail={detail}
              locale={locale}
              onClearRuntimeFocus={() => void handleClearRuntimeFocus()}
              onOpenAgentReportChat={(report) => void handleOpenAgentReportChat(report)}
              onSelectAssignmentFocus={(assignmentId) => void handleSelectAssignmentFocus(assignmentId)}
              onSelectBacklogFocus={(backlogItemId) => void handleSelectBacklogFocus(backlogItemId)}
            />
          )}
        </Card>
      </div>
    </div>
  );
}
