import { lazy, Suspense, type ComponentType } from "react";

import type { IAgentScopeRuntimeWebUIOptions } from "@agentscope-ai/chat/lib/AgentScopeRuntimeWebUI/core/types";

import styles from "./index.module.less";

const RuntimeWebUI = lazy(async () => {
  const mod = await import(
    "@agentscope-ai/chat/lib/AgentScopeRuntimeWebUI/core/ChatAnywhere"
  );
  return { default: mod.default };
});

type RuntimeComponentProps = {
  options: IAgentScopeRuntimeWebUIOptions;
};

type ChatComposerAdapterProps = {
  chatUiKey: string;
  options: IAgentScopeRuntimeWebUIOptions;
  RuntimeComponent?: ComponentType<RuntimeComponentProps>;
};

export function ChatComposerAdapter({
  chatUiKey,
  options,
  RuntimeComponent = RuntimeWebUI as ComponentType<RuntimeComponentProps>,
}: ChatComposerAdapterProps) {
  return (
    <div className={styles.canvasStream}>
      <Suspense
        fallback={
          <div className={styles.canvasSpinner}>
            <div className={styles.spinnerRing} />
            <span className={styles.spinnerText}>正在加载对话引擎…</span>
          </div>
        }
      >
        <RuntimeComponent key={chatUiKey} options={options} />
      </Suspense>
    </div>
  );
}
