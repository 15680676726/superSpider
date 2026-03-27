import { Link } from "react-router-dom";
import { ArrowRight, Github } from "lucide-react";
import { motion } from "motion/react";
import { type Lang } from "../i18n";

interface HeroProps {
  projectName: string;
  projectEnglishName: string;
  tagline: string;
  lang: Lang;
  docsPath: string;
  repoUrl: string;
}

const container = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.1, delayChildren: 0.05 },
  },
};

const item = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0 },
};

export function Hero({
  projectName,
  projectEnglishName,
  tagline,
  lang,
  docsPath,
  repoUrl,
}: HeroProps) {
  const title = lang === "zh" ? "Spider Mesh 系统" : "Spider Mesh System";
  const showSecondaryName =
    projectEnglishName.trim().length > 0 && projectEnglishName.trim() !== projectName.trim();
  const summary =
    lang === "zh"
      ? "把目标、环境、证据与长期执行收敛到同一个本地 Runtime Center，让执行、观察与演进在一处闭环。"
      : "A local execution system that brings goals, environments, evidence, and long-running work into one Runtime Center.";

  return (
    <motion.section
      style={{
        margin: "0 auto",
        maxWidth: "min(100% - 2rem, 72rem)",
        padding: "3rem 0 2rem",
      }}
      variants={container}
      initial="hidden"
      animate="visible"
    >
      <div
        style={{
          border: "1px solid rgba(76, 122, 196, 0.18)",
          borderRadius: "2rem",
          background:
            "linear-gradient(135deg, rgba(237,245,255,0.96) 0%, rgba(255,255,255,0.98) 58%, rgba(240,247,255,0.92) 100%)",
          boxShadow: "0 24px 60px rgba(39, 88, 164, 0.08)",
          padding: "2.5rem",
          display: "grid",
          gap: "1.75rem",
        }}
      >
        <motion.div
          variants={item}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "1rem",
            flexWrap: "wrap",
          }}
        >
          <img
            src={`${import.meta.env.BASE_URL}baize-symbol.svg`}
            alt=""
            width={88}
            height={88}
            style={{ display: "block", borderRadius: "1.5rem" }}
          />
          <div style={{ display: "grid", gap: "0.35rem" }}>
            <span
              style={{
                display: "inline-flex",
                width: "fit-content",
                padding: "0.4rem 0.75rem",
                borderRadius: 999,
                background: "rgba(56, 115, 208, 0.12)",
                color: "#2957a4",
                fontSize: "0.78rem",
                fontWeight: 700,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
              }}
            >
              {showSecondaryName ? `${projectName} / ${projectEnglishName}` : projectName}
            </span>
            <h1
              style={{
                margin: 0,
                fontSize: "clamp(2rem, 5vw, 3.75rem)",
                lineHeight: 1.05,
                letterSpacing: "-0.04em",
              }}
            >
              {title}
            </h1>
          </div>
        </motion.div>
        <motion.p
          variants={item}
          style={{
            margin: 0,
            maxWidth: "48rem",
            fontSize: "1rem",
            color: "var(--text-muted)",
            lineHeight: 1.75,
          }}
        >
          {summary}
        </motion.p>
        <motion.p
          variants={item}
          style={{
            margin: 0,
            maxWidth: "48rem",
            fontSize: "0.95rem",
            color: "#2957a4",
            lineHeight: 1.75,
          }}
        >
          {tagline}
        </motion.p>
        <motion.div
          variants={item}
          style={{ display: "flex", flexWrap: "wrap", gap: "0.9rem" }}
        >
          <Link
            to={`${docsPath.replace(/\/$/, "") || "/docs"}/intro`}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.6rem",
              padding: "0.95rem 1.2rem",
              background: "linear-gradient(135deg, #2d67c7 0%, #427fdf 100%)",
              color: "#fff",
              borderRadius: "999px",
              fontWeight: 700,
              textDecoration: "none",
              boxShadow: "0 12px 30px rgba(66, 127, 223, 0.24)",
            }}
          >
            <span>{lang === "zh" ? "查看产品说明" : "Read the overview"}</span>
            <ArrowRight size={18} strokeWidth={2} aria-hidden />
          </Link>
          <a
            href={repoUrl}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.6rem",
              padding: "0.95rem 1.2rem",
              background: "rgba(255, 255, 255, 0.88)",
              color: "var(--text)",
              borderRadius: "999px",
              fontWeight: 700,
              textDecoration: "none",
              border: "1px solid rgba(76, 122, 196, 0.18)",
            }}
          >
            <Github size={18} strokeWidth={2} aria-hidden />
            <span>{lang === "zh" ? "查看源码仓库" : "Open source repository"}</span>
          </a>
        </motion.div>
      </div>
    </motion.section>
  );
}
