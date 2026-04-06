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
  BuddyIdentityResponse,
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

function parseLines(value?: string | null): string[] {
  return (value || "")
    .split(/[\n,，、]/)
    .map((item) => item.trim())
    .filter(Boolean);
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
  const [selectedDirection, setSelectedDirection] = useState("");

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
          setIdentity({
            session_id: surface.onboarding.session_id ?? "",
            profile: surface.profile,
            question_count: surface.onboarding.question_count,
            next_question: surface.onboarding.next_question,
            finished: surface.onboarding.completed,
          });
          setClarification({
            session_id: surface.onboarding.session_id ?? "",
            question_count: surface.onboarding.question_count,
            tightened: surface.onboarding.tightened,
            finished:
              surface.onboarding.requires_direction_confirmation ||
              surface.onboarding.completed,
            next_question: surface.onboarding.next_question,
            candidate_directions: surface.onboarding.candidate_directions,
            recommended_direction: surface.onboarding.recommended_direction,
          });
          setSelectedDirection(
            surface.onboarding.selected_direction ||
              surface.onboarding.recommended_direction ||
              "",
          );
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
      setClarification(null);
      setSelectedDirection("");
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
      const result = await api.answerBuddyClarification({
        session_id: identity.session_id,
        answer: questionAnswer.trim(),
        existing_question_count: clarification?.question_count,
      });
      setClarification(result);
      setQuestionAnswer("");
      if (result.finished && result.recommended_direction) {
        setSelectedDirection(result.recommended_direction);
      }
    } catch (rawError) {
      setError(rawError instanceof Error ? rawError.message : "方向澄清失败");
    } finally {
      setSubmitting(false);
    }
  };

  const handleConfirmDirection = async () => {
    if (!identity || !selectedDirection.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.confirmBuddyDirection({
        session_id: identity.session_id,
        selected_direction: selectedDirection,
      });
      writeBuddyProfileId(result.session.profile_id);
      setConfirmPayload(result);
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
            Buddy 初次建档
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
            <Button type="primary" htmlType="submit" loading={submitting}>
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
                loading={submitting}
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
              onChange={(event) => setSelectedDirection(event.target.value)}
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
            <Button
              type="primary"
              disabled={!selectedDirection}
              loading={submitting}
              onClick={() => void handleConfirmDirection()}
              data-testid="buddy-direction-confirm"
            >
              确认这个主方向，进入聊天主场
            </Button>
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
