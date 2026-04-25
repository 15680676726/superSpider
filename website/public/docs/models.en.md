# Models

You need to configure a model before chatting with Spider Mesh. You can do this under **Console → System Settings → Models**.

Console models (screenshot removed)

Spider Mesh supports multiple LLM providers: **cloud providers** (require API Key), **local providers** (llama.cpp / MLX), and **Ollama provider**, and you can add **custom providers**. This page explains how to configure each type.

---

## Configure cloud providers

Cloud providers call remote models via API and require an **API Key**.

**In the console:**

1. Open the console and go to **System Settings → Models**.
2. Find the target cloud provider card and click **Settings**. Enter your **API key** and click **Save**.

   save (screenshot removed)

3. After saving, the card status in the top-right becomes **Available**. In the **LLM Configuration** section at the top, you can select this provider in the **Provider** dropdown and see the list of models in the **Model** dropdown.

   choose (screenshot removed)

4. Choose the target model (e.g. qwen3.5-plus) and click **Save**.

   save (screenshot removed)

5. The LLM Configuration bar will show the current provider and model in the top-right.

   model (screenshot removed)

> To revoke a cloud provider, click **Settings** on its card, then **Revoke Authorization** and confirm. The provider status will change to **Unavailable**.
>
> cancel (screenshot removed)

## Local providers (llama.cpp / MLX)

Local providers run models on your machine with **no API Key**; data stays on-device.

**Prerequisites:**

- Install the matching backend in the same environment as Spider Mesh:
  - llama.cpp: `pip install 'copaw[llamacpp]'`
  - MLX: `pip install 'copaw[mlx]'`

1. On the Models page you’ll see cards for llama.cpp and MLX.

   card (screenshot removed)

2. Click **Models** on the target local provider card (e.g. llama.cpp), then **Download model**.

   download (screenshot removed)

3. Enter the **Repo ID** and choose the **Source**, then click **Download model**.

   id (screenshot removed)

4. The download will run; wait for it to finish.

   wait (screenshot removed)

5. When the download completes, the local provider card status becomes **Available**.

   avai (screenshot removed)

6. In **LLM Configuration** at the top, select the local provider in the **Provider** dropdown and the newly added model in the **Model** dropdown, then click **Save**.

   model (screenshot removed)

7. The LLM Configuration area will show the local provider and the selected model name.

   see (screenshot removed)

> Click **Models** on a local provider card to see model names, sizes, and sources. To remove a model, click the **trash icon** on the right of that model and confirm.
>
> delete (screenshot removed)

## Ollama provider

The Ollama provider uses the **Ollama daemon** installed on your machine. Models are managed by Ollama; Spider Mesh does not download them directly, and the list syncs with Ollama.

**Prerequisites:**

- Install Ollama from [ollama.com](https://ollama.com).
- Install Ollama support in Spider Mesh’s environment: `pip install 'copaw[ollama]'`.

1. On the Models page you’ll see the Ollama provider card.

2. Click **Settings** at the bottom right. On the Ollama config page, enter an **API Key** (any value is fine, e.g. `ollama`). Click **Save**.

   set (screenshot removed)

3. Click **Models** at the bottom right. If you’ve already pulled models with Ollama, they’ll appear here. To pull a new model, click **Download model**.

   download (screenshot removed)

4. Enter the **Model name**, then click **Download Model**.

   download (screenshot removed)

5. The model will download; wait for it to complete.

   wait (screenshot removed)

6. When done, in **LLM Configuration** at the top, select **Ollama** in the **Provider** dropdown and your model in the **Model** dropdown, then click **Save**.

   save (screenshot removed)

7. The LLM Configuration area will show the Ollama provider and the selected model name.

   name (screenshot removed)

> If you see `Ollama SDK not installed. Install with: pip install 'copaw[ollama]'`, make sure Ollama is installed from ollama.com and you’ve run `pip install 'copaw[ollama]'` in Spider Mesh’s environment. To remove a model, click **Models** on the Ollama card, then the **trash icon** next to the model and confirm.
>
> delete (screenshot removed)

## Add custom provider

1. On the Models page click **Add provider**.

   add (screenshot removed)

2. Enter **Provider ID** and **Display name**, then click **Create**.

   create (screenshot removed)

3. The new provider card will appear.

   card (screenshot removed)

4. Click **Settings**, enter **Base URL** and **API Key**, then click **Save**.

   save (screenshot removed)

5. The card will show the configured Base URL and API Key, but the status will still be **Unavailable** until you add a model.

   model (screenshot removed)

6. Click **Models**, enter the **Model ID**, then click **Add model**.

   add (screenshot removed)

7. The custom provider will then show as **Available**. In **LLM Configuration** at the top, select it in the **Provider** dropdown and the new model in the **Model** dropdown, then click **Save**.

   model (screenshot removed)

8. The LLM Configuration area will show the custom provider ID and the selected model name.

   save (screenshot removed)

> If configuration fails, double-check **Base URL**, **API Key**, and **Model ID** (including case). To remove a custom provider, click **Delete provider** on its card and confirm.
>
> delete (screenshot removed)
