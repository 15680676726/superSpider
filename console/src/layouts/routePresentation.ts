export interface RoutePresentation {
  title: string;
  description: string;
  groupLabel: string;
  shortLabel: string;
}

const DEFAULT_PRESENTATION: RoutePresentation = {
  title: "主脑驾驶舱",
  description: "让当前运行事实、风险、证据和待确认事项始终保持可见。",
  groupLabel: "运行中心",
  shortLabel: "驾驶舱",
};

const ROUTE_PRESENTATIONS: Record<string, RoutePresentation> = {
  chat: {
    title: "超级伙伴聊天主场",
    description: "与主脑保持单窗口连续对话，在主场里接收解释、建议和唯一下一步动作。",
    groupLabel: "对话",
    shortLabel: "聊天",
  },
  "runtime-center": {
    title: "主脑驾驶舱",
    description: "集中查看运行事实、治理状态、证据回流与当前主脑节奏。",
    groupLabel: "运行中心",
    shortLabel: "驾驶舱",
  },
  industry: {
    title: "行业工作台",
    description: "围绕当前执行载体查看团队骨架、执行位、调整入口与运行焦点。",
    groupLabel: "运行中心",
    shortLabel: "行业",
  },
  knowledge: {
    title: "知识中枢",
    description: "把文档、事实、召回命中和派生记忆统一收进正式知识链。",
    groupLabel: "洞察",
    shortLabel: "知识",
  },
  reports: {
    title: "报告中心",
    description: "按日报、周报和月报窗口观察真实运行产出，而不是只看日志。",
    groupLabel: "洞察",
    shortLabel: "报告",
  },
  performance: {
    title: "绩效面板",
    description: "对齐角色贡献、执行表现、阻塞与增长趋势。",
    groupLabel: "洞察",
    shortLabel: "绩效",
  },
  calendar: {
    title: "节奏日历",
    description: "查看当前运行节奏、周期计划和需要介入的时间节点。",
    groupLabel: "洞察",
    shortLabel: "日历",
  },
  predictions: {
    title: "预测与复盘",
    description: "把预测、建议、执行结果和复盘命中率放在同一条闭环里。",
    groupLabel: "洞察",
    shortLabel: "复盘",
  },
  "capability-market": {
    title: "能力市场",
    description: "统一发现、评估、安装和启用 skill、MCP 与外扩项目能力。",
    groupLabel: "运行中心",
    shortLabel: "市场",
  },
  system: {
    title: "系统维护",
    description: "处理运行体健康、恢复、自检和治理级维护动作。",
    groupLabel: "设置",
    shortLabel: "系统",
  },
  channels: {
    title: "渠道设置",
    description: "管理消息入口和渠道配置，让输入输出链路保持稳定。",
    groupLabel: "设置",
    shortLabel: "渠道",
  },
  models: {
    title: "模型设置",
    description: "管理对话模型、提供商和回退链，保证主脑用的是正式模型链。",
    groupLabel: "设置",
    shortLabel: "模型",
  },
  environments: {
    title: "环境设置",
    description: "查看环境变量与运行挂载，确保执行位具备稳定可复用的工作环境。",
    groupLabel: "设置",
    shortLabel: "环境",
  },
  "agent-config": {
    title: "智能体配置",
    description: "查看角色配置、岗位边界和执行位相关能力设置。",
    groupLabel: "设置",
    shortLabel: "智能体",
  },
};

export function getRoutePresentation(selectedKey: string): RoutePresentation {
  return ROUTE_PRESENTATIONS[selectedKey] ?? DEFAULT_PRESENTATION;
}
