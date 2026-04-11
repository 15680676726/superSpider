// @vitest-environment node

import { describe, expect, it } from "vitest";

import viteConfig from "../../vite.config";

type ConfigFactoryEnv = {
  command: "build" | "serve";
  mode: string;
  isSsrBuild?: boolean;
  isPreview?: boolean;
};

function resolveManualChunks() {
  const configFactory = viteConfig as unknown as (env: ConfigFactoryEnv) => {
    build?: {
      rollupOptions?: {
        output?: {
          manualChunks?: ((id: string) => string | undefined) | Record<string, string[]>;
        };
      };
    };
  };
  const config = configFactory({
    command: "build",
    mode: "production",
    isPreview: false,
    isSsrBuild: false,
  });
  const manualChunks = config.build?.rollupOptions?.output?.manualChunks;
  if (typeof manualChunks !== "function") {
    throw new Error("manualChunks is not configured as a function");
  }
  return manualChunks;
}

describe("vite manual chunking", () => {
  it("splits heavy Ant Design support packages into focused vendor chunks", () => {
    const manualChunks = resolveManualChunks();

    expect(
      manualChunks("/workspace/console/node_modules/antd/es/button/index.js"),
    ).toBeUndefined();
    expect(
      manualChunks("/workspace/console/node_modules/@ant-design/cssinjs/es/index.js"),
    ).toBe("vendor-antd-style");
    expect(
      manualChunks("/workspace/console/node_modules/rc-menu/es/index.js"),
    ).toBe("vendor-antd-components");
    expect(
      manualChunks("/workspace/console/node_modules/rc-field-form/es/index.js"),
    ).toBe("vendor-antd-components");
  });

  it("leaves AgentScope chat runtime to route-level lazy splitting", () => {
    const manualChunks = resolveManualChunks();

    expect(
      manualChunks(
        "/workspace/console/node_modules/@agentscope-ai/chat/lib/AgentScopeRuntimeWebUI/core/ChatAnywhere.js",
      ),
    ).toBeUndefined();
    expect(
      manualChunks("/workspace/console/node_modules/antd-style/es/index.js"),
    ).toBeUndefined();
  });
});
