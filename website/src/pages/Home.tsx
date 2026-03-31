import type { SiteConfig } from "../config";
import { type Lang } from "../i18n";
import { Nav } from "../components/Nav";
import { Hero } from "../components/Hero";
import { Footer } from "../components/Footer";

interface HomeProps {
  config: SiteConfig;
  lang: Lang;
  onLangClick: () => void;
}

type StoryCard = {
  title: string;
  body: string;
};

function buildCards(lang: Lang): StoryCard[] {
  if (lang === "zh") {
    return [
      {
        title: "以目标驱动持续执行",
        body:
          "Spider Mesh 不是一次性对话壳，而是围绕目标与任务持续推进的执行系统。计划、执行、观察与反馈属于同一条运行主链。",
      },
      {
        title: "环境不会每轮重建",
        body:
          "浏览器、文件、渠道、工作目录与会话不该靠提示词临时恢复。Spider Mesh 把环境挂在运行现场里，让长期任务真正连起来。",
      },
      {
        title: "证据先于结论",
        body:
          "重要动作应该留下证据、回放与产物。Spider Mesh 强调可归因、可回放、可审计，而不是把关键事实埋进零散日志。",
      },
      {
        title: "运行中心统一可见",
        body:
          "目标、智能体、任务、环境、证据、决策与补丁应该在同一个运行中心里被看见、被治理、被推进。",
      },
    ];
  }

  return [
    {
      title: "Goal-first execution",
      body:
        "Spider Mesh is not a disposable chat wrapper. It is an execution system where goals and tasks stay on one runtime chain from planning to observation.",
    },
    {
      title: "Persistent environments",
      body:
        "Browsers, files, channels, working directories, and sessions should not be rebuilt from scratch every turn. Spider Mesh treats environment as a mounted runtime surface.",
    },
    {
      title: "Evidence before claims",
      body:
        "Important actions should leave evidence, replay pointers, and artifacts. Spider Mesh is designed for attribution, replay, and auditability.",
    },
    {
      title: "One visible Runtime Center",
      body:
        "Goals, agents, tasks, environments, evidence, decisions, and patches belong on one visible operating surface instead of being scattered across separate tools.",
    },
  ];
}

