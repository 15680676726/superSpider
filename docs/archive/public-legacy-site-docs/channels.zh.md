# 频道配置

**频道** = 你和 Spider Mesh 在「哪里」对话：接钉钉就在钉钉里回，接 QQ 就在 QQ 里回。不熟悉这个词的话可以先看 [项目介绍](./intro)。

配置频道有两种方式：

- **控制台**（推荐）— 在 [控制台](./console) 的 **系统设置 → 频道** 页面，点击频道卡片，在抽屉里启用并填写鉴权信息，保存即生效。
- **手动编辑 `config.json`** — 默认在 `~/.copaw/config.json` （由 `copaw init` 生成），将需要的频道设 `enabled: true` 并填好鉴权信息；保存后自动重载，无需重启。

所有频道都有如下通用字段:

- **enabled** — 是否启用
- **bot_prefix** — 机器人回复前缀（如 `[BOT]`），方便区分
- **filter_tool_messages** — （可选，默认 `false`）过滤工具调用和输出消息，不发送给用户。设为 `true` 可隐藏工具执行详情。
- **filter_thinking** — （可选，默认 `false`）过滤模型的思考/推理内容，不发送给用户。设为 `true` 可隐藏 thinking 内容。

下面按频道说明如何获取凭证并填写配置。

---

## 钉钉（推荐）

### 创建钉钉应用

视频操作流程：

