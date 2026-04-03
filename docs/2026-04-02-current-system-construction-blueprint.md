# 当前系统构建蓝图

> 基线：已合并主线架构  
> 审计叠层：当前根工作区存在并行施工冲突，单独标注，不计入正式主线蓝图

> `2026-04-03` 补充：`/runtime-center/main-brain` 现在已经把 `main_brain_planning` 提升成 dedicated read contract；Runtime Center 主脑 cockpit 不再只借道 `report_cognition.replan` 或 `current_cycle.main_brain_planning`，而是直接消费同名 planning surface，展示 `strategy_constraints / latest_cycle_decision / focused_assignment_plan / replan` 四段正式规划壳。

## 总蓝图

```mermaid
flowchart LR
  classDef qian fill:#fff4d6,stroke:#c28b00,color:#1f2328
  classDef jie fill:#ddefff,stroke:#1f6feb,color:#1f2328
  classDef he fill:#e8f5e9,stroke:#2e7d32,color:#1f2328
  classDef zhen fill:#f3e5f5,stroke:#7b1fa2,color:#1f2328
  classDef guan fill:#ffe0e0,stroke:#b42318,color:#1f2328

  U["操作者 / 用户"]:::qian

  subgraph Q["前台产品面"]
    Q0["控制台前台"]:::qian
    Q1["运行中心"]:::qian
    Q2["对话中心"]:::qian
    Q3["行业中心"]:::qian
    Q4["预测中心"]:::qian
    Q5["智能体工作台"]:::qian
    Q6["设置与能力市场"]:::qian
  end

  subgraph J["接口聚合面"]
    J0["后端接口聚合"]:::jie
    J1["运行中心接口面"]:::jie
    J2["目标 / 行业 / 预测 / 能力 / 系统接口面"]:::jie
  end

  subgraph H["统一运行图"]
    H0["运行装配中心"]:::he
    H1["内核运行层"]:::he
    H2["正式规划与行业执行"]:::he
    H3["能力接入层"]:::he
    H4["环境运行层"]:::he
    H5["证据与事件层"]:::guan
    H6["学习与治理层"]:::guan
  end

  subgraph Z["单一真相面"]
    Z0["统一状态真相库"]:::zhen
    Z1["运行中心状态读面"]:::zhen
    Z2["战略共享解析口"]:::zhen
  end

  U --> Q0
  Q0 --> Q1
  Q0 --> Q2
  Q0 --> Q3
  Q0 --> Q4
  Q0 --> Q5
  Q0 --> Q6

  Q1 --> J1
  Q2 --> J1
  Q3 --> J1
  Q4 --> J2
  Q5 --> J1
  Q6 --> J2

  J0 --> J1
  J0 --> J2
  J1 --> H0
  J2 --> H0

  H0 --> H1
  H0 --> H2
  H0 --> H3
  H0 --> H4
  H0 --> H5
  H0 --> H6

  H1 --> Z0
  H2 --> Z0
  H3 --> Z0
  H4 --> Z0
  H5 --> Z0
  H6 --> Z0

  J1 --> Z1
  H2 --> Z2
  H1 --> Z2
  Z1 --> Q1
  H5 --> Q1
```

## 产品入口与接口挂载

```mermaid
flowchart TB
  classDef qian fill:#fff4d6,stroke:#c28b00,color:#1f2328
  classDef jie fill:#ddefff,stroke:#1f6feb,color:#1f2328
  classDef zhen fill:#f3e5f5,stroke:#7b1fa2,color:#1f2328
  classDef guan fill:#ffe0e0,stroke:#b42318,color:#1f2328

  subgraph Q["前台入口"]
    Q0["运行中心总览与主脑读面"]:::qian
    Q1["对话提交与持续会话"]:::qian
    Q2["行业详情与经营视图"]:::qian
    Q3["预测案例与建议处理"]:::qian
    Q4["智能体详情与工作台"]:::qian
    Q5["设置、环境与能力配置"]:::qian
    Q6["全局运行事件订阅"]:::qian
  end

  subgraph J["正式接口面"]
    J0["运行中心总览读口"]:::jie
    J1["运行中心主脑读口"]:::jie
    J2["运行事件流"]:::jie
    J3["运行中心对话写入口"]:::jie
    J4["行业实例读口"]:::jie
    J5["智能体读口"]:::jie
    J6["受治理决策写口"]:::jie
    J7["预测接口面"]:::jie
    J8["目标 / 能力 / 环境 / 系统接口面"]:::jie
  end

  subgraph B["读写闭环"]
    B0["运行中心查询服务"]:::zhen
    B1["内核回合执行器"]:::zhen
    B2["运行事件总线"]:::guan
    B3["受治理变更派发"]:::guan
  end

  Q0 --> J0
  Q0 --> J1
  Q0 --> J2
  Q0 --> J5
  Q0 --> J6
  Q1 --> J3
  Q1 --> J2
  Q2 --> J4
  Q3 --> J7
  Q4 --> J5
  Q5 --> J8
  Q6 --> J2

  J0 --> B0
  J1 --> B0
  J2 --> B2
  J3 --> B1
  J4 --> B0
  J5 --> B0
  J6 --> B3
  J7 --> B0
  J8 --> B0

  B1 --> B2
  B3 --> B2
  B2 --> Q0
  B2 --> Q1
```

