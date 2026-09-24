<p align="center"><img src="assets/AppIcon.png" width="112" alt="Qwen Studio 图标"></p>

# Qwen Studio

[English](README.en.md) | 简体中文

Qwen Studio 是为解决 Ollama 等平台暂不支持 Qwen Image 2.1 情况的替代交流平台。

在一个本地桌面窗口里生成图片、修改图片，也可以接入已有的 Ollama 模型讨论创意。图像由 Diffusers 运行 Qwen-Image-2.1生成。这个项目是独立社区应用，与 Qwen、Ollama 没有隶属关系。

![Qwen Studio 首页](docs/images/home.png)

*上图为共享界面的截图。Mac 使用 AppKit 和 WKWebView，Windows 使用 WinForms 和 WebView2。*

## 下载与开始使用

前往 [Releases](https://github.com/rigorhormist/QwenStudio/releases/latest) 下载对应平台的 ZIP。首次安装需要联网下载 Python 依赖，模型文件随后在应用中单独下载。

| 平台 | 下载包 | 首次使用 |
| --- | --- | --- |
| Windows x64 | [QwenStudio-2.2.3-windows-x64.exe](https://github.com/rigorhormist/QwenStudio/releases/download/v2.2.3/QwenStudio-2.2.3-windows-x64.exe) | 直接打开 EXE，在软件中选择 Python、依赖源并完成环境设置 |
| Mac Apple Silicon | [QwenStudio-2.2.3-macos-arm64.zip](https://github.com/rigorhormist/QwenStudio/releases/download/v2.2.3/QwenStudio-2.2.3-macos-arm64.zip) | 解压，打开 `Qwen Studio.app`，按环境检测页完成设置 |

安装包包含桌面程序，**不包含 Python、模型权重和 Ollama**。Windows 包自带 .NET 运行时；Mac 的 Python 依赖安装在应用数据目录中，完成安装后可以将 App 移入“应用程序”。当前发布包没有开发者证书签名或 Apple 公证。

完整步骤、校验方法和更新说明见 [安装与下载](docs/installation.zh-CN.md)。通过环境检测后，可以先启动 Ollama 使用普通聊天，无需先下载图像权重。

## 可以做什么

- 完整中文、英文与跟随系统，切换语言不改写用户输入或聊天记录。
- 首次启动及发现依赖缺失时显示环境检测页；通过的项目显示 🎉，必需项通过后进入应用。
- 在应用中安装或修复 Python 依赖；缺少 Python、WebView2 或显卡驱动时提供对应入口。
- 输入提示词生成图片，添加参考图继续编辑；支持透明背景请求。
- 调整图片尺寸、生成步数和随机种子，包括 2K 尺寸选项。
- 在 Ollama 模型之间切换，并按模型能力调整思考强度。
- 保存和搜索会话，浏览图片库，点开原图或另存为 PNG。
- 排队提交任务，查看生成预览，停止正在执行的任务。
- 我们提供ModelScope 或 Hugging Face下载源，并允许您自由选择。


<p align="center"><img src="docs/images/download-source.png" width="460" alt="首次下载时选择 ModelScope 或 Hugging Face"></p>

## 运行环境

| 项目 | 要求与说明 |
| --- | --- |
| Mac | Apple Silicon，macOS 14 或更新；通过 PyTorch MPS 运行 |
| Windows | Windows 10/11 x64，WebView2 Evergreen Runtime，支持所选 PyTorch CUDA 构建的 NVIDIA 显卡和驱动 |
| Python | 64 位 Python 3.10–3.13；首次安装脚本优先查找 3.11 |
| 模型空间 | 图像模型约 33.1 GB，两个增强模型各约 18.84 GB；分段下载合并、Python 依赖和生成结果还需要额外空间 |
| 内存 | 使用 CPU offload；需求随图片尺寸和任务变化，尚未测出通用最低配置 |
| 普通聊天 | 本机 Ollama，地址 `http://127.0.0.1:11434`，至少已下载一个聊天模型 |

Mac 开发环境为 48 GB 统一内存的 Apple M5 Pro。Windows 桌面已可编译；不同 NVIDIA 显卡的显存需求和生成速度仍需实机反馈。遇到内存不足时，先用 512 或 768 尺寸。

## 模型来源与参数

应用使用 [Qwen-Image-2.1 官方模型](https://github.com/QwenLM/Qwen-Image-2.1)，可从 [ModelScope](https://modelscope.cn/models/Qwen/Qwen-Image-2.1) 或 [Hugging Face](https://huggingface.co/Qwen/Qwen-Image-2.1) 下载。两个来源对应同一组固定版本的文件，下载完成后进行 SHA-256 校验。

步数和种子来自 Diffusers 的推理参数。步数控制去噪迭代次数；种子用来复现初始随机噪声。默认采用官方推荐的 40 步和 2048 × 2048。PE-T2I 和 PE-I2I 均为可选下载。缺少对应模型时会弹窗提醒，选择“直接生成”即可使用原始提示词；已下载且启用时才会运行增强。更详细的参数和显存说明见 [使用说明](docs/usage.zh-CN.md)。

图像解码使用原始 FP32 VAE 和完整画面解码，避免低精度、分块解码引入的色带和拼接痕迹。生成中的预览也从完整潜空间解码后再缩小。模型本身仍可能生成不符合提示词、文字有误或细节异常的图片。

## 本地数据

- Mac：`~/Library/Application Support/Qwen Studio`
- Windows：`%LOCALAPPDATA%\QwenStudio`

会话保存在 SQLite 中，图片放在 `images`，模型默认放在 `models/Qwen-Image-2.1`。Windows 可用 `settings.local.json` 指定其他磁盘；已有配置会保留。应用没有账户系统，也不包含遥测。安装依赖和下载模型会访问相应的软件源；普通聊天连接本机 Ollama。详见 [安全与隐私](SECURITY.md)。

## 从源码构建

```sh
git clone https://github.com/rigorhormist/QwenStudio.git
cd QwenStudio
```

Mac 需要 Xcode Command Line Tools；在 `macos` 目录运行 `./build.sh` 和 `./setup.command`。Windows 需要 .NET 10 SDK；在 `windows` 目录运行 `build.ps1`，生成 `app/Qwen Studio.exe`，环境设置全部在软件内完成。构建桌面程序不需要下载模型。

```text
macos/       AppKit 桌面外壳、MPS 后端和界面
windows/     WinForms 桌面外壳、CUDA 后端和界面
assets/      项目图标
docs/        中英文安装、使用和开发文档
scripts/     发布打包工具
```

贡献流程和检查命令见 [CONTRIBUTING.md](CONTRIBUTING.md)。界面文件在两个平台中保持一致，后端保留各自的进程和 GPU 处理方式。

## 官方生成能力

已接入生图与改图的官方 Prompt Enhancer、七种 2K 比例、参考图比例继承、圈选/涂抹/独立蒙版、精确文案、RGBA、反向提示词和批量生成。增强模型各约 18.84 GB，可按需在模型设置中分别下载。参见[完整配置与文字生成说明](docs/generation.zh-CN.md)，其中也列出了此次检查的范围和未实测的部分。

## 许可证与致谢

应用自有代码采用 [MIT License](LICENSE)。**模型权重不适用 MIT**，使用 Qwen-Image-2.1 须遵守上游 [Qwen Research License](LICENSE.model.txt)，其中包含非商业使用限制。发布包不分发模型权重。

本项目依赖 Qwen-Image-2.1、Diffusers、PyTorch、Transformers、Ollama 和 Microsoft WebView2。加号菜单的圆形排列与动画参考并改写自 [Ramotion/CircleMenu](https://github.com/Ramotion/circle-menu)，保留其 MIT 声明。详见 [第三方声明](THIRD_PARTY_NOTICES.md)。
