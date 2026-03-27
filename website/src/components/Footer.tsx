import { t, type Lang } from "../i18n";

export function Footer({ lang }: { lang: Lang }) {
  return (
    <footer
      style={{
        marginTop: "auto",
        padding: "2rem 0 3rem",
        borderTop: "1px solid var(--border)",
        fontSize: "0.95rem",
        color: "var(--text-muted)",
      }}
    >
      <div
        style={{
          margin: "0 auto",
          maxWidth: "min(100% - 2rem, 72rem)",
          display: "grid",
          gap: "0.5rem",
          textAlign: "left",
        }}
      >
        <div>{t(lang, "footer.note")}</div>
        <div style={{ fontSize: "0.86rem" }}>
          {t(lang, "footer.builtOn")}{" "}
          <a
            href="https://github.com/agentscope-ai/agentscope-runtime"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: "inherit", textDecoration: "underline" }}
          >
            AgentScope Runtime
          </a>{" "}
          +{" "}
          <a
            href="https://github.com/agentscope-ai/agentscope"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: "inherit", textDecoration: "underline" }}
          >
            AgentScope
          </a>
          .
        </div>
      </div>
    </footer>
  );
}