## 正式对象主链与规划闭环

```mermaid
flowchart TD
  classDef zhen fill:#f3e5f5,stroke:#7b1fa2,color:#1f2328
  classDef yi fill:#e8f5e9,stroke:#2e7d32,color:#1f2328
  classDef jue fill:#ffe0e0,stroke:#b42318,color:#1f2328
  classDef yu fill:#ddefff,stroke:#1f6feb,color:#1f2328

  A["战略记忆<br/>包含赛道权重、战略不确定性、赛道预算、复盘规则"]:::zhen
  B["战略共享解析口"]:::zhen
  C["战略规划编译器"]:::yi
  D["规划约束<br/>包含战略不确定性、赛道预算、触发规则"]:::yi

  E["经营赛道"]:::zhen
  F["待办项"]:::zhen
  G["周期规划编译器"]:::yi
  H["周期决策"]:::yi
  I["经营周期"]:::zhen

  J["派工规划编译器"]:::yi
  K["派工计划壳"]:::yi
  L["派工单"]:::zhen

  M["目标编译与内核任务物化"]:::yi
  N["任务记录"]:::zhen
  O["任务运行态"]:::zhen
  P["工作上下文"]:::zhen
  Q["运行帧"]:::zhen

  R["智能体报告"]:::zhen
  S["报告综合"]:::yi
  T["重规划引擎"]:::yi
  U["重规划决策<br/>包含触发规则、受影响赛道、受影响不确定性"]:::jue

  V["预测规划快照"]:::yu

  A --> B --> C --> D
  A --> E --> F
  D --> G
  F --> G
  R --> G
  G --> H --> I

  I --> J
  D --> J
  F --> J
  J -. 侧挂计划壳 .-> K
  J --> L

  L --> M
  K --> M
  M --> N
  M --> O
  M --> P
  M --> Q

  N --> R
  O --> R
  P --> R
  R --> S --> T --> U

  U -->|生成后续待办| F
  U -->|周期重平衡| G
  U -->|赛道重加权| A
  U -->|要求战略复审| A

  I --> V
  S --> V
  U --> V
```

## 运行与执行闭环

```mermaid
flowchart TD
  classDef qian fill:#fff4d6,stroke:#c28b00,color:#1f2328
  classDef jie fill:#ddefff,stroke:#1f6feb,color:#1f2328
  classDef he fill:#e8f5e9,stroke:#2e7d32,color:#1f2328
  classDef zhen fill:#f3e5f5,stroke:#7b1fa2,color:#1f2328
  classDef guan fill:#ffe0e0,stroke:#b42318,color:#1f2328

  A["对话或运行中心操作"]:::qian
  B["前台请求构造<br/>包含业务参数白名单"]:::qian
  C["运行中心对话写入口"]:::jie
  D["内核回合执行器<br/>自动分流到轻对话或编排执行"]:::he
  E["主脑轻对话路径"]:::he
  F["主脑编排器"]:::he
  G["主脑意图与执行计划"]:::he
  H["环境协调与恢复协调"]:::he
  I["查询执行运行时"]:::he
  J["子运行写租约壳<br/>读并发、写串行、失败清理"]:::guan
  K["能力服务"]:::he
  L["环境服务"]:::he
  M["调度器与邮箱执行体"]:::he
  N["结果提交器"]:::guan
  O["任务仓库组"]:::zhen
  P["决策仓库"]:::zhen
  Q["证据账本"]:::zhen
  R["会话快照侧挂"]:::zhen
  S["运行事件总线"]:::guan
  T["运行中心状态读面"]:::zhen
  U["运行事件流接口"]:::jie
  V["前台事件订阅"]:::qian
  W["受治理写接口"]:::jie

  A --> B --> C --> D
  D -->|轻对话| E
  D -->|编排执行| F
  F --> G --> H --> I
  I --> K
  I --> L
  I --> M
  M --> J
  J --> L

  E --> N
  I --> N
  N --> O
  N --> P
  N --> Q
  N --> R
  N --> S

  W --> P
  W --> O
  S --> U --> V
  O --> T
  P --> T
  Q --> T
  T --> A
```

