import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Form,
  Input,
  Modal,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import api from "../../api";
import type {
  FixedSopBindingCreatePayload,
  FixedSopBindingDetail,
  FixedSopDoctorReport,
  FixedSopRunDetail,
  FixedSopTemplateSummary,
} from "../../api/modules/fixedSops";
import type { IndustryInstanceSummary } from "../../api/modules/industry";
import {
  runtimeRiskColor,
  runtimeRiskLabel,
  runtimeStatusColor,
} from "../../runtime/tagSemantics";
import styles from "./index.module.less";
import { formatRuntimeStatus, localizeRuntimeText } from "./text";

const { Paragraph, Text } = Typography;

interface CreateBindingValues {
  template_id?: string;
  binding_name?: string;
  owner_scope?: string;
  industry_instance_id?: string;
  owner_agent_id?: string;
  trigger_mode?: string;
  risk_baseline?: string;
}

interface FixedSopPanelProps {
  focusScope?: string | null;
  openDetail: (route: string, title: string) => Promise<void>;
  onRuntimeChanged?: () => Promise<void> | void;
}

function formatTimestamp(value?: string | null): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function textValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function booleanValue(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function summarizeHostRequirement(requirement: unknown): string {
  const requirementRecord = asRecord(requirement);
  if (!requirementRecord) {
    return "-";
  }
  return (
    textValue(requirementRecord.app_family) ||
    textValue(requirementRecord.surface_kind) ||
    "-"
  );
}

function summarizeHostRequirementDetails(requirement: unknown): string[] {
  const requirementRecord = asRecord(requirement);
  if (!requirementRecord) {
    return [];
  }
  return [
    textValue(requirementRecord.surface_kind),
    booleanValue(requirementRecord.mutating) ? "mutating" : null,
  ].filter((item): item is string => Boolean(item));
}

function getHostCoordination(preflight: unknown): Record<string, unknown> {
  const preflightRecord = asRecord(preflight);
  return asRecord(preflightRecord?.coordination) || {};
}

function getHostSchedulerAction(preflight: unknown): string {
  return textValue(getHostCoordination(preflight).recommended_scheduler_action) || "-";
}

function getHostBlockerReason(preflight: unknown): string | null {
  const coordination = getHostCoordination(preflight);
  const contentionForecast = asRecord(coordination.contention_forecast);
  return textValue(contentionForecast?.reason) || textValue(coordination.reason) || null;
}

function getHostContinuityStatus(preflight: unknown): string | null {
  const preflightRecord = asRecord(preflight);
  return textValue(asRecord(preflightRecord?.continuity)?.status);
}

function getBindingMetadata(detail?: FixedSopBindingDetail | null): Record<string, unknown> {
  return asRecord(detail?.binding.metadata) || {};
}

function getBindingEnvironmentId(
  detail: FixedSopBindingDetail,
  runDetail?: FixedSopRunDetail,
): string | undefined {
  return (
    textValue(runDetail?.environment_id) ||
    textValue(getBindingMetadata(detail).environment_id) ||
    undefined
  );
}

function getBindingSessionMountId(
  detail: FixedSopBindingDetail,
  runDetail?: FixedSopRunDetail,
): string | undefined {
  return (
    textValue(runDetail?.session_mount_id) ||
    textValue(getBindingMetadata(detail).session_mount_id) ||
    undefined
  );
}

function getBindingHostRequirement(
  detail: FixedSopBindingDetail,
  runDetail?: FixedSopRunDetail,
): Record<string, unknown> {
  return (
    asRecord(runDetail?.host_requirement) ||
    asRecord(getBindingMetadata(detail).host_requirement) ||
    {}
  );
}

function renderHostSummaryLines(
  environmentId?: string,
  sessionMountId?: string,
  hostRequirement?: Record<string, unknown>,
  hostPreflight?: Record<string, unknown>,
): JSX.Element[] {
  const items: JSX.Element[] = [];
  if (environmentId) {
    items.push(
      <Text key="environment" type="secondary">
        Environment: {environmentId}
      </Text>,
    );
  }
  if (sessionMountId) {
    items.push(
      <Text key="session" type="secondary">
        Session: {sessionMountId}
      </Text>,
    );
  }
  if (hostRequirement && Object.keys(hostRequirement).length > 0) {
    items.push(
      <Text key="requirement" type="secondary">
        Requirement: {summarizeHostRequirement(hostRequirement)}
      </Text>,
    );
  }
  const schedulerAction = getHostSchedulerAction(hostPreflight);
  if (schedulerAction !== "-") {
    items.push(
      <Text key="snapshot" type="secondary">
        Host snapshot: {schedulerAction}
      </Text>,
    );
  }
  return items;
}

function describeBindingContext(
  detail: FixedSopBindingDetail,
  instances: Map<string, IndustryInstanceSummary>,
): string {
  const industryLabel = detail.binding.industry_instance_id
    ? instances.get(detail.binding.industry_instance_id)?.label ||
      detail.binding.industry_instance_id
    : null;
  const parts = [
    industryLabel ? `Industry: ${industryLabel}` : null,
    detail.binding.owner_scope ? `Scope: ${detail.binding.owner_scope}` : null,
    detail.binding.owner_agent_id ? `Owner: ${detail.binding.owner_agent_id}` : null,
  ].filter((item): item is string => Boolean(item));
  return parts.join(" | ") || "Unscoped";
}

export default function FixedSopPanel({
  focusScope,
  openDetail,
  onRuntimeChanged,
}: FixedSopPanelProps) {
  const [templateCatalog, setTemplateCatalog] = useState<FixedSopTemplateSummary[]>([]);
  const [bindings, setBindings] = useState<FixedSopBindingDetail[]>([]);
  const [instances, setInstances] = useState<IndustryInstanceSummary[]>([]);
  const [runDetails, setRunDetails] = useState<Record<string, FixedSopRunDetail>>(
    {},
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionKey, setActionKey] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [doctorReports, setDoctorReports] = useState<Record<string, FixedSopDoctorReport>>(
    {},
  );
  const [doctorBindingId, setDoctorBindingId] = useState<string | null>(null);
  const [createForm] = Form.useForm<CreateBindingValues>();

  const watchedIndustryInstanceId = Form.useWatch("industry_instance_id", createForm);
  const watchedTemplateId = Form.useWatch("template_id", createForm);

  const instanceMap = useMemo(
    () => new Map(instances.map((item) => [item.instance_id, item])),
    [instances],
  );
  const selectedInstance = useMemo(
    () =>
      watchedIndustryInstanceId
        ? instanceMap.get(watchedIndustryInstanceId) || null
        : null,
    [instanceMap, watchedIndustryInstanceId],
  );
  const selectedTemplate = useMemo(
    () =>
      watchedTemplateId
        ? templateCatalog.find((item) => item.template.template_id === watchedTemplateId) ||
          null
        : null,
    [templateCatalog, watchedTemplateId],
  );
  const ownerAgentOptions = useMemo(
    () =>
      (selectedInstance?.team.agents || []).map((agent) => ({
        label: `${agent.name} (${agent.role_name})`,
        value: agent.agent_id,
      })),
    [selectedInstance],
  );
  const doctorTarget = useMemo(
    () =>
      doctorBindingId
        ? bindings.find((item) => item.binding.binding_id === doctorBindingId) || null
        : null,
    [bindings, doctorBindingId],
  );
  const doctorReport = doctorBindingId ? doctorReports[doctorBindingId] : undefined;

  useEffect(() => {
    if (selectedInstance?.owner_scope) {
      createForm.setFieldValue("owner_scope", selectedInstance.owner_scope);
    }
    createForm.setFieldValue("owner_agent_id", undefined);
  }, [createForm, selectedInstance]);

  useEffect(() => {
    if (selectedTemplate?.template.risk_baseline) {
      createForm.setFieldValue("risk_baseline", selectedTemplate.template.risk_baseline);
    }
  }, [createForm, selectedTemplate]);

  const loadPanel = async () => {
    setLoading(true);
    try {
      const [templatePayload, bindingPayload, instancePayload] = await Promise.all([
        api.listFixedSopTemplates({ status: "active" }),
        api.listFixedSopBindings({ limit: 100 }),
        api.listIndustryInstances({ limit: 50, status: "active" }),
      ]);
      const nextTemplates = templatePayload?.items || [];
      const nextBindings = Array.isArray(bindingPayload) ? bindingPayload : [];
      const nextInstances = Array.isArray(instancePayload) ? instancePayload : [];
      const runIds = Array.from(
        new Set(
          nextBindings
            .map((item) => item.binding.last_run_id)
            .filter((item): item is string => Boolean(item)),
        ),
      );
      const nextRunDetails: Record<string, FixedSopRunDetail> = {};
      await Promise.all(
        runIds.map(async (runId) => {
          try {
            nextRunDetails[runId] = await api.getFixedSopRun(runId);
          } catch {
            // Keep the binding visible even if the historical run is no longer available.
          }
        }),
      );
      setTemplateCatalog(nextTemplates);
      setBindings(nextBindings);
      setInstances(nextInstances);
      setRunDetails(nextRunDetails);
      setDoctorReports((current) => {
        const next: Record<string, FixedSopDoctorReport> = {};
        nextBindings.forEach((item) => {
          const report = current[item.binding.binding_id];
          if (report) {
            next[item.binding.binding_id] = report;
          }
        });
        return next;
      });
      setError(null);
    } catch (loadError) {
      setError(
        localizeRuntimeText(
          loadError instanceof Error ? loadError.message : String(loadError),
        ),
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadPanel();
  }, []);

  const handleRefresh = async () => {
    await loadPanel();
  };

  const handleCreateOpen = () => {
    createForm.setFieldsValue({
      template_id: templateCatalog[0]?.template.template_id,
      owner_scope: focusScope || undefined,
      trigger_mode: "manual",
      risk_baseline: templateCatalog[0]?.template.risk_baseline || "guarded",
    });
    setCreateOpen(true);
  };

  const handleCreateBinding = async () => {
    const values = await createForm.validateFields();
    const payload: FixedSopBindingCreatePayload = {
      template_id: values.template_id || "",
      binding_name: values.binding_name?.trim() || undefined,
      status: "active",
      owner_scope: values.owner_scope?.trim() || undefined,
      owner_agent_id: values.owner_agent_id || undefined,
      industry_instance_id: values.industry_instance_id || undefined,
      trigger_mode: values.trigger_mode || "manual",
      risk_baseline:
        values.risk_baseline || selectedTemplate?.template.risk_baseline || "guarded",
      metadata: {
        created_from: "runtime-center",
      },
    };
    setActionKey("create");
    try {
      await api.createFixedSopBinding(payload);
      message.success("Binding created");
      setCreateOpen(false);
      createForm.resetFields();
      await loadPanel();
      await onRuntimeChanged?.();
    } catch (createError) {
      message.error(
        localizeRuntimeText(
          createError instanceof Error ? createError.message : String(createError),
        ),
      );
    } finally {
      setActionKey(null);
    }
  };

  const handleRunBinding = async (detail: FixedSopBindingDetail) => {
    setActionKey(`run:${detail.binding.binding_id}`);
    try {
      const result = await api.runFixedSopBinding(detail.binding.binding_id, {
        input_payload: {},
        owner_agent_id: detail.binding.owner_agent_id || undefined,
        owner_scope: detail.binding.owner_scope || focusScope || undefined,
        dry_run: false,
        metadata: {
          source: "runtime-center",
        },
      });
      message.success(localizeRuntimeText(result.summary || "Run finished"));
      await loadPanel();
      await onRuntimeChanged?.();
    } catch (runError) {
      message.error(
        localizeRuntimeText(
          runError instanceof Error ? runError.message : String(runError),
        ),
      );
    } finally {
      setActionKey(null);
    }
  };

  const handleDoctor = async (detail: FixedSopBindingDetail) => {
    setActionKey(`doctor:${detail.binding.binding_id}`);
    try {
      const report = await api.runFixedSopDoctor(detail.binding.binding_id);
      setDoctorReports((current) => ({
        ...current,
        [detail.binding.binding_id]: report,
      }));
      setDoctorBindingId(detail.binding.binding_id);
      await onRuntimeChanged?.();
    } catch (doctorError) {
      message.error(
        localizeRuntimeText(
          doctorError instanceof Error ? doctorError.message : String(doctorError),
        ),
      );
    } finally {
      setActionKey(null);
    }
  };

  const bindingColumns: ColumnsType<FixedSopBindingDetail> = [
    {
      title: "Binding",
      key: "binding",
      render: (_, detail) => (
        <Space direction="vertical" size={2}>
          <Text strong>{detail.binding.binding_name}</Text>
          <Text type="secondary">{describeBindingContext(detail, instanceMap)}</Text>
        </Space>
      ),
    },
    {
      title: "Template",
      key: "template",
      render: (_, detail) => (
        <Space direction="vertical" size={2}>
          <Text>{detail.template.name}</Text>
          <Text type="secondary">{detail.binding.trigger_mode}</Text>
        </Space>
      ),
    },
    {
      title: "Status",
      key: "status",
      render: (_, detail) => (
        <Space wrap size={8}>
          <Tag color={runtimeStatusColor(detail.binding.status)}>
            {formatRuntimeStatus(detail.binding.status)}
          </Tag>
          <Tag color={runtimeRiskColor(detail.binding.risk_baseline)}>
            {runtimeRiskLabel(detail.binding.risk_baseline)}
          </Tag>
        </Space>
      ),
    },
    {
      title: "Latest Run",
      key: "latest-run",
      render: (_, detail) => {
        const runId = detail.binding.last_run_id || undefined;
        const run = runId ? runDetails[runId] : undefined;
        const environmentId = getBindingEnvironmentId(detail, run);
        const sessionMountId = getBindingSessionMountId(detail, run);
        const hostRequirement = getBindingHostRequirement(detail, run);
        const hostSummaryLines = renderHostSummaryLines(
          environmentId,
          sessionMountId,
          hostRequirement,
          asRecord(run?.host_preflight) || undefined,
        );
        return (
          <Space direction="vertical" size={2}>
            <Text>{runId || "-"}</Text>
            {run ? (
              <>
                <Tag color={runtimeStatusColor(run.run.status)}>
                  {formatRuntimeStatus(run.run.status)}
                </Tag>
                <Text type="secondary">Evidence: {run.run.evidence_ids.length}</Text>
                {hostSummaryLines}
              </>
            ) : (
              <>
                <Text type="secondary">
                  Verified: {formatTimestamp(detail.binding.last_verified_at)}
                </Text>
                {hostSummaryLines}
              </>
            )}
          </Space>
        );
      },
    },
    {
      title: "Actions",
      key: "actions",
      render: (_, detail) => {
        const detailRoute =
          detail.routes.detail ||
          `/api/fixed-sops/bindings/${encodeURIComponent(detail.binding.binding_id)}`;
        const runRoute = detail.binding.last_run_id
          ? `/api/fixed-sops/runs/${encodeURIComponent(detail.binding.last_run_id)}`
          : null;
        return (
          <Space wrap>
            <Button
              size="small"
              onClick={() => {
                void openDetail(detailRoute, detail.binding.binding_name);
              }}
            >
              Detail
            </Button>
            <Button
              size="small"
              loading={actionKey === `doctor:${detail.binding.binding_id}`}
              onClick={() => {
                void handleDoctor(detail);
              }}
            >
              Doctor
            </Button>
            <Button
              size="small"
              type="primary"
              loading={actionKey === `run:${detail.binding.binding_id}`}
              onClick={() => {
                void handleRunBinding(detail);
              }}
            >
              Run
            </Button>
            {runRoute ? (
              <Button
                size="small"
                onClick={() => {
                  void openDetail(runRoute, `Run ${detail.binding.last_run_id}`);
                }}
              >
                Latest run
              </Button>
            ) : null}
          </Space>
        );
      },
    },
  ];

  return (
    <>
      <Card
        className={styles.card}
        title={<span className={styles.cardTitle}>Fixed SOP</span>}
        extra={
          <Space>
            <Button
              loading={loading && templateCatalog.length > 0}
              onClick={() => {
                void handleRefresh();
              }}
            >
              Refresh
            </Button>
            <Button type="primary" onClick={handleCreateOpen}>
              New binding
            </Button>
          </Space>
        }
      >
        {focusScope ? (
          <Alert
            showIcon
            type="info"
            message={`Current focus scope: ${focusScope}`}
            style={{ marginBottom: 16 }}
          />
        ) : null}
        {error ? (
          <Alert
            showIcon
            type="error"
            message="Failed to load fixed SOP data"
            description={error}
            style={{ marginBottom: 16 }}
          />
        ) : null}
        <Row gutter={[24, 24]}>
          <Col xs={24} xl={9}>
            <Card
              type="inner"
              title="Builtin templates"
              loading={loading && templateCatalog.length === 0}
            >
              {templateCatalog.length === 0 ? (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No templates" />
              ) : (
                <Space direction="vertical" size={12} style={{ width: "100%" }}>
                  {templateCatalog.map((item) => (
                    <div
                      key={item.template.template_id}
                      style={{
                        border: "1px solid var(--baize-border-color)",
                        borderRadius: 12,
                        padding: 12,
                      }}
                    >
                      <Space
                        align="start"
                        style={{ display: "flex", justifyContent: "space-between" }}
                      >
                        <div>
                          <Space wrap size={8}>
                            <Text strong>{item.template.name}</Text>
                            <Tag color={runtimeStatusColor(item.template.status)}>
                              {formatRuntimeStatus(item.template.status)}
                            </Tag>
                            <Tag color={runtimeRiskColor(item.template.risk_baseline)}>
                              {runtimeRiskLabel(item.template.risk_baseline)}
                            </Tag>
                          </Space>
                          <Paragraph style={{ marginBottom: 4, marginTop: 8 }}>
                            {item.template.summary}
                          </Paragraph>
                          <Text type="secondary">Bindings: {item.binding_count}</Text>
                        </div>
                        <Button
                          size="small"
                          onClick={() => {
                            void openDetail(
                              item.routes.detail ||
                                `/api/fixed-sops/templates/${encodeURIComponent(
                                  item.template.template_id,
                                )}`,
                              item.template.name,
                            );
                          }}
                        >
                          Detail
                        </Button>
                      </Space>
                    </div>
                  ))}
                </Space>
              )}
            </Card>
          </Col>
          <Col xs={24} xl={15}>
            <Card type="inner" title="Bindings" loading={loading && bindings.length === 0}>
              <Table
                rowKey={(detail) => detail.binding.binding_id}
                columns={bindingColumns}
                dataSource={bindings}
                pagination={false}
                locale={{
                  emptyText: (
                    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No bindings" />
                  ),
                }}
                scroll={{ x: 920 }}
              />
            </Card>
          </Col>
        </Row>
      </Card>

      <Modal
        destroyOnHidden
        open={doctorBindingId !== null}
        title="Doctor report"
        footer={[
          <Button key="close" onClick={() => setDoctorBindingId(null)}>
            Close
          </Button>,
        ]}
        onCancel={() => setDoctorBindingId(null)}
      >
        {doctorTarget && doctorReport ? (
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <Alert
              showIcon
              type={doctorReport.status === "blocked" ? "error" : "info"}
              message={doctorReport.summary || "Doctor completed"}
              description={
                getHostBlockerReason(doctorReport.host_preflight) ? (
                  <span>Blocker: {getHostBlockerReason(doctorReport.host_preflight)}</span>
                ) : undefined
              }
            />
            <Space direction="vertical" size={4} style={{ width: "100%" }}>
              {renderHostSummaryLines(
                textValue(doctorReport.environment_id) || undefined,
                textValue(doctorReport.session_mount_id) || undefined,
                asRecord(doctorReport.host_requirement) || undefined,
                asRecord(doctorReport.host_preflight) || undefined,
              )}
              {getHostSchedulerAction(doctorReport.host_preflight) !== "-" ? (
                <Text type="secondary">
                  Scheduler action: {getHostSchedulerAction(doctorReport.host_preflight)}
                </Text>
              ) : null}
              {getHostBlockerReason(doctorReport.host_preflight) ? (
                <Text type="secondary">
                  Blocker: {getHostBlockerReason(doctorReport.host_preflight)}
                </Text>
              ) : null}
            </Space>
            <Descriptions
              bordered
              size="small"
              column={1}
              items={[
                {
                  key: "binding",
                  label: "Binding",
                  children: doctorTarget.binding.binding_name,
                },
                {
                  key: "environment",
                  label: "Environment",
                  children: doctorReport.environment_id || "-",
                },
                {
                  key: "session",
                  label: "Session",
                  children: doctorReport.session_mount_id || "-",
                },
                {
                  key: "requirement",
                  label: "Requirement",
                  children: summarizeHostRequirement(doctorReport.host_requirement),
                },
                {
                  key: "scheduler-action",
                  label: "Scheduler action",
                  children: getHostSchedulerAction(doctorReport.host_preflight),
                },
                {
                  key: "continuity",
                  label: "Continuity",
                  children: getHostContinuityStatus(doctorReport.host_preflight) || "-",
                },
              ]}
            />
            {summarizeHostRequirementDetails(doctorReport.host_requirement).length > 0 ? (
              <Text type="secondary">
                Requirement details:{" "}
                {summarizeHostRequirementDetails(doctorReport.host_requirement).join(" / ")}
              </Text>
            ) : null}
            <Space direction="vertical" size={8} style={{ width: "100%" }}>
              {doctorReport.checks.map((check) => (
                <Alert
                  key={check.key}
                  showIcon
                  type={
                    check.status === "fail"
                      ? "error"
                      : check.status === "warn"
                        ? "warning"
                        : "info"
                  }
                  message={check.label}
                  description={check.message}
                />
              ))}
            </Space>
          </Space>
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No doctor report" />
        )}
      </Modal>

      <Modal
        destroyOnHidden
        open={createOpen}
        title="Create fixed SOP binding"
        okText="Create"
        cancelText="Cancel"
        confirmLoading={actionKey === "create"}
        onCancel={() => setCreateOpen(false)}
        onOk={() => {
          void handleCreateBinding();
        }}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item
            name="template_id"
            label="Template"
            rules={[{ required: true, message: "Select a fixed SOP template" }]}
          >
            <Select
              options={templateCatalog.map((item) => ({
                label: item.template.name,
                value: item.template.template_id,
              }))}
            />
          </Form.Item>
          <Form.Item name="binding_name" label="Binding name">
            <Input placeholder="Retail follow-up" />
          </Form.Item>
          <Form.Item name="owner_scope" label="Owner scope">
            <Input placeholder="industry-demo" />
          </Form.Item>
          <Form.Item name="industry_instance_id" label="Industry instance">
            <Select
              allowClear
              options={instances.map((item) => ({
                label: item.label,
                value: item.instance_id,
              }))}
            />
          </Form.Item>
          <Form.Item name="owner_agent_id" label="Owner agent">
            <Select allowClear options={ownerAgentOptions} />
          </Form.Item>
          <Form.Item name="trigger_mode" label="Trigger mode">
            <Select
              options={[
                { label: "manual", value: "manual" },
                { label: "event", value: "event" },
                { label: "schedule", value: "schedule" },
              ]}
            />
          </Form.Item>
          <Form.Item name="risk_baseline" label="Risk baseline">
            <Select
              options={[
                { label: "auto", value: "auto" },
                { label: "guarded", value: "guarded" },
                { label: "confirm", value: "confirm" },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
