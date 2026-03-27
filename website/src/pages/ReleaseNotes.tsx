import type { SiteConfig } from "../config";
import { type Lang } from "../i18n";
import { Nav } from "../components/Nav";
import { Footer } from "../components/Footer";

interface ReleaseNotesProps {
  config: SiteConfig;
  lang: Lang;
  onLangClick: () => void;
}

function archiveBase(): string {
  return (import.meta.env.BASE_URL ?? "/").replace(/\/$/, "");
}

export function ReleaseNotes({
  config,
  lang,
  onLangClick,
}: ReleaseNotesProps) {
  const releases = [
    {
      version: "v0.0.5",
      href: `${archiveBase()}/release-notes/${
        lang === "zh" ? "v0.0.5.zh.md" : "v0.0.5.md"
      }`,
    },
    {
      version: "v0.0.5-beta.3",
      href: `${archiveBase()}/release-notes/${
        lang === "zh" ? "v0.0.5-beta.3.zh.md" : "v0.0.5-beta.3.md"
      }`,
    },
    {
      version: "v0.0.4",
      href: `${archiveBase()}/release-notes/${
        lang === "zh" ? "v0.0.4.zh.md" : "v0.0.4.md"
      }`,
    },
  ];

  const repoDocs = [
    {
      label: lang === "zh" ? "升级总方案" : "Master plan",
      href: `${config.repoUrl}/blob/main/COPAW_CARRIER_UPGRADE_MASTERPLAN.md`,
    },
    {
      label: lang === "zh" ? "实时任务状态" : "Task status",
      href: `${config.repoUrl}/blob/main/TASK_STATUS.md`,
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
      <main
        style={{
          margin: "0 auto",
          maxWidth: "min(100% - 2rem, 72rem)",
          padding: "2rem 0 3rem",
          display: "grid",
          gap: "1rem",
        }}
      >
        <section
          style={{
            border: "1px solid var(--border)",
            borderRadius: "1.75rem",
            background: "linear-gradient(135deg, #eef6ff 0%, #ffffff 100%)",
            padding: "1.75rem",
            boxShadow: "0 16px 36px rgba(0, 0, 0, 0.05)",
          }}
        >
          <div style={{ display: "grid", gap: "0.85rem" }}>
            <span
              style={{
                display: "inline-flex",
                width: "fit-content",
                padding: "0.35rem 0.75rem",
                borderRadius: 999,
                background: "rgba(56, 115, 208, 0.12)",
                color: "#2957a4",
                fontSize: "0.78rem",
                fontWeight: 700,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
              }}
            >
              {lang === "zh" ? "历史归档" : "Historical archive"}
            </span>
            <h1 style={{ margin: 0, fontSize: "2rem", letterSpacing: "-0.04em" }}>
              {lang === "zh" ? "Spider Mesh 版本记录" : "Spider Mesh Release Notes"}
            </h1>
            <p style={{ margin: 0, color: "var(--text-muted)", lineHeight: 1.75 }}>
              {lang === "zh"
                ? "这里按版本保留 Spider Mesh 的阶段性发布说明。系统方向、当前能力边界与施工进度仍以升级总方案和任务状态为准。"
                : "This page keeps versioned release notes for Spider Mesh. For current direction, scope, and implementation progress, use the master plan and task status."}
            </p>
          </div>
        </section>
        <section
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(16rem, 1fr))",
            gap: "1rem",
          }}
        >
          {releases.map((release) => (
            <a
              key={release.version}
              href={release.href}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                border: "1px solid var(--border)",
                borderRadius: "1.25rem",
                background: "rgba(255, 255, 255, 0.92)",
                padding: "1.2rem",
                textDecoration: "none",
                color: "inherit",
              }}
            >
              <strong style={{ display: "block", marginBottom: "0.5rem" }}>
                {release.version}
              </strong>
              <span style={{ color: "var(--text-muted)" }}>
                {lang === "zh" ? "查看归档版本说明" : "Open archived release note"}
              </span>
            </a>
          ))}
        </section>
        <section
          style={{
            border: "1px solid var(--border)",
            borderRadius: "1.5rem",
            background: "rgba(255, 255, 255, 0.92)",
            padding: "1.4rem",
            display: "grid",
            gap: "0.9rem",
          }}
        >
          <h2 style={{ margin: 0 }}>
            {lang === "zh" ? "当前阶段建议同时查看" : "Also use these live references"}
          </h2>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(16rem, 1fr))",
              gap: "0.9rem",
            }}
          >
            {repoDocs.map((doc) => (
              <a
                key={doc.label}
                href={doc.href}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  border: "1px solid rgba(76, 122, 196, 0.14)",
                  borderRadius: "1rem",
                  padding: "1rem",
                  textDecoration: "none",
                  color: "inherit",
                }}
              >
                {doc.label}
              </a>
            ))}
          </div>
        </section>
      </main>
      <Footer lang={lang} />
    </>
  );
}
