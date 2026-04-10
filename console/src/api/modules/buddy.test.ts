import { beforeEach, describe, expect, it, vi } from "vitest";

const requestMock = vi.fn();

vi.mock("../request", () => ({
  request: (...args: unknown[]) => requestMock(...args),
}));

import { buddyApi } from "./buddy";

describe("buddyApi", () => {
  beforeEach(() => {
    requestMock.mockReset();
    requestMock.mockResolvedValue({ ok: true });
  });

  it("posts identity submit with canonical buddy onboarding payload", async () => {
    await buddyApi.submitBuddyIdentity({
      display_name: "Alex",
      profession: "Designer",
      current_stage: "transition",
      interests: ["writing"],
      strengths: ["systems thinking"],
      constraints: ["time"],
      goal_intention: "Build a meaningful long-term direction",
    });

    expect(requestMock).toHaveBeenCalledWith("/buddy/onboarding/identity", {
      method: "POST",
      body: JSON.stringify({
        display_name: "Alex",
        profession: "Designer",
        current_stage: "transition",
        interests: ["writing"],
        strengths: ["systems thinking"],
        constraints: ["time"],
        goal_intention: "Build a meaningful long-term direction",
      }),
    });
  });

  it("posts contract, confirmation, and naming mutations to buddy routes", async () => {
    await buddyApi.submitBuddyContract({
      session_id: "session-1",
      service_intent: "Help me build a durable writing rhythm.",
      collaboration_role: "orchestrator",
      autonomy_level: "guarded-proactive",
      confirm_boundaries: ["external spend"],
      report_style: "decision-first",
      collaboration_notes: "Keep reports concise.",
    });
    await buddyApi.previewBuddyDirectionTransition({
      session_id: "session-1",
      selected_direction: "Build a durable writing lane.",
    });
    await buddyApi.confirmBuddyDirection({
      session_id: "session-1",
      selected_direction: "Build a durable writing lane.",
      capability_action: "start-new",
    });
    await buddyApi.nameBuddy({
      session_id: "session-1",
      buddy_name: "Nova",
    });

    expect(requestMock).toHaveBeenNthCalledWith(1, "/buddy/onboarding/contract", {
      method: "POST",
      body: JSON.stringify({
        session_id: "session-1",
        service_intent: "Help me build a durable writing rhythm.",
        collaboration_role: "orchestrator",
        autonomy_level: "guarded-proactive",
        confirm_boundaries: ["external spend"],
        report_style: "decision-first",
        collaboration_notes: "Keep reports concise.",
      }),
    });
    expect(requestMock).toHaveBeenNthCalledWith(
      2,
      "/buddy/onboarding/direction-transition-preview",
      {
        method: "POST",
        body: JSON.stringify({
          session_id: "session-1",
          selected_direction: "Build a durable writing lane.",
        }),
      },
    );
    expect(requestMock).toHaveBeenNthCalledWith(
      3,
      "/buddy/onboarding/confirm-direction",
      {
        method: "POST",
        body: JSON.stringify({
          session_id: "session-1",
          selected_direction: "Build a durable writing lane.",
          capability_action: "start-new",
        }),
      },
    );
    expect(requestMock).toHaveBeenNthCalledWith(4, "/buddy/name", {
      method: "POST",
      body: JSON.stringify({
        session_id: "session-1",
        buddy_name: "Nova",
      }),
    });
  });

  it("reads contract draft and buddy surface through query endpoints", async () => {
    await buddyApi.getBuddyContractDraft("session-1");
    await buddyApi.getBuddySurface();
    await buddyApi.getBuddySurface("profile-1");

    expect(requestMock).toHaveBeenNthCalledWith(
      1,
      "/buddy/onboarding/session-1/candidates",
    );
    expect(requestMock).toHaveBeenNthCalledWith(2, "/buddy/surface");
    expect(requestMock).toHaveBeenNthCalledWith(
      3,
      "/buddy/surface?profile_id=profile-1",
    );
  });
});
