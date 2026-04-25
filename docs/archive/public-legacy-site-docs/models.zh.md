# 模型

在与 Spider Mesh 对话前，需要先配置模型。在 **控制台 → 系统设置 → 模型** 中可以快捷配置。

控制台模型 (screenshot removed)

Spider Mesh 支持多种 LLM 提供商：**云提供商**（需 API Key）、**本地提供商**（llama.cpp / MLX）和 **Ollama 提供商**，且支持添加自定义 **提供商**。本文介绍这几类提供商的配置方式。

---

## 配置云提供商

云提供商通过 API 调用远程模型，需要配置 **API Key**。

**在控制台中配置：**

1. 打开控制台，进入 **系统设置 → 模型**。
2. 找到目标云提供商卡片，点击 **设置**。输入你的 **API key**，点击 **保存**。

   save (screenshot removed)

3. 保存后可以看到目标云提供商卡片右上角状态变成 **可用**，此时在上方的 **LLM 配置** 中，**提供商** 对应的下拉菜单中可以选择目标云提供商，**模型** 对应的下拉菜单中出现一系列可选模型。

   choose (screenshot removed)

4. 选择目标模型（以 qwen3.5-plus 为例），点击 **保存**。

   save (screenshot removed)

5. 可以看到 LLM 配置栏右上角显示当前正在使用的模型提供商及模型。

   model (screenshot removed)

> 注：如果想撤销某个云提供商授权，点击目标云提供商卡片的 **设置**，点击撤销授权，二次确认撤销授权后，可将目标提供商的状态调整为 **不可用**。
>
> cancel (screenshot removed)

## 本地提供商（llama.cpp / MLX）

本地提供商在本地运行模型，**无需 API Key**，数据不出本机。

**前置条件：**

- 在Spider Mesh所在环境中安装对应后端：
  - llama.cpp：`pip install 'copaw[llamacpp]'`
  - MLX：`pip install 'copaw[mlx]'`

1. 在控制台的模型页面可以找到 llama.cpp 和 MLX 对应的卡片。

   card (screenshot removed)

2. 点击目标本地提供商（以llama.cpp为例）卡片的 **模型**，选择 **下载模型**。

   download (screenshot removed)

3. 填写 **仓库 ID**，并选择 **来源**，点击 **下载模型**。

   id (screenshot removed)

4. 可以看到正在下载模型，需要等待一段时间。

   wait (screenshot removed)

5. 模型下载完成后，可以看到本地提供商卡片右上角转为 **可用** 状态。

   avai (screenshot removed)

6. 在上方的 **LLM 配置** 中，**提供商** 对应的下拉菜单中可以选择本地提供商，**模型** 对应的下拉菜单中可选择刚刚添加的模型。点击保存。

   model (screenshot removed)

7. 可以看到 LLM 配置右上角显示本地提供商和选择的模型名称。

   see (screenshot removed)

> 注：点击对应本地提供商卡片上的 **模型**，可以看到不同模型名称、大小、下载来源。如果想删除模型，点击对应模型最右侧的 **垃圾桶图标**，二次确认后即可删除。
>
> delete (screenshot removed)

## Ollama 提供商

Ollama 提供商对接本机安装的 **Ollama 守护进程**，使用其中的模型，无需由 Spider Mesh 直接下载模型文件，列表会与 Ollama 自动同步。

**前置条件：**

- 从 [ollama.com](https://ollama.com) 安装 Ollama。
- 在 Spider Mesh所在虚拟环境中安装 Ollama：`pip install 'copaw[ollama]'`。

1. 在控制台的模型界面中，可以看到 ollama 提供商对应的卡片。

2. 点击右下角 **设置**，在配置 ollama 的页面中，填写 **API Key**。此处可随意填写一个内容，例如 ollama。点击 **保存**。

   set (screenshot removed)

3. 点击 **模型**，如果已经使用 Ollama 下载过一些模型，则可以看到对应的模型列表。如果还没有下载模型，或需要下载额外模型，点击 **下载模型**。

   download (screenshot removed)

4. 填写 **模型名称**，点击 **下载模型**。

   download (screenshot removed)

5. 可以看到进入模型下载状态，等待模型下载完成。

   wait (screenshot removed)

6. 下载完成后，可以在上方的 **LLM 配置** 中，**提供商** 对应的下拉菜单中可以选择 Ollama，**模型** 对应的下拉菜单中可选择想使用的模型。点击 **保存**。

   save (screenshot removed)

7. 可以看到 LLM 配置右上角显示 Ollama 提供商和选择的模型名称。

   name (screenshot removed)

> 如果在过程中遇到 `Ollama SDK not installed. Install with: pip install 'copaw[ollama]'`的提示，请先确认是否已经在 ollama.com 下载 Ollama，并在 Spider Mesh所在虚拟环境中执行过 `pip install 'copaw[ollama]'`。如果想删除某个模型，点击 Ollama 卡片右下角的 **模型**，在模型列表中，点击想要删除的模型右侧的 **垃圾桶按钮**，二次确认后即可删除。
>
> delete (screenshot removed)

## 添加自定义提供商

1. 在控制台的模型页面点击 **添加提供商**。

   add (screenshot removed)

2. 填写 **提供商 ID** 和 **显示名称**，点击 **创建**。

   create (screenshot removed)

3. 可以看见新添加的提供商卡片。

   card (screenshot removed)

4. 点击设置，填写 **Base URL** 和 **API Key**，点击 **保存**。

   save (screenshot removed)

5. 可以看到自定义提供商卡片中已经显示刚刚配置的 Base_URL 和 API Key，但此时右上角仍显示 **不可用**， 还需要配置模型。

   model (screenshot removed)

6. 点击 **模型**，填写 **模型 ID**，点击 **添加模型**。

   add (screenshot removed)

7. 此时可见自定义提供商为 **可见**。在上方的 **LLM 配置** 中，**提供商** 对应的下拉菜单中可以选择自定义提供商，**模型** 对应的下拉菜单中可选择刚刚添加的模型。点击 **保存**。

   model (screenshot removed)

8. 可以看到 LLM 配置右上角显示自定义提供商的 ID 和选择的模型名称。

   save (screenshot removed)

> 注：如果无法成功配置，请重点检查 **Base URL，API Key 和 模型 ID** 是否填写正确，尤其是模型的大小写。如果想删除自定义提供商，在对应卡片右下角点击 **删除提供商**，二次确认后可成功删除。
>
> delete (screenshot removed)