## 环境、能力、证据、数据关系

```mermaid
flowchart TB
  classDef zhen fill:#f3e5f5,stroke:#7b1fa2,color:#1f2328
  classDef he fill:#e8f5e9,stroke:#2e7d32,color:#1f2328
  classDef guan fill:#ffe0e0,stroke:#b42318,color:#1f2328

  subgraph Z1["战略与规划载荷"]
    A["战略记忆<br/>战略编号、范围、赛道权重、复盘规则"]:::zhen
    B["战略不确定性<br/>不确定项、置信度、复盘周期、升级条件"]:::zhen
    C["赛道预算<br/>目标占比、上下限、审查压力"]:::zhen
    D["经营周期<br/>待办集合、派工集合、报告集合、正式规划"]:::zhen
    E["派工单<br/>周期、赛道、待办、任务、负责人"]:::zhen
    F["派工计划壳<br/>检查点、验收标准、侧挂计划"]:::he
  end

  subgraph Z2["执行载荷"]
    G["任务记录<br/>目标、派工、赛道、周期、工作上下文"]:::zhen
    H["任务运行态<br/>当前阶段、最近负责人、最近证据"]:::zhen
    I["智能体报告<br/>发现、疑点、是否需要追踪"]:::zhen
    J["重规划决策<br/>决策类型、触发规则、受影响赛道"]:::guan
  end

  subgraph Z3["环境与能力载荷"]
    K["环境挂载<br/>环境编号、引用、类型、状态、元数据"]:::he
    L["会话挂载<br/>环境、通道、会话、租约状态"]:::he
    M["能力挂载<br/>能力类型、风险级别、适用角色、环境要求"]:::he
  end

  subgraph Z4["证据载荷"]
    N["证据记录<br/>任务、执行者、环境、能力、风险、动作摘要、结果摘要"]:::guan
    O["产物记录<br/>证据、产物类型、存储位置"]:::guan
    P["回放指针<br/>证据、回放类型、存储位置"]:::guan
  end

  A --> B
  A --> C
  D --> E
  E --> F
  E --> G
  G --> H
  G --> I
  I --> J

  K --> L
  M --> N
  N --> O
  N --> P
  H --> N
  L --> N
```

## 审计叠层：当前断层与闭环状态

```mermaid
flowchart LR
  classDef ok fill:#e8f5e9,stroke:#2e7d32,color:#1f2328
  classDef risk fill:#ffe0e0,stroke:#b42318,color:#1f2328
  classDef note fill:#fff4d6,stroke:#c28b00,color:#1f2328

  subgraph A["正式主线基线"]
    A0["干净工作树"]:::ok
    A1["规划主链闭环<br/>战略记忆 → 经营赛道 → 待办项 → 经营周期 → 派工单 → 智能体报告 → 重规划"]:::ok
    A2["运行主链闭环<br/>对话写入口 → 回合执行 → 结果提交 → 状态 / 证据 / 事件 → 运行中心读面"]:::ok
    A3["关键契约已核对<br/>旧审查兼容口只保留回归测试<br/>内核任务列表已脱离即时生命周期枚举<br/>战略消费侧统一走共享解析口"]:::ok
    A0 --> A1
    A0 --> A2
    A0 --> A3
  end

  subgraph B["当前根工作区施工断层"]
    B0["当前根工作区"]:::risk
    B1["任务状态文档冲突"]:::risk
    B2["正式规划缺口设计文档冲突"]:::risk
    B3["周期规划器冲突"]:::risk
    B4["报告重规划引擎冲突"]:::risk
    B5["行业运行视图冲突"]:::risk
    B6["运行中心总览卡片冲突"]:::risk
    B0 --> B1
    B0 --> B2
    B0 --> B3
    B0 --> B4
    B0 --> B5
    B0 --> B6
  end

  C["结论<br/>正式系统蓝图按主线基线取值<br/>当前根工作区不能直接当作系统当前真相"]:::note

  A --> C
  B --> C
```
