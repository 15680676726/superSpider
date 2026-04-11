import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Form,
  Input,
  Radio,
  Space,
  Spin,
  Steps,
  Typography,
} from "antd";
import { useNavigate } from "react-router-dom";

import api, { isApiError } from "../../api";
import type {
  BuddyConfirmDirectionResponse,
  BuddyContractCompileResponse,
  BuddyDirectionTransitionPreviewResponse,
  BuddyIdentityResponse,
  BuddySurfaceResponse,
} from "../../api/modules/buddy";
import { resolveBuddyEntryDecision } from "../../runtime/buddyFlow";
import {
  readBuddyProfileId,
  writeBuddyProfileId,
} from "../../runtime/buddyProfileBinding";
import { seedBuddySummary } from "../../runtime/buddySummaryStore";
import {
  buildBuddyExecutionCarrierChatBinding,
  openRuntimeChat,
} from "../../utils/runtimeChat";
import {
  clearBuddyOnboardingDraft,
  loadBuddyOnboardingDraft,
  saveBuddyOnboardingDraft,
} from "./draftState";

const { Paragraph, Text, Title } = Typography;
const { TextArea } = Input;
const BUDDY_CONFIRM_POLL_INTERVAL_MS = 400;
const BUDDY_CONFIRM_TIMEOUT_MS = 20_000;

type IdentityFormValues = {
  display_name: string;
  profession: string;
  current_stage: string;
  interests: string;
  strengths: string;
  constraints: string;
  goal_intention: string;
};

type ContractFormValues = {
  service_intent: string;
  collaboration_role: string;
  autonomy_level: string;
  confirm_boundaries: string[];
  report_style: string;
  collaboration_notes: string;
};

type BuddyOnboardingDraft = {
  identity?: Partial<IdentityFormValues>;
  contract?: Partial<ContractFormValues>;
  selected_direction?: string;
  capability_action?: "keep-active" | "restore-archived" | "start-new" | null;
  target_domain_id?: string;
  buddy_name?: string;
  step?: number;
};

const DEFAULT_CONTRACT_VALUES: ContractFormValues = {
  service_intent: "",
  collaboration_role: "orchestrator",
  autonomy_level: "proactive",
  confirm_boundaries: [],
  report_style: "result-first",
  collaboration_notes: "",
};

