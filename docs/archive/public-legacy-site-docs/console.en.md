# Console

The **Console** is Spider Mesh's built-in web interface. After running `copaw app`,
open `http://127.0.0.1:8088/` in your browser to enter the Console.

**In the Console, you can:**

- Chat with Spider Mesh in real time
- Enable/disable messaging channels
- View and manage all chat sessions
- Manage scheduled jobs
- Edit Spider Mesh's persona and behavior files
- Enable/disable skills to extend Spider Mesh's capabilities
- Manage MCP clients
- Modify runtime configuration
- Configure LLM providers and select active models
- Manage environment variables needed by tools

The sidebar groups features into **Chat**, **Run**, and **System Settings**.
The **Run** section also contains secondary groups such as **Insight &
Optimization**. The sections below walk through each feature in order.

> **Not seeing the Console?** Make sure the frontend has been built. See
> [CLI](./cli).

---

## Chat

> Sidebar: **Chat → Chat**

This is where you talk to Spider Mesh. Open it from the sidebar whenever you want a
direct conversation surface.

Chat (screenshot removed)

**Send a message:**
Type in the input box at the bottom, then press **Enter** or click the send
button (↑). Spider Mesh replies in real time.

**Create a new session:**
Click the **+ New Chat** button at the top of the chat sidebar to start a new
conversation. Each session keeps separate history.

**Switch sessions:**
Click any session name in the chat sidebar to load its history.

**Delete a session:**
Click the **···** button on a session item, then click the **trash** icon.

---

## Channels

> Sidebar: **System Settings → Channels**

Manage channel for DingTalk, Feishu, Discord, QQ,
iMessage, and Console.

Channels (screenshot removed)

**Enable a channel:**

1. Click the channel card you want to configure.
2. A settings panel slides out on the right. Turn on **Enable**.

   Channel Configuration (screenshot removed)

3. Fill in required credentials (fields differ by channel):

   | Channel      | Required fields                                                |
   | ------------ | -------------------------------------------------------------- |
   | **DingTalk** | Client ID, Client Secret                                       |
   | **Feishu**   | App ID, App Secret, Encrypt Key, Verification Token, Media Dir |
   | **Discord**  | Bot Token, HTTP Proxy, Proxy Auth                              |
   | **QQ**       | App ID, Client Secret                                          |
   | **iMessage** | Database path, Poll interval                                   |
   | **Console**  | _(toggle only)_                                                |

4. Click **Save**. Changes take effect in seconds, no restart required.

**Disable a channel:**
Open the same panel, turn off **Enable**, then click **Save**.

> For credential setup details, see [Channels](./channels).

---

## Sessions

> Sidebar: **Chat → Chat**

View, filter, and clean up chat sessions across all channels.

Sessions (screenshot removed)

**Find sessions:**
Use the search box to filter by user, or use the dropdown to filter by
channel. The table updates immediately.

**Rename a session:**
Click **Edit** on a row → change the name → click **Save**.

**Delete one session:**
Click **Delete** on a row → confirm.

**Batch delete:**
Select rows → click **Batch Delete** → confirm.

---

## Cron Jobs

> Sidebar: **Run → Runtime Center → Automation**

Create and manage scheduled jobs that Spider Mesh runs automatically by time.

Cron Jobs (screenshot removed)

**Create a new job:**

> If the cron job fails to be created, please refer to the **Troubleshooting Scheduled (Cron) Tasks** section in the [FAQ](./faq) to identify the cause.

The **simplest way to create a cron job is to chat directly with Spider Mesh** and let it handle the creation for you. For example, if you want to receive a reminder to drink water on DingTalk, simply message Spider Mesh on DingTalk: "Help me create a cron job to remind me to drink water every 5 minutes." Once created, you can view the new task under **Run → Runtime Center → Automation** in the console.

Alternatively, you can create tasks directly via the Console interface:

1. Click **+ Create Job**.

   Create Cron Job (screenshot removed)

