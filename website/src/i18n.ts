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
      "Spider Mesh 把目标、环境、证据与持续执行收敛到同一个本地 Runtime Center。",
    "footer.builtOn": "底层能力栈由",
  },
  en: {
    "common.loading": "Loading...",
    "nav.home": "Home",
    "nav.docs": "Overview",
    "nav.releaseNotes": "Releases",
    "nav.lang": "中文",
    "nav.github": "Source",
    "footer.note":
      "Spider Mesh brings goals, environments, evidence, and long-running execution into one local Runtime Center.",
    "footer.builtOn": "The runtime foundation is provided by",
  },
};

export function t(lang: Lang, key: string): string {
  return i18n[lang][key] ?? key;
}
