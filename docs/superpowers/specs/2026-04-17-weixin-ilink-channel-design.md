# 微信个人（iLink）渠道正式设计

日期：2026-04-17

## 1. 目标

在 CoPaw 中新增 `微信个人（iLink）` 正式渠道，使用户能够：

- 通过个人微信私聊直接与主脑对话
- 在微信群中通过 `@主脑`、消息前缀或白名单全开放模式触发主脑
- 让主脑主动向个人会话或白名单群发送汇报消息
- 通过扫码登录获取并持久化 iLink token，重启后无需重复扫码

该能力必须走现有正式主链：

- channel ingress
- kernel / main brain front-door
- evidence / writeback
- settings / runtime center 读面

不允许实现成“微信旁路直接调模型”的平行链路。

## 2. 方案选择

已评估三种方案：

1. 最小接入型
2. 正式产品型
3. 重执行器型

本次选择 `方案 2：正式产品型`。

理由：

- 需求不只是“能聊”，而是“主脑正式通道 + 主动汇报 + 可验收”
- iLink 是 HTTP 渠道，没必要按重型桌面附着执行器实现
- 需要让 Settings、Runtime Center、evidence 都看见这条通道的真实运行状态

## 3. 对象与配置边界

### 3.1 正式 key

- 前端显示名：`微信个人（iLink）`
- 后端正式 key：`weixin_ilink`

不使用裸 `weixin`，避免未来与公众号、服务号、企业微信混淆。

### 3.2 落位原则

该能力收敛到现有渠道体系：

- 配置真相：`src/copaw/config/config.py`
- 渠道注册：`src/copaw/app/channels/registry.py`
- 渠道基类：`src/copaw/app/channels/base.py`
- 渠道调度：`src/copaw/app/channels/manager.py`
- 控制面：`src/copaw/app/routers/config.py`
- 前端设置页：`console/src/pages/Settings/Channels/*`

### 3.3 持久化配置字段

新增 `WeixinILinkConfig`，建议字段：

- `enabled`
- `bot_prefix`
- `bot_token`
- `bot_token_file`
- `base_url`
- `media_dir`
- `dm_policy`
- `group_policy`
- `group_reply_mode`
- `group_allowlist`
- `proactive_targets`

其中：

- `group_reply_mode` 首版枚举建议：
  - `mention_or_prefix`
  - `whitelist_full_open`
- `proactive_targets` 用于定义主脑可主动汇报的个人或群目标

### 3.4 运行态投影

以下字段不进入正式配置真相，只作为 runtime projection：

- `login_status`
- `last_qr_issued_at`
- `token_source`
- `polling_status`
- `last_update_id`
- `last_receive_at`
- `last_send_at`
- `last_error`

## 4. 登录与运行生命周期

### 4.1 生命周期状态

首版生命周期固定为五态：

1. `unconfigured`
2. `waiting_scan`
3. `authorized_pending_save`
4. `running`
5. `auth_expired`

### 4.2 行为规则

- 没有 `bot_token` 且读不到 `bot_token_file` 时，前端显示“未登录”
- 点击“获取登录二维码”后，后端向 iLink 请求二维码并进入 `waiting_scan`
- 扫码成功后，先写 `bot_token_file`，再把 token 回填到设置表单
- 只有用户显式保存后，token 才进入正式 `ChannelConfig`
- 运行中用 `getupdates` 长轮询拉取消息，用 `sendmessage` 发送文本回复
- token 失效或鉴权失败时进入 `auth_expired`，允许用户重新扫码

### 4.3 三条硬规则

- `bot_token_file` 优先于空配置
- 扫码流程不直接修改正式配置
- 登录状态属于 runtime truth，不属于配置真相

### 4.4 需要新增的控制面接口

建议新增：

- `POST /config/channels/weixin_ilink/login/qr`
- `GET /config/channels/weixin_ilink/login/status`
- `POST /config/channels/weixin_ilink/login/rebind`

