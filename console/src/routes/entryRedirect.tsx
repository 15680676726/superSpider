import { useEffect } from "react";
import { Spin } from "antd";
import { useNavigate } from "react-router-dom";

import api from "../api";
import {
  readActiveBuddyProfileId,
  writeBuddyProfileId,
} from "../runtime/buddyProfileBinding";
import { resolveBuddyEntryDecision } from "../runtime/buddyFlow";
import {
  buildBuddyExecutionCarrierChatBinding,
  openRuntimeChat,
} from "../utils/runtimeChat";

interface CustomWindow extends Window {
  currentThreadMeta?: Record<string, unknown>;
}

declare const window: CustomWindow;

export default function EntryRedirect() {
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;

    const redirectToOnboarding = () => {
      navigate("/buddy-onboarding", { replace: true });
    };

    void (async () => {
      const profileId = readActiveBuddyProfileId(window.currentThreadMeta);
      if (!profileId) {
        redirectToOnboarding();
        return;
      }

      try {
        const surface = await api.getBuddySurface(profileId);
        if (cancelled) {
          return;
        }

        const resolvedProfileId = surface?.profile?.profile_id;
        if (!resolvedProfileId) {
          redirectToOnboarding();
          return;
        }
        writeBuddyProfileId(resolvedProfileId);

        const decision = resolveBuddyEntryDecision(surface);
        if (decision.mode !== "chat-ready" || !surface.execution_carrier) {
          redirectToOnboarding();
          return;
        }

        const binding = buildBuddyExecutionCarrierChatBinding({
          sessionId: surface.onboarding?.session_id ?? null,
          profileId: resolvedProfileId,
          profileDisplayName: surface.profile.display_name,
          executionCarrier: surface.execution_carrier,
          entrySource: "entry-redirect",
        });
        await openRuntimeChat(binding, navigate, {
          replace: true,
          shouldNavigate: () => !cancelled,
        });
      } catch {
        if (!cancelled) {
          redirectToOnboarding();
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [navigate]);

  return (
    <div
      style={{
        minHeight: "60vh",
        display: "grid",
        placeItems: "center",
      }}
    >
      <div style={{ display: "grid", gap: 12, justifyItems: "center" }}>
        <Spin size="large" />
        <div>正在为你打开页面…</div>
      </div>
    </div>
  );
}
