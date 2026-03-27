import { Link, useParams } from "react-router-dom";
import type { SiteConfig } from "../config";
import { type Lang } from "../i18n";
import { Nav } from "../components/Nav";
import { Footer } from "../components/Footer";

interface DocsProps {
  config: SiteConfig;
  lang: Lang;
  onLangClick: () => void;
}

type DocKey =
  | "intro"
  | "quickstart"
  | "console"
  | "channels"
  | "models"
  | "config"
  | "faq";

type LocalizedText = {
  zh: string;
  en: string;
};

type DocSection = {
  title: LocalizedText;
  paragraphs: LocalizedText[];
  code?: string;
};

type DocDefinition = {
  title: LocalizedText;
  summary: LocalizedText;
  sections: DocSection[];
};

const NAV_ITEMS: Array<{ key: DocKey; label: LocalizedText }> = [
  { key: "intro", label: { zh: "Spider Mesh 是什么", en: "What Is Spider Mesh" } },
  { key: "quickstart", label: { zh: "快速开始", en: "Quick Start" } },
  { key: "console", label: { zh: "运行中心", en: "Runtime Center" } },
  { key: "channels", label: { zh: "外部连接", en: "Channels" } },
  { key: "models", label: { zh: "模型与能力", en: "Models" } },
  { key: "config", label: { zh: "本地运行", en: "Local Runtime" } },
  { key: "faq", label: { zh: "常见问题", en: "FAQ" } },
];

const DOC_ALIASES: Record<string, DocKey> = {
  intro: "intro",
  roadmap: "intro",
  comparison: "intro",
  quickstart: "quickstart",
  desktop: "quickstart",
  console: "console",
  skills: "console",
  mcp: "models",
  memory: "console",
  compact: "console",
  heartbeat: "channels",
  channels: "channels",
  models: "models",
  config: "config",
  cli: "quickstart",
  commands: "faq",
  faq: "faq",
  community: "faq",
  contributing: "faq",
  search: "faq",
};

function text(lang: Lang, value: LocalizedText): string {
  return lang === "zh" ? value.zh : value.en;
}

function repoFile(repoUrl: string, path: string): string {
  return `${repoUrl}/blob/main/${path}`;
}

