import { useCallback, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Empty,
  Form,
  Input,
  List,
  Pagination,
  Space,
  Spin,
  Switch,
  Tabs,
  Tag,
  Typography,
  message,
} from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { Sparkles } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import api, { type CuratedSkillCatalogEntry } from "../../api";
import type {
  CapabilityMarketAttachmentTruth,
  CapabilityMarketProjectInstallAcceptedResponse,
  CapabilityMarketProjectInstallJobStatusResponse,
  CapabilityMarketProjectInstallResponse,
} from "../../api/modules/capabilityMarket";
import {
  localizeRemoteSkillText,
  presentRecommendationInstallKind,
  presentRecommendationManifestStatus,
  presentRecommendationRiskLevel,
  presentRecommendationSourceLabel,
  presentRemoteSkillName,
  presentRemoteSkillSummary,
  presentRemoteVersion,
} from "../../utils/remoteSkillPresentation";
import { PageHeader } from "../../components/PageHeader";
import styles from "./index.module.less";
import {
  buildCuratedInstallKey,
  CURATED_CATEGORY_DEFINITIONS,
  CURATED_PAGE_SIZE,
  MARKET_TAB_KEY_SET,
  parseTemplateConfigValue,
  presentTemplateAvailabilityLabel,
  templateStatusColor,
  type TemplateConfigField,
} from "./presentation";
import { useCapabilityMarketState } from "./useCapabilityMarketState";

const { Paragraph, Text } = Typography;
const { TextArea, Password } = Input;

type ProjectInstallNotice = {
  type: "info" | "success" | "error";
  message: string;
  description?: string;
};

const PROJECT_INSTALL_POLL_INTERVAL_MS = 2000;
const PROJECT_INSTALL_POLL_MAX_ATTEMPTS = 20;

function resolveAttachmentSummary(
  attachment: CapabilityMarketAttachmentTruth | null | undefined,
  fallback: string,
): string {
  const summary = String(attachment?.summary || "").trim();
  return summary || fallback;
}

function buildProjectInstallNoticeFromAccepted(
  accepted: CapabilityMarketProjectInstallAcceptedResponse,
): ProjectInstallNotice {
  return {
    type: "info",
    message: String(accepted.progress_summary || "外扩项目安装任务已受理。"),
    description: "安装还在后台继续，等任务完成后才代表能力真的可用。",
  };
}

function buildProjectInstallNoticeFromJob(
  job: CapabilityMarketProjectInstallJobStatusResponse,
): ProjectInstallNotice {
  if (job.status === "failed") {
    return {
      type: "error",
      message: String(job.error || job.progress_summary || "外扩项目安装失败。"),
      description: "请查看任务详情或日志，再决定是否重试。",
    };
  }
  return {
    type: job.status === "completed" ? "success" : "info",
    message: String(job.progress_summary || "外扩项目安装正在继续。"),
    description:
      job.status === "completed"
        ? "后台任务已完成，下面显示的是正式安装结果。"
        : "任务仍在后台执行，当前不是最终安装结果。",
  };
}

function buildProjectInstallNoticeFromResult(
  result: CapabilityMarketProjectInstallResponse,
): ProjectInstallNotice {
  const attachmentSummary = resolveAttachmentSummary(
    result.attachment,
    "外扩项目已完成安装。",
  );
  const attachedCount = result.attachment?.attached_agent_ids?.length || 0;
  return {
    type: result.attachment?.status === "attached" ? "success" : "info",
    message: attachmentSummary,
    description:
      attachedCount > 0
        ? `已挂到 ${attachedCount} 个执行位。`
        : "当前只进入能力库存，尚未挂到执行位。",
  };
}

