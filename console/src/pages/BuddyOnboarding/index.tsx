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
  BuddyOnboardingOperationResponse,
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

type PendingBuddyOperation = BuddyOnboardingOperationResponse;

function parseLines(value?: string | null): string[] {
  return (value || "")
    .split(/[\n,，、]/)
    .map((item) => item.trim())
    .filter(Boolean);
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
    !surface.execution_carrier
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
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [identity, setIdentity] = useState<BuddyIdentityResponse | null>(null);
  const [clarification, setClarification] =
    useState<BuddyClarificationResponse | null>(null);
  const [questionAnswer, setQuestionAnswer] = useState("");
  const [confirmPayload, setConfirmPayload] =
    useState<BuddyConfirmDirectionResponse | null>(null);
  const [pendingOperation, setPendingOperation] =
    useState<PendingBuddyOperation | null>(null);
  const [selectedDirection, setSelectedDirection] = useState("");
  const [transitionPreview, setTransitionPreview] =
    useState<BuddyDirectionTransitionPreviewResponse | null>(null);
  const [selectedCapabilityAction, setSelectedCapabilityAction] = useState<
    "keep-active" | "restore-archived" | "start-new" | null
  >(null);
  const [selectedTargetDomainId, setSelectedTargetDomainId] = useState<string | undefined>();

  const applyBuddySurface = (surface: BuddySurfaceResponse) => {
    const nextIdentity = buildIdentityFromSurface(surface);
    const nextClarification = buildClarificationFromSurface(surface);
    const nextConfirmPayload = buildConfirmPayloadFromSurface(surface);
    if (surface.profile?.profile_id) {
      writeBuddyProfileId(surface.profile.profile_id);
    }
    setIdentity(nextIdentity);
    setClarification(nextClarification);
    if (surface.onboarding?.recommended_direction) {
      setSelectedDirection(
        surface.onboarding.selected_direction ||
          surface.onboarding.recommended_direction ||
          "",
      );
    }
    if (nextConfirmPayload) {
      setConfirmPayload(nextConfirmPayload);
    }
  };

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
            setError("伙伴主场尚未准备完成，请刷新后重试。");
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
          decision.mode === "chat-needs-naming" &&
          surface?.profile?.profile_id
        ) {
          if (!surface.execution_carrier) {
            setError("伙伴主场尚未准备完成，请刷新后重试。");
            return;
          }
          const binding = buildBuddyExecutionCarrierChatBinding({
            sessionId: decision.sessionId,
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
          if (
            surface.onboarding.operation_status === "running" &&
            surface.onboarding.operation_id
          ) {
            setPendingOperation({
              session_id: surface.onboarding.session_id ?? "",
              profile_id: surface.profile.profile_id,
              operation_id: surface.onboarding.operation_id,
              operation_kind: surface.onboarding.operation_kind,
              operation_status: surface.onboarding.operation_status,
            });
          }
        }
      } catch (rawError) {
        if (cancelled) return;
        if (!isApiError(rawError) || rawError.status !== 404) {
          setError(rawError instanceof Error ? rawError.message : "伙伴建档加载失败");
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

  useEffect(() => {
    if (!pendingOperation) {
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const poll = async () => {
      try {
        const surface = await api.getBuddySurface(pendingOperation.profile_id);
        if (cancelled || !surface) {
          return;
        }
        const onboarding = surface.onboarding;
        if (
          onboarding.session_id !== pendingOperation.session_id ||
          onboarding.operation_id !== pendingOperation.operation_id
        ) {
          timer = setTimeout(() => {
            void poll();
          }, 1500);
          return;
        }
        if (onboarding.operation_status === "running") {
          timer = setTimeout(() => {
            void poll();
          }, 1500);
          return;
        }
        applyBuddySurface(surface);
        if (onboarding.operation_status === "failed") {
          setError(onboarding.operation_error || "Buddy 建档失败");
        }
        setPendingOperation(null);
      } catch (rawError) {
        if (!cancelled) {
          setError(rawError instanceof Error ? rawError.message : "Buddy 建档失败");
          setPendingOperation(null);
        }
      }
    };

    void poll();

    return () => {
      cancelled = true;
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, [pendingOperation]);

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
      const operation = await api.startBuddyIdentity(payload);
      writeBuddyProfileId(operation.profile_id);
      setIdentity({
        session_id: operation.session_id,
        profile: {
          profile_id: operation.profile_id,
          display_name: payload.display_name,
          profession: payload.profession,
          current_stage: payload.current_stage,
          interests: payload.interests,
          strengths: payload.strengths,
          constraints: payload.constraints,
          goal_intention: payload.goal_intention,
        },
        question_count: 1,
        next_question: "",
        finished: false,
      });
      setClarification(null);
      setConfirmPayload(null);
      setSelectedDirection("");
      setTransitionPreview(null);
      setSelectedCapabilityAction(null);
      setSelectedTargetDomainId(undefined);
      setPendingOperation(operation);
    } catch (rawError) {
      setError(rawError instanceof Error ? rawError.message : "身份建档失败");
    } finally {
      setSubmitting(false);
    }
  };

  const handleClarify = async () => {
    if (!identity || !questionAnswer.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const operation = await api.startBuddyClarification({
        session_id: identity.session_id,
        answer: questionAnswer.trim(),
        existing_question_count: clarification?.question_count,
      });
      setQuestionAnswer("");
      setTransitionPreview(null);
      setSelectedCapabilityAction(null);
      setSelectedTargetDomainId(undefined);
      setPendingOperation(operation);
    } catch (rawError) {
      setError(rawError instanceof Error ? rawError.message : "方向澄清失败");
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
      setError(rawError instanceof Error ? rawError.message : "主方向确认失败");
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
      const operation = await api.startBuddyConfirmDirection({
        session_id: identity.session_id,
        selected_direction: selectedDirection,
        capability_action: selectedCapabilityAction,
        target_domain_id:
          selectedCapabilityAction === "restore-archived"
            ? selectedTargetDomainId
            : undefined,
      });
      setPendingOperation(operation);
    } catch (rawError) {
      setError(rawError instanceof Error ? rawError.message : "主方向确认失败");
    } finally {
      setSubmitting(false);
    }
  };

  const handleEnterChat = async () => {
    if (!identity || !confirmPayload?.session?.session_id) return;
    const executionCarrier = confirmPayload.execution_carrier;
    if (!executionCarrier) {
      setError("伙伴主场尚未准备完成，请刷新后重试。");
      return;
    }
    try {
      const binding = buildBuddyExecutionCarrierChatBinding({
        sessionId: confirmPayload.session.session_id,
        profileId: identity.profile.profile_id,
        profileDisplayName: identity.profile.display_name,
        executionCarrier,
      });
      await openRuntimeChat(binding, navigate);
      return;
    } catch (rawError) {
      setError(rawError instanceof Error ? rawError.message : "进入聊天失败");
      return;
    }
  };

  const stepIndex = confirmPayload ? 2 : clarification?.finished ? 2 : identity ? 1 : 0;

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
            超级伙伴初次建档
          </Title>
          <Paragraph style={{ margin: 0 }}>
            先让我认真了解你，再一起把长期方向收口成一个足够大的主方向。
            默认不会把整棵计划树都压给你，只会先让你看清最终目标和当前这一步。
          </Paragraph>
          <Steps
            current={stepIndex}
            items={[
              { title: "身份建档" },
              { title: "方向澄清" },
              { title: "确认主方向" },
            ]}
          />
        </Space>
      </Card>

      {error ? <Alert type="error" showIcon message={error} /> : null}
      {pendingOperation ? (
        <Alert
          type="info"
          showIcon
          message="我在后台认真分析你的情况，模型慢时会继续处理中，不用重复点击。"
        />
      ) : null}

      {!identity ? (
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
            <Button type="primary" htmlType="submit" loading={submitting || Boolean(pendingOperation)}>
              开始建立伙伴关系
            </Button>
          </Form>
        </Card>
      ) : null}

      {identity && !clarification?.finished ? (
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
              <Button
                type="primary"
                onClick={() => void handleClarify()}
                loading={submitting || Boolean(pendingOperation)}
                data-testid="buddy-clarification-submit"
              >
                继续
              </Button>
            </Space>
          </Space>
        </Card>
      ) : null}

      {identity && clarification?.finished && !confirmPayload ? (
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
                loading={submitting || Boolean(pendingOperation)}
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
                      loading={submitting || Boolean(pendingOperation)}
                      disabled={
                        !selectedCapabilityAction ||
                        (selectedCapabilityAction === "restore-archived" &&
                          !selectedTargetDomainId)
                      }
                      onClick={() => void handleConfirmDirection()}
                      data-testid="buddy-transition-confirm"
                    >
                      确认切换方式，进入聊天主场
                    </Button>
                  </Space>
                </Space>
              </Card>
            )}
          </Space>
        </Card>
      ) : null}

      {identity && confirmPayload ? (
        <Card
          title="已完成方向确认，准备进入伙伴主场"
          data-testid="buddy-direction-confirmed"
        >
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <Alert
              type="success"
              showIcon
              message="你的长期方向已经生成好了"
              description="下一步进入聊天主场，给伙伴起名，然后只看最终目标和当前这一步。"
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
            <Button
              type="primary"
              onClick={() => void handleEnterChat()}
              data-testid="buddy-direction-enter-chat"
            >
              进入聊天，给伙伴起名
            </Button>
          </Space>
        </Card>
      ) : null}
    </div>
  );
}
