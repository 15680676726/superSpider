# Spider Mesh 桌面版打包脚本

一键打包时，脚本会先通过 `scripts/wheel_build.sh` 或 `scripts/wheel_build.ps1`
重新构建当前仓库的 wheel，其中包含最新的 `console/` 前端产物；随后使用临时
conda 环境和 `conda-pack` 生成可分发桌面包，因此产物对应的是你打包当下仓库里的最新代码。

- Windows：wheel -> conda-pack -> 解压 -> NSIS 安装包（`.exe`）
- macOS：wheel -> conda-pack -> 解压成 `.app` -> 可选 zip

## 系统要求

- Windows：Windows 10 或更高版本
- macOS：macOS 14 及以上，推荐 Apple Silicon

## 前置依赖

- `conda`（Miniconda / Anaconda）已在 `PATH`
- `Node.js / npm`，用于构建当前前端
- 仅 Windows：`makensis` 已在 `PATH`
- `scripts/pack/assets/` 下已提供 `icon.ico` 与 `icon.icns`

## 一键打包

在仓库根目录执行：

### macOS

```bash
bash ./scripts/pack/build_macos.sh
# 产出：dist/Spider Mesh.app

CREATE_ZIP=1 bash ./scripts/pack/build_macos.sh
# 额外产出：dist/Spider-Mesh-<version>-macOS.zip
```

### Windows

```powershell
./scripts/pack/build_win.ps1
# 产出：dist/Spider-Mesh-Setup-<version>.exe
```

安装后会创建两个可见入口：

- `Spider Mesh`
- `Spider Mesh（调试）`

## macOS 终端调试

如果双击 `.app` 后没有打开窗口，可在终端执行：

```bash
APP_ENV="$(pwd)/dist/Spider Mesh.app/Contents/Resources/env"
PYTHONPATH= PYTHONHOME="$APP_ENV" "$APP_ENV/bin/python" -m copaw desktop
```

如果从 Finder 双击启动但没有窗口，启动日志会写入 `~/.copaw/desktop.log`。

## macOS 安全放行

当前 macOS 包尚未公证。如果系统拦截，可用以下方式放行：

- 右键 `Spider Mesh.app` -> `打开`
- 在“系统设置 -> 隐私与安全性”中点击“仍要打开”
- 或在终端执行 `xattr -cr /Applications/Spider\ Mesh.app`

## CI

`.github/workflows/desktop-release.yml` 会在 Release 发布或手动触发时构建：

- Windows：上传 `.exe`
- macOS：上传 `*-macOS.zip`

## 脚本说明

| 文件 | 说明 |
|------|------|
| `build_common.py` | 创建临时 conda 环境，从当前 wheel 安装 `copaw[full]` 并执行 `conda-pack` |
| `build_macos.sh` | 一键生成 `Spider Mesh.app` 与可选 zip |
| `build_win.ps1` | 一键生成 Windows 安装包与桌面快捷方式 |
| `copaw_desktop.nsi` | Windows NSIS 安装脚本 |