export function Home({ config, lang, onLangClick }: HomeProps) {
  const cards = buildCards(lang);
  const repoFile = (path: string) => `${config.repoUrl}/blob/main/${path}`;
  const entryPoints =
    lang === "zh"
      ? [
          {
            label: "升级总方案",
            href: repoFile("COPAW_CARRIER_UPGRADE_MASTERPLAN.md"),
            desc: "系统目标、架构边界与施工主线",
          },
          {
            label: "任务状态",
            href: repoFile("TASK_STATUS.md"),
            desc: "当前做到哪里、下一步做什么",
          },
          {
            label: "前端升级路线",
            href: repoFile("FRONTEND_UPGRADE_PLAN.md"),
            desc: "为什么 Spider Mesh 的前端是一座运行中心",
          },
          {
            label: "运行中心 UI 规范",
            href: repoFile("RUNTIME_CENTER_UI_SPEC.md"),
            desc: "目标、智能体、任务、环境与证据的可见化边界",
          },
        ]
      : [
          {
            label: "Master plan",
            href: repoFile("COPAW_CARRIER_UPGRADE_MASTERPLAN.md"),
            desc: "System target, architectural boundaries, and build sequence",
          },
          {
            label: "Task status",
            href: repoFile("TASK_STATUS.md"),
            desc: "What is done, what is active, and what comes next",
          },
          {
            label: "Frontend upgrade plan",
            href: repoFile("FRONTEND_UPGRADE_PLAN.md"),
            desc: "Why Spider Mesh uses a runtime center instead of a static control panel",
          },
          {
            label: "Runtime Center UI spec",
            href: repoFile("RUNTIME_CENTER_UI_SPEC.md"),
            desc: "Visibility boundaries for goals, agents, tasks, environments, and evidence",
          },
        ];

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
      <main>
        <Hero
          projectName={config.projectName}
          projectEnglishName={config.projectEnglishName}
          tagline={lang === "zh" ? config.projectTaglineZh : config.projectTaglineEn}
          lang={lang}
          docsPath={config.docsPath}
          repoUrl={config.repoUrl}
        />
        <section
          style={{
            margin: "0 auto",
            maxWidth: "min(100% - 2rem, 72rem)",
            paddingBottom: "2rem",
            display: "grid",
            gap: "1.5rem",
          }}
        >
          <div style={{ display: "grid", gap: "0.75rem" }}>
            <h2 style={{ margin: 0, fontSize: "1.75rem", letterSpacing: "-0.03em" }}>
              {lang === "zh" ? "Spider Mesh 如何工作" : "How Spider Mesh works"}
            </h2>
            <p style={{ margin: 0, color: "var(--text-muted)", maxWidth: "48rem" }}>
              {lang === "zh"
                ? "Spider Mesh 面向的是长期任务、持续环境和证据化执行。重点不是做一个更花的聊天入口，而是把真实运行主链收敛到本地。"
                : "Spider Mesh is built for long-running tasks, persistent environments, and evidence-backed execution. The point is not a flashier chat shell but a tighter local runtime chain."}
            </p>
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(16rem, 1fr))",
              gap: "1rem",
            }}
          >
            {cards.map((card) => (
              <article
                key={card.title}
                style={{
                  border: "1px solid var(--border)",
                  borderRadius: "1.25rem",
                  background: "rgba(255, 255, 255, 0.92)",
                  padding: "1.25rem",
                  boxShadow: "0 12px 30px rgba(0, 0, 0, 0.04)",
                }}
              >
                <h3 style={{ marginTop: 0, marginBottom: "0.75rem" }}>{card.title}</h3>
                <p style={{ margin: 0, color: "var(--text-muted)" }}>{card.body}</p>
              </article>
            ))}
          </div>
          <div
            style={{
              border: "1px solid var(--border)",
              borderRadius: "1.5rem",
              background: "rgba(255, 255, 255, 0.9)",
              padding: "1.5rem",
              display: "grid",
              gap: "1rem",
            }}
          >
            <div style={{ display: "grid", gap: "0.4rem" }}>
              <h3 style={{ margin: 0 }}>
                {lang === "zh" ? "为什么叫 Spider Mesh" : "Why the name Spider Mesh"}
              </h3>
              <p style={{ margin: 0, color: "var(--text-muted)", maxWidth: "48rem" }}>
                {lang === "zh"
                  ? "Spider Mesh 指的是一个由执行中枢统筹、多 Agent 持续协作，并把记忆、证据与工作流织成网络的运行结构。这个名字服务于系统形态，而不是装饰性的吉祥物。"
                  : "Spider Mesh describes a runtime structure where one control core coordinates multiple agents and weaves memory, evidence, and workflows into a durable operating mesh. The name reflects the architecture, not mascot copy."}
              </p>
            </div>
          </div>
          <div
            style={{
              border: "1px solid var(--border)",
              borderRadius: "1.5rem",
              background: "rgba(255, 255, 255, 0.9)",
              padding: "1.5rem",
              display: "grid",
              gap: "1rem",
            }}
          >
            <div style={{ display: "grid", gap: "0.4rem" }}>
              <h3 style={{ margin: 0 }}>
                {lang === "zh" ? "从这里进入 Spider Mesh" : "Enter Spider Mesh here"}
              </h3>
              <p style={{ margin: 0, color: "var(--text-muted)" }}>
                {lang === "zh"
                  ? `本地运行中心默认地址：${config.consoleUrl}`
                  : `Default local Runtime Center address: ${config.consoleUrl}`}
              </p>
            </div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(16rem, 1fr))",
                gap: "0.9rem",
              }}
            >
              {entryPoints.map((item) => (
                <a
                  key={item.label}
                  href={item.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    border: "1px solid rgba(76, 122, 196, 0.14)",
                    borderRadius: "1rem",
                    padding: "1rem",
                    textDecoration: "none",
                    color: "inherit",
                    background: "linear-gradient(180deg, #ffffff 0%, #f7fbff 100%)",
                  }}
                >
                  <strong style={{ display: "block", marginBottom: "0.4rem" }}>
                    {item.label}
                  </strong>
                  <span style={{ color: "var(--text-muted)", fontSize: "0.95rem" }}>
                    {item.desc}
                  </span>
                </a>
              ))}
            </div>
          </div>
        </section>
      </main>
      <Footer lang={lang} />
    </>
  );
}
