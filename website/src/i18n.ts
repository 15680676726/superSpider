export type Lang = "zh" | "en";

export const i18n: Record<Lang, Record<string, string>> = {
  zh: {
    "common.loading": "加载中...",
    "nav.home": "首页",
    "nav.docs": "产品说明",
    "nav.releaseNotes": "版本记录",
    "nav.lang": "EN",
    "nav.github": "源码",
    "footer.note":
      "superSpider 把主脑、环境、证据与持续执行收敛到同一个本地运行中心。",
    "footer.surface": "公开说明文档在 website/，内部架构与迁移文档在 docs/architecture/，退役历史文档在 docs/archive/。",
  },
  en: {
    "common.loading": "Loading...",
    "nav.home": "Home",
    "nav.docs": "Overview",
    "nav.releaseNotes": "Releases",
    "nav.lang": "中文",
    "nav.github": "Source",
    "footer.note":
      "superSpider brings the main brain, environments, evidence, and long-running execution into one local Runtime Center.",
    "footer.surface": "Public-facing docs live in website/, internal architecture and migration records live in docs/architecture/, and retired history lives in docs/archive/.",
  },
};

export function t(lang: Lang, key: string): string {
  return i18n[lang][key] ?? key;
}
