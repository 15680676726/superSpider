export interface RuntimeWaitState {
  startedAt: number;
  activeLabel: string;
  fallbackCount: number;
  resolutionReason?: string | null;
}

export interface RuntimeHealthNotice {
  type: "warning" | "error";
  title: string;
  description: string;
}

interface RuntimeErrorText {
  title: string;
  summary: string;
  type?: "warning" | "error";
}

const RUNTIME_ERROR_TEXT_MAP: Record<string, RuntimeErrorText> = {
  MODEL_AUTH_FAILED: {
    title: "模型鉴权失败",
    summary: "模型通道鉴权失败，请检查接口密钥、账号状态或上游渠道授权。",
    type: "error",
  },
  MODEL_RATE_LIMITED: {
    title: "模型请求受限",
    summary: "模型上游当前限流或额度不足，系统可以尝试其他候选模型。",
    type: "warning",
  },
  MODEL_FIRST_TOKEN_TIMEOUT: {
    title: "模型首响应超时",
    summary: "等待首个响应片段超时，通常是上游模型或渠道暂时不稳定。",
    type: "warning",
  },
  MODEL_REQUEST_TIMEOUT: {
    title: "模型请求超时",
    summary: "模型请求超时，当前上游没有在预期时间内完成响应。",
    type: "warning",
  },
  MODEL_CONNECTION_FAILED: {
    title: "模型连接失败",
    summary: "模型上游连接异常，当前请求未能建立稳定通道。",
    type: "error",
  },
  MODEL_UPSTREAM_BAD_GATEWAY: {
    title: "模型上游网关异常",
    summary: "上游渠道返回了网关错误，通常是中转或线路暂时不可用。",
    type: "error",
  },
  MODEL_CHANNEL_UNAVAILABLE: {
    title: "模型通道不可用",
    summary: "当前模型通道不可用，系统会优先尝试回退候选。",
    type: "warning",
  },
  MODEL_UPSTREAM_UNAVAILABLE: {
    title: "模型上游不可用",
    summary: "上游模型当前不可用，系统会优先尝试其他候选。",
    type: "warning",
  },
  MODEL_UPSTREAM_ERROR: {
    title: "模型上游异常",
    summary: "模型上游返回异常，当前请求无法稳定执行。",
    type: "error",
  },
  MODEL_REQUEST_INVALID: {
    title: "模型请求无效",
    summary: "当前请求被模型上游拒绝，通常是参数、上下文或工具载荷不合法。",
    type: "error",
  },
  MODEL_SLOT_UNAVAILABLE: {
    title: "没有可用模型",
    summary: "当前没有可用的聊天模型，请检查激活模型、接口密钥和回退链配置。",
    type: "error",
  },
  MODEL_RUNTIME_FAILED: {
    title: "模型执行失败",
    summary: "模型执行过程中发生异常。",
    type: "error",
  },
  AGENT_UNKNOWN_ERROR: {
    title: "执行异常",
    summary: "执行过程中发生未归类异常，请结合诊断信息继续排查。",
    type: "error",
  },
};

export function localizeRuntimeError(
  code: unknown,
  message: unknown,
): RuntimeHealthNotice & {
  rawCode: string;
  rawMessage: string;
} {
  const rawCode =
    typeof code === "string" && code.trim() ? code.trim() : "RUNTIME_ERROR";
  const rawMessage =
    typeof message === "string" && message.trim()
      ? message.trim()
      : "执行过程中发生异常。";
  const preset = RUNTIME_ERROR_TEXT_MAP[rawCode];
  const title = preset?.title || rawCode;
  const defaultSummary = preset?.summary || "执行过程中发生异常。";
  const description =
    rawMessage === rawCode ? defaultSummary : rawMessage || defaultSummary;
  return {
    type: preset?.type || "error",
    title,
    description,
    rawCode,
    rawMessage,
  };
}

export function localizeRuntimeChunk(chunk: unknown): unknown {
  if (!chunk || typeof chunk !== "object") {
    return chunk;
  }
  const nextChunk = { ...(chunk as Record<string, unknown>) };
  const objectType = nextChunk.object;
  if (objectType === "response") {
    const error = nextChunk.error;
    if (error && typeof error === "object") {
      const localized = localizeRuntimeError(
        (error as Record<string, unknown>).code,
        (error as Record<string, unknown>).message,
      );
      nextChunk.error = {
        ...(error as Record<string, unknown>),
        code: localized.title,
        message: localized.description,
        raw_code: localized.rawCode,
      };
    }
    return nextChunk;
  }
  if (objectType === "message" && nextChunk.type === "error") {
    const localized = localizeRuntimeError(nextChunk.code, nextChunk.message);
    return {
      ...nextChunk,
      code: localized.title,
      message: localized.description,
      raw_code: localized.rawCode,
    };
  }
  return nextChunk;
}

export function extractRuntimeHealthNotice(
  chunk: unknown,
): RuntimeHealthNotice | null {
  if (!chunk || typeof chunk !== "object") {
    return null;
  }
  const nextChunk = chunk as Record<string, unknown>;
  if (nextChunk.object === "response") {
    const error = nextChunk.error;
    if (error && typeof error === "object") {
      const localized = localizeRuntimeError(
        (error as Record<string, unknown>).raw_code ||
          (error as Record<string, unknown>).code,
        (error as Record<string, unknown>).message,
      );
      return {
        type: localized.type,
        title: localized.title,
        description: localized.description,
      };
    }
  }
  if (nextChunk.object === "message" && nextChunk.type === "error") {
    const localized = localizeRuntimeError(
      nextChunk.raw_code || nextChunk.code,
      nextChunk.message,
    );
    return {
      type: localized.type,
      title: localized.title,
      description: localized.description,
    };
  }
  return null;
}

export function hasRuntimeStartedResponding(chunk: unknown): boolean {
  if (!chunk || typeof chunk !== "object") {
    return false;
  }
  const nextChunk = chunk as Record<string, unknown>;
  if (
    nextChunk.object === "message" &&
    nextChunk.role !== "user" &&
    nextChunk.type !== "heartbeat" &&
    nextChunk.type !== "error"
  ) {
    return true;
  }
  if (nextChunk.object === "content") {
    return nextChunk.type !== "error";
  }
  return false;
}

export function formatRuntimeWaitMessage(
  waitState: RuntimeWaitState,
  now: number = Date.now(),
): string {
  const elapsedSeconds = Math.max(
    0,
    Math.floor((now - waitState.startedAt) / 1000),
  );
  return `正在等待模型响应，已等待 ${elapsedSeconds} 秒`;
}

export function formatRuntimeWaitDescription(waitState: RuntimeWaitState): string {
  const parts = [`当前模型：${waitState.activeLabel}`];
  if (waitState.fallbackCount > 0) {
    parts.push(`已启用回退候选 ${waitState.fallbackCount} 项`);
  }
  if (waitState.resolutionReason) {
    parts.push(waitState.resolutionReason);
  }
  return `${parts.join("；")}。如果上游线路异常，系统会优先尝试回退链。`;
}
