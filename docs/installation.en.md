# Installation and downloads

[简体中文](installation.zh-CN.md) | [Home](../README.en.md)

## Choose a package

Download the Windows x64 or Mac arm64 ZIP from [GitHub Releases](https://github.com/rigorhormist/QwenStudio/releases/latest) and extract the entire archive into a writable directory. Keep the Windows EXE with its accompanying folders. Source archives require a local build; platform ZIPs include the compiled desktop application.

Setup has three stages: download the desktop app, install Python dependencies, then download weights inside the app. Image weights occupy about 33.1 GB. The two optional enhancers add about 37.7 GB if you choose to download both. Chunk assembly temporarily uses extra space. Reserve at least 120 GB for a full installation; saved images require additional space.

## Windows

1. Extract the entire Windows ZIP and open `start.cmd` or `app/Qwen Studio.exe`. No setup script is required before opening the app.
2. Follow the environment check. If WebView2 is missing, its native fallback screen provides a download link and a retry button.
3. If needed, use Download Python to install 64-bit Python 3.10–3.13 (3.11 with Python Launcher is recommended). Select Install or repair dependencies. The app preserves working packages and prepares missing or damaged dependencies in a separate runtime under your data directory, with installation logs.
4. Select Open Qwen Studio when all required checks pass. If the GPU check fails, install or update the NVIDIA driver and check again.
5. Open Settings, select Download model and choose a source before generating an image.

The setup wrapper uses `ExecutionPolicy Bypass` for that PowerShell process only. It does not change the system execution policy. The release package includes the .NET 10 runtime; an SDK is unnecessary for normal use.

Python discovery first checks the last successful runtime saved in your data directory, then legacy app runtimes, Python Launcher, registered installations, installed Store Python and PATH. A newer ZIP can reuse the saved runtime even when extracted elsewhere. If Python is present but a package is missing, repair the package without reinstalling Python. Keep any older environment folder still used by the app; the check page shows its path.

For a CUDA 12.8 driver environment:

```powershell
.\setup.ps1 -Cuda cu128
```

To select an installed interpreter:

```powershell
.\setup.ps1 -Python 'C:\Python311\python.exe'
```

Refer to [PyTorch installation instructions](https://pytorch.org/get-started/previous-versions/) for CUDA builds and driver compatibility. Image inference on Windows requires NVIDIA CUDA; this release has no CPU, AMD or Intel GPU image backend.

## Mac

1. On an Apple Silicon Mac with macOS 14 or later, extract the ZIP and open `Qwen Studio.app`. You can move it to Applications first.
2. The environment screen checks each component. If Python is missing, use Download Python to install the python.org Python 3.11 universal2 build. Native arm64 Python 3.10–3.13 is supported.
3. Select Install or repair dependencies. Dependencies go into `~/Library/Application Support/Qwen Studio/runtime`; checks run again after installation.
4. Select Open Qwen Studio when all required checks pass, then choose a model download source in Settings.

The App has an ad-hoc signature and is not Apple-notarized. If macOS cannot verify the developer, check the source and SHA-256 checksum first, then use the opening option offered in Privacy & Security. There is no need to disable system security checks.

Setup reuses the saved runtime, managed runtime or legacy app environment before looking for compatible python.org and Homebrew installations. To select another interpreter:

```sh
QWEN_STUDIO_PYTHON_BOOTSTRAP=/path/to/python3 ./setup.command
```

The download includes a compiled App. Xcode Command Line Tools are only needed when building from source.

## In-app environment checks

Checks cover the OS, desktop display runtime, writable storage, Python, package imports and compatibility, the Qwen pipeline API, a tiny GPU operation and the downloader. Each passing item shows 🎉. Checks do not download weights, load the image model or generate images. Passing does not guarantee enough GPU memory for every image size.

First use requires selecting Open Qwen Studio. Later launches check again and enter automatically when ready. Missing dependencies or a stopped local service return to the check screen. Use Settings → Environment check to run checks manually after stopping active and queued work. If a task discovers a missing dependency, queued work stops; prompts and task results remain in their chats.

Ollama and the prompt enhancer interface are optional and do not block direct image generation. Download image weights after entering the app. Installer diagnostics retain their original text; application explanations and controls support both languages.

Advanced users can still run `setup.cmd` / `setup.command`. Windows defaults to CUDA 13.0. Use the command above for CUDA 12.8; repairs reuse a working CUDA installation. A CPU-only PyTorch build is identified separately from a missing GPU driver.

Environment checks validate only Qwen Studio and its dependency graph. Unrelated packages in a shared Python installation do not block entry. Independent import checks run concurrently; each child is bounded to 60 seconds and the desktop probe is capped at three minutes. Stop cancels checks or repairs, and the result and action buttons remain visible while scrolling. A healthy environment disables unnecessary repair.

## Model downloads and resuming

The first download requires an explicit source choice. ModelScope may be easier to reach from mainland China; choose Hugging Face when it is reliable on your network. The selection is stored locally and can be changed later.

Progress includes downloaded size, recent transfer speed and estimated time remaining. Verification and disk writes can make these estimates fluctuate. Restarting a download keeps completed chunks, including when switching sources. Source changes are disabled during an active download.

`backend/model-files.json` pins file sizes and SHA-256 hashes. Hugging Face URLs use a fixed commit; ModelScope URLs use file revisions. Model weights are excluded from release packages.

## Connect Ollama

Install and start [Ollama](https://ollama.com/download), then download a chat model suitable for your hardware through Ollama. Qwen Studio connects to `127.0.0.1:11434`. Choose the chat tab, then select an installed model.

Image inference is handled separately by Diffusers. Thinking controls follow capabilities reported by Ollama and are omitted for models that do not support them.

## Storage and existing models

| Platform | Default data directory | Default model directory |
| --- | --- | --- |
| Mac | `~/Library/Application Support/Qwen Studio` | `models/Qwen-Image-2.1` under the data directory |
| Windows | `%LOCALAPPDATA%\QwenStudio` | `models\Qwen-Image-2.1` under the data directory |

On Windows, copy `settings.example.json` to `settings.local.json` and set your directories. Backslashes in JSON must be escaped as `\\`. Download packages never contain or replace your local configuration. After a successful environment check, Windows remembers storage locations in `%LOCALAPPDATA%\QwenStudio\locations.json`. New packages reuse those model and conversation folders; app-local `settings.local.json` takes precedence.

Both platforms accept `QWEN_STUDIO_DATA`. Windows also accepts `QWEN_STUDIO_MODEL`; Mac accepts `QWEN_STUDIO_PYTHON` for a custom interpreter. Mac model storage follows the data directory. Apps started through Finder do not inherit temporary shell environment variables.

Existing weights must be a complete Diffusers directory matching the file manifest, including transformer, text_encoder, vae and tokenizer components. GGUF files, LoRA files and other Qwen Image versions cannot be substituted directly.

## Updates and removal

Close the app before updating and keep the data directory. On Windows, replace application files while preserving `.venv`, any legacy `runtime` directory, `runtime-path.json` and `settings.local.json`. On Mac, replace the App and keep the data directory. Both platforms remember successful runtime paths in the data directory. A repair activates a separate candidate only after its checks pass; a failed or cancelled repair leaves the current selection intact. Manual checks are also available in Settings.

Removing the application does not erase saved conversations or models. Back up images before deleting the data directory yourself. Mac Python dependencies also live there. Deleting a conversation removes its messages but leaves generated image files on disk.

## Verify an archive

Each release includes `SHA256SUMS.txt`. From the download directory:

```sh
# Mac
shasum -a 256 QwenStudio-2.2.2-macos-arm64.zip
```

```powershell
# Windows
Get-FileHash .\QwenStudio-2.2.2-windows-x64.zip -Algorithm SHA256
```

Compare the complete hash with the release checksum file. See the [Usage guide](usage.en.md) for troubleshooting.
