# Scripts

Run from **repo root**.

## Installers

The platform installers under `scripts/install.{ps1,bat,sh}` still try to install the built-in `QMD` sidecar with `npm install -g @tobilu/qmd` as an optional compatibility extra.

- If `qmd` is already on `PATH`, the installer reuses it.
- If `npm` is missing, CoPaw still installs.
- This does **not** change the current formal memory contract:
  - shared memory remains `truth-first`
  - formal shared memory remains `no-vector`
  - `QMD` is not part of the formal runtime/operator readiness contract

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

## P0 Runtime Terminal Gate

```bash
python scripts/run_p0_runtime_terminal_gate.py --list
python scripts/run_p0_runtime_terminal_gate.py
```

- `--list` 只打印当前正式 gate 命令束，不执行。
- 默认执行顺序会串起：
  - 后端主链回归
  - 长跑与删旧回归
  - 控制台定向回归
  - 控制台构建
- 这条脚本用于 `P0-4` 的正式发布前门槛，不替代开发中的单项定向测试。

## Live Self-Evolution Smoke

```bash
python scripts/run_live_self_evolution_smoke.py --help
python scripts/run_live_self_evolution_smoke.py
```

- 这条脚本会在隔离 `runtime-root` 下复制当前 `config/providers/envs`，启动一条真实本地 `uvicorn` 服务进程，然后跑完整的 self-evolution live smoke。
- 当前 smoke 会覆盖：
  - system self-check
  - runtime preview / execution
  - learning / patch / growth 读面
  - 服务重启后的状态可读性
- 输出是 JSON 结果摘要，并把运行日志写到 `runtime-root` 下。
- 这条脚本依赖本机已有可用的工作目录配置、secret providers，以及对应 live 能力前置条件；它不是默认 CI 测试。
