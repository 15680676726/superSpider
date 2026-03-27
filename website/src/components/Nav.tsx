import type { CSSProperties } from "react";
import { Link } from "react-router-dom";
import { BookOpen, FileText, Github, Globe, Home } from "lucide-react";
import { t, type Lang } from "../i18n";

interface NavProps {
  projectName: string;
  projectEnglishName: string;
  lang: Lang;
  onLangClick: () => void;
  docsPath: string;
  repoUrl: string;
}

export function Nav({
  projectName,
  projectEnglishName,
  lang,
  onLangClick,
  docsPath,
  repoUrl,
}: NavProps) {
  const docsBase = docsPath.replace(/\/$/, "") || "/docs";
  const showSecondaryName =
    projectEnglishName.trim().length > 0 && projectEnglishName.trim() !== projectName.trim();

  const linkStyle: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: "0.5rem",
    color: "var(--text-muted)",
    textDecoration: "none",
    fontSize: "0.95rem",
  };

  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        zIndex: 10,
        background: "rgba(255, 255, 255, 0.92)",
        borderBottom: "1px solid var(--border)",
        backdropFilter: "blur(16px)",
      }}
    >
      <nav
        style={{
          margin: "0 auto",
          maxWidth: "min(100% - 2rem, 72rem)",
          padding: "1rem 0",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "1rem",
        }}
      >
        <Link
          to="/"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.875rem",
            color: "var(--text)",
            textDecoration: "none",
          }}
          aria-label={projectName}
        >
          <img
            src={`${import.meta.env.BASE_URL}baize-symbol.svg`}
            alt=""
            width={40}
            height={40}
            style={{ display: "block", borderRadius: "0.875rem" }}
          />
          <div style={{ lineHeight: 1.1 }}>
            <div style={{ fontSize: "1rem", fontWeight: 700 }}>{projectName}</div>
            {showSecondaryName ? (
              <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                {projectEnglishName}
              </div>
            ) : null}
          </div>
        </Link>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "1rem",
            flexWrap: "wrap",
            justifyContent: "flex-end",
          }}
        >
          <Link to="/" style={linkStyle}>
            <Home size={18} strokeWidth={1.6} aria-hidden />
            <span>{t(lang, "nav.home")}</span>
          </Link>
          <Link to={`${docsBase}/intro`} style={linkStyle}>
            <BookOpen size={18} strokeWidth={1.5} aria-hidden />
            <span>{t(lang, "nav.docs")}</span>
          </Link>
          <Link to="/release-notes" style={linkStyle}>
            <FileText size={18} strokeWidth={1.5} aria-hidden />
            <span>{t(lang, "nav.releaseNotes")}</span>
          </Link>
          <button
            type="button"
            onClick={onLangClick}
            style={{
              ...linkStyle,
              background: "none",
              border: "none",
              padding: 0,
            }}
            aria-label={t(lang, "nav.lang")}
          >
            <Globe size={18} strokeWidth={1.5} aria-hidden />
            <span>{t(lang, "nav.lang")}</span>
          </button>
          <a
            href={repoUrl}
            target="_blank"
            rel="noopener noreferrer"
            style={linkStyle}
            title={repoUrl}
          >
            <Github size={18} strokeWidth={1.5} aria-hidden />
            <span>{t(lang, "nav.github")}</span>
          </a>
        </div>
      </nav>
    </header>
  );
}
