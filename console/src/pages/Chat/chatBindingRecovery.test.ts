import { describe, expect, it } from "vitest";

import type { IndustryInstanceSummary } from "../../api/modules/industry";
import {
  resolveChatBindingRecoveryAction,
} from "./chatBindingRecovery";

const executionCoreInstance = {
  instance_id: "industry-1",
  label: "Industry One",
} as unknown as IndustryInstanceSummary;

describe("chatBindingRecovery", () => {
  it("auto-binds the sole execution-core suggestion when chat opens without an explicit thread", () => {
    const action = resolveChatBindingRecoveryAction({
      requestedThreadId: null,
      requestedThreadLooksBound: false,
      threadBootstrapError: null,
      threadBootstrapPending: false,
      autoBindingPending: false,
      hasBoundAgentContext: false,
      defaultAutoBindAttempted: false,
      recoveryAttempts: new Set<string>(),
      executionCoreSuggestions: [executionCoreInstance],
    });

    expect(action).toEqual({
      type: "bind-instance",
      instance: executionCoreInstance,
      recoveryToken: null,
      markDefaultAttempt: true,
    });
  });

  it("rebinds a failed industry control thread to its matched execution-core instance", () => {
    const action = resolveChatBindingRecoveryAction({
      requestedThreadId: "industry-chat:industry-1:execution-core",
      requestedThreadLooksBound: true,
      threadBootstrapError: "missing owner",
      threadBootstrapPending: false,
      autoBindingPending: false,
      hasBoundAgentContext: false,
      defaultAutoBindAttempted: true,
      recoveryAttempts: new Set<string>(),
      executionCoreSuggestions: [executionCoreInstance],
    });

    expect(action).toEqual({
      type: "bind-instance",
      instance: executionCoreInstance,
      recoveryToken: "industry-chat:industry-1:execution-core",
      markDefaultAttempt: false,
    });
  });

  it("falls back to resetting chat when a bound thread loses owner context and no matching instance exists", () => {
    const action = resolveChatBindingRecoveryAction({
      requestedThreadId: "industry-chat:industry-missing:execution-core",
      requestedThreadLooksBound: true,
      threadBootstrapError: null,
      threadBootstrapPending: false,
      autoBindingPending: false,
      hasBoundAgentContext: false,
      defaultAutoBindAttempted: true,
      recoveryAttempts: new Set<string>(),
      executionCoreSuggestions: [executionCoreInstance],
    });

    expect(action).toEqual({
      type: "reset-chat",
      recoveryToken:
        "rebind:industry-chat:industry-missing:execution-core:missing-owner",
    });
  });

  it("does not repeat reset recovery when bootstrap error details change for the same thread", () => {
    const action = resolveChatBindingRecoveryAction({
      requestedThreadId: "industry-chat:industry-missing:execution-core",
      requestedThreadLooksBound: true,
      threadBootstrapError: "bootstrap timed out after 8s",
      threadBootstrapPending: false,
      autoBindingPending: false,
      hasBoundAgentContext: false,
      defaultAutoBindAttempted: true,
      recoveryAttempts: new Set<string>([
        "rebind:industry-chat:industry-missing:execution-core:bootstrap-error",
      ]),
      executionCoreSuggestions: [executionCoreInstance],
    });

    expect(action).toBeNull();
  });

  it("emits a stable bootstrap-error recovery token independent of raw error text", () => {
    const action = resolveChatBindingRecoveryAction({
      requestedThreadId: "industry-chat:industry-missing:execution-core",
      requestedThreadLooksBound: true,
      threadBootstrapError: "rpc failed: timeout",
      threadBootstrapPending: false,
      autoBindingPending: false,
      hasBoundAgentContext: false,
      defaultAutoBindAttempted: true,
      recoveryAttempts: new Set<string>(),
      executionCoreSuggestions: [executionCoreInstance],
    });

    expect(action).toEqual({
      type: "reset-chat",
      recoveryToken:
        "rebind:industry-chat:industry-missing:execution-core:bootstrap-error",
    });
  });
});
