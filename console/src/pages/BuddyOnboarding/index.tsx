import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
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
  BuddyClarificationResponse,
  BuddyConfirmDirectionResponse,
  BuddyDirectionTransitionPreviewResponse,
  BuddyIdentityResponse,
  BuddySurfaceResponse,
} from "../../api/modules/buddy";
import { resolveBuddyEntryDecision } from "../../runtime/buddyFlow";
import {
  readBuddyProfileId,
  writeBuddyProfileId,
} from "../../runtime/buddyProfileBinding";
import {
  buildBuddyExecutionCarrierChatBinding,
  openRuntimeChat,
} from "../../utils/runtimeChat";
import {
  clearBuddyOnboardingDraft,
  loadBuddyOnboardingDraft,
  saveBuddyOnboardingDraft,
} from "./draftState";

const { Paragraph, Title } = Typography;
const { TextArea } = Input;

type IdentityFormValues = {
  display_name: string;
  profession: string;
  current_stage: string;
  interests: string;
  strengths: string;
  constraints: string;
  goal_intention: string;
};

type BuddyOnboardingDraft = {
  identity?: Partial<IdentityFormValues>;
  clarification?: {
    answer?: string;
    selected_direction?: string;
    capability_action?: "keep-active" | "restore-archived" | "start-new" | null;
    target_domain_id?: string;
  };
  naming?: {
    buddy_name?: string;
  };
  step?: number;
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
    question_count: Math.max(1, surface.onboarding.question_count || 1),
    next_question: surface.onboarding.next_question || "",
    finished: Boolean(surface.onboarding.completed),
  };
}

function buildClarificationFromSurface(
  surface: BuddySurfaceResponse,
): BuddyClarificationResponse | null {
  if (!surface.onboarding?.session_id) {
    return null;
  }
  return {
    session_id: surface.onboarding.session_id,
    question_count: Math.max(1, surface.onboarding.question_count || 1),
    tightened: Boolean(surface.onboarding.tightened),
    finished: Boolean(
      surface.onboarding.requires_direction_confirmation ||
        surface.onboarding.requires_naming ||
        surface.onboarding.completed,
    ),
    next_question: surface.onboarding.next_question || "",
    candidate_directions: surface.onboarding.candidate_directions || [],
    recommended_direction: surface.onboarding.recommended_direction || "",
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
      question_count: Math.max(1, surface.onboarding.question_count || 1),
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
      },
    domain_capability: null,
    execution_carrier: surface.execution_carrier,
  };
}

