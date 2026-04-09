import { describe, expect, it } from "vitest";

import {
  buildBuddyExecutionCarrierChatBinding,
  resolveRuntimeChatEntryPath,
} from "./runtimeChat";

describe("resolveRuntimeChatEntryPath", () => {
  it("keeps a formal runtime thread bound to the chat route", () => {
    expect(
      resolveRuntimeChatEntryPath("industry-chat:industry-1:execution-core"),
    ).toBe("/chat?threadId=industry-chat%3Aindustry-1%3Aexecution-core");
  });

  it("falls back to the generic chat route when no formal thread is active", () => {
    expect(resolveRuntimeChatEntryPath(null)).toBe("/chat");
    expect(resolveRuntimeChatEntryPath("chat:transient")).toBe("/chat");
  });

  it("prefers the canonical buddy control thread derived from instance_id over stale carrier ids", () => {
    const binding = buildBuddyExecutionCarrierChatBinding({
      profileId: "profile-1",
      profileDisplayName: "Buddy",
      executionCarrier: {
        instance_id: "buddy:profile-1:domain-current",
        label: "Buddy Carrier",
        owner_scope: "profile-1",
        current_cycle_id: "cycle-1",
        team_generated: true,
        thread_id: "industry-chat:buddy:profile-1:domain-stale:execution-core",
        control_thread_id: "industry-chat:buddy:profile-1:domain-stale:execution-core",
        chat_binding: {
          thread_id: "industry-chat:buddy:profile-1:domain-stale:execution-core",
          control_thread_id: "industry-chat:buddy:profile-1:domain-stale:execution-core",
          context_key:
            "control-thread:industry-chat:buddy:profile-1:domain-stale:execution-core",
          binding_kind: "buddy-execution-carrier",
        },
      },
      entrySource: "buddy-onboarding-resume",
    });

    expect(binding.threadId).toBe(
      "industry-chat:buddy:profile-1:domain-current:execution-core",
    );
    expect(binding.meta?.control_thread_id).toBe(
      "industry-chat:buddy:profile-1:domain-current:execution-core",
    );
    expect(binding.meta?.context_key).toBe(
      "control-thread:industry-chat:buddy:profile-1:domain-current:execution-core",
    );
  });
});
