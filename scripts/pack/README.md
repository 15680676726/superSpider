# Spider Mesh desktop packaging scripts

One-click build: each script first builds a **wheel** via
`scripts/wheel_build.sh` (includes the console frontend), then uses a
**temporary conda environment** and **conda-pack** (no current dev env).
Dependencies follow `pyproject.toml`.

- **Windows**: wheel -> conda-pack -> unpack -> NSIS installer (`.exe`)
- **macOS**: wheel -> conda-pack -> unpack into `.app` -> optional zip

## System Requirements

- **Windows**: Windows 10 or later
- **macOS**: macOS 14 (Sonoma) or later, Apple Silicon (M1/M2/M3/M4) recommended for MLX support

## Prerequisites

- **conda** (Miniconda/Anaconda) on PATH
- **Node.js / npm** (for the console frontend)
- (Windows only) **NSIS**: `makensis` on PATH
- **Icons**: pre-generated `icon.ico` (Windows) and `icon.icns` (macOS) are included in `scripts/pack/assets/`

## One-click build

From the **repo root**:

**macOS**

```bash
bash ./scripts/pack/build_macos.sh
# Output: dist/Spider Mesh.app

CREATE_ZIP=1 bash ./scripts/pack/build_macos.sh
# Extra output: dist/Spider-Mesh-<version>-macOS.zip
```

**Windows (PowerShell)**

```powershell
./scripts/pack/build_win.ps1
# Output: dist/Spider-Mesh-Setup-<version>.exe
# Installs customer-visible shortcuts:
#   - Spider Mesh
#   - Spider Mesh（调试）
```

## Run from terminal and see logs (macOS)

If the `.app` crashes on double-click, run it from Terminal to see the full error and logs:

```bash
# From repo root; force packed env only (no system conda / PYTHONPATH). Adjust path if needed.
APP_ENV="$(pwd)/dist/Spider Mesh.app/Contents/Resources/env"
PYTHONPATH= PYTHONHOME="$APP_ENV" "$APP_ENV/bin/python" -m copaw desktop
```

All stdout/stderr (including Python tracebacks) will appear in the terminal. Use this to debug startup errors or to run with `--log-level debug`.

When you **double-click** the app and nothing appears, the launcher writes stderr/stdout to `~/.copaw/desktop.log`. Inspect that file for errors.

On first launch macOS may ask for "Desktop" or "Files and Folders" access: click **Allow** so the app can run properly; if you click **Don't Allow**, the window may close.

## macOS: if Gatekeeper blocks the app

The Spider Mesh macOS app is currently **not notarized**. Users can still open it as follows:

- **Right-click to open (recommended)**
  Right-click (or Control+click) `Spider Mesh.app` -> **Open** -> in the dialog click **Open** again.

- **Allow in System Settings**
  If still blocked, go to **System Settings -> Privacy & Security**, find the blocked app message, and click **Open Anyway** or **Allow**.

- **Remove quarantine attribute (not recommended for most users)**
  In Terminal: `xattr -cr /Applications/Spider\ Mesh.app` (or the path to the `.app` after unzipping).

## CI

`.github/workflows/desktop-release.yml`:

- **Triggers**: Release publish or manual `workflow_dispatch`
- **Windows**: build console -> temporary conda env + conda-pack -> NSIS -> upload artifact
- **macOS**: build console -> temporary conda env + conda-pack -> `.app` -> zip -> upload artifact
- **Release**: when triggered by a release, uploads the Windows installer and macOS zip as release assets

## Script reference

| File | Description |
|------|-------------|
| `build_common.py` | Create temporary conda env, install `copaw[full]` from a wheel, conda-pack; produces archive. |
| `build_macos.sh` | One-click: build wheel -> build_common -> unpack into `Spider Mesh.app`; optional zip. |
| `build_win.ps1` | One-click: build wheel -> build_common -> unpack -> create VBS/BAT launchers -> `makensis` installer. |
| `copaw_desktop.nsi` | NSIS script: pack `dist/win-unpacked`, add icons, and create shortcuts. |
| `assets/icon.ico` | Pre-generated Windows icon (installer and shortcuts). |
| `assets/icon.icns` | Pre-generated macOS icon (app bundle). |