![视频操作流程](https://cloud.video.taobao.com/vod/Fs7JecGIcHdL-np4AS7cXaLoywTDNj7BpiO7_Hb2_cA.mp4)

图文操作流程：

1. 打开 [钉钉开发者后台](https://open-dev.dingtalk.com/)

2. 进入"应用开发→企业内部应用→钉钉应用→创建 **应用**"

   钉钉开发者后台 (screenshot removed)

3. 在"应用能力→添加应用能力"中添加 **「机器人」**

   添加机器人 (screenshot removed)

4. 配置机器人基础信息，设置消息接收模式为 **Stream 模式**（流式接收），点击发布

   机器人基础信息 (screenshot removed)

   Stream模式+发布 (screenshot removed)

5. 在"应用发布→版本管理与发布"中创建新版本，填写基础信息后保存

   创建新版本 (screenshot removed)

   保存 (screenshot removed)

6. 在"基础信息→凭证与基础信息"中获取：

   - **Client ID**（即 AppKey）
   - **Client Secret**（即 AppSecret）

   client (screenshot removed)

7. （可选） **将服务器 IP 加入白名单** — 调用钉钉开放平台 API（如下载用户发送的图片和文件）时需要此配置。在应用设置中进入 **"安全设置→服务器出口 IP"**，添加运行 Spider Mesh 的机器的公网 IP。可在终端执行 `curl ifconfig.me` 查看公网 IP。若未配置白名单，图片和文件下载将报 `Forbidden.AccessDenied.IpNotInWhiteList` 错误。

### 绑定应用

可以在console前端配置，或者修改`~/.copaw/config.json`。

**方法1**: 在console前端配置

从“系统设置 → 频道”找到 **DingTalk**，点击后填入刚刚获取的 **Client ID** 和 **Client Secret**

console (screenshot removed)

**方法2**: 修改`~/.copaw/config.json`

在 `config.json` 里找到 `channels.dingtalk`，填入对应信息，例如：

```json
"dingtalk": {
  "enabled": true,
  "bot_prefix": "[BOT]",
  "client_id": "你的 Client ID",
  "client_secret": "你的 Client Secret"
  "filter_tool_messages": false
}
```

- 若希望隐藏工具执行详情，可设置 `filter_tool_messages: true`。

保存后若服务已运行会自动重载；未运行则执行 `copaw app` 启动。

### 找到创建的应用

视频操作流程：

![视频操作流程](https://cloud.video.taobao.com/vod/e0icQREdiZ1LI0b1mWdBDQI94KdJSaJxO09X5BPaWvk.mp4)

图文操作流程：

1. 点击钉钉【消息】栏的“搜索框”

机器人名称 (screenshot removed)

2. 搜索刚刚创建的 “机器人名称”，在【功能】下找到机器人

机器人 (screenshot removed)

3. 点击后进入对话框

对话框 (screenshot removed)

> 注：可以在钉钉群中通过**群设置→机器人→添加机器人**将机器人添加到群聊。需要注意的是，从与机器人的单聊界面中创建群聊，会无法触发机器人的回复。

---

## 飞书

飞书频道通过 **WebSocket 长连接** 接收消息，无需公网 IP 或 webhook；发送走飞书开放平台 Open API。支持文本、图片、文件收发；群聊场景下会将 `chat_id`、`message_id` 放入请求消息的 metadata，便于下游去重与群上下文识别。

### 创建飞书应用并获取凭证

1. 打开 [飞书开放平台](https://open.feishu.cn/app)，创建企业自建应用

飞书 (screenshot removed)

build (screenshot removed)

2. 在「凭证与基础信息」中获取 **App ID**、**App Secret**

id & secret (screenshot removed)

3. 在 `config.json` 中填写上述 **App ID** 和 **App Secret**（见下方「填写 config.json」），保存

4. 执行 **`copaw app`** 启动Spider Mesh服务

5. 回到飞书开放平台，在「能力」中启用 **机器人**

bot (screenshot removed)

6. 选择「权限管理」中的「批量导入/导出权限」，将以下JSON代码复制进去

```json
{
  "scopes": {
    "tenant": [
      "aily:file:read",
      "aily:file:write",
      "aily:message:read",
      "aily:message:write",
      "corehr:file:download",
      "im:chat",
      "im:message",
      "im:message.group_msg",
      "im:message.p2p_msg:readonly",
      "im:message.reactions:read",
      "im:resource",
      "contact:user.base:readonly"
    ],
    "user": []
  }
}
```

in/out (screenshot removed)

json (screenshot removed)

confirm (screenshot removed)

confirm (screenshot removed)

7. 在「事件与回调」中，点击「事件配置」，选择订阅方式为**长连接（WebSocket）** 模式（无需公网 IP）

> 注：**操作顺序**为先配置 App ID/Secret → 启动 `copaw app` → 再在开放平台配置长连接，如果此处仍显示错误，尝试先暂停copaw服务并重新启动 `copaw app`。

websocket (screenshot removed)

8. 选择「添加事件」，搜索**接收消息**，订阅**接收消息 v2.0**

reveive (screenshot removed)

click (screenshot removed)

result (screenshot removed)

9. 在「应用发布」的「版本管理与发布」中，**创建版本**，填写基础信息，**保存**并**发布**

create (screenshot removed)

info (screenshot removed)

save (screenshot removed)

### 填写 config.json

在`config.json`（默认在 `~/.copaw/config.json`）中找到`channels.feishu`，只需填 **App ID** 和 **App Secret**（在开放平台「凭证与基础信息」里复制）：

```json
"feishu": {
  "enabled": true,
  "bot_prefix": "[BOT]",
  "app_id": "cli_xxxxx",
  "app_secret": "你的 App Secret"
}
```

其他字段（encrypt_key、verification_token、media_dir）可选，WebSocket 模式可不填，有默认值。依赖：`pip install lark-oapi`，然后 `copaw app`。如果你使用 SOCKS 代理联网，还需安装 `python-socks`（例如 `pip install python-socks`），否则可能报错：`python-socks is required to use a SOCKS proxy`。

> 注: **App ID** 和 **App Secret** 信息也可以在Console前端填写，但需重启copaw服务，才能继续配置长链接的操作。
> console (screenshot removed)

### 机器人权限建议

第6步中的json文件为应用配备了以下权限（应用身份、已开通），以保证收发消息与文件正常：

| 权限名称                       | 权限标识                       | 权限类型     | 说明           |
| ------------------------------ | ------------------------------ | ------------ | -------------- |
| 获取文件                       | aily:file:read                 | 应用身份     | -              |
| 上传文件                       | aily:file:write                | 应用身份     | -              |
| 获取消息                       | aily:message:read              | 应用身份     | -              |
| 发送消息                       | aily:message:write             | 应用身份     | -              |
| 下载文件                       | corehr:file:download           | 应用身份     | -              |
| 获取与更新群组信息             | im:chat                        | 应用身份     | -              |
| 获取与发送单聊、群组消息       | im:message                     | 应用身份     | -              |
| 获取群组中所有消息（敏感权限） | im:message.group_msg           | 应用身份     | -              |
| 读取用户发给机器人的单聊消息   | im:message.p2p_msg:readonly    | 应用身份     | -              |
| 查看消息表情回复               | im:message.reactions:read      | 应用身份     | -              |
| 获取与上传图片或文件资源       | im:resource                    | 应用身份     | -              |
| **以应用身份读取通讯录**       | **contact:user.base:readonly** | **应用身份** | **见下方说明** |

> **获取用户昵称（推荐）**：若希望会话和日志中显示**用户昵称**（如「张三#1d1a」）而非「unknown#1d1a」，需额外开通通讯录只读权限 **以应用身份读取通讯录**（`contact:user.base:readonly`）。未开通时，飞书仅返回 open_id 等身份字段，不返回姓名，Spider Mesh无法解析昵称。开通后需重新发布/更新应用版本，权限生效后即可正常显示用户名称。

### 将机器人添加到常用

1. 在**工作台**点击**添加常用**

添加常用 (screenshot removed)

2. 搜索刚刚创建的机器人名称并**添加**

添加 (screenshot removed)

3. 可以看到机器人已添加到常用中，双击可进入对话界面

已添加 (screenshot removed)

对话界面 (screenshot removed)

---

## iMessage（仅 macOS）

> ⚠️ iMessage 频道仅支持 **macOS**，依赖本地「信息」应用与 iMessage 数据库，无法在 Linux / Windows 上使用。

通过本地 iMessage 数据库轮询新消息并代为回复。

1. 确保本地 **「信息」(Messages)** 已登录 Apple ID（系统设置里打开「信息」并登录）。

2. 安装 **imsg**（用于访问 iMessage 数据库）：

   ```bash
   brew install steipete/tap/imsg
   ```

   > 如果 Intel 芯片 Mac 用户通过上述方式无法安装成功，需要先克隆源码再编译
   >
   > ```bash
   > git clone https://github.com/steipete/imsg.git
   > cd imsg
   > make build
   > sudo cp build/Release/imsg /usr/local/bin/
   > cp ./bin/imsg /usr/local/bin/
   > ```

3. 为了使 iMessage 中的信息能被获取，需要 **终端** （或你用来运行 Spider Mesh 的 app） 和 **消息** 有 **完全磁盘访问权限**（系统设置 → 隐私与安全性 → 完全磁盘访问权限）。

   权限 (screenshot removed)

4. 填写 iMessage 数据库路径。默认路径为 `~/Library/Messages/chat.db`，若你改过系统路径，请填实际路径。有以下两种填写方案：

   - 进入 **控制台 → 系统设置 → 频道**，点击 **iMessage** 卡片，将 **Enable** 开关打开，在 **DB Path** 中填写上面的路径，点击 **保存**。

     控制台 (screenshot removed)

   - 填写 config.json（路径通常为~/.copaw/config.json）：

     ```json
     "imessage": {
     "enabled": true,
     "bot_prefix": "[BOT]",
     "db_path": "~/Library/Messages/chat.db",
     "poll_sec": 1.0
     }
     ```

     **db_path** — iMessage 数据库路径

     **poll_sec** — 轮询间隔（秒），默认 1 即可

5. 填写完成后，使用你的手机，给当前电脑登录的 iMessage 账号（与电脑Apple ID一致）发送任意一条消息，可以看到回复。

   聊天 (screenshot removed)

---

## Discord

### 获取 Bot Token

1. 打开 [Discord 开发者门户](https://discord.com/developers/applications)

Discord开发者门户 (screenshot removed)

2. 新建应用（或选已有应用）

新建应用 (screenshot removed)

3. 左侧进入 **Bot**，新建 Bot，复制 **Token**

token (screenshot removed)

4. 下滑，给予 Bot “Message Content Intent” 和 “Send Messages” 的权限，并保存

权限 (screenshot removed)

5. 在 **OAuth2 → URL 生成器** 里勾选 `bot` 权限，给予 Bot “Send Messages” 的权限，生成邀请链接

bot (screenshot removed)

send messages (screenshot removed)

link (screenshot removed)

6. 在浏览器中访问该链接，会自动跳转到discord页面。将 Bot 拉进你的服务器

服务器 (screenshot removed)

服务器 (screenshot removed)

7. 在服务器中可以看到 Bot已被拉入

博天 (screenshot removed)

### 绑定 Bot

可以在console前端配置，或者修改`~/.copaw/config.json`。

**方法1**: 在console前端配置

从“系统设置 → 频道”找到 **Discord**，点击后填入刚刚获取的 **Bot Token**

console (screenshot removed)

**方法2**: 修改`~/.copaw/config.json`

在 `config.json` 里找到 `channels.discord`，填入对应信息，例如：

```json
"discord": {
  "enabled": true,
  "bot_prefix": "[BOT]",
  "bot_token": "你的 Bot Token",
  "http_proxy": "",
  "http_proxy_auth": ""
}
```

国内网络访问 Discord API 可能需代理。如需代理：

- **http_proxy** — 例如 `http://127.0.0.1:7890`
- **http_proxy_auth** — 若代理需鉴权，填 `用户名:密码`，否则留空

---

## QQ

### 获取 QQ 机器人凭证

1. 打开 [QQ 开放平台](https://q.qq.com/)

开放平台 (screenshot removed)

2. 创建 **机器人应用**，点击进入编辑页面

bot (screenshot removed)

confirm (screenshot removed)

3. 选择**回调配置**，首先在**单聊事件**中勾选**C2C消息事件**，再在**群事件**中勾选**群消息事件AT事件**，确认配置

c2c (screenshot removed)

at (screenshot removed)

4. 选择**沙箱配置**中的**消息列表配置项**，点击**添加成员**，选择添加**自己**

1 (screenshot removed)

1 (screenshot removed)

5. 在**开发管理**中获取**AppID**和**AppSecret**（即 ClientSecret），填入config，方式见下方填写config.json。在**IP白名单**中添加一个IP。

1 (screenshot removed)

6. 在沙箱配置中，使用QQ扫码，将机器人添加到消息列表

1 (screenshot removed)

### 填写 config.json

在 `config.json` 里找到 `channels.qq`，把上面两个值分别填进 `app_id` 和 `client_secret`：

```json
"qq": {
  "enabled": true,
  "bot_prefix": "[BOT]",
  "app_id": "你的 AppID",
  "client_secret": "你的 AppSecret"
}
```

注意：这里填的是 **AppID** 和 **AppSecret** 两个字段，不是拼成一条 Token。

或者也可以在console前端填写

1 (screenshot removed)

---

## Telegram

### 获取 Telegram 机器人凭证

1. 打开 Telegram 并搜索 `@BotFather` 添加 Bot（注意需要是官方 @BotFather，有蓝色认证标识）。
2. 打开与 @BotFather 的聊天，根据对话中的指引创建新机器人

   创建机器人 (screenshot removed)

3. 在对话框中创建 bot_name，复制 bot_token

   复制token (screenshot removed)

### 绑定 Bot

可以在console前端配置，或者修改`~/.copaw/config.json`。

**方法1**: 在console前端配置

从“系统设置 → 频道”找到 **Telegram**，点击后填入刚刚获取的 **Bot Token**

console (screenshot removed)

**方法2**: 修改`~/.copaw/config.json`

在 `config.json` 里找到 `channels.telegram`，填入对应信息，例如：

```json
"telegram": {
    "enabled": true,
    "bot_prefix": "[BOT]",
    "bot_token": "你的 Bot Token",
    "http_proxy": "",
    "http_proxy_auth": ""
}
```

国内网络访问 Telegram API 可能需代理。如需代理：

- **http_proxy** — 例如 `http://127.0.0.1:7890`
- **http_proxy_auth** — 若代理需鉴权，填 `用户名:密码`，否则留空

### 备注

目前telegram白名单机制仍在施工中，推荐个人场景部署，不暴露username到公共环境中。

建议在 `@BotFather` 设置：

```
/setprivacy -> ENABLED # 设置bot回复权限
/setjoingroups -> DISABLED # 拦截Group邀请
```

---

## MQTT

### 介绍

当前仅支持了文本和JSON格式消息。

JSON消息格式

```
{
  "text": "...",
  "redirect_client_id": "..."
}
```

### 基础配置

| 描述                    | 属性            | 必须项 | 举例                    |
| ----------------------- | --------------- | ------ | ----------------------- |
| 连接地址                | host            | Y      | 127.0.0.1               |
| 连接端口                | port            | Y      | 1883                    |
| 协议                    | transport       | Y      | tcp                     |
| 清除会话                | clean_session   | Y      | true                    |
| 服务质量 / 消息投递等级 | qos             | Y      | 2                       |
| 用户名                  | username        | N      |                         |
| 密码                    | password        | N      |                         |
| 订阅主题                | subscribe_topic | Y      | server/+/up             |
| 推送主题                | publish_topic   | Y      | client/{client_id}/down |
| 开启加密                | tls_enabled     | N      | false                   |
| CA 根证书               | tls_ca_certs    | N      | /tsl/ca.pem             |
| 客户端 证书文件         | tls_certfile    | N      | /tsl/client.pem         |
| 客户端私钥文件          | tls_keyfile     | N      | /tsl/client.key         |

### 主题

1. 简单订阅和推送

   | subscribe_topic | publish_topic |
   | --------------- | ------------- |
   | server          | client        |

2. 模糊匹配订阅和自动推送

   模糊订阅全server/+/up主题，根据客户端的client_id自动推送到对应的主题，例如客户端向`/server/client_a/up`推送，Spider Mesh处理完后，将会向`/client/client_b/down`推送消息。

   | subscribe_topic | publish_topic           |
   | --------------- | ----------------------- |
   | server/+/up     | client/{client_id}/down |

3. 重定向主题推送

   发送消息为JSON格式，订阅主题为`server/client_a/up`，推送主题为`client/client_a/down`

   ```json
   {
     "text": "讲个笑话，直接回复文本即可。",
     "redirect_client_id": "client_b"
   }
   ```

   消息会根据redirect_client_id属性，推送至 `client/client_b/down`，从而实现跨主题推送。在物联网场景，可以做到以Spider Mesh为核心，根据个人需求，多设备间自主推送消息。

---

## 附录

### 配置总览

| 频道     | 配置键   | 必填/主要字段                                                       |
| -------- | -------- | ------------------------------------------------------------------- |
| 钉钉     | dingtalk | client_id, client_secret                                            |
| 飞书     | feishu   | app_id, app_secret；可选 encrypt_key, verification_token, media_dir |
| iMessage | imessage | db_path, poll_sec（仅 macOS）                                       |
| Discord  | discord  | bot_token；可选 http_proxy, http_proxy_auth                         |
| QQ       | qq       | app_id, client_secret                                               |
| Telegram | telegram | bot_token；可选 http_proxy, http_proxy_auth                         |

各频道字段与完整结构见上文表格及 [配置与工作目录](./config)。

### 多模态消息支持

不同频道对「文本 / 图片 / 视频 / 音频 / 文件」的**接收**（用户发给机器人）与**发送**（机器人回复用户）支持程度如下。
「✓」= 已支持；「🚧」= 施工中（可实现但尚未实现）；「✗」= 不支持（该频道本身无法支持）。

| 频道     | 接收文本 | 接收图片 | 接收视频 | 接收音频 | 接收文件 | 发送文本 | 发送图片 | 发送视频 | 发送音频 | 发送文件 |
| -------- | -------- | -------- | -------- | -------- | -------- | -------- | -------- | -------- | -------- | -------- |
| 钉钉     | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        |
| 飞书     | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        |
| Discord  | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | 🚧       | 🚧       | 🚧       | 🚧       |
| iMessage | ✓        | ✗        | ✗        | ✗        | ✗        | ✓        | ✗        | ✗        | ✗        | ✗        |
| QQ       | ✓        | 🚧       | 🚧       | 🚧       | 🚧       | ✓        | 🚧       | 🚧       | 🚧       | 🚧       |
| Telegram | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        |

说明：

- **钉钉**：接收支持富文本与单文件（downloadCode），发送通过会话 webhook 支持图片 / 语音 / 视频 / 文件。
- **飞书**：WebSocket 长连接收消息，Open API 发送；支持文本 / 图片 / 文件收发；群聊时在消息 metadata 中带 `feishu_chat_id`、`feishu_message_id` 便于下游去重与群上下文。
- **Discord**：接收时附件会解析为图片 / 视频 / 音频 / 文件并传入 Agent；回复时真实附件发送为 🚧 施工中，当前仅以链接形式附在文本中。
- **iMessage**：基于本地 imsg + 数据库轮询，仅支持文本收发；平台/实现限制，无法支持附件（✗）。
- **QQ**：接收侧附件解析为多模态、发送侧真实媒体均为 🚧 施工中，当前仅文本 + 链接形式。
- **Telegram**：接收时附件会解析为文件并传入，可在telegram对话界面以对应格式打开（图片 / 语音 / 视频 / 文件）

### 通过 HTTP 修改配置

服务运行时可读写频道配置，修改会写回 `config.json` 并自动生效：

- `GET /config/channels` — 获取全部频道
- `PUT /config/channels` — 整体覆盖
- `GET /config/channels/{channel_name}` — 获取单个（如 `dingtalk`、`imessage`）
- `PUT /config/channels/{channel_name}` — 更新单个

---

## 扩展渠道

如需接入新平台（如企业微信、Slack 等），可基于 **BaseChannel** 实现子类，无需改核心源码。

### 数据流与队列

- **ChannelManager** 为每个启用队列的 channel 维护一个队列；收到消息时 channel 调用 **`self._enqueue(payload)`**（由 manager 启动时注入），manager 在消费循环中再调用 **`channel.consume_one(payload)`**。
- 基类已实现 **默认 `consume_one`**：把 payload 转成 `AgentRequest`、跑 `_process`、对每条完成消息调用 `send_message_content`、错误时调用 `_on_consume_error`。多数渠道只需实现「入口→请求」和「回复→出口」，不必重写 `consume_one`。

### 子类必须实现

| 方法                                                    | 说明                                                                                                                                       |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `build_agent_request_from_native(self, native_payload)` | 将渠道原生消息转为 `AgentRequest`（使用 runtime 的 `Message`/`TextContent`/`ImageContent` 等），并设置 `request.channel_meta` 供发送使用。 |
| `from_env` / `from_config`                              | 从环境变量或配置构建实例。                                                                                                                 |
| `async start()` / `async stop()`                        | 生命周期（建连、订阅、清理等）。                                                                                                           |
| `async send(self, to_handle, text, meta=None)`          | 发送一条文本（及可选附件）。                                                                                                               |

### 基类提供的通用能力

- **消费流程**：`_payload_to_request`（payload→AgentRequest）、`get_to_handle_from_request`（解析发送目标，默认 `user_id`）、`get_on_reply_sent_args`（回调参数）、`_before_consume_process`（处理前钩子，如保存 receive_id）、`_on_consume_error`（错误时发送，默认 `send_content_parts`）、可选 **`refresh_webhook_or_token`**（空实现，子类需刷新 token 时覆盖）。
- **辅助**：`resolve_session_id`、`build_agent_request_from_user_content`、`_message_to_content_parts`、`send_message_content`、`send_content_parts`、`to_handle_from_target`。

需要不同消费逻辑时（如控制台打印、钉钉合并去抖）再覆盖 **`consume_one`**；需要不同发送目标或回调参数时覆盖 **`get_to_handle_from_request`** / **`get_on_reply_sent_args`**。

### 示例：最简渠道（仅文本）

只处理文本、使用 manager 队列时，不必实现 `consume_one`，基类默认即可：

```python
# my_channel.py
from agentscope_runtime.engine.schemas.agent_schemas import TextContent, ContentType
from copaw.app.channels.base import BaseChannel
from copaw.app.channels.schema import ChannelType

class MyChannel(BaseChannel):
    channel: ChannelType = "my_channel"

    def __init__(self, process, enabled=True, bot_prefix="", **kwargs):
        super().__init__(process, on_reply_sent=kwargs.get("on_reply_sent"))
        self.enabled = enabled
        self.bot_prefix = bot_prefix

    @classmethod
    def from_config(cls, process, config, on_reply_sent=None, show_tool_details=True):
        return cls(process=process, enabled=getattr(config, "enabled", True),
                   bot_prefix=getattr(config, "bot_prefix", ""), on_reply_sent=on_reply_sent)

    @classmethod
    def from_env(cls, process, on_reply_sent=None):
        return cls(process=process, on_reply_sent=on_reply_sent)

    def build_agent_request_from_native(self, native_payload):
        payload = native_payload if isinstance(native_payload, dict) else {}
        channel_id = payload.get("channel_id") or self.channel
        sender_id = payload.get("sender_id") or ""
        meta = payload.get("meta") or {}
        session_id = self.resolve_session_id(sender_id, meta)
        text = payload.get("text", "")
        content_parts = [TextContent(type=ContentType.TEXT, text=text)]
        request = self.build_agent_request_from_user_content(
            channel_id=channel_id, sender_id=sender_id, session_id=session_id,
            content_parts=content_parts, channel_meta=meta,
        )
        request.channel_meta = meta
        return request

    async def start(self):
        pass

    async def stop(self):
        pass

    async def send(self, to_handle, text, meta=None):
        # 调用你的 HTTP API 等发送
        pass
```

收到消息时组一个 native 字典并入队（`_enqueue` 由 manager 注入）：

```python
native = {
    "channel_id": "my_channel",
    "sender_id": "user_123",
    "text": "你好",
    "meta": {},
}
self._enqueue(native)
```

### 示例：多模态（文本 + 图片/视频/音频/文件）

在 `build_agent_request_from_native` 里把附件解析成 runtime 的 content，再调用 `build_agent_request_from_user_content`：

```python
from agentscope_runtime.engine.schemas.agent_schemas import (
    TextContent, ImageContent, VideoContent, AudioContent, FileContent, ContentType,
)

def build_agent_request_from_native(self, native_payload):
    payload = native_payload if isinstance(native_payload, dict) else {}
    channel_id = payload.get("channel_id") or self.channel
    sender_id = payload.get("sender_id") or ""
    meta = payload.get("meta") or {}
    session_id = self.resolve_session_id(sender_id, meta)
    content_parts = []
    if payload.get("text"):
        content_parts.append(TextContent(type=ContentType.TEXT, text=payload["text"]))
    for att in payload.get("attachments") or []:
        t = (att.get("type") or "file").lower()
        url = att.get("url") or ""
        if not url:
            continue
        if t == "image":
            content_parts.append(ImageContent(type=ContentType.IMAGE, image_url=url))
        elif t == "video":
            content_parts.append(VideoContent(type=ContentType.VIDEO, video_url=url))
        elif t == "audio":
            content_parts.append(AudioContent(type=ContentType.AUDIO, data=url))
        else:
            content_parts.append(FileContent(type=ContentType.FILE, file_url=url))
    if not content_parts:
        content_parts = [TextContent(type=ContentType.TEXT, text="")]
    request = self.build_agent_request_from_user_content(
        channel_id=channel_id, sender_id=sender_id, session_id=session_id,
        content_parts=content_parts, channel_meta=meta,
    )
    request.channel_meta = meta
    return request
```

### 自定义渠道目录与 CLI

- **目录**：工作目录下的 `custom_channels/`（默认 `~/.copaw/custom_channels/`）用于存放自定义渠道模块。Manager 启动时会扫描该目录下的 `.py` 文件与包（含 `__init__.py` 的子目录），加载其中的 `BaseChannel` 子类，并按类的 `channel` 属性注册。
- **安装**：`copaw channels install <key>` 会在 `custom_channels/` 下生成名为 `<key>.py` 的模板文件，可直接编辑实现；也可用 `--path <本地路径>` 或 `--url <URL>` 从本地/网络复制渠道模块。`copaw channels add <key>` 等价于安装后并写入 config 默认项，且可加 `--path`/`--url`。
- **删除**：`copaw channels remove <key>` 会从 `custom_channels/` 中删除该渠道模块（仅支持自定义渠道，内置渠道不可删）；加 `--no-keep-config`（默认）会同时从 `config.json` 的 `channels` 中移除对应 key。
- **Config**：`ChannelConfig` 使用 `extra="allow"`，`config.json` 的 `channels` 下可写任意 key；自定义渠道的配置会保存在 extra 中。配置方式与内置一致：`copaw channels config` 交互式配置，或直接编辑 config。

---

## 相关页面

- [项目介绍](./intro) — 这个项目可以做什么
- [快速开始](./quickstart) — 安装与首次启动
- [心跳](./heartbeat) — 定时自检/摘要
- [CLI](./cli) — init、app、cron、clean
- [配置与工作目录](./config) — config.json 与工作目录
