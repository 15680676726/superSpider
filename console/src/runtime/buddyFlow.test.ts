import { describe, expect, it } from "vitest";

import {
  BUDDY_IDENTITY_CENTER_ROUTE,
  resolveBuddyEntryDecision,
} from "./buddyFlow";

describe("buddyFlow", () => {
  it("pins the identity center to buddy onboarding", () => {
    expect(BUDDY_IDENTITY_CENTER_ROUTE).toBe("/buddy-onboarding");
  });

  it("defaults to start-onboarding when backend entry is missing", () => {
    const decision = resolveBuddyEntryDecision(null);
    expect(decision).toEqual({
      mode: "start-onboarding",
      sessionId: null,
      profileId: null,
    });
  });

  it("maps backend start-onboarding entry directly", () => {
    const decision = resolveBuddyEntryDecision({
      mode: "start-onboarding",
      profile_id: null,
      session_id: null,
    });
    expect(decision).toEqual({
      mode: "start-onboarding",
      sessionId: null,
      profileId: null,
    });
  });

  it("maps backend resume-onboarding entry directly", () => {
    const decision = resolveBuddyEntryDecision({
      mode: "resume-onboarding",
      profile_id: "profile-1",
      session_id: "session-1",
    });
    expect(decision).toEqual({
      mode: "resume-onboarding",
      sessionId: "session-1",
      profileId: "profile-1",
    });
  });

  it("maps backend chat-ready entry directly", () => {
    const decision = resolveBuddyEntryDecision({
      mode: "chat-ready",
      profile_id: "profile-1",
      profile_display_name: "Mina",
      session_id: null,
      execution_carrier: {
        instance_id: "instance-1",
        label: "Mina",
        owner_scope: "profile-1",
        current_cycle_id: "cycle-1",
        team_generated: true,
        thread_id: "thread-1",
        control_thread_id: "thread-1",
        chat_binding: {
          thread_id: "thread-1",
          control_thread_id: "thread-1",
          user_id: "buddy:profile-1",
          channel: "console",
          context_key: "control-thread:thread-1",
          binding_kind: "buddy-execution-carrier",
          metadata: {
            industry_instance_id: "instance-1",
            industry_role_id: "execution-core",
            industry_role_name: "execution-core",
            owner_scope: "profile-1",
            team_generated: true,
          },
        },
      },
    });
    expect(decision).toEqual({
      mode: "chat-ready",
      sessionId: null,
      profileId: "profile-1",
      profileDisplayName: "Mina",
      executionCarrier: {
        instance_id: "instance-1",
        label: "Mina",
        owner_scope: "profile-1",
        current_cycle_id: "cycle-1",
        team_generated: true,
        thread_id: "thread-1",
        control_thread_id: "thread-1",
        chat_binding: {
          thread_id: "thread-1",
          control_thread_id: "thread-1",
          user_id: "buddy:profile-1",
          channel: "console",
          context_key: "control-thread:thread-1",
          binding_kind: "buddy-execution-carrier",
          metadata: {
            industry_instance_id: "instance-1",
            industry_role_id: "execution-core",
            industry_role_name: "execution-core",
            owner_scope: "profile-1",
            team_generated: true,
          },
        },
      },
    });
  });
});
