# Scripts

Run from **repo root**.

## Installers

The platform installers under `scripts/install.{ps1,bat,sh}` now also try to install the built-in `QMD` sidecar with `npm install -g @tobilu/qmd`.

- If `qmd` is already on `PATH`, the installer reuses it.
- If `npm` is missing, CoPaw still installs, but memory sidecar retrieval stays on local backends until Node.js/QMD is installed.
- CoPaw defaults the QMD embedding model to `Qwen3-Embedding-0.6B` via its internal memory backend config.
- On Windows, CoPaw bypasses broken global `qmd.cmd/.ps1` wrappers and launches `QMD` via `node .../dist/cli/qmd.js`.
- On Windows, the built-in QMD sidecar defaults to lightweight `search` mode and falls back to local `hybrid-local` when QMD returns no hits.

## Build wheel (with latest console)

```bash
bash scripts/wheel_build.sh
```

- Builds the console frontend (`console/`), copies `console/dist` to `src/copaw/console/dist`, then builds the wheel. Output: `dist/*.whl`.

## Build website

```bash
bash scripts/website_build.sh
```

- Installs dependencies (pnpm or npm) and runs the Vite build. Output: `website/dist/`.

## Build Docker image

```bash
bash scripts/docker_build.sh [IMAGE_TAG] [EXTRA_ARGS...]
```

- Default tag: `copaw:latest`. Uses `deploy/Dockerfile` (multi-stage: builds console then Python app).
- Example: `bash scripts/docker_build.sh myreg/copaw:v1 --no-cache`.