function buildDocs(config: SiteConfig): Record<DocKey, DocDefinition> {
  return {
    intro: {
      title: { zh: "Spider Mesh 是什么", en: "What Spider Mesh is" },
      summary: {
        zh: "Spider Mesh 是一个面向长期任务的本地执行系统，把目标、环境、证据与持续执行收敛到同一个 Runtime Center。",
        en: "Spider Mesh is a local execution system that brings goals, environments, evidence, and long-running work into one Runtime Center.",
      },
      sections: [
        {
          title: { zh: "系统定位", en: "System positioning" },
          paragraphs: [
            {
              zh: "Spider Mesh 不是零散功能页的集合，也不是一次性对话壳。它围绕 Goal、Agent、Task、Environment、Evidence 与 Patch 建立同一运行现场。",
              en: "Spider Mesh is not a loose bundle of feature pages and not a disposable chat wrapper. It builds one runtime surface around goals, agents, tasks, environments, evidence, and patches.",
            },
            {
              zh: "它面向的是长期执行、持续环境和可回放结果。真正的日常操作在 Runtime Center 完成，website/ 负责对 Spider Mesh 本身做清晰介绍与入口说明。",
              en: "It is built for long-running execution, persistent environments, and replayable outcomes. Daily operation happens in the Runtime Center, while website/ explains the system and its entry points.",
            },
          ],
        },
        {
          title: { zh: "为什么叫 Spider Mesh", en: "Why the name Spider Mesh" },
          paragraphs: [
            {
              zh: "Spider Mesh 强调的是一个由执行中枢统筹、多 Agent 持续协作、把记忆、证据与工作流织成网络的运行结构。这个名字服务于系统形态，而不是装饰性的品牌口号。",
              en: "Spider Mesh describes a runtime structure where one control core coordinates multiple agents and weaves memory, evidence, and workflows into a durable operating mesh. The name reflects the system shape, not mascot copy.",
            },
            {
              zh: "Spider Mesh 的设计原则是：一个中枢、多条专业协作链路、环境持续挂载、证据优先、结果可回放，以及所有关键对象都能在 Runtime Center 里被看见。",
              en: "Its design principles are one control core, multiple specialist lanes, mounted environments, evidence-first execution, replayable outcomes, and one Runtime Center where important objects stay visible.",
            },
          ],
        },
      ],
    },
    quickstart: {
      title: { zh: "快速开始", en: "Quick start" },
      summary: {
        zh: "用最短路径启动 Spider Mesh，并进入 Runtime Center 开始使用。",
        en: "Use the shortest path to start Spider Mesh and enter the Runtime Center.",
      },
      sections: [
        {
          title: { zh: "启动服务", en: "Start the service" },
          paragraphs: [
            {
              zh: `启动后在浏览器打开 ${config.consoleUrl}，进入 Runtime Center。`,
              en: `After startup, open ${config.consoleUrl} in the browser to enter the Runtime Center.`,
            },
          ],
          code: "pip install -e .\ncopaw init --defaults\ncopaw app",
        },
        {
          title: { zh: "开发运行中心", en: "Develop the Runtime Center" },
          paragraphs: [
            {
              zh: "主前端是 console/。它承接 Spider Mesh 的运行、配置、观测和治理，是最重要的交互入口。",
              en: "The main frontend is console/. It carries Spider Mesh runtime operations, configuration, observability, and governance.",
            },
          ],
          code: "cd console\nnpm install\nnpm run dev",
        },
        {
          title: { zh: "开发产品站", en: "Develop the product site" },
          paragraphs: [
            {
              zh: "website/ 承接 Spider Mesh 的品牌介绍、产品说明与对外入口，不负责真实运行态操作。",
              en: "website/ carries Spider Mesh brand, overview, and public entry information. It is not the operational runtime surface.",
            },
          ],
          code: "cd website\nnpm install\nnpm run dev",
        },
      ],
    },
    console: {
      title: { zh: "运行中心", en: "Runtime Center" },
      summary: {
        zh: "Runtime Center 是 Spider Mesh 的指挥、运行与观测界面。",
        en: "The Runtime Center is Spider Mesh's command, execution, and observability surface.",
      },
      sections: [
        {
          title: { zh: "一等对象", en: "First-class objects" },
          paragraphs: [
            {
              zh: "Spider Mesh 的一等对象是 Goal、Agent、Task、Environment、Evidence、Decision 和 Patch。它们决定了系统如何看见任务、推进任务、记录任务，以及让系统继续演进。",
              en: "Spider Mesh's first-class objects are goals, agents, tasks, environments, evidence, decisions, and patches. They define how work is seen, executed, recorded, and improved.",
            },
          ],
        },
        {
          title: { zh: "在运行中心里做什么", en: "What happens in the Runtime Center" },
          paragraphs: [
            {
              zh: "在这里配置模型和渠道、查看 Agent 与任务、观察环境与证据、处理决策与补丁，并让长期任务在同一界面中持续推进。",
              en: "This is where models and channels are configured, agents and tasks are inspected, environments and evidence are observed, and decisions and patches are handled on one surface.",
            },
            {
              zh: "如果一个能力无法在 Runtime Center 被看见、被归因、被追踪，它就不算真正落地。",
              en: "If a capability cannot be seen, attributed, and tracked in the Runtime Center, it is not fully landed yet.",
            },
          ],
        },
      ],
    },
    channels: {
      title: { zh: "外部连接", en: "Channels" },
      summary: {
        zh: "频道是 Spider Mesh 和人、消息入口、外部系统连接的触点。",
        en: "Channels are the touchpoints where Spider Mesh connects to people, message surfaces, and external systems.",
      },
      sections: [
        {
          title: { zh: "在哪里配置", en: "Where to configure them" },
          paragraphs: [
            {
              zh: "频道配置在 Runtime Center 的 Settings > Channels 中完成。每个频道都应该作为统一运行主链的入口，而不是各自维护一套独立状态。",
              en: "Channels are configured in Settings > Channels inside the Runtime Center. Each one should enter the same runtime chain rather than inventing its own state model.",
            },
          ],
        },
        {
          title: { zh: "频道的角色", en: "What channels are for" },
          paragraphs: [
            {
              zh: "频道负责把消息带进来、把结果送出去，但系统真相、任务推进、环境状态与证据记录都应该统一留在 Spider Mesh 内部。",
              en: "Channels bring messages in and send results out, but the system state, task progression, environment state, and evidence should stay inside Spider Mesh.",
            },
          ],
        },
      ],
    },
    models: {
      title: { zh: "模型与能力", en: "Models" },
      summary: {
        zh: "模型负责推理、规划与工具调用编排，但不替代系统状态、环境与证据。",
        en: "Models provide reasoning, planning, and tool orchestration, but they do not replace system state, environments, or evidence.",
      },
      sections: [
        {
          title: { zh: "模型入口", en: "Model entry point" },
          paragraphs: [
            {
              zh: "模型配置入口在 Runtime Center 的 Settings > Models。云模型、本地模型与自定义 provider 都应从这里进入统一运行面。",
              en: "Model configuration lives under Settings > Models in the Runtime Center. Cloud, local, and custom providers should enter the same runtime surface from here.",
            },
            {
              zh: "在 Spider Mesh 里，模型负责理解与决策建议，Capability 负责外部动作，Evidence 负责留下事实。三者需要清晰分工。",
              en: "In Spider Mesh, models reason and propose, capabilities perform external actions, and evidence keeps the record. Those responsibilities need to stay distinct.",
            },
          ],
        },
      ],
    },
    config: {
      title: { zh: "本地运行方式", en: "Local runtime" },
      summary: {
        zh: "Spider Mesh 默认围绕本地服务、浏览器入口和工作目录运行。",
        en: "Spider Mesh is designed around a local service, browser entry point, and working directory.",
      },
      sections: [
        {
          title: { zh: "当前运行约定", en: "Current runtime convention" },
          paragraphs: [
            {
              zh: `当前服务启动命令是 \`copaw app\`，默认浏览器入口是 ${config.consoleUrl}，默认工作目录是 \`~/.copaw\`。这些约定共同组成 Spider Mesh 当前的本地运行方式。`,
              en: `The current service command is \`copaw app\`, the default browser entry is ${config.consoleUrl}, and the default working directory is \`~/.copaw\`. Together they form Spider Mesh's current local runtime convention.`,
            },
          ],
        },
        {
          title: { zh: "为什么强调本地", en: "Why local-first matters" },
          paragraphs: [
            {
              zh: "Spider Mesh 的关键价值在于任务、环境、证据和结果都能围绕同一台本地运行系统闭环。它不是把状态拆散到外部平台后再靠人工拼回来的产品。",
              en: "Spider Mesh is valuable because tasks, environments, evidence, and results close the loop around one local runtime system. It is not meant to scatter state across external surfaces and stitch it back manually.",
            },
          ],
        },
      ],
    },
    faq: {
      title: { zh: "常见问题", en: "FAQ" },
      summary: {
        zh: "关于 Spider Mesh 系统，最常见的几个问题。",
        en: "The most common questions about Spider Mesh.",
      },
      sections: [
        {
          title: { zh: "Spider Mesh 适合什么任务？", en: "What kinds of work is Spider Mesh for?" },
          paragraphs: [
            {
              zh: "适合那些需要持续环境、反复观察、可追溯结果和长期推进的任务，例如多步骤执行、周期任务、带证据的治理与系统化运营。",
              en: "Spider Mesh is for work that needs persistent environments, repeated observation, traceable results, and long-running execution, such as multi-step automation, recurring work, and evidence-backed operations.",
            },
          ],
        },
        {
          title: { zh: "哪个前端才是现在要看的？", en: "Which frontend matters right now?" },
          paragraphs: [
            {
              zh: "日常使用看 console/ 对应的 Runtime Center。website/ 负责介绍 Spider Mesh、解释系统边界，并提供公开入口。",
              en: "For daily use, go to console/ and its Runtime Center. website/ introduces Spider Mesh, explains the system, and provides public-facing entry points.",
            },
          ],
        },
        {
          title: { zh: "去哪里看系统架构？", en: "Where should I read the architecture?" },
          paragraphs: [
            {
              zh: `优先看升级总方案、任务状态、前端升级路线和运行中心 UI 规范：${repoFile(config.repoUrl, "COPAW_CARRIER_UPGRADE_MASTERPLAN.md")}`,
              en: `Start with the master plan, task status, frontend upgrade plan, and Runtime Center UI spec: ${repoFile(config.repoUrl, "COPAW_CARRIER_UPGRADE_MASTERPLAN.md")}`,
            },
          ],
        },
      ],
    },
  };
}

