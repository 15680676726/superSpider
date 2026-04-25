# FAQ

This page collects the most frequently asked questions from the community.
Click a question to expand the answer.

---

### Spider Mesh Capability Overview

Please check the [Capability Overview](./comparison) page for the current Spider Mesh product surface.

### How to install Spider Mesh

Spider Mesh supports multiple installation methods. See
[Quick Start](./quickstart) for details:

1. One-line installer (sets up Python automatically)

```
# macOS / Linux:
curl -fsSL https://raw.githubusercontent.com/15680676726/superSpider/main/scripts/install.sh | bash
# Windows (PowerShell):
irm https://raw.githubusercontent.com/15680676726/superSpider/main/scripts/install.ps1 | iex
# For latest instructions, refer to docs and prefer pip if needed.
```

2. Install with pip

Python version requirement: >= 3.10, < 3.14

```
pip install copaw
```

3. Install with Docker

If Docker is installed, run the following commands and then open
`http://127.0.0.1:8088/` in your browser:

```
docker pull <your-dockerhub-namespace>/superspider:latest
docker run -p 127.0.0.1:8088:8088 -v copaw-data:/app/working <your-dockerhub-namespace>/superspider:latest
```

> **⚠️ Special Notice for Windows Enterprise LTSC Users**
>
> If you are using Windows LTSC or an enterprise environment governed by strict security policies, PowerShell may run in **Constrained Language Mode**, potentially causing the following issue:
>
> 1. **If using CMD (.bat): Script executes successfully but fails to write to `Path`**
>
>    The script completes file installation. Due to **Constrained Language Mode**, it cannot automatically update environment variables. Manually configure as follows:
>
>    - **Locate the installation directory**:
>      - Check if `uv` is available: Enter `uv --version` in CMD. If a version number appears, **only configure the app bin path**. If you receive the prompt `'uv' is not recognized as an internal or external command, operable program or batch file,` configure both paths.
>      - uv path (choose one based on installation location; use if step 1 fails): Typically `%USERPROFILE%\.local\bin`, `%USERPROFILE%\AppData\Local\uv`, or the `Scripts` folder within your Python installation directory
>      - App bin path: Typically located at `%USERPROFILE%\.copaw\bin`.
>    - **Manually add to the system's Path environment variable**:
>      - Press `Win + R`, type `sysdm.cpl` and press Enter to open System Properties.
>      - Click “Advanced” -> “Environment Variables”.
>      - Under “System variables”, locate and select `Path`, then click “Edit”.
>      - Click “New”, enter both directory paths sequentially, then click OK to save.
>
> 2. **If using PowerShell (.ps1): Script execution interrupted**
>
> Due to **Constrained Language Mode**, the script may fail to automatically download `uv`.
>
> - **Manually install uv**: Refer to the [GitHub Release](https://github.com/astral-sh/uv/releases) to download `uv.exe` and place it in `%USERPROFILE%\.local\bin` or `%USERPROFILE%\AppData\Local\uv`; or ensure Python is installed and run `python -m pip install -U uv`.
> - **Configure `uv` environment variables**: Add the `uv` directory and `%USERPROFILE%\.copaw\bin` to your system's `Path` variable.
> - **Re-run the installation**: Open a new terminal and execute the installation script again to complete the Spider Mesh installation.
> - **Configure the app bin path in `Path`**: Add `%USERPROFILE%\.copaw\bin` to your system's `Path` variable.

### How to update Spider Mesh

To update Spider Mesh, use the method matching your installation type:

1. If installed via one-line script, re-run the installer to upgrade.

2. If installed via pip, run:

```
pip install --upgrade copaw
```

3. If installed from source, pull the latest code and reinstall:

```
cd superSpider
git pull origin main
pip install -e .
```

4. If using Docker, pull the latest image and restart the container:

```
docker pull <your-dockerhub-namespace>/superspider:latest
docker run -p 127.0.0.1:8088:8088 -v copaw-data:/app/working <your-dockerhub-namespace>/superspider:latest
```

After upgrading, restart the service with `copaw app`.

### How to initialize and start Spider Mesh service

Recommended quick initialization:

```bash
copaw init --defaults
```

Start service:

```bash
copaw app
```

The default Console URL is `http://127.0.0.1:8088/`. After quick init, you can
open Console and customize settings. See
[Quick Start](./quickstart).

### Open-source repository

Spider Mesh is open source. Official repository:
`https://github.com/15680676726/superSpider`

### Where to check latest version upgrade details

You can check version changes in Spider Mesh GitHub
[Releases](https://github.com/15680676726/superSpider/releases).

### How to configure models

In Console, go to **System Settings -> Models** to configure. See the
[Models](./models) doc for details:

- Cloud models: fill the API key for your chosen provider (or your custom OpenAI-compatible provider),
  then select the active model.
- Local models: supports `llama.cpp`, `MLX`, and Ollama. After download, select
  the active model on the same page.

You can also use `copaw models` CLI commands for configuration, download, and
switching. See
[CLI -> Models and environment variables -> copaw models](./cli#copaw-models).

### Troubleshooting scheduled (cron) tasks

In Console, go to **Run -> Runtime Center -> Automation** to create and manage scheduled tasks.

cron (screenshot removed)

The easiest way to create a cron job is to talk to Spider Mesh in the channel where you want the results. For example, say: “Create a scheduled task that reminds me to drink water every five minutes.” You can then see the enabled job in Console.

If a scheduled task does not run as expected, try the following:

1. Confirm that the Spider Mesh service is running.

2. Check that the task **Status** is **Enabled**.

   enable (screenshot removed)

3. Check that **Dispatch Channel** is set to the channel where you want the result (e.g. console, dingtalk, feishu, discord, imessage).

   channel (screenshot removed)

4. Check that **Dispatch Target User ID** and **Dispatch Target Session ID** are correct.

   id (screenshot removed)

   In Console, go to **Chat -> Chat** and find the session you used when creating the task. To have the task reply in that session, the **User ID** and **Session ID** there must match the task’s **Dispatch Target User ID** and **Dispatch Target Session ID**.

   id (screenshot removed)

5. If the task runs at the wrong time, check the **Schedule (Cron)** for the task.

   cron (screenshot removed)

6. To verify that the task was created and can run, click **Execute Now**. If it works, you should see the reply in the target channel. You can also ask Spider Mesh: “Trigger the ‘drink water reminder’ task I just created.”

   exec (screenshot removed)

### How to manage Skills

Go to **Run -> Capability Market -> Skills** in Console. You can enable/disable Skills, create
custom Skills, and import Skills from Skills Hub. See
[Skills](./skills).

### How to configure MCP

Go to **Run -> Capability Market -> MCP** in Console. You can enable/disable/delete/create MCP
clients there. See [MCP](./mcp).

### Common error

1. Error pattern: `You didn't provide an API key`

Error detail:

```
Error: Unknown agent error: AuthenticationError: Error code: 401 - {'error': {'message': "You didn't provide an API key. You need to provide your API key in an Authorization header using Bearer auth (i.e. Authorization: Bearer YOUR_KEY). ", 'type': 'invalid_request_error', 'param': None, 'code': None}, 'request_id': 'xxx'}
```

Cause 1: model API key is not configured. Get an API key and configure it in
**Console -> System Settings -> Models**.

Cause 2: key is configured but still fails. In most cases, one of the
configuration fields is incorrect (for example `base_url`, `api key`, or model
name).

If it still fails, please check:

- whether `base_url` is correct;
- whether the API key is copied completely (no extra spaces);
- whether the model name exactly matches the provider value (case-sensitive).

---

### How to get support when errors occur

To speed up troubleshooting and fixes, please open an
[issue](https://github.com/15680676726/superSpider/issues) in the Spider Mesh GitHub
repository and attach the full error message and any error detail file.

Console errors often include a path to an error detail file. For example:

Error: Unknown agent error: AuthenticationError: Error code: 401 - {'error': {'message': "You didn't provide an API key. You need to provide your API key in an Authorization header using Bearer auth (i.e. Authorization: Bearer YOUR_KEY). ", 'type': 'invalid_request_error', 'param': None, 'code': None}, 'request_id': 'xxx'}(Details: /var/folders/.../copaw_query_error_qzbx1mv1.json)

Please upload that file (e.g. `/var/folders/.../copaw_query_error_qzbx1mv1.json`)
and also provide your current model provider, model name, and Spider Mesh version.
