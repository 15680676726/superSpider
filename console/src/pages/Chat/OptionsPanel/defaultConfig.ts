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
    disclaimer: "Spider Mesh · 主脑运行对话前台",
  },
  welcome: {
    greeting: "这里是 Spider Mesh 主脑对话前台。",
    description:
      "你当前进入的是运行线程入口。我会围绕当前绑定的主脑控制线程、焦点事项、写回目标和治理状态来协作推进任务。",
    avatar: `${import.meta.env.BASE_URL}spider-mesh-symbol.svg`,
    prompts: [
      {
        icon: `${import.meta.env.BASE_URL}spider-mesh-symbol.svg`,
        value: "帮我梳理当前线程的最终目标和这一步要做什么",
      },
      {
        icon: `${import.meta.env.BASE_URL}spider-mesh-symbol.svg`,
        value: "告诉我这条线程现在会写回到哪里，以及还缺什么证据",
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