2. Fill in each section:
   - **Basic Info** — Job ID (e.g. `job-001`) and job name (e.g. "Daily Summary").
   - **Schedule** — Cron expression (e.g. `0 9 * * *` = 9:00 AM daily) and
     timezone
   - **Task Type & Content** — **Text** (fixed message) or **Agent** (ask
     Spider Mesh and forward reply), then the content
   - **Delivery** — Target channel (Console, DingTalk, etc.), target user & session id, and
     mode (**Stream** = real-time, **Final** = one complete response)
   - **Advanced** — Max concurrency, timeout, misfire grace time
3. Click **Save**.

**Edit a job:**
Click **Edit** on a row → modify fields → **Save**.

**Enable/disable a job:**
Toggle the switch in the row.

**Run once immediately:**
Click **Execute Now** → confirm.

**Delete a job:**
Click **Delete** → confirm.

---

## Workspace

> Sidebar: **Run → Agent Workbench → Workspace**

Edit files that define Spider Mesh's persona and behavior, such as `SOUL.md`,
`AGENTS.md`, and `HEARTBEAT.md`, directly in the browser.

Workspace (screenshot removed)

**Edit files:**

1. Click a file in the list (e.g. `SOUL.md`).
2. The editor shows file content. Make your changes.
3. Click **Save** to apply, or **Reset** to discard and reload.

**View daily memory:**
If `MEMORY.md` exists, click the **▶** arrow to expand date-based entries.
Click a date to view or edit that day's memory.

**Download workspace:**
Click **Download** (⬇) to export the entire workspace as a `.zip`.

**Upload/restore workspace:**
Click **Upload** (⬆) → choose a `.zip` (max 100 MB). Existing workspace files
will be replaced. Useful for migration and backup restore.

---

## Skills

> Sidebar: **Run → Capability Market → Skills**

Manage skills that extend Spider Mesh's capabilities (for example: PDF reading,
Word document creation, news retrieval).

Skills (screenshot removed)

**Enable a skill:**
Click **Enable** at the bottom of a skill card. It takes effect immediately.

**View skill details:**
Click a skill card to open its full description.

**Disable a skill:**
Click **Disable**. It also takes effect immediately.

**Import from Skill Hub:**

1. Click **Import Skill**.
2. Enter a skill URL, then click import.
3. Wait for import to complete. The skill appears as enabled.

Import Skill (screenshot removed)

**Create a custom skill:**

1. Click **Create Skill**.
2. Enter a skill name (e.g. `weather_query`) and skill content in Markdown
   (must include `name` and `description`).
3. Click **Save**. The new skill appears immediately.

Create Skill (screenshot removed)

**Delete a custom skill:**
Disable the skill first, then click the **🗑** icon on its card and confirm.

> For built-in skill details, Skill Hub import, and custom skill authoring, see
> [Skills](./skills).

---

## MCP

> Sidebar: **Run → Capability Market → MCP**

Enable/disable/delete **MCP** clients here, or create new ones.

MCP (screenshot removed)

**Create a client**
Click **Create Client** in the top-right, fill in the required information, then click **Create**. The new MCP client appears in the list.

---

## Runtime Config

> Sidebar: **System Settings → Agent Config**

Runtime Config (screenshot removed)

Adjust **Max iterations** and **Max input length** here; click **Save** after changing.

---

## Models

> Sidebar: **System Settings → Models**

Configure LLM providers and choose the model Spider Mesh uses. Spider Mesh supports both
cloud providers (API key required) and local providers (no API key required).

Models (screenshot removed)

### Cloud providers

**Configure a provider:**

1. Click **Settings** on a provider card.
2. Enter your **API Key**.
3. Click **Save**. Card status becomes "Authorized".
4. To add a custom provider, click **Add Provider**.
5. Enter provider ID, display name, and required fields, then click **Create**.
6. Open **Settings** for the created provider, fill required fields, then
   **Save**. Status becomes "Authorized".

**Revoke authorization:**
Open the provider settings dialog and click **Revoke Authorization**. API key
data is cleared. If this provider is currently active, model selection is also
cleared.

### Local providers (llama.cpp / MLX)

Local providers show a purple **Local** tag. Install backend dependencies
first (`pip install 'copaw[llamacpp]'` or `pip install 'copaw[mlx]'`).

**Download a model:**

