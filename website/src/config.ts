export interface SiteConfig {
  projectName: string;
  projectEnglishName: string;
  projectTaglineEn: string;
  projectTaglineZh: string;
  repoUrl: string;
  docsPath: string;
  consoleUrl: string;
}

const defaultConfig: SiteConfig = {
  projectName: "superSpider",
  projectEnglishName: "superSpider",
  projectTaglineEn: "The main brain for local autonomous execution.",
  projectTaglineZh: "面向本地长期自治执行的主脑系统。",
  repoUrl: "https://github.com/15680676726/superSpider",
  docsPath: "/docs/",
  consoleUrl: "http://127.0.0.1:8088/",
};

let cached: SiteConfig | null = null;

export async function loadSiteConfig(): Promise<SiteConfig> {
  if (cached) return cached;
  try {
    const response = await fetch("/site.config.json");
    if (response.ok) {
      cached = (await response.json()) as SiteConfig;
      return cached;
    }
  } catch {
    /* use defaults */
  }
  return defaultConfig;
}
