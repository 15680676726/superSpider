const defaultConfig = {
  theme: {
    colorPrimary: "#3b82f6",
    darkMode: true,
    prefix: "baize",
    leftHeader: {
      logo: "",
      title: "Spider Mesh",
    },
  },
  sender: {
    attachments: false,
    maxLength: 10000,
    disclaimer: "Spider Mesh - 多智能体执行工作网",
  },
  welcome: {
    greeting: "你好，我是 Spider Mesh，有什么可以帮到您？",
    description:
      "我是一个以执行、协作和持续工作网为核心的多智能体系统，可以帮助你推进任务与编排团队执行。",
    avatar: `${import.meta.env.BASE_URL}spider-mesh-symbol.svg`,
    prompts: [
      {
        icon: `${import.meta.env.BASE_URL}spider-mesh-symbol.svg`,
        value: "让我们开启一段新的旅程吧！",
      },
      {
        icon: `${import.meta.env.BASE_URL}spider-mesh-symbol.svg`,
        value: "能告诉我你有哪些技能吗？",
      },
    ],
  },
  api: {
    baseURL: "",
    token: "",
  },
} as const;

export default defaultConfig;

export type DefaultConfig = typeof defaultConfig;