此外需在 Runtime Center 现有 surface 中增加 `weixin_ilink` runtime projection。

## 5. 消息路由与主脑对话规则

### 5.1 入站规则

- 私聊：默认进入主脑
- 群聊：仅在下列条件命中时进入主脑
  - `@主脑`
  - 消息带 `bot_prefix`
  - 所属群在 `group_allowlist` 中且 `group_reply_mode=whitelist_full_open`
- 未命中触发条件的群消息不回模型，只记 ingress 观测

### 5.2 归一化消息结构

所有微信入站消息统一转成现有 `content_parts + meta`：

- 文本：转 `TextContent`
- 图片/文件：下载到 `media_dir` 后引用进入 `content_parts`
- 语音：优先使用 iLink 返回的 ASR 文本，同时保留文件引用

建议最小 `meta`：

- `channel_id=weixin_ilink`
- `conversation_kind=dm|group`
- `chat_id`
- `sender_id`
- `sender_name`
- `group_id`
- `group_name`
- `message_id`
- `is_mention`
- `has_bot_prefix`

### 5.3 线程归属

- 私聊线程键：`channel:weixin_ilink:dm:{sender_id}`
- 群聊线程键：`channel:weixin_ilink:group:{group_id}`

这样可以保证：

- 个人私聊上下文连续
- 每个群有独立线程
- 私聊与群聊不会串线

### 5.4 主脑主动汇报规则

- 主脑只允许向 `proactive_targets` 中配置的目标主动发消息
- 群主动汇报仅允许发送到白名单群
- 首版仅支持文本主动汇报，不假装支持富媒体

## 6. 证据链与读面

### 6.1 证据类型

首版至少产出四类正式证据：

- `login_evidence`
- `channel_ingress_evidence`
- `channel_egress_evidence`
- `channel_runtime_evidence`

### 6.2 Settings 读面

在 `Settings -> Channels -> 微信个人（iLink）` 中显示：

- 当前登录状态
- token 来源
- 轮询状态
- 最近收发时间
- 最近错误
- 获取二维码 / 检查状态 / 重新扫码

### 6.3 Runtime Center 读面

在 Runtime Center 中显示：

- 微信通道是否在线
- 最近 ingress / egress 证据
- 哪些私聊/群聊命中了主脑
- 主脑主动汇报发给了谁
- 当前错误归因：登录、轮询或发送

## 7. 测试与验收

### 7.1 L1 单测

至少覆盖：

- 配置模型
- token 文件读写
- 二维码状态机
- 消息解析
- 群触发判定
- 主动汇报路由

### 7.2 L2 集成

至少覆盖：

- `/config/channels/weixin_ilink/*` 接口
- 渠道注册与启动
- `getupdates -> BaseChannel -> kernel -> sendmessage`
- Settings / Runtime Center 读面合同

### 7.3 L3 live

在有权限账号上至少跑通：

- 真获取二维码
- 真扫码登录
- 真私聊主脑
- 真群聊 `@主脑`
- 真主动汇报到个人
- 真主动汇报到白名单群
- 真重启后自动读取 `bot_token_file`

### 7.4 完成口径

本次功能完成声明至少要求：

- `L1` 通过
- `L2` 通过
- `L3` 在有权限账号上跑通核心闭环

不得仅以局部单测或接口 200 作为“已完成”依据。

## 8. 实施顺序建议

1. 补配置模型与注册表
2. 实现 `weixin_ilink` 渠道类与 iLink API client
3. 打通二维码登录与 token 持久化
4. 打通长轮询收消息与文本发送
5. 打通群触发规则与主动汇报
6. 补 Settings 控制面与二维码交互
7. 补 Runtime Center 运行投影
8. 跑完 L1 / L2 / L3 验收

## 9. 不做事项

首版明确不做：

- 微信公众号 / 服务号 / 企业微信复用接入
- 富媒体主动发送
- 脱离现有 kernel 的微信专用旁路执行链
- 把 iLink 做成重型桌面会话执行器

