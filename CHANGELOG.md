# Changelog

## 2.2.4 (2026-09-24)

- Both platforms can select model and dependency folders, including external drives.
- Import existing image/PE models and Hugging Face snapshots in place with local verification and cancellation.
- Locate existing Python environments by folder. New dependency caches and temporary files follow the chosen installation folder.
- Preserve previous locations after failed imports and report disconnected drives without silently changing storage.

两端均支持选择下载目录、复用已有模型和 Python 环境。详见 [2.2.4 发布说明](docs/releases/v2.2.4.md)。

## 2.2.3 (2026-09-24)

- Windows ships as a standalone EXE with embedded application resources and in-app dependency repair.
- Both platforms support Python interpreter selection, manual browsing, dependency-source selection and live installation progress.
- Windows CUDA version selection moves into the environment page. Healthy runtimes and existing user data are preserved.

Windows 无需外部 setup/start 脚本；两端均支持多 Python 选择、依赖换源和下载进度。详见 [2.2.3 发布说明](docs/releases/v2.2.3.md)。

## 2.2.2 (2026-09-24)

- Made PE-T2I and PE-I2I optional, with a bilingual reminder, direct generation, and a documented fallback if enhancement fails.
- Merged external-drive fixes for scoped dependency checks, concurrent bounded probes, cancellation and visible check actions.
- Stage dependency repairs separately and activate only after validation; reuse working GPU packages and preserve old environments and model data.
- Remember validated runtimes on both platforms and custom Windows storage locations across releases. Preserve system and Store Python discovery.
- Distinguish CPU-only PyTorch from driver failures and report malformed Windows storage configuration before opening the workspace.

两个平台均可在不下载增强模型的情况下直接生图、改图。修复不再清空原有环境，升级可复用保存的运行环境和存储位置。详见 [2.2.2 发布说明](docs/releases/v2.2.2.md)。

## 2.2.1 (2026-09-21)

- Fixed Windows Python discovery in freshly extracted downloads. The app checks an existing app environment, Python Launcher, registered installations and current/user/system PATH, then probes the actual interpreter.
- Dependency setup uses the same discovery logic. A working global Python environment can be used directly; repairs install into the app environment. Unsupported versions, 32-bit interpreters and missing dependencies have distinct results.
- Added Windows tests for fresh installs, existing environments, registration without PATH and incompatible interpreters.

修复 Windows 下载版将“尚未建立应用环境”误报为未安装 Python 的问题；检测与安装共用查找逻辑，并显示实际 Python 路径。Mac 功能无变化。

## 2.2.0 (2026-09-21)

- Added a Python-independent environment screen, required-check gate, in-app dependency repair and recovery after runtime failures on both platforms.
- Added a native Windows fallback for missing WebView2.
- Completed Chinese/English UI localization, including dynamic states and native menus, without rewriting user content.
- Added the official PE-T2I / PE-I2I profiles, separately verified downloads and sequential enhancer/diffusion execution.
- Switched the default to official 2K / 40 steps; added ratio inheritance, exact lettering, annotations/masks, negative prompts and serial batches.
- Preserved prompt provenance and per-image seeds; corrected reference-image area budgeting and removed upload downscaling.
- Added dependency-failure, localization, generation-contract and process-boundary checks.

两端加入应用内环境检测、🎉 通过状态和依赖修复，并补齐完整中英文界面。必需项通过后开放主界面；运行环境缺失时重新检测。

## 2.1.0 (2026-09-21)

First public source release containing both desktop platforms.

- Added ModelScope and Hugging Face selection before the first download, with persisted preferences and resumable transfers.
- Synchronized the Windows interface with Mac: animated task tray, red stop actions, a slightly taller in-conversation composer and previews that keep their aspect ratio.
- Included the flat black Q icon on both platforms.
- Added portable storage defaults, first-time dependency setup, bilingual documentation and release packaging.
- Preserved FP32 full-frame decoding and added 2K output presets. Windows PNG metadata now contains generation settings without application file paths.

首次公开源码版本同时提供 Mac 和 Windows。两端同步下载源选择和界面修复，补齐首次安装、图标、中英文说明与下载包。详见发布页的验证范围与已知限制。
