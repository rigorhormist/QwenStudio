# 安装与下载

[English](installation.en.md) | [返回首页](../README.md)

## 选择下载包

从 [GitHub Releases](https://github.com/rigorhormist/QwenStudio/releases/latest) 下载 Windows x64 的 EXE 或 Mac arm64 的 ZIP。Windows 可直接运行单个 EXE；ZIP 版本另外附带使用文档。源码包用于自行构建。

安装分为三部分：下载桌面程序，安装 Python 依赖，在应用内下载模型。图像模型约 33.1 GB；两个增强模型均为可选下载，全部下载会额外占用约 37.7 GB。下载分段合并还需要临时空间；完整安装建议预留至少 120 GB，长期保存图片需另行增加。

## Windows

1. 双击 `QwenStudio-2.2.4-windows-x64.exe`。无需运行 setup 或 start 脚本，也无需安装 .NET SDK。
2. 应用会在本地数据目录下展开内置界面和后端，随后显示环境检测页。缺少 WebView2 时，使用原生检测页的下载入口安装，再点“重新检测”。
3. 在“Python 解释器”中选择版本。列表同时显示路径与虚拟环境标记；“选择其他…”可指定未被扫描到的 `python.exe`。不兼容的版本会显示在列表中，但不能用于安装。若未安装 Python，先通过“下载 Python”安装 64 位 3.10–3.13（建议 3.11）。
4. 选择“依赖下载源”和新装 CUDA 版本，再点“安装或修复依赖”。已有可用的 CUDA 会复用；修复在独立环境中进行。安装页显示当前步骤、文件下载量、可获取的速度和日志。
5. 必需项目通过后进入软件，在模型设置中选择模型下载源。

应用扫描已保存的运行环境、旧版目录、Python Launcher、注册表、Store Python、PATH，以及常见 Conda 和 pyenv 目录。选择新解释器会重新检测其中的依赖；只有通过检测的环境才会被记住并用于启动服务。多个版本不会再被自动合并成一个选项。

EXE 自带 .NET 运行时、界面、后端及依赖安装逻辑，不包含 Python、WebView2、GPU 驱动、Ollama 或模型权重。内置资源位于 `%LOCALAPPDATA%\QwenStudio\application`，模型和会话仍保存在原数据目录。
PyTorch 的 CUDA 构建和驱动要求见 [官方安装说明](https://pytorch.org/get-started/previous-versions/)。应用仅为图像推理启用 CUDA，没有 Windows CPU、AMD 或 Intel GPU 图像后端。

## Mac

1. 在 Apple Silicon Mac（macOS 14 或更新）上解压 ZIP，打开 `Qwen Studio.app`。也可以先把 App 移入“应用程序”。
2. 环境检测页会逐项检查。若缺少 Python，使用“下载 Python”安装 python.org 的 Python 3.11 universal2；也支持原生 arm64 的 3.10–3.13。
3. 选择依赖下载目录和下载源，再点“安装或修复依赖”。默认目录为 `~/Library/Application Support/Qwen Studio/runtime`，安装结束后重新检测。
4. 必需项目全部通过后，点“进入 Qwen Studio”，在设置中选择模型下载源。

发布包使用本地临时签名，没有 Apple 公证。如果系统提示无法验证开发者，请先核对下载来源与 SHA-256，再按 macOS“隐私与安全性”页面提供的打开方式处理，不需要关闭系统安全检查。

环境页支持选择 Python 版本和路径，也可手动定位解释器。程序会搜索已保存环境、python.org、Homebrew、PATH 以及常见 Conda 和 pyenv 安装。开发者从源码启动时仍可使用：

```sh
QWEN_STUDIO_PYTHON_BOOTSTRAP=/path/to/python3 ./setup.command
```

下载包已带编译好的 App，首次安装无需 Xcode。只有从源码构建时才需要 Xcode Command Line Tools。

## 应用内环境检测

检测包括系统、桌面显示组件、可写存储、Python、依赖导入与版本兼容性、Qwen 推理接口、GPU 基础运算和下载工具。每项通过后显示 🎉。检测不下载权重、不加载图像模型，也不生成测试图片；通过检测不代表显存足以完成任意尺寸。

首次使用需手动进入。以后启动仍会检查环境，通过后自动进入；依赖失败或本地服务退出会返回检测页。“模型设置 → 环境检测”可手动重查，正在执行或排队的任务需要先停止。缺失依赖造成的任务失败会停止后续排队任务，保留对话中的提示词和结果记录。

Ollama 和提示词增强接口均为可选项，缺少时不会阻挡直接生图或改图。模型权重在进入应用后单独下载。安装工具的原始诊断日志保留原文，应用说明与操作控件均支持中英文。

两个平台均可选择官方 PyPI 或[清华大学镜像](https://mirrors.tuna.tsinghua.edu.cn/help/pypi/)，软件会记住选择。该设置用于 Python 包；PyTorch CUDA 包仍使用 PyTorch 官方索引，固定版本的 Diffusers 源码仍从 GitHub 下载。Windows 可在页面选择 CUDA 13.0 或 12.8，这只影响需要新装的 CUDA 环境。

下载条显示当前文件的真实字节进度，不代表全部依赖的总进度；解析、校验和安装期间显示当前步骤。旧版 pip 会先在新环境内更新，更新期间可查看实时日志。安装中可停止，换源后重新开始时保留 pip 已有缓存。

环境检测只检查 Qwen Studio 及其依赖，不会因为同一 Python 中其他软件的包冲突而阻挡使用。独立导入检查并行执行，单项最多等待 60 秒，桌面依赖检查最多等待三分钟。可以随时停止检测或修复；滚动时结果和操作按钮保持可见，环境正常时不再提供重复安装。修复只有通过检查后才切换到新环境，失败或取消会保留原有选择。

## 选择下载目录或使用已有文件

两个平台都有相同入口：

- **模型设置**：主模型和两个可选增强模型各有“选择下载目录”“使用已有模型”。选择下载父目录时，应用会为每个模型使用独立子目录；选择模型文件夹本身时可保留其中的下载分段。
- **环境检测**：“依赖下载目录”决定新环境、pip 缓存和安装临时文件的位置。“使用已有环境目录”可选择 venv、Conda 环境或已有 Python 安装目录。也可通过“选择其他…”直接选择 Python 解释器文件。

已有模型可以是完整模型目录、包含模型的父目录或 Hugging Face 缓存目录。存在多个缓存版本时，请选择具体的 `snapshots/<revision>` 文件夹。应用按固定文件清单进行本地检查；首次导入未校验的模型会读取文件计算 SHA-256，页面显示进度并允许停止。检查通过后直接使用原文件，不复制权重，也不下载模型。只读模型目录也可使用，检查记录保存在应用数据目录。

如果目录只下载了一部分，请使用“选择下载目录”，选中该模型目录后继续下载。其他版本、GGUF 或 LoRA 不符合本应用的完整模型清单，不能直接替用。

切换下载位置不会移动或删除原文件，也不会移动会话和图片。目录设置会在更新后保留。模型任务、下载或文件检查进行时需先停止，再切换目录。外置硬盘断开时会提示目录不可用；连接原硬盘或重新选择目录后再继续。已有可用的 Python 包会复用，修复时只在所选位置创建独立环境。

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

Windows 可在 EXE 旁创建 `settings.local.json`，使用 `{"data":"D:\\QwenStudioData","model":"D:\\Qwen-Image-2.1"}` 指定目录。JSON 中的反斜杠必须写成 `\\`。原有用户的本地配置不会被下载包覆盖。Windows 通过环境检测后还会把存储位置记入 `%LOCALAPPDATA%\QwenStudio\locations.json`，让后续下载包沿用原来的模型和会话目录；当前目录的 `settings.local.json` 优先于旧版位置记录；在应用中另选的模型目录优先于两者。

两端均支持 `QWEN_STUDIO_DATA`、`QWEN_STUDIO_MODEL` 和 `QWEN_STUDIO_PYTHON` 环境变量。显式指定模型或解释器时，对应的界面选择会锁定。通过 Finder 启动 App 时不会继承终端里临时设置的环境变量。

已有模型必须是与应用文件清单匹配的完整 Diffusers 目录，包含 transformer、text_encoder、vae、tokenizer 等组件。GGUF、LoRA 或其他 Qwen Image 版本不能直接放进去替用。

## 更新与卸载

更新前关闭应用，保留数据目录。Windows 替换 EXE 即可，同时保留 `.venv`、旧版 `runtime` 目录、`runtime-path.json` 和 `settings.local.json`。通过检测的运行环境路径会保存在数据目录中，后续解压到其他目录也能复用。Mac 替换 App 后会自动检测环境；也可在设置中重新检测。不要在任务执行中覆盖程序。

卸载程序不会自动删除会话和模型。需要清理时，先备份所需图片，再自行删除数据目录；自选的模型和依赖目录需单独保留或清理。删除会话只删除对应聊天记录，生成的图片文件仍保留。

## 校验下载包

发布页面提供 `SHA256SUMS.txt`。在下载目录执行：

```sh
# Mac
shasum -a 256 QwenStudio-2.2.4-macos-arm64.zip
```

```powershell
# Windows
Get-FileHash .\QwenStudio-2.2.4-windows-x64.zip -Algorithm SHA256
```

将结果与发布页的校验文件逐字比较。常见错误处理见 [使用说明](usage.zh-CN.md)。
