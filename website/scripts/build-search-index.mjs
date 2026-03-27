#!/usr/bin/env node
/**
 * Build the minimal search index for the Spider Mesh product site.
 * Historical markdown under public/docs is intentionally excluded.
 */
import { writeFile } from "fs/promises";
import { join } from "path";
import { fileURLToPath } from "url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const outPath = join(__dirname, "..", "public", "search-index.json");

const entries = [
  {
    slug: "intro",
    lang: "en",
    title: "What Spider Mesh is",
    headings: [
      { text: "System positioning", id: "system-positioning" },
      { text: "Why the name Spider Mesh", id: "why-the-name-baize" },
    ],
    excerpt:
      "Spider Mesh is a local execution system that brings goals, environments, evidence, and long-running work into one Runtime Center.",
  },
  {
    slug: "intro",
    lang: "zh",
    title: "Spider Mesh 是什么",
    headings: [
      { text: "系统定位", id: "system-positioning" },
      { text: "为什么叫 Spider Mesh", id: "why-the-name-baize" },
    ],
    excerpt:
      "Spider Mesh 是一个面向长期任务的本地执行系统，把目标、环境、证据与持续执行收敛到同一个 Runtime Center。",
  },
  {
    slug: "quickstart",
    lang: "en",
    title: "Quick start",
    headings: [
      { text: "Start the service", id: "start-the-service" },
      { text: "Develop the Runtime Center", id: "develop-the-runtime-center" },
      { text: "Develop the product site", id: "develop-the-product-site" },
    ],
    excerpt:
      "Use pip install -e ., copaw init --defaults, and copaw app to start Spider Mesh. Develop console/ as the Runtime Center and website/ as the product site.",
  },
  {
    slug: "quickstart",
    lang: "zh",
    title: "快速开始",
    headings: [
      { text: "启动服务", id: "start-the-service" },
      { text: "开发运行中心", id: "develop-the-runtime-center" },
      { text: "开发产品站", id: "develop-the-product-site" },
    ],
    excerpt:
      "当前最短启动路径是 pip install -e .、copaw init --defaults、copaw app。console/ 是运行中心，website/ 是产品站。",
  },
  {
    slug: "console",
    lang: "en",
    title: "Runtime Center",
    headings: [
      { text: "First-class objects", id: "first-class-objects" },
      {
        text: "What happens in the Runtime Center",
        id: "what-happens-in-the-runtime-center",
      },
    ],
    excerpt:
      "The Runtime Center is Spider Mesh's command, execution, and observability surface.",
  },
  {
    slug: "console",
    lang: "zh",
    title: "运行中心",
    headings: [
      { text: "一等对象", id: "first-class-objects" },
      { text: "在运行中心里做什么", id: "what-happens-in-the-runtime-center" },
    ],
    excerpt: "Runtime Center 是 Spider Mesh 的指挥、运行与观测界面。",
  },
  {
    slug: "channels",
    lang: "en",
    title: "Channels",
    headings: [
      { text: "Where to configure them", id: "where-to-configure-them" },
      { text: "What channels are for", id: "what-channels-are-for" },
    ],
    excerpt:
      "Channels are the touchpoints where Spider Mesh connects to people, message surfaces, and external systems.",
  },
  {
    slug: "channels",
    lang: "zh",
    title: "外部连接",
    headings: [
      { text: "在哪里配置", id: "where-to-configure-them" },
      { text: "频道的角色", id: "what-channels-are-for" },
    ],
    excerpt: "频道是 Spider Mesh 和人、消息入口、外部系统连接的触点。",
  },
  {
    slug: "models",
    lang: "en",
    title: "Models",
    headings: [{ text: "Model entry point", id: "model-entry-point" }],
    excerpt:
      "Models provide reasoning, planning, and tool orchestration, but they do not replace system state, environments, or evidence.",
  },
  {
    slug: "models",
    lang: "zh",
    title: "模型与能力",
    headings: [{ text: "模型入口", id: "model-entry-point" }],
    excerpt:
      "模型负责推理、规划与工具调用编排，但不替代系统状态、环境与证据。",
  },
  {
    slug: "config",
    lang: "en",
    title: "Local runtime",
    headings: [
      { text: "Current runtime convention", id: "current-runtime-convention" },
      { text: "Why local-first matters", id: "why-local-first-matters" },
    ],
    excerpt:
      "Spider Mesh is designed around a local service, browser entry point, and working directory.",
  },
  {
    slug: "config",
    lang: "zh",
    title: "本地运行方式",
    headings: [
      { text: "当前运行约定", id: "current-runtime-convention" },
      { text: "为什么强调本地", id: "why-local-first-matters" },
    ],
    excerpt: "Spider Mesh 默认围绕本地服务、浏览器入口和工作目录运行。",
  },
  {
    slug: "faq",
    lang: "en",
    title: "FAQ",
    headings: [
      {
        text: "What kinds of work is Spider Mesh for?",
        id: "what-kinds-of-work-is-baize-for",
      },
      {
        text: "Which frontend matters right now?",
        id: "which-frontend-matters-right-now",
      },
      {
        text: "Where should I read the architecture?",
        id: "where-should-i-read-the-architecture",
      },
    ],
    excerpt:
      "The most common questions about Spider Mesh: what it is for, which frontend to use, and where to read the architecture.",
  },
  {
    slug: "faq",
    lang: "zh",
    title: "常见问题",
    headings: [
      { text: "Spider Mesh 适合什么任务？", id: "what-kinds-of-work-is-baize-for" },
      { text: "哪个前端才是现在要看的？", id: "which-frontend-matters-right-now" },
      { text: "去哪里看系统架构？", id: "where-should-i-read-the-architecture" },
    ],
    excerpt:
      "关于 Spider Mesh 系统，最常见的几个问题：适合什么任务、该看哪个前端、以及系统架构去哪看。",
  },
];

async function main() {
  await writeFile(outPath, JSON.stringify(entries), "utf-8");
  console.log(`Wrote ${entries.length} Spider Mesh entries to ${outPath}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
