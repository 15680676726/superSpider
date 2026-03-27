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
  projectName: "Spider Mesh",
  projectEnglishName: "Spider Mesh",
  projectTaglineEn:
    "A local execution system for goals, environments, evidence, and long-running work.",
  projectTaglineZh: "面向目标、环境、证据与长期任务的本地执行系统。",
  repoUrl: "https://github.com/agentscope-ai/CoPaw",
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