function parseLines(value?: string | null): string[] {
  return (value || "")
    .split(/[\n,，、]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinLines(value?: string[] | null): string {
  return Array.isArray(value) ? value.join("\n") : "";
}

function sanitizeDraft(value: unknown): BuddyOnboardingDraft | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  return value as BuddyOnboardingDraft;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function resolveApiErrorMessage(
  rawError: unknown,
  fallback: string,
): string {
  if (isApiError(rawError)) {
    const detail = String(rawError.detail || "").trim();
    if (detail) {
      return detail;
    }
  }
  if (rawError instanceof Error) {
    const message = String(rawError.message || "").trim();
    if (message) {
      return message;
    }
  }
  return fallback;
}

function buildIdentityFormValues(
  profile: BuddyIdentityResponse["profile"],
): IdentityFormValues {
  return {
    display_name: profile.display_name,
    profession: profile.profession,
    current_stage: profile.current_stage,
    interests: joinLines(profile.interests),
    strengths: joinLines(profile.strengths),
    constraints: joinLines(profile.constraints),
    goal_intention: profile.goal_intention,
  };
}

function buildIdentityFromSurface(
  surface: BuddySurfaceResponse,
): BuddyIdentityResponse | null {
  if (!surface.profile?.profile_id || !surface.onboarding?.session_id) {
    return null;
  }
  return {
    session_id: surface.onboarding.session_id,
    profile: surface.profile,
    status: surface.onboarding.status,
  };
}

function buildContractValuesFromSurface(
  surface: BuddySurfaceResponse,
): ContractFormValues {
  const source = surface.relationship ?? surface.onboarding;
  return {
    service_intent: source?.service_intent || "",
    collaboration_role: source?.collaboration_role || "orchestrator",
    autonomy_level: source?.autonomy_level || "proactive",
    confirm_boundaries: source?.confirm_boundaries || [],
    report_style: source?.report_style || "result-first",
    collaboration_notes: source?.collaboration_notes || "",
  };
}

function buildConfirmPayloadFromSurface(
  surface: BuddySurfaceResponse,
): BuddyConfirmDirectionResponse | null {
  if (
    !surface.profile?.profile_id ||
    !surface.onboarding?.session_id ||
    !surface.growth_target ||
    !surface.execution_carrier ||
    (!surface.onboarding.requires_naming && !surface.onboarding.completed)
  ) {
    return null;
  }
  return {
    session: {
      session_id: surface.onboarding.session_id,
      profile_id: surface.profile.profile_id,
      status: surface.onboarding.status,
      service_intent: surface.onboarding.service_intent || "",
      collaboration_role: surface.onboarding.collaboration_role || "orchestrator",
      autonomy_level: surface.onboarding.autonomy_level || "proactive",
      confirm_boundaries: surface.onboarding.confirm_boundaries || [],
      report_style: surface.onboarding.report_style || "result-first",
      collaboration_notes: surface.onboarding.collaboration_notes || "",
      candidate_directions: surface.onboarding.candidate_directions || [],
      recommended_direction: surface.onboarding.recommended_direction || "",
      selected_direction:
        surface.onboarding.selected_direction ||
        surface.growth_target.primary_direction ||
        "",
    },
    growth_target: surface.growth_target,
    relationship:
      surface.relationship || {
        relationship_id: "",
        profile_id: surface.profile.profile_id,
        buddy_name: "",
        encouragement_style: "old-friend",
        service_intent: surface.onboarding.service_intent || "",
        collaboration_role: surface.onboarding.collaboration_role || "orchestrator",
        autonomy_level: surface.onboarding.autonomy_level || "proactive",
        confirm_boundaries: surface.onboarding.confirm_boundaries || [],
        report_style: surface.onboarding.report_style || "result-first",
        collaboration_notes: surface.onboarding.collaboration_notes || "",
      },
    domain_capability: null,
    execution_carrier: surface.execution_carrier,
  };
}

async function waitForBuddyDirectionConfirmation(
  profileId: string,
  operationId: string,
): Promise<BuddySurfaceResponse> {
  const deadline = Date.now() + BUDDY_CONFIRM_TIMEOUT_MS;
  while (Date.now() < deadline) {
    const surface = await api.getBuddySurface(profileId);
    if (surface) {
      const confirmPayload = buildConfirmPayloadFromSurface(surface);
      if (confirmPayload) {
        return surface;
      }
      const onboarding = surface.onboarding;
      if (
        onboarding?.operation_status === "failed" &&
        (!operationId || onboarding.operation_id === operationId)
      ) {
        throw new Error(
          String(onboarding.operation_error || "").trim() ||
            "主方向确认失败，请稍后重试。",
        );
      }
    }
    await sleep(BUDDY_CONFIRM_POLL_INTERVAL_MS);
  }
  throw new Error("主方向确认超时，请稍后重试。");
}

export default function BuddyOnboardingPage() {
  const navigate = useNavigate();
  const [identityForm] = Form.useForm<IdentityFormValues>();
  const [contractForm] = Form.useForm<ContractFormValues>();
  const watchedIdentityValues = Form.useWatch([], identityForm);
  const watchedContractValues = Form.useWatch([], contractForm);
  const [initialDraft] = useState<BuddyOnboardingDraft | null>(() =>
    sanitizeDraft(loadBuddyOnboardingDraft()),
  );
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [identity, setIdentity] = useState<BuddyIdentityResponse | null>(null);
  const [contractDraft, setContractDraft] =
    useState<BuddyContractCompileResponse | null>(null);
  const [confirmPayload, setConfirmPayload] =
    useState<BuddyConfirmDirectionResponse | null>(null);
  const [currentStep, setCurrentStep] = useState<number>(
    () => initialDraft?.step ?? 0,
  );
  const [selectedDirection, setSelectedDirection] = useState(
    () => initialDraft?.selected_direction || "",
  );
  const [transitionPreview, setTransitionPreview] =
    useState<BuddyDirectionTransitionPreviewResponse | null>(null);
  const [selectedCapabilityAction, setSelectedCapabilityAction] = useState<
    "keep-active" | "restore-archived" | "start-new" | null
  >(() => initialDraft?.capability_action ?? null);
  const [selectedTargetDomainId, setSelectedTargetDomainId] = useState<
    string | undefined
  >(() => initialDraft?.target_domain_id);
  const [buddyNameDraft, setBuddyNameDraft] = useState(
    () => initialDraft?.buddy_name || "",
  );
  const [draftEnabled, setDraftEnabled] = useState(true);

  useEffect(() => {
    if (initialDraft?.identity) {
      identityForm.setFieldsValue(initialDraft.identity);
    }
    contractForm.setFieldsValue({
      ...DEFAULT_CONTRACT_VALUES,
      ...(initialDraft?.contract || {}),
    });
  }, [contractForm, identityForm, initialDraft]);

  useEffect(() => {
    if (!draftEnabled) {
      return;
    }
    saveBuddyOnboardingDraft({
      identity:
        watchedIdentityValues && typeof watchedIdentityValues === "object"
          ? watchedIdentityValues
          : undefined,
      contract:
        watchedContractValues && typeof watchedContractValues === "object"
          ? {
              ...DEFAULT_CONTRACT_VALUES,
              ...watchedContractValues,
            }
          : undefined,
      selected_direction: selectedDirection,
      capability_action: selectedCapabilityAction,
      target_domain_id: selectedTargetDomainId,
      buddy_name: buddyNameDraft,
      step: currentStep,
    } satisfies BuddyOnboardingDraft);
  }, [
    buddyNameDraft,
    currentStep,
    draftEnabled,
    selectedCapabilityAction,
    selectedDirection,
    selectedTargetDomainId,
    watchedContractValues,
    watchedIdentityValues,
  ]);

  useEffect(() => {
    let cancelled = false;

    const hydrateContractDraft = async (
      sessionId: string | null | undefined,
    ): Promise<void> => {
      if (!sessionId) {
        return;
      }
      const draft = await api.getBuddyContractDraft(sessionId);
      if (cancelled) {
        return;
      }
      setContractDraft(draft);
      setSelectedDirection(
        draft.recommended_direction || draft.candidate_directions[0] || "",
      );
      contractForm.setFieldsValue({
        service_intent: draft.service_intent,
        collaboration_role: draft.collaboration_role,
        autonomy_level: draft.autonomy_level,
        confirm_boundaries: draft.confirm_boundaries,
        report_style: draft.report_style,
        collaboration_notes: draft.collaboration_notes,
      });
      setCurrentStep(2);
    };

    void (async () => {
      try {
        const requestedProfileId = readBuddyProfileId();
        const entry = await api.getBuddyEntry(requestedProfileId);
        if (cancelled) return;
        const decision = resolveBuddyEntryDecision(entry);
        const profileIdFromEntry = decision.profileId ?? requestedProfileId ?? undefined;
        if (decision.profileId) {
          writeBuddyProfileId(decision.profileId);
        }
        if (decision.mode === "start-onboarding") {
          return;
        }
        if (decision.mode === "chat-ready" && decision.profileId) {
          const binding = buildBuddyExecutionCarrierChatBinding({
            sessionId: null,
            profileId: decision.profileId,
            profileDisplayName: decision.profileDisplayName,
            executionCarrier: decision.executionCarrier,
            entrySource: "buddy-onboarding-resume",
          });
          await openRuntimeChat(binding, navigate, {
            shouldNavigate: () => !cancelled,
          });
          return;
        }
        const surface = await api.getBuddySurface(profileIdFromEntry);
        if (cancelled) return;
        if (surface?.profile?.profile_id) {
          writeBuddyProfileId(surface.profile.profile_id);
          seedBuddySummary(surface.profile.profile_id, surface);
        }
        if (
          decision.mode === "resume-onboarding" &&
          surface?.profile?.profile_id &&
          surface.onboarding
        ) {
          const nextIdentity = buildIdentityFromSurface(surface);
          const nextConfirmPayload = buildConfirmPayloadFromSurface(surface);
          if (nextIdentity) {
            setIdentity(nextIdentity);
            identityForm.setFieldsValue(buildIdentityFormValues(nextIdentity.profile));
          }
          contractForm.setFieldsValue(buildContractValuesFromSurface(surface));
          if (surface.onboarding.recommended_direction) {
            setSelectedDirection(
              surface.onboarding.selected_direction ||
                surface.onboarding.recommended_direction,
            );
          }
          if (surface.relationship?.buddy_name?.trim()) {
            setBuddyNameDraft(surface.relationship.buddy_name.trim());
          }
          if (nextConfirmPayload) {
            setConfirmPayload(nextConfirmPayload);
            setCurrentStep(2);
          } else if (surface.onboarding.requires_direction_confirmation) {
            await hydrateContractDraft(surface.onboarding.session_id);
          } else if (nextIdentity) {
            setCurrentStep(1);
          }
        }
      } catch (rawError) {
        if (cancelled) return;
        if (!isApiError(rawError) || rawError.status !== 404) {
          setError("伙伴档案加载失败，请稍后重试。");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [contractForm, identityForm, navigate]);

  const handleSubmitIdentity = async (values: IdentityFormValues) => {
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.submitBuddyIdentity({
        display_name: values.display_name,
        profession: values.profession,
        current_stage: values.current_stage,
        interests: parseLines(values.interests),
        strengths: parseLines(values.strengths),
        constraints: parseLines(values.constraints),
        goal_intention: values.goal_intention,
      });
      writeBuddyProfileId(result.profile.profile_id);
      setIdentity(result);
      setContractDraft(null);
      setConfirmPayload(null);
      setTransitionPreview(null);
      setSelectedCapabilityAction(null);
      setSelectedTargetDomainId(undefined);
      setSelectedDirection("");
      contractForm.setFieldsValue(DEFAULT_CONTRACT_VALUES);
      setCurrentStep(1);
    } catch {
      setError("身份信息提交失败，请稍后重试。");
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmitContract = async (values: ContractFormValues) => {
    if (!identity) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.submitBuddyContract({
        session_id: identity.session_id,
        service_intent: values.service_intent.trim(),
        collaboration_role: values.collaboration_role,
        autonomy_level: values.autonomy_level,
        confirm_boundaries: values.confirm_boundaries || [],
        report_style: values.report_style,
        collaboration_notes: values.collaboration_notes.trim(),
      });
      setContractDraft(result);
      setSelectedDirection(
        result.recommended_direction || result.candidate_directions[0] || "",
      );
      setTransitionPreview(null);
      setSelectedCapabilityAction(null);
      setSelectedTargetDomainId(undefined);
      setCurrentStep(2);
    } catch {
      setError("合作方式提交失败，请稍后重试。");
    } finally {
      setSubmitting(false);
    }
  };

  const handlePreviewDirectionTransition = async () => {
    if (!identity || !selectedDirection.trim()) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const preview = await api.previewBuddyDirectionTransition({
        session_id: identity.session_id,
        selected_direction: selectedDirection,
      });
      setTransitionPreview(preview);
      setSelectedCapabilityAction(preview.recommended_action);
      setSelectedTargetDomainId(
        preview.recommended_action === "restore-archived"
          ? preview.archived_matches[0]?.domain_id
          : undefined,
      );
    } catch {
      setError("主方向预览失败，请稍后重试。");
    } finally {
      setSubmitting(false);
    }
  };

  const handleConfirmDirection = async () => {
    if (!identity || !selectedDirection.trim() || !selectedCapabilityAction) {
      return;
    }
    if (selectedCapabilityAction === "restore-archived" && !selectedTargetDomainId) {
      setError("请选择要恢复的历史领域能力。");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const handle = await api.startBuddyConfirmDirection({
        session_id: identity.session_id,
        selected_direction: selectedDirection,
        capability_action: selectedCapabilityAction,
        target_domain_id:
          selectedCapabilityAction === "restore-archived"
            ? selectedTargetDomainId
            : undefined,
      });
      const surface = await waitForBuddyDirectionConfirmation(
        handle.profile_id,
        handle.operation_id,
      );
      if (surface.profile?.profile_id) {
        writeBuddyProfileId(surface.profile.profile_id);
        seedBuddySummary(surface.profile.profile_id, surface);
      }
      if (surface.relationship?.buddy_name?.trim()) {
        setBuddyNameDraft(surface.relationship.buddy_name.trim());
      }
      const nextConfirmPayload = buildConfirmPayloadFromSurface(surface);
      if (!nextConfirmPayload) {
        throw new Error("主方向已确认，但进入聊天前的数据还没准备好。");
      }
      setConfirmPayload(nextConfirmPayload);
      setCurrentStep(2);
    } catch (rawError) {
      setError(
        resolveApiErrorMessage(rawError, "主方向确认失败，请稍后重试。"),
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleStartChat = async () => {
    if (!identity || !confirmPayload?.execution_carrier || !buddyNameDraft.trim()) {
      return;
    }
    try {
      await api.nameBuddy({
        session_id: confirmPayload.session.session_id,
        buddy_name: buddyNameDraft.trim(),
      });
      setDraftEnabled(false);
      clearBuddyOnboardingDraft();
      const binding = buildBuddyExecutionCarrierChatBinding({
        sessionId: confirmPayload.session.session_id,
        profileId: identity.profile.profile_id,
        profileDisplayName: identity.profile.display_name,
        executionCarrier: confirmPayload.execution_carrier,
      });
      await openRuntimeChat(binding, navigate);
    } catch {
      setError("进入聊天前命名失败，请稍后重试。");
    }
  };

  const stepIndex = confirmPayload ? 2 : contractDraft ? 2 : identity ? 1 : 0;

  if (loading) {
    return (
      <div style={{ minHeight: "60vh", display: "grid", placeItems: "center" }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20, paddingBottom: 24 }}>
      <Card>
        <Space direction="vertical" size={8} style={{ width: "100%" }}>
          <Title level={2} style={{ margin: 0 }}>
            超级伙伴首次建档
          </Title>
          <Paragraph style={{ margin: 0 }}>
            先确认你是谁、你希望我怎么和你协作，再把长期主方向落成正式执行主链。
          </Paragraph>
          <Steps
            current={stepIndex}
            items={[
              { title: "身份建档" },
              { title: "合作方式" },
              { title: "确认主方向" },
            ]}
          />
        </Space>
      </Card>

      {error ? <Alert type="error" showIcon message={error} /> : null}

      {!identity ? (
        <Card title="先告诉我你是谁">
          <Form
            form={identityForm}
            layout="vertical"
            onFinish={(values) => void handleSubmitIdentity(values)}
            data-testid="buddy-identity-form"
          >
            <Form.Item label="姓名" name="display_name" rules={[{ required: true }]}>
              <Input
                placeholder="你希望我怎么称呼你？"
                data-testid="buddy-identity-display-name"
              />
            </Form.Item>
            <Form.Item label="职业" name="profession" rules={[{ required: true }]}>
              <Input
                placeholder="你现在主要在做什么？"
                data-testid="buddy-identity-profession"
              />
            </Form.Item>
            <Form.Item label="当前阶段" name="current_stage" rules={[{ required: true }]}>
              <Input
                placeholder="例如：探索期、转型期、重建期"
                data-testid="buddy-identity-current-stage"
              />
            </Form.Item>
            <Form.Item label="兴趣" name="interests">
              <TextArea rows={2} placeholder="可用逗号、顿号或换行分隔" />
            </Form.Item>
            <Form.Item label="优势" name="strengths">
              <TextArea rows={2} placeholder="你比大多数人更稳的地方" />
            </Form.Item>
            <Form.Item label="限制 / 约束" name="constraints">
              <TextArea rows={2} placeholder="时间、资金、精力、环境约束等" />
            </Form.Item>
            <Form.Item label="目标意向" name="goal_intention" rules={[{ required: true }]}>
              <TextArea
                rows={3}
                placeholder="你想长期改变什么，先模糊地说也可以。"
                data-testid="buddy-identity-goal-intention"
              />
            </Form.Item>
            <Button type="primary" htmlType="submit" loading={submitting}>
              开始建档
            </Button>
          </Form>
        </Card>
      ) : null}

      {identity && !contractDraft && !confirmPayload ? (
        <Card title="先约定我们的合作方式">
          <Form
            form={contractForm}
            layout="vertical"
            initialValues={DEFAULT_CONTRACT_VALUES}
            onFinish={(values) => void handleSubmitContract(values)}
            data-testid="buddy-contract-form"
          >
            <Form.Item
              label="你希望我为你做什么？"
              name="service_intent"
              rules={[{ required: true, message: "请先告诉我你希望我为你做什么。" }]}
            >
              <TextArea
                rows={4}
                placeholder="例如：帮我把写作从想法变成稳定发布节奏。"
                data-testid="buddy-contract-service-intent"
              />
            </Form.Item>
            <Form.Item label="我主要扮演什么角色" name="collaboration_role">
              <Radio.Group>
                <Space direction="vertical">
                  <Radio value="orchestrator">统筹推进</Radio>
                  <Radio value="executor">执行推进</Radio>
                  <Radio value="advisor">顾问辅助</Radio>
                  <Radio value="companion">陪跑伙伴</Radio>
                </Space>
              </Radio.Group>
            </Form.Item>
            <Form.Item label="我可以主动到什么程度" name="autonomy_level">
              <Radio.Group>
                <Space direction="vertical">
                  <Radio value="reactive">你说一步我做一步</Radio>
                  <Radio value="proactive">默认主动推进</Radio>
                  <Radio value="guarded-proactive">主动推进，但关键边界先确认</Radio>
                </Space>
              </Radio.Group>
            </Form.Item>
            <Form.Item label="哪些动作必须先确认" name="confirm_boundaries">
              <Checkbox.Group
                options={[
                  { label: "外部花费", value: "external spend" },
                  { label: "公开发布", value: "public publishing" },
                  { label: "破坏性改动", value: "destructive change" },
                ]}
              />
            </Form.Item>
            <Form.Item label="默认汇报风格" name="report_style">
              <Radio.Group>
                <Space direction="vertical">
                  <Radio value="result-first">结果优先</Radio>
                  <Radio value="decision-first">决策优先</Radio>
                  <Radio value="milestone-summary">里程碑汇报</Radio>
                </Space>
              </Radio.Group>
            </Form.Item>
            <Form.Item label="还有什么合作偏好" name="collaboration_notes">
              <TextArea rows={3} placeholder="可选，告诉我你希望我记住的协作习惯。" />
            </Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={submitting}
              data-testid="buddy-contract-submit"
            >
              生成合作合同
            </Button>
          </Form>
        </Card>
      ) : null}

      {identity && contractDraft && !confirmPayload ? (
        <Card title="确认这次长期主方向">
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <Card size="small" data-testid="buddy-contract-summary">
              <Space direction="vertical" size={8} style={{ width: "100%" }}>
                <Text strong>合作目标</Text>
                <Text>{contractDraft.service_intent}</Text>
                <Text strong>推荐长期方向</Text>
                <Text>{contractDraft.recommended_direction}</Text>
                <Text strong>最终目标</Text>
                <Text>{contractDraft.final_goal}</Text>
                <Text strong>为什么现在值得做</Text>
                <Text>{contractDraft.why_it_matters}</Text>
              </Space>
            </Card>

            <Radio.Group
              value={selectedDirection}
              onChange={(event) => {
                setSelectedDirection(event.target.value);
                setTransitionPreview(null);
                setSelectedCapabilityAction(null);
                setSelectedTargetDomainId(undefined);
              }}
              style={{ width: "100%" }}
            >
              <Space direction="vertical" size={12} style={{ width: "100%" }}>
                {contractDraft.candidate_directions.map((direction) => (
                  <Radio key={direction} value={direction}>
                    {direction}
                  </Radio>
                ))}
              </Space>
            </Radio.Group>

            {!transitionPreview ? (
              <Button
                type="primary"
                disabled={!selectedDirection}
                loading={submitting}
                onClick={() => void handlePreviewDirectionTransition()}
                data-testid="buddy-direction-confirm"
              >
                预览能力继承方式
              </Button>
            ) : (
              <Card size="small" title="确认这次方向切换的能力处理方式">
                <Space direction="vertical" size={16} style={{ width: "100%" }}>
                  <Alert
                    type="info"
                    showIcon
                    message="系统建议"
                    description={transitionPreview.reason_summary}
                  />
                  <Radio.Group
                    value={selectedCapabilityAction}
                    onChange={(event) =>
                      setSelectedCapabilityAction(event.target.value)
                    }
                    style={{ width: "100%" }}
                  >
                    <Space direction="vertical" size={12} style={{ width: "100%" }}>
                      <Radio
                        value="keep-active"
                        disabled={!transitionPreview.current_domain}
                      >
                        继续沿用当前领域能力
                      </Radio>
                      <Radio
                        value="restore-archived"
                        disabled={!transitionPreview.archived_matches.length}
                      >
                        恢复历史领域能力
                      </Radio>
                      <Radio value="start-new">作为新领域重新开始</Radio>
                    </Space>
                  </Radio.Group>
                  {selectedCapabilityAction === "restore-archived" &&
                  transitionPreview.archived_matches.length ? (
                    <Radio.Group
                      value={selectedTargetDomainId}
                      onChange={(event) =>
                        setSelectedTargetDomainId(event.target.value)
                      }
                      style={{ width: "100%" }}
                    >
                      <Space direction="vertical" size={8} style={{ width: "100%" }}>
                        {transitionPreview.archived_matches.map((item) => (
                          <Radio key={item.domain_id} value={item.domain_id}>
                            {item.domain_label}
                          </Radio>
                        ))}
                      </Space>
                    </Radio.Group>
                  ) : null}
                  <Button
                    type="primary"
                    loading={submitting}
                    disabled={
                      !selectedCapabilityAction ||
                      (selectedCapabilityAction === "restore-archived" &&
                        !selectedTargetDomainId)
                    }
                    onClick={() => void handleConfirmDirection()}
                    data-testid="buddy-transition-confirm"
                  >
                    确认并进入伙伴主场
                  </Button>
                </Space>
              </Card>
            )}
          </Space>
        </Card>
      ) : null}

      {identity && confirmPayload ? (
        <Card title="给伙伴起名，然后进入聊天主场" data-testid="buddy-direction-confirmed">
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <Alert
              type="success"
              showIcon
              message="长期方向已经确认"
              description={confirmPayload.growth_target.final_goal}
            />
            <Input
              value={buddyNameDraft}
              onChange={(event) => setBuddyNameDraft(event.target.value)}
              placeholder="给你的伙伴起一个名字"
              data-testid="buddy-name-input"
            />
            <Button
              type="primary"
              onClick={() => void handleStartChat()}
              disabled={!buddyNameDraft.trim()}
              data-testid="buddy-start-chat"
            >
              进入聊天主场
            </Button>
          </Space>
        </Card>
      ) : null}
    </div>
  );
}