1. Click **Manage Models** on a local provider card.
2. Click **Download Model**, then fill:
   - **Repo ID** (required) — e.g. `Qwen/Qwen3-4B-GGUF`
   - **Filename** (optional) — leave empty for auto-selection
   - **Source** — the configured model source
3. Click **Download** and wait for completion.

**View and delete models:**
Downloaded models are listed with file size, source badge,
and delete button.

### Ollama provider

The Ollama provider integrates with your local Ollama daemon and dynamically
loads models from it.

**Prerequisites:**

- Install Ollama from [ollama.com](https://ollama.com)
- Install the Ollama SDK: `pip install 'copaw[ollama]'` (or re-run the installer with `--extras ollama`)

**Download a model:**

1. Click **Settings** on the Ollama provider card.
2. In **API Key**, enter a value (for example `ollama`), then click **Save**.
3. Click **Manage Models** on the Ollama card, click **Download Model**, and
   enter a model name (e.g. `mistral:7b`, `qwen3:8b`).
4. Click **Download Model** and wait for completion.

**Cancel a download:**
During download, click **✕** next to the progress indicator to cancel.

**View and delete models:**
Downloaded models are listed with size and delete button. The list updates
automatically when models are added/removed via Ollama CLI or Console.

**How it differs from local providers:**

- Models come from the Ollama daemon (not downloaded directly by Spider Mesh)
- Model list is auto-synced with Ollama
- Popular model examples: `mistral:7b`, `qwen3:8b`

> You can also manage Ollama models via CLI: `copaw models ollama-pull`,
> `copaw models ollama-list`, `copaw models ollama-remove`. See
> [CLI](./cli#ollama-models).

### Choose the active model

1. In the **LLM Config** section, select a **Provider** from the dropdown
   (only authorized providers or local providers with downloaded models appear).
2. Select a **Model** from the model dropdown.
3. Click **Save**.

> **Note:** Cloud API key validity is your responsibility. Spider Mesh does not
> verify key correctness.
>
> For provider details, see [Config — LLM Providers](./config#llm-providers).

---

## Environment Variables

> Sidebar: **System Settings → Environment**

Manage runtime environment variables needed by Spider Mesh tools and skills
(for example, `TAVILY_API_KEY`).

Environments (screenshot removed)

**Add a variable:**

1. Click **+ Add Variable**.
2. Enter the variable name (e.g. `TAVILY_API_KEY`) and value.
3. Click **Save**.

**Edit a variable:**
Change the **Value** field, then click **Save**.
(Variable names are read-only after save; to rename, delete and recreate.)

**Delete a variable:**
Click the **🗑** icon on a row, then confirm if prompted.

**Batch delete:**
Select rows → click **Delete** in the toolbar → confirm.

> **Note:** Variable validity is your responsibility. Spider Mesh only stores and
> loads values.
>
> See [Config — Environment Variables](./config#environment-variables) for more.

---

## Quick Reference

| Page                  | Sidebar path                     | What you can do                                      |
| --------------------- | -------------------------------- | ---------------------------------------------------- |
| Chat                  | Chat → Chat                      | Talk with Spider Mesh, manage sessions                     |
| Channels              | System Settings → Channels       | Enable/disable channels, configure credentials       |
| Sessions              | Chat → Chat                      | Filter, rename, delete sessions                      |
| Cron Jobs             | Run → Runtime Center → Automation | Create/edit/delete jobs, run immediately            |
| Workspace             | Run → Agent Workbench → Workspace | Edit persona files, view memory, upload/download    |
| Skills                | Run → Capability Market → Skills | Enable/disable/create/delete skills                  |
| MCP                   | Run → Capability Market → MCP    | Enable/disable/create/delete MCP clients             |
| Runtime Config        | System Settings → Agent Config   | Modify runtime configuration                         |
| Models                | System Settings → Models         | Configure providers, manage local/Ollama, pick model |
| Environment Variables | System Settings → Environment    | Add/edit/delete environment variables                |

---

## Related Pages

- [Config & Working Directory](./config) — Config fields, providers, env vars
- [Channels](./channels) — Per-channel setup and credentials
- [Skills](./skills) — Built-in skills and custom skills
- [Heartbeat](./heartbeat) — Heartbeat configuration
- [CLI](./cli) — Command-line reference