export default function BuddyOnboardingPage() {
  const navigate = useNavigate();
  const [form] = Form.useForm<IdentityFormValues>();
  const watchedIdentityValues = Form.useWatch([], form);
  const [initialDraft] = useState<BuddyOnboardingDraft | null>(() =>
    sanitizeDraft(loadBuddyOnboardingDraft()),
  );
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [identity, setIdentity] = useState<BuddyIdentityResponse | null>(null);
  const [clarification, setClarification] =
    useState<BuddyClarificationResponse | null>(null);
  const [questionAnswer, setQuestionAnswer] = useState(
    () => initialDraft?.clarification?.answer || "",
  );
  const [confirmPayload, setConfirmPayload] =
    useState<BuddyConfirmDirectionResponse | null>(null);
  const [currentStep, setCurrentStep] = useState<number>(
    () => initialDraft?.step ?? 0,
  );
  const [selectedDirection, setSelectedDirection] = useState(
    () => initialDraft?.clarification?.selected_direction || "",
  );
  const [transitionPreview, setTransitionPreview] =
    useState<BuddyDirectionTransitionPreviewResponse | null>(null);
  const [selectedCapabilityAction, setSelectedCapabilityAction] = useState<
    "keep-active" | "restore-archived" | "start-new" | null
  >(() => initialDraft?.clarification?.capability_action ?? null);
  const [selectedTargetDomainId, setSelectedTargetDomainId] = useState<string | undefined>(
    () => initialDraft?.clarification?.target_domain_id,
  );
  const [buddyNameDraft, setBuddyNameDraft] = useState(
    () => initialDraft?.naming?.buddy_name || "",
  );
  const [draftEnabled, setDraftEnabled] = useState(true);

  const applyBuddySurface = (surface: BuddySurfaceResponse) => {
    const nextIdentity = buildIdentityFromSurface(surface);
    const nextClarification = buildClarificationFromSurface(surface);
    const nextConfirmPayload = buildConfirmPayloadFromSurface(surface);
    if (surface.profile?.profile_id) {
      writeBuddyProfileId(surface.profile.profile_id);
    }
    setIdentity(nextIdentity);
    setClarification(nextClarification);
    if (nextIdentity?.profile) {
      form.setFieldsValue(buildIdentityFormValues(nextIdentity.profile));
    }
    if (surface.onboarding?.recommended_direction) {
      setSelectedDirection(
        surface.onboarding.selected_direction ||
          surface.onboarding.recommended_direction ||
          "",
      );
    }
    if (surface.relationship?.buddy_name?.trim()) {
      setBuddyNameDraft(surface.relationship.buddy_name.trim());
    }
    if (nextConfirmPayload) {
      setConfirmPayload(nextConfirmPayload);
      setCurrentStep(2);
      return;
    }
    if (nextIdentity) {
      setCurrentStep(1);
      return;
    }
    setCurrentStep(0);
  };

  useEffect(() => {
    if (initialDraft?.identity) {
      form.setFieldsValue(initialDraft.identity);
    }
  }, [form, initialDraft]);

  useEffect(() => {
    if (!draftEnabled) {
      return;
    }
    saveBuddyOnboardingDraft({
      identity:
        watchedIdentityValues && typeof watchedIdentityValues === "object"
          ? watchedIdentityValues
          : undefined,
      clarification: {
        answer: questionAnswer,
        selected_direction: selectedDirection,
        capability_action: selectedCapabilityAction,
        target_domain_id: selectedTargetDomainId,
      },
      naming: {
        buddy_name: buddyNameDraft,
      },
      step: currentStep,
    } satisfies BuddyOnboardingDraft);
  }, [
    buddyNameDraft,
    currentStep,
    draftEnabled,
    questionAnswer,
    selectedCapabilityAction,
    selectedDirection,
    selectedTargetDomainId,
    watchedIdentityValues,
  ]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const surface = await api.getBuddySurface(readBuddyProfileId());
        if (cancelled) return;
        if (surface?.profile?.profile_id) {
          writeBuddyProfileId(surface.profile.profile_id);
        }
        const decision = resolveBuddyEntryDecision(surface);
        if (decision.mode === "chat-ready" && surface?.profile?.profile_id) {
          if (!surface.execution_carrier) {
            setError("伙伴聊天页还没准备好，请刷新后重试。");
            return;
          }
          const binding = buildBuddyExecutionCarrierChatBinding({
            sessionId: null,
            profileId: surface.profile.profile_id,
            profileDisplayName: surface.profile.display_name,
            executionCarrier: surface.execution_carrier,
            entrySource: "buddy-onboarding-resume",
          });
          await openRuntimeChat(binding, navigate, {
            shouldNavigate: () => !cancelled,
          });
          return;
        }
        if (
          decision.mode === "resume-onboarding" &&
          surface?.profile?.profile_id &&
          surface.onboarding
        ) {
          applyBuddySurface(surface);
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
  }, [navigate]);

  const handleSubmitIdentity = async (values: IdentityFormValues) => {
    setSubmitting(true);
    setError(null);
    try {
      const payload = {
        display_name: values.display_name,
        profession: values.profession,
        current_stage: values.current_stage,
        interests: parseLines(values.interests),
        strengths: parseLines(values.strengths),
        constraints: parseLines(values.constraints),
        goal_intention: values.goal_intention,
      };
      const result = await api.submitBuddyIdentity(payload);
      writeBuddyProfileId(result.profile.profile_id);
      setIdentity(result);
      setClarification({
        session_id: result.session_id,
        question_count: result.question_count,
        tightened: false,
        finished: false,
        next_question: result.next_question,
        candidate_directions: [],
        recommended_direction: "",
      });
      setConfirmPayload(null);
      setSelectedDirection("");
      setTransitionPreview(null);
      setSelectedCapabilityAction(null);
      setSelectedTargetDomainId(undefined);
      setBuddyNameDraft("");
      setCurrentStep(1);
    } catch (rawError) {
      void rawError;
      setError("身份信息提交失败，请稍后重试。");
    } finally {
      setSubmitting(false);
    }
  };

  const handleClarify = async () => {
    if (!identity || !questionAnswer.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.answerBuddyClarification({
        session_id: identity.session_id,
        answer: questionAnswer.trim(),
        existing_question_count: clarification?.question_count,
      });
      setClarification(result);
      setQuestionAnswer("");
      setTransitionPreview(null);
      setSelectedCapabilityAction(null);
      setSelectedTargetDomainId(undefined);
      if (result.finished && result.recommended_direction) {
        setSelectedDirection(result.recommended_direction);
      }
    } catch (rawError) {
      void rawError;
      setError("方向澄清失败，请稍后重试。");
    } finally {
      setSubmitting(false);
    }
  };

  const handlePreviewDirectionTransition = async () => {
    if (!identity || !selectedDirection.trim()) return;
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
    } catch (rawError) {
      void rawError;
      setError("方向确认失败，请稍后重试。");
    } finally {
      setSubmitting(false);
    }
  };

  const handleConfirmDirection = async () => {
    if (!identity || !selectedDirection.trim() || !transitionPreview || !selectedCapabilityAction) {
      return;
    }
    if (selectedCapabilityAction === "restore-archived" && !selectedTargetDomainId) {
      setError("请选择要恢复的历史领域能力。");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.confirmBuddyDirection({
        session_id: identity.session_id,
        selected_direction: selectedDirection,
        capability_action: selectedCapabilityAction,
        target_domain_id:
          selectedCapabilityAction === "restore-archived"
            ? selectedTargetDomainId
            : undefined,
      });
      writeBuddyProfileId(result.session.profile_id);
      setConfirmPayload(result);
      setCurrentStep(2);
    } catch (rawError) {
      void rawError;
      setError("方向确认失败，请稍后重试。");
    } finally {
      setSubmitting(false);
    }
  };

  const handleStartChat = async () => {
    if (
      !identity ||
      !confirmPayload?.session?.session_id ||
      !buddyNameDraft.trim()
    ) {
      return;
    }
    const executionCarrier = confirmPayload.execution_carrier;
    if (!executionCarrier) {
      setError("伙伴聊天页还没准备好，请刷新后重试。");
      return;
    }
    try {
      setSubmitting(true);
      setError(null);
      const named = await api.nameBuddy({
        session_id: confirmPayload.session.session_id,
        buddy_name: buddyNameDraft.trim(),
      });
      writeBuddyProfileId(named.profile_id);
      setDraftEnabled(false);
      clearBuddyOnboardingDraft();
      const binding = buildBuddyExecutionCarrierChatBinding({
        sessionId: confirmPayload.session.session_id,
        profileId: identity.profile.profile_id,
        profileDisplayName: identity.profile.display_name,
        executionCarrier,
      });
      await openRuntimeChat(binding, navigate);
    } catch (rawError) {
      void rawError;
      setError("进入聊天失败，请稍后重试。");
    } finally {
      setSubmitting(false);
    }
  };

  const stepIndex = currentStep;

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
            首次创建伙伴档案
          </Title>
          <Paragraph style={{ margin: 0 }}>
            先让我认真了解你，再一起把长期方向收口成一个足够大的主方向。
            默认不会把整棵计划树都压给你，只会先让你看清最终目标和当前这一步。
          </Paragraph>
          <Steps
            current={stepIndex}
            items={[
              { title: "身份资料" },
              { title: "方向确认" },
              { title: "伙伴名称" },
            ]}
          />
        </Space>
      </Card>

      {error ? <Alert type="error" showIcon message={error} /> : null}
      {(!identity || currentStep === 0) ? (
        <Card title="先告诉我你是谁">
          <Form
            form={form}
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
                placeholder="例如：探索期、转型期、重建期、稳定增长期"
                data-testid="buddy-identity-current-stage"
              />
            </Form.Item>
            <Form.Item label="爱好" name="interests">
              <TextArea rows={2} placeholder="可用逗号、顿号或换行分隔" />
            </Form.Item>
            <Form.Item label="特长" name="strengths">
              <TextArea rows={2} placeholder="你做得比大多数人更稳的事情" />
            </Form.Item>
            <Form.Item label="限制 / 困境" name="constraints">
              <TextArea rows={2} placeholder="时间、金钱、精力、环境约束等" />
            </Form.Item>
            <Form.Item label="目标意向" name="goal_intention" rules={[{ required: true }]}>
              <TextArea
                rows={3}
                placeholder="先说你隐约想改变什么，模糊也没有关系。"
                data-testid="buddy-identity-goal-intention"
              />
            </Form.Item>
            <Button type="primary" htmlType="submit" loading={submitting}>
              开始创建伙伴档案
            </Button>
          </Form>
        </Card>
      ) : null}

      {currentStep === 1 && identity && !clarification?.finished ? (
        <Card title="再回答我几句，我帮你把方向收得更准">
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <Alert
              type="info"
              showIcon
              message={`第 ${clarification?.question_count ?? identity.question_count} / 9 问`}
              description={
                clarification?.tightened
                  ? "我会开始收紧追问，避免一直聊天却得不到真正可执行的方向。"
                  : "现在模糊没有关系，我会陪你慢慢把方向收口。"
              }
            />
            <Card size="small">
              <strong>{clarification?.next_question || identity.next_question}</strong>
            </Card>
            <TextArea
              rows={4}
              value={questionAnswer}
              onChange={(event) => setQuestionAnswer(event.target.value)}
              placeholder="用最真实的话回答我，不用写得很工整。"
              data-testid="buddy-clarification-answer"
            />
            <Space>
              <Button onClick={() => setCurrentStep(0)} data-testid="buddy-step-back">
                返回上一步
              </Button>
              <Button
                type="primary"
                onClick={() => void handleClarify()}
                loading={submitting}
                data-testid="buddy-clarification-submit"
              >
                继续
              </Button>
            </Space>
          </Space>
        </Card>
      ) : null}

      {currentStep === 1 && identity && clarification?.finished && !confirmPayload ? (
        <Card title="我先给你 2-3 个候选大方向，但你只确认 1 个主方向">
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <Paragraph style={{ marginBottom: 0 }}>
              主方向必须足够大，不能是零碎愿望。后面的阶段目标和当前任务，都会从这个方向里拆出来。
            </Paragraph>
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
                {clarification.candidate_directions.map((direction) => (
                  <Radio key={direction} value={direction}>
                    {direction}
                  </Radio>
                ))}
              </Space>
            </Radio.Group>
            <Alert
              type="success"
              showIcon
              message="推荐主方向"
              description={clarification.recommended_direction}
              data-testid="buddy-direction-recommendation"
            />
            {!transitionPreview ? (
              <Button
                type="primary"
                disabled={!selectedDirection}
                loading={submitting}
                onClick={() => void handlePreviewDirectionTransition()}
                data-testid="buddy-direction-confirm"
              >
                先预览能力继承方式
              </Button>
            ) : (
              <Card
                size="small"
                title="确认这次目标切换怎么处理超级伙伴的能力积累"
                data-testid="buddy-transition-choice-panel"
              >
                <Space direction="vertical" size={16} style={{ width: "100%" }}>
                  <Alert
                    type="info"
                    showIcon
                    message="系统建议"
                    description={transitionPreview.reason_summary}
                  />
                  <Paragraph
                    type="secondary"
                    style={{ marginBottom: 0 }}
                    data-testid="buddy-transition-scope-note"
                  >
                    普通领域扩展继续在聊天里推进；这里只用于切换当前主领域。
                  </Paragraph>
                  {transitionPreview.current_domain ? (
                    <Paragraph style={{ marginBottom: 0 }}>
                      <strong>当前活跃领域：</strong>
                      {` ${transitionPreview.current_domain.domain_label} · 积分 ${transitionPreview.current_domain.capability_points ?? 0}`}
                    </Paragraph>
                  ) : null}
                  {transitionPreview.archived_matches.length ? (
                    <Paragraph style={{ marginBottom: 0 }}>
                      <strong>可恢复历史领域：</strong>
                      {` ${transitionPreview.archived_matches.map((item) => `${item.domain_label}(积分 ${item.capability_points ?? 0})`).join(" / ")}`}
                    </Paragraph>
                  ) : null}
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
                        继续当前领域能力
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
                            {`${item.domain_label} · 积分 ${item.capability_points ?? 0}`}
                          </Radio>
                        ))}
                      </Space>
                    </Radio.Group>
                  ) : null}
                  <Space>
                    <Button
                      onClick={() => {
                        setTransitionPreview(null);
                        setSelectedCapabilityAction(null);
                        setSelectedTargetDomainId(undefined);
                      }}
                    >
                      重新选择方向
                    </Button>
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
                      确认切换方式，填写伙伴名称
                    </Button>
                  </Space>
                </Space>
              </Card>
            )}
          </Space>
        </Card>
      ) : null}

      {currentStep === 2 && identity && confirmPayload ? (
        <Card
          title="已确认方向，填写伙伴名称"
          data-testid="buddy-direction-confirmed"
        >
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <Alert
              type="success"
              showIcon
              message="你的长期方向已经生成好了"
              description="下一步先给伙伴取名，确认后再进入聊天页。"
            />
            <Paragraph style={{ marginBottom: 0 }}>
              <strong>已确认方向：</strong>{" "}
              {confirmPayload.growth_target?.primary_direction || selectedDirection}
            </Paragraph>
            {confirmPayload.execution_carrier?.label ? (
              <Paragraph style={{ marginBottom: 0 }}>
                <strong>已生成载体：</strong> {confirmPayload.execution_carrier.label}
              </Paragraph>
            ) : null}
            <Input
              value={buddyNameDraft}
              onChange={(event) => setBuddyNameDraft(event.target.value)}
              placeholder="给伙伴起个名字"
              data-testid="buddy-name-input"
            />
            <Button
              onClick={() => {
                setConfirmPayload(null);
                setCurrentStep(1);
              }}
              data-testid="buddy-step-back"
            >
              返回上一步
            </Button>
            <Button
              type="primary"
              loading={submitting}
              disabled={!buddyNameDraft.trim()}
              onClick={() => void handleStartChat()}
              data-testid="buddy-start-chat"
            >
              开始聊天
            </Button>
          </Space>
        </Card>
      ) : null}
    </div>
  );
}
