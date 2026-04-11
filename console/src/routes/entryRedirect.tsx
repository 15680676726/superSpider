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
      const profileId = readActiveBuddyProfileId(window.currentThreadMeta) ?? undefined;

      try {
        const entry = await api.getBuddyEntry(profileId);
        if (cancelled) {
          return;
        }

        const decision = resolveBuddyEntryDecision(entry);
        if (decision.profileId) {
          writeBuddyProfileId(decision.profileId);
        }
        if (decision.mode !== "chat-ready") {
          redirectToOnboarding();
          return;
        }

        const resolvedProfileId = decision.profileId ?? profileId;
        if (!resolvedProfileId) {
          redirectToOnboarding();
          return;
        }
        writeBuddyProfileId(resolvedProfileId);

        const binding = buildBuddyExecutionCarrierChatBinding({
          sessionId: null,
          profileId: resolvedProfileId,
          profileDisplayName: decision.profileDisplayName,
          executionCarrier: decision.executionCarrier,
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
        <div>正在为你打开伙伴主场…</div>
      </div>
    </div>
  );
}