async function waitForProjectInstallPoll(ms: number): Promise<void> {
  await new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function pollProjectInstallJobUntilTerminal(
  taskId: string,
): Promise<CapabilityMarketProjectInstallJobStatusResponse> {
  let latestJob = await api.getCapabilityMarketProjectInstallJob(taskId);
  let attempts = 1;
  while (
    latestJob.status !== "completed" &&
    latestJob.status !== "failed" &&
    attempts < PROJECT_INSTALL_POLL_MAX_ATTEMPTS
  ) {
    await waitForProjectInstallPoll(PROJECT_INSTALL_POLL_INTERVAL_MS);
    latestJob = await api.getCapabilityMarketProjectInstallJob(taskId);
    attempts += 1;
  }
  return latestJob;
}

function presentAttachmentNotice(
  attachment: CapabilityMarketAttachmentTruth | null | undefined,
  fallback: string,
): { method: "success" | "info"; message: string } {
  return {
    method: attachment?.status === "attached" ? "success" : "info",
    message: resolveAttachmentSummary(attachment, fallback),
  };
}

export default function CapabilityMarketPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [templateForm] = Form.useForm<Record<string, unknown>>();
  const [mcpForm] = Form.useForm<Record<string, unknown>>();
  const [projectInstallNotice, setProjectInstallNotice] =
    useState<ProjectInstallNotice | null>(null);
  const {
    activeTab,
    categoryCounts,
    curatedCategory,
    curatedError,
    curatedLoading,
    curatedPage,
    curatedQuery,
    curatedRangeText,
    curatedReviewAcknowledgements,
    filteredCuratedItems,
    handleRefreshAll,
    installingCuratedId,
    loadCurated,
    loadMcpCatalog,
    loadProjects,
    mcpCatalog,
    mcpCatalogLoading,
    mcpClients,
    mcpQuery,
    installedCapabilities,
    projectInstallKey,
    projectLoading,
    projectQuery,
    projectResults,
    requestedTemplateId,
    selectedTemplate,
    setCuratedCategory,
    setCuratedPage,
    setCuratedQuery,
    setCuratedReviewAcknowledgements,
    setInstallingCuratedId,
    setMcpQuery,
    setProjectInstallKey,
    setProjectQuery,
    setTemplateActionKey,
    setTemplateInstallSummary,
    skills,
    templateActionKey,
    templateInstallSummary,
    templates,
    templatesLoading,
    updateSearchParams,
  } = useCapabilityMarketState({ templateForm, mcpForm, searchParams, setSearchParams });

  const handleTabChange = useCallback(
    (nextTab: string) => {
      updateSearchParams({
        tab: MARKET_TAB_KEY_SET.has(nextTab) ? nextTab : "installed",
        template: nextTab === "install-templates" ? requestedTemplateId : null,
      });
    },
    [requestedTemplateId, updateSearchParams],
  );

  const handleCuratedSearch = useCallback(async () => {
    setCuratedPage(1);
    await loadCurated(curatedQuery.trim());
  }, [curatedQuery, loadCurated, setCuratedPage]);

  const handleProjectSearch = useCallback(async () => {
    await loadProjects(projectQuery.trim());
  }, [loadProjects, projectQuery]);

  const installCuratedSkill = useCallback(
    async (item: CuratedSkillCatalogEntry) => {
      const installKey = buildCuratedInstallKey(item);
      if (item.review_required && !curatedReviewAcknowledgements[installKey]) {
        message.warning("请先确认审核提示");
        return;
      }
      setInstallingCuratedId(installKey);
      try {
        const result = await api.installCapabilityMarketCuratedCatalogEntry({
          source_id: item.source_id,
          candidate_id: item.candidate_id,
          review_acknowledged: Boolean(curatedReviewAcknowledgements[installKey]),
          enable: true,
        });
        const notice = presentAttachmentNotice(result.attachment, "安装成功");
        message[notice.method](notice.message);
      } catch (error) {
        message.error(error instanceof Error ? error.message : String(error));
      } finally {
        setInstallingCuratedId(null);
      }
    },
    [curatedReviewAcknowledgements, setInstallingCuratedId],
  );

  const buildTemplateConfigPayload = useCallback(async () => {
    if (!selectedTemplate?.config_schema?.fields?.length) {
      return {};
    }
    await templateForm.validateFields();
    const rawValues = templateForm.getFieldsValue(true);
    return Object.fromEntries(
      selectedTemplate.config_schema.fields.map((field) => [field.key, parseTemplateConfigValue(field, rawValues[field.key])]),
    );
  }, [selectedTemplate, templateForm]);

  const handleInstallTemplate = useCallback(async () => {
    if (!requestedTemplateId) return;
    setTemplateActionKey(`install:${requestedTemplateId}`);
    try {
      const config = await buildTemplateConfigPayload();
      const result = await api.installCapabilityMarketInstallTemplate(requestedTemplateId, { config, enabled: true });
      const notice = presentAttachmentNotice(
        result.attachment,
        result.summary || "安装成功",
      );
      setTemplateInstallSummary(notice.message);
      message[notice.method](notice.message);
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
    } finally {
      setTemplateActionKey(null);
    }
  }, [buildTemplateConfigPayload, requestedTemplateId, setTemplateActionKey, setTemplateInstallSummary]);

  const installProject = useCallback(
    async (item: {
      source_url: string;
      version?: string;
      candidate_kind?: string;
      display_name?: string;
    }) => {
      const installKey = item.source_url || item.display_name || "project";
      setProjectInstallKey(installKey);
      setProjectInstallNotice(null);
      try {
        const accepted = await api.installCapabilityMarketProject({
          source_url: item.source_url,
          version: item.version,
          capability_kind:
            item.candidate_kind === "adapter"
              ? "adapter"
              : item.candidate_kind === "runtime-component"
                ? "runtime-component"
                : "project-package",
          overwrite: true,
          enable: true,
        });
        const acceptedNotice = buildProjectInstallNoticeFromAccepted(accepted);
        setProjectInstallNotice(acceptedNotice);

        const job = await pollProjectInstallJobUntilTerminal(accepted.task_id);
        if (job.status === "completed") {
          const result =
            job.result ||
            (await api.getCapabilityMarketProjectInstallJobResult(accepted.task_id));
          const resultNotice = buildProjectInstallNoticeFromResult(result);
          setProjectInstallNotice(resultNotice);
          message[
            resultNotice.type === "error"
              ? "error"
              : resultNotice.type === "success"
                ? "success"
                : "info"
          ](resultNotice.message);
          await handleRefreshAll();
        } else if (job.status === "failed") {
          const failedNotice = buildProjectInstallNoticeFromJob(job);
          setProjectInstallNotice(failedNotice);
          message.error(failedNotice.message);
        } else {
          const runningNotice = buildProjectInstallNoticeFromJob(job);
          setProjectInstallNotice(runningNotice);
          message.info(runningNotice.message);
        }
      } catch (error) {
        const detail = error instanceof Error ? error.message : String(error);
        setProjectInstallNotice({
          type: "error",
          message: detail,
          description: "外扩项目安装没有完成，请检查 donor 任务状态。",
        });
        message.error(detail);
      } finally {
        setProjectInstallKey(null);
      }
    },
    [handleRefreshAll, setProjectInstallKey],
  );

  const renderTemplateConfigField = useCallback((field: TemplateConfigField) => {
    const fieldType = String(field.field_type || "string").trim().toLowerCase();
    if (fieldType === "boolean") return <Form.Item key={field.key} name={field.key} label={field.label || field.key} valuePropName="checked"><Switch /></Form.Item>;
    if (fieldType === "string[]") return <Form.Item key={field.key} name={field.key} label={field.label || field.key}><TextArea rows={3} /></Form.Item>;
    return <Form.Item key={field.key} name={field.key} label={field.label || field.key}>{field.secret ? <Password /> : <Input />}</Form.Item>;
  }, []);

  return (
    <div className={`${styles.page} page-container`}>
      <PageHeader
        eyebrow="能力市场"
        title="能力市场"
        description="统一发现、评估、安装和启用 skill、MCP 与外扩项目能力，不再让能力入口散落在各处。"
        stats={[
          { label: "已装能力", value: String(installedCapabilities.length).padStart(2, "0") },
          { label: "可用技能", value: String(skills.length).padStart(2, "0") },
          { label: "安装模板", value: String(templates.length).padStart(2, "0") },
          { label: "MCP 客户端", value: String(mcpClients.length).padStart(2, "0") },
        ]}
        actions={(
          <Button icon={<ReloadOutlined />} onClick={() => void handleRefreshAll()} className="baize-btn">
            刷新
          </Button>
        )}
      />
      {curatedError ? <Alert type="error" showIcon message={curatedError} /> : null}
      <Tabs
        activeKey={activeTab}
        onChange={handleTabChange}
        items={[
          {
            key: "curated",
            label: "精选中心",
            children: (
              <div className={styles.hubStack}>
                <div className={styles.searchBar}>
                  <Input value={curatedQuery} prefix={<Sparkles size={16} />} onChange={(e) => setCuratedQuery(e.currentTarget.value)} onPressEnter={() => void handleCuratedSearch()} />
                  <Button onClick={() => void handleCuratedSearch()}>搜索</Button>
                  <Button icon={<ReloadOutlined />} onClick={() => void loadCurated(curatedQuery.trim())}>刷新</Button>
                </div>
                <Space wrap>{CURATED_CATEGORY_DEFINITIONS.map((d) => <Button key={d.key} type={curatedCategory === d.key ? "primary" : "default"} onClick={() => setCuratedCategory(d.key)}>{d.label} ({categoryCounts[d.key] || 0})</Button>)}</Space>
                <Tag>{curatedRangeText}</Tag>
                {curatedLoading ? <Spin /> : filteredCuratedItems.length ? (
                  <>
                    <div className={styles.hubGrid}>
                      {filteredCuratedItems.slice((curatedPage - 1) * CURATED_PAGE_SIZE, curatedPage * CURATED_PAGE_SIZE).map(({ item }) => {
                        const installKey = buildCuratedInstallKey(item);
                        return (
                          <Card key={installKey} className={styles.hubCard}>
                            <Paragraph strong>{presentRemoteSkillName({ slug: item.candidate_id, title: item.title, description: item.description })}</Paragraph>
                            <Paragraph>{presentRemoteSkillSummary({ slug: item.candidate_id, title: item.title, description: item.description })}</Paragraph>
                            <Space wrap>
                              <Tag>{presentRecommendationSourceLabel(item.source_label)}</Tag>
                              <Tag>{presentRecommendationManifestStatus(item.manifest_status)}</Tag>
                              <Tag>{presentRecommendationRiskLevel("guarded")}</Tag>
                              <Tag>{presentRemoteVersion(item.version)}</Tag>
                            </Space>
                            {item.review_summary ? <Paragraph type="secondary">{localizeRemoteSkillText(item.review_summary)}</Paragraph> : null}
                            {item.review_required ? <Checkbox checked={Boolean(curatedReviewAcknowledgements[installKey])} onChange={(e) => setCuratedReviewAcknowledgements((current) => ({ ...current, [installKey]: e.target.checked }))}>已确认审核提示</Checkbox> : null}
                            <Button loading={installingCuratedId === installKey} onClick={() => void installCuratedSkill(item)}>安装</Button>
                          </Card>
                        );
                      })}
                    </div>
                    <Pagination current={curatedPage} pageSize={CURATED_PAGE_SIZE} total={filteredCuratedItems.length} onChange={(p) => setCuratedPage(p)} />
                  </>
                ) : <Empty />}
              </div>
            ),
          },
          {
            key: "projects",
            label: "项目",
            children: (
              <Card>
                <Space direction="vertical" style={{ width: "100%" }}>
                  {projectInstallNotice ? (
                    <Alert
                      type={projectInstallNotice.type}
                      showIcon
                      message={projectInstallNotice.message}
                      description={projectInstallNotice.description}
                    />
                  ) : null}
                  <Space.Compact style={{ width: "100%" }}>
                    <Input
                      value={projectQuery}
                      onChange={(e) => setProjectQuery(e.currentTarget.value)}
                      onPressEnter={() => void handleProjectSearch()}
                      placeholder="输入 GitHub 仓库地址或搜索词"
                    />
                    <Button onClick={() => void handleProjectSearch()}>搜索</Button>
                  </Space.Compact>
                  {projectLoading ? <Spin /> : null}
                  <List
                    dataSource={projectResults}
                    locale={{
                      emptyText: (
                        <Empty
                          description={
                            projectQuery.trim()
                              ? "暂无可安装项目"
                              : "输入 GitHub 仓库地址或搜索词后开始搜索"
                          }
                        />
                      ),
                    }}
                    renderItem={(item) => (
                      <List.Item
                        actions={[
                          <Button
                            key="install"
                            loading={projectInstallKey === (item.source_url || item.display_name)}
                            onClick={() => void installProject(item)}
                          >
                            安装
                          </Button>,
                        ]}
                      >
                        <List.Item.Meta
                          title={item.display_name}
                          description={
                            <Space direction="vertical" size={4}>
                              <Text>{item.summary || item.source_url}</Text>
                              <Text type="secondary">{item.source_url}</Text>
                            </Space>
                          }
                        />
                      </List.Item>
                    )}
                  />
                </Space>
              </Card>
            ),
          },
          {
            key: "install-templates",
            label: "安装模板",
            children: (
              <div className={styles.templateGrid}>
                <Card title="模板" className={styles.templateList} loading={templatesLoading}>
                  <List dataSource={templates} renderItem={(item) => <List.Item onClick={() => updateSearchParams({ template: item.id, tab: "install-templates" })}><Space><Text>{item.name}</Text><Tag color={templateStatusColor(item)}>{presentTemplateAvailabilityLabel(item)}</Tag><Tag>{presentRecommendationInstallKind(item.install_kind)}</Tag></Space></List.Item>} />
                </Card>
                <Card className={styles.templateDetail}>
                  {selectedTemplate ? (
                    <Space direction="vertical" style={{ width: "100%" }}>
                      {templateInstallSummary ? <Alert type="success" message={templateInstallSummary} /> : null}
                      <Form form={templateForm} layout="vertical">{selectedTemplate.config_schema?.fields?.map(renderTemplateConfigField)}</Form>
                      <Button type="primary" loading={templateActionKey === `install:${selectedTemplate.id}`} onClick={() => void handleInstallTemplate()}>安装</Button>
                    </Space>
                  ) : <Empty />}
                </Card>
              </div>
            ),
          },
          {
            key: "installed",
            label: "已安装",
            children: (
              <Card>
                <List
                  dataSource={installedCapabilities}
                  locale={{ emptyText: <Empty /> }}
                  renderItem={(item) => (
                    <List.Item>
                      <List.Item.Meta title={item.name} description={item.id} />
                    </List.Item>
                  )}
                />
              </Card>
            ),
          },
          {
            key: "skills",
            label: "技能",
            children: (
              <Card>
                <List
                  dataSource={skills}
                  locale={{ emptyText: <Empty /> }}
                  renderItem={(item) => (
                    <List.Item>
                      <List.Item.Meta title={item.name} description={item.source} />
                    </List.Item>
                  )}
                />
              </Card>
            ),
          },
          {
            key: "mcp",
            label: "MCP",
            children: (
              <Card>
                <Input
                  value={mcpQuery}
                  onChange={(e) => setMcpQuery(e.currentTarget.value)}
                  onPressEnter={() =>
                    void loadMcpCatalog({ query: mcpQuery, category: "all", cursor: null, page: 1 })
                  }
                />
                {mcpCatalogLoading ? <Spin /> : <Tag>{mcpCatalog?.items?.length || 0}</Tag>}
              </Card>
            ),
          },
        ]}
      />
    </div>
  );
}
