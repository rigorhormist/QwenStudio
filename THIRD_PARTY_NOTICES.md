# Third-party notices / 第三方声明

The MIT license in this repository covers original application code. Dependencies, model weights and adapted components retain their own terms. / 本仓库 MIT 许可适用于应用自有代码，依赖、权重和改写组件保留各自许可。

| Component | Use | Upstream license or terms |
| --- | --- | --- |
| [Qwen-Image-2.1](https://github.com/QwenLM/Qwen-Image-2.1) | Separately downloaded image model | [Qwen Research License](LICENSE.model.txt), non-commercial restrictions |
| [PE-T2I](https://huggingface.co/Qwen/Qwen-Image-2.1-PE-T2I) / [PE-I2I](https://huggingface.co/Qwen/Qwen-Image-2.1-PE-I2I) | Separately downloaded official prompt enhancers; original app adapter follows published profiles | Checkpoint license files, downloaded with the weights |
| [Diffusers](https://github.com/huggingface/diffusers) | Image inference pipeline | Apache-2.0 |
| [Transformers](https://github.com/huggingface/transformers) | Text encoder | Apache-2.0 |
| [Accelerate](https://github.com/huggingface/accelerate) | CPU/GPU offload | Apache-2.0 |
| [PyTorch](https://github.com/pytorch/pytorch) | Tensor runtime | BSD-style license and bundled dependency notices |
| [Pillow](https://github.com/python-pillow/Pillow) | Image I/O | MIT-CMU and bundled dependency notices |
| [psutil](https://github.com/giampaolo/psutil) | Process cleanup | BSD-3-Clause |
| [filelock](https://github.com/tox-dev/filelock) | Windows download lock | Unlicense |
| [Ollama](https://github.com/ollama/ollama) | Separately installed chat service | MIT; downloaded chat models have their own licenses |
| [WebView2](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) | Windows embedded browser | Microsoft WebView2 SDK and Runtime terms |
| [.NET](https://github.com/dotnet/runtime) | Windows desktop runtime | MIT and included third-party notices |
| [Ramotion/CircleMenu](https://github.com/Ramotion/circle-menu) | Circular geometry and animation ported to JavaScript | [MIT notice](windows/web/CIRCLE_MENU_LICENSE.txt) |

CircleMenu was adapted for a desktop web view: the actions, positioning, keyboard behavior and reduced-motion handling are application-specific. The original Swift library is not linked into the app.

The Q icon was created for this project. It is not an upstream Qwen or Ollama logo. Project naming describes compatibility and does not imply endorsement. The upstream model license separately restricts use of Qwen names for derivative products; review its terms before redistributing model-derived products.

Release packages include available .NET and WebView2 notices. The standalone Windows EXE embeds these notices alongside its application resources. Python packages are installed separately by the in-app environment installer and carry their own license files. See each upstream project for the full terms.