function codeLabel(lang: Lang): string {
  return lang === "zh" ? "命令" : "Commands";
}

export function Docs({ config, lang, onLangClick }: DocsProps) {
  const { slug } = useParams<{ slug: string }>();
  const key = DOC_ALIASES[slug ?? "intro"] ?? "intro";
  const docs = buildDocs(config);
  const page = docs[key];

  return (
    <>
      <Nav
        projectName={config.projectName}
        projectEnglishName={config.projectEnglishName}
        lang={lang}
        onLangClick={onLangClick}
        docsPath={config.docsPath}
        repoUrl={config.repoUrl}
      />
      <div
        style={{
          margin: "0 auto",
          maxWidth: "min(100% - 2rem, 72rem)",
          padding: "2rem 0 3rem",
          display: "grid",
          gridTemplateColumns: "minmax(15rem, 18rem) minmax(0, 1fr)",
          gap: "1.5rem",
        }}
      >
        <aside
          style={{
            border: "1px solid var(--border)",
            borderRadius: "1.5rem",
            background: "rgba(255, 255, 255, 0.92)",
            padding: "1.25rem",
            height: "fit-content",
            position: "sticky",
            top: "5.5rem",
          }}
        >
          <div style={{ display: "grid", gap: "0.35rem", marginBottom: "1rem" }}>
            <strong>{lang === "zh" ? "文档导航" : "Docs navigation"}</strong>
            <span style={{ color: "var(--text-muted)", fontSize: "0.92rem" }}>
              {lang === "zh"
                ? "这里给的是 Spider Mesh 系统当前的产品说明与运行方式。"
                : "This is the current product overview and operating guide for Spider Mesh."}
            </span>
          </div>
          <nav style={{ display: "grid", gap: "0.5rem" }}>
            {NAV_ITEMS.map((item) => {
              const active = item.key === key;
              return (
                <Link
                  key={item.key}
                  to={`/docs/${item.key}`}
                  style={{
                    padding: "0.8rem 0.9rem",
                    borderRadius: "1rem",
                    textDecoration: "none",
                    color: active ? "#214d99" : "var(--text)",
                    background: active ? "rgba(56, 115, 208, 0.1)" : "transparent",
                    border: active
                      ? "1px solid rgba(56, 115, 208, 0.15)"
                      : "1px solid transparent",
                  }}
                >
                  {text(lang, item.label)}
                </Link>
              );
            })}
          </nav>
        </aside>
        <main
          style={{
            display: "grid",
            gap: "1rem",
          }}
        >
          <article
            style={{
              border: "1px solid var(--border)",
              borderRadius: "1.75rem",
              background: "rgba(255, 255, 255, 0.94)",
              padding: "1.75rem",
              boxShadow: "0 16px 36px rgba(0, 0, 0, 0.05)",
            }}
          >
            <div style={{ display: "grid", gap: "0.7rem", marginBottom: "1.5rem" }}>
              <h1 style={{ margin: 0, fontSize: "2rem", letterSpacing: "-0.04em" }}>
                {text(lang, page.title)}
              </h1>
              <p style={{ margin: 0, color: "var(--text-muted)", lineHeight: 1.75 }}>
                {text(lang, page.summary)}
              </p>
            </div>
            <div style={{ display: "grid", gap: "1rem" }}>
              {page.sections.map((section) => (
                <section
                  key={text(lang, section.title)}
                  style={{
                    border: "1px solid rgba(76, 122, 196, 0.14)",
                    borderRadius: "1.25rem",
                    padding: "1.2rem",
                    background: "linear-gradient(180deg, #ffffff 0%, #f7fbff 100%)",
                  }}
                >
                  <h2 style={{ marginTop: 0, marginBottom: "0.8rem", fontSize: "1.15rem" }}>
                    {text(lang, section.title)}
                  </h2>
                  <div style={{ display: "grid", gap: "0.85rem" }}>
                    {section.paragraphs.map((paragraph, index) => (
                      <p
                        key={`${text(lang, section.title)}-${index}`}
                        style={{ margin: 0, color: "var(--text-muted)", lineHeight: 1.75 }}
                      >
                        {text(lang, paragraph)}
                      </p>
                    ))}
                    {section.code ? (
                      <div style={{ display: "grid", gap: "0.45rem" }}>
                        <strong style={{ fontSize: "0.92rem" }}>{codeLabel(lang)}</strong>
                        <pre
                          style={{
                            margin: 0,
                            padding: "1rem",
                            borderRadius: "1rem",
                            background: "#0f172a",
                            color: "#e2e8f0",
                            overflowX: "auto",
                            fontSize: "0.92rem",
                            lineHeight: 1.6,
                          }}
                        >
                          <code>{section.code}</code>
                        </pre>
                      </div>
                    ) : null}
                  </div>
                </section>
              ))}
            </div>
          </article>
        </main>
      </div>
      <Footer lang={lang} />
    </>
  );
}
