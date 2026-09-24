# 安装与下载

[English](installation.en.md) | [返回首页](../README.md)

## 选择下载包

从 [GitHub Releases](https://github.com/rigorhormist/QwenStudio/releases/latest) 下载 Windows x64 或 Mac arm64 的 ZIP，并完整解压到可写目录。不要只复制 Windows 的 EXE。源码压缩包用于自行构建；想直接打开桌面程序，请选名称包含平台的发布包。

安装分为三部分：下载桌面程序，安装 Python 依赖，在应用内下载模型。图像模型约 33.1 GB；两个增强模型均为可选下载，全部下载会额外占用约 37.7 GB。下载分段合并还需要临时空间；完整安装建议预留至少 120 GB，长期保存图片需另行增加。

## Windows

1. 完整解压 Windows ZIP，双击 `start.cmd` 或 `app/Qwen Studio.exe`。无需先运行依赖安装脚本。
2. 应用会显示环境检测页。缺少 WebView2 时，先使用原生检测页的下载入口安装，再点“重新检测”。
3. 若未安装 Python，使用“下载 Python”安装 64 位 Python 3.10–3.13（建议 3.11，启用 Python Launcher）。点“安装或修复依赖”，应用会保留可用依赖，在数据目录的独立环境中准备缺失或损坏的依赖，并显示安装日志。
4. 必需项目全部通过后，点“进入 Qwen Studio”。如 GPU 检查失败，先安装或更新 NVIDIA 驱动，再重新检测。
5. 首次生成图片前，在“模型设置”中点击“下载模型”，选择下载源。

应用优先查找保存在数据目录中的上次可用环境，再查找旧版应用环境、Python Launcher、系统安装登记、已安装的 Store Python 和 PATH。新版 ZIP 解压到其他目录后，也能复用已保存的环境。已安装 Python、但缺少依赖时，无需重装 Python。检测页会显示实际使用的解释器路径；请保留仍被引用的旧环境目录。

安装脚本只在该次 PowerShell 进程使用 `ExecutionPolicy Bypass`，不改系统执行策略。Windows 发布包自带 .NET 10 运行时，普通使用无需安装 SDK。

如果驱动环境需要 CUDA 12.8，使用：

```powershell
.\setup.ps1 -Cuda cu128
```

指定已安装的 Python：

```powershell
.\setup.ps1 -Python 'C:\Python311\python.exe'
```

PyTorch 的 CUDA 构建和驱动要求见 [官方安装说明](https://pytorch.org/get-started/previous-versions/)。应用仅为图像推理启用 CUDA，没有 Windows CPU、AMD 或 Intel GPU 图像后端。

## Mac

1. 在 Apple Silicon Mac（macOS 14 或更新）上解压 ZIP，打开 `Qwen Studio.app`。也可以先把 App 移入“应用程序”。
2. 环境检测页会逐项检查。若缺少 Python，使用“下载 Python”安装 python.org 的 Python 3.11 universal2；也支持原生 arm64 的 3.10–3.13。
3. 点“安装或修复依赖”。依赖安装到 `~/Library/Application Support/Qwen Studio/runtime`，安装结束后重新检测。
4. 必需项目全部通过后，点“进入 Qwen Studio”，在设置中选择模型下载源。

发布包使用本地临时签名，没有 Apple 公证。如果系统提示无法验证开发者，请先核对下载来源与 SHA-256，再按 macOS“隐私与安全性”页面提供的打开方式处理，不需要关闭系统安全检查。

安装脚本优先复用保存的环境、应用管理的环境或旧版应用环境，再寻找兼容的 python.org 和 Homebrew Python。也可指定解释器：

```sh
QWEN_STUDIO_PYTHON_BOOTSTRAP=/path/to/python3 ./setup.command
```

下载包已带编译好的 App，首次安装无需 Xcode。只有从源码构建时才需要 Xcode Command Line Tools。

## 应用内环境检测

检测包括系统、桌面显示组件、可写存储、Python、依赖导入与版本兼容性、Qwen 推理接口、GPU 基础运算和下载工具。每项通过后显示 🎉。检测不下载权重、不加载图像模型，也不生成测试图片；通过检测不代表显存足以完成任意尺寸。

首次使用需手动进入。以后启动仍会检查环境，通过后自动进入；依赖失败或本地服务退出会返回检测页。“模型设置 → 环境检测”可手动重查，正在执行或排队的任务需要先停止。缺失依赖造成的任务失败会停止后续排队任务，保留对话中的提示词和结果记录。

Ollama 和提示词增强接口均为可选项，缺少时不会阻挡直接生图或改图。模型权重在进入应用后单独下载。安装工具的原始诊断日志保留原文，应用说明与操作控件均支持中英文。

高级用户仍可运行包内 `setup.cmd` / `setup.command`。Windows 默认采用 CUDA 13.0；需要 CUDA 12.8 时使用下方指定方式，修复会复用可用的 CUDA 环境，并区分 CPU 版 PyTorch 与显卡驱动缺失。

环境检测只检查 Qwen Studio 及其依赖，不会因为同一 Python 中其他软件的包冲突而阻挡使用。独立导入检查并行执行，单项最多等待 60 秒，桌面依赖检查最多等待三分钟。可以随时停止检测或修复；滚动时结果和操作按钮保持可见，环境正常时不再提供重复安装。修复只有通过检查后才切换到新环境，失败或取消会保留原有选择。

## 模型下载与断点续传

首次点击“下载模型”时不会自动替你决定来源。ModelScope 通常更适合中国大陆网络，Hugging Face 适用于能够稳定访问它的网络。选择保存在本地，之后可以在设置中更改。

下载时会显示已完成体积、速度和预计剩余时间。估算基于最近的传输速度，校验与磁盘写入期间数值可能波动。中断后重新点击下载会保留已有分段；切换来源也会保留分段。正在下载时不能切换来源。

`backend/model-files.json` 固定文件大小和 SHA-256；Hugging Face 固定到指定提交，ModelScope 使用文件版本。发布包不含模型权重。

## 接入 Ollama

安装并启动 [Ollama](https://ollama.com/download)，然后先在 Ollama 下载一个适合自己设备的聊天模型。应用连接固定的本机端口 `127.0.0.1:11434`。在首页选择“对话”，从模型列表选择已安装模型即可。

Ollama 不参与本应用的图像推理。思考强度控件根据 Ollama 返回的模型能力显示；模型不支持时不会强行发送该参数。

## 数据目录和已有模型

| 平台 | 默认数据目录 | 默认模型目录 |
| --- | --- | --- |
| Mac | `~/Library/Application Support/Qwen Studio` | 数据目录下 `models/Qwen-Image-2.1` |
| Windows | `%LOCALAPPDATA%\QwenStudio` | 数据目录下 `models\Qwen-Image-2.1` |

Windows 可复制 `settings.example.json` 为 `settings.local.json`，填写自己的目录。JSON 中的反斜杠必须写成 `\\`。原有用户的本地配置不会被下载包覆盖。Windows 通过环境检测后还会把存储位置记入 `%LOCALAPPDATA%\QwenStudio\locations.json`，让后续下载包沿用原来的模型和会话目录；当前目录的 `settings.local.json` 优先。

两端均支持 `QWEN_STUDIO_DATA` 环境变量。Windows 另支持 `QWEN_STUDIO_MODEL`；Mac 自定义解释器使用 `QWEN_STUDIO_PYTHON`。Mac 的模型目录跟随数据目录。通过 Finder 启动 App 时不会继承终端里临时设置的环境变量。

已有模型必须是与应用文件清单匹配的完整 Diffusers 目录，包含 transformer、text_encoder、vae、tokenizer 等组件。GGUF、LoRA 或其他 Qwen Image 版本不能直接放进去替用。

## 更新与卸载

更新前关闭应用，保留数据目录。Windows 可覆盖程序和源码文件，同时保留 `.venv`、旧版 `runtime` 目录、`runtime-path.json` 和 `settings.local.json`。通过检测的运行环境路径会保存在数据目录中，后续解压到其他目录也能复用。Mac 替换 App 后会自动检测环境；也可在设置中重新检测。不要在任务执行中覆盖程序。

卸载程序不会自动删除会话和模型。需要清理时，先备份所需图片，再自行删除数据目录；Mac 的 Python 运行环境也位于这个目录。删除会话只删除对应聊天记录，生成的图片文件仍保留。

## 校验下载包

发布页面提供 `SHA256SUMS.txt`。在下载目录执行：

```sh
# Mac
shasum -a 256 QwenStudio-2.2.2-macos-arm64.zip
```

```powershell
# Windows
Get-FileHash .\QwenStudio-2.2.2-windows-x64.zip -Algorithm SHA256
```

将结果与发布页的校验文件逐字比较。常见错误处理见 [使用说明](usage.zh-CN.md)。
