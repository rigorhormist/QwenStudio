# Official generation capabilities and settings

[简体中文](generation.zh-CN.md) | [Home](../README.en.md)

Qwen Studio 2.2.4 uses the Diffusers path for Qwen-Image-2.1, with the published interfaces, recommended settings and Prompt Enhancer profiles. The table separates model capabilities from app controls and hardware limits. Supporting an option does not mean it has been tested on every device.

## Available controls

| Capability | App behavior |
| --- | --- |
| Text to image | Image mode; defaults to 2048 × 2048 and 40 steps |
| Single and multiple reference editing | Upload images or continue editing a result; up to 10 references, labeled `<image1>`, `<image2>` in order |
| Circles, paint and separate masks | Open an image → Annotate areas to edit. Add a marked reference, or the original plus a black-and-white mask with white edit regions |
| Transparent generation and editing | The transparency switch uses the upstream RGBA prompt format; uploads, inference and PNG files preserve alpha |
| Official PE-T2I | Optional download; enabled text-only tasks use this enhancer when available |
| Official PE-I2I | Optional download; enabled tasks with references use this enhancer, with images before text in their original order |
| Canvas ratio | Use the enhancer's `wh_ratio` or `ratio_follow`, selected dimensions, or the first reference ratio |
| Exact wording | Enter literal copy in Text in the image. Quoted wording in the prompt is also preserved in its original language |
| Negative prompts and CFG | Advanced options; CFG defaults to 1. A negative prompt requires CFG above 1 |
| Multiple results | 1–4 images, generated serially to reduce peak memory, with consecutive seeds |
| Traceable output | Generation details retain original, enhanced and effective prompts, dimensions and seeds. PNG metadata records actual generation settings |
| Prefix KV cache | Explicitly enabled in the official pipeline |

Annotations and masks are model references rather than a pixel-level compositing constraint. Unmarked regions may still change. A separate mask counts toward the 10-reference limit. The app adds reference-number instructions to the unsent prompt for you to review.

## Official 2K sizes

| Ratio | Dimensions |
| --- | --- |
| 1:1 | 2048 × 2048 |
| 4:3 | 2400 × 1792 |
| 3:4 | 1792 × 2400 |
| 3:2 | 2528 × 1696 |
| 2:3 | 1696 × 2528 |
| 16:9 | 2752 × 1536 |
| 9:16 | 1536 × 2752 |

Automatic ratios use the selected pixel area as their budget. The 2K setting uses the sizes above; smaller options remain available for previews and limited memory. Reference ratios are matched within 32-pixel alignment and the app's dimension limits. Memory errors never silently reduce the selected resolution.

## Downloading and running Prompt Enhancer

Download PE-T2I and PE-I2I separately in Settings. Each is about 18.84 GB. Including the roughly 33.1 GB image model, the three models need about 70.8 GB, plus space for download chunks, assembly files and the Python runtime. Choose ModelScope or Hugging Face before the first download. Downloads pin revisions, verify SHA-256, resume interrupted transfers and display speed.

These are the official fine-tuned Qwen3.5-VL 9B checkpoints. The app does not substitute an Ollama chat model. It reads each checkpoint's own `system_prompt.txt`, enables thinking, supplies multimodal token types and uses the published sampling settings:

| Setting | PE-T2I | PE-I2I |
| --- | --- | --- |
| temperature | 1.0 | 1.0 |
| top_p / top_k / min_p | 0.95 / 20 / 0 | 0.95 / 20 / 0 |
| presence_penalty | 1.5 | 0 |
| max_new_tokens | 16256 | 24000 |
| Reference image pixel limit | No references | 1024 × 1024 pixel area per image |

Presence penalty applies only to generated tokens and differs from repetition penalty. An enhancement must contain a complete, valid result and a valid canvas choice. If enhancement fails or returns invalid output, the app continues with your original prompt and records a notice in Generation details. Missing weights show a reminder with a Generate directly option. You can also turn enhancement off in image parameters.

Enhancement and diffusion run in separate, sequential processes. Enhancer allocations are released before image weights load. Windows supports automatic CUDA/CPU placement for the enhancer; Mac uses MPS. Loading time and memory use, especially with long prompts, depend on the device.

## Garbled lettering: findings and limits

Earlier app versions defaulted to 768 × 768 without the official enhancer. This version defaults to 2K and adds a text/diagram preset, literal wording and official enhancement. Those changes do not guarantee correct lettering.

The pinned Diffusers version already includes the Qwen3-VL final RMSNorm compatibility fix, which matters for text rendering with Transformers 5. Environment checks now verify that interface too. Image prompts are not tokenizer-truncated. Reference images use an area-based budget and are no longer reduced to a 2048-pixel edge at upload. Original FP32 VAE weights and full-frame decoding remain in use to avoid tiled decoding seams and color artifacts.

For a request such as “a flowchart explaining World War II,” decide on short labels and enter them under Text in the image. Dense paragraphs remain difficult even at 2K. Review both historical facts and rendered lettering before sharing.

This update checks interfaces, settings, parsing, queues, cancellation and UI behavior without downloading enhancer weights or generating new test images. Windows NVIDIA inference and the actual PE output quality on either platform were not validated in this update.

## Sources and versions

- [Official model documentation](https://github.com/QwenLM/Qwen-Image-2.1)
- [Pinned official Prompt Enhancer profiles](https://github.com/QwenLM/Qwen-Image-2.1/tree/fb7ae1d1f9611cd91524d03c53c5246b36ac8577/prompt_rewrite)
- [PE-T2I](https://huggingface.co/Qwen/Qwen-Image-2.1-PE-T2I) / [PE-I2I](https://huggingface.co/Qwen/Qwen-Image-2.1-PE-I2I)
- [Pinned Diffusers implementation](https://github.com/huggingface/diffusers/tree/80c7ed262aeffbeb43ef13ae04baeb9b84515a69)

The desktop package does not bundle vLLM, SGLang, multi-GPU serving, quantization training or LoRA training workflows. Models and enhancer weights retain their upstream licenses; original app adapter code is covered by this repository's MIT license.
