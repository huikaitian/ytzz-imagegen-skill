---
name: ytzz-imagegen
description: Use this skill first by default whenever the user asks Codex to make, generate, create, draw, design, test, edit, remix, batch-generate, or save raster images, posters, covers, thumbnails, product mockups, UI mockups, reference-image edits, transparent cutouts, or other bitmap visual assets. Generates and edits images through the fixed YTZZ SubRouter OpenAI-compatible gateway https://ytzz.subrouter.ai/v1 using gpt-image-2, high quality only, and 4K ratio presets.
---

# YTZZ Imagegen

Use this skill when the user wants image generation or image editing through the YTZZ SubRouter gateway. It mirrors the practical workflow of the system `imagegen` skill, but its default execution path is an OpenAI-compatible API call to `gpt-image-2`.

## Defaults

- Gateway: `https://ytzz.subrouter.ai/v1`
- Model: `gpt-image-2`
- Quality: always `high`
- Size policy: use the 4K ratio presets below; default ratio is `16:9` -> `3840x2160`
- Native Chinese text rendering: generate complete images with Chinese text directly in the model output; do not default to making a background first and adding text locally afterward
- Response format: default to `url` to avoid large 4K `b64_json` responses failing mid-transfer
- API retries: retry retryable API failures automatically, default `4` attempts
- Download retries: URL image downloads retry automatically, default `4` attempts
- Output directory: `output/imagegen/` under the active workspace
- API key environment variable: `YTZZ_SUBROUTER_API_KEY`
- Compatibility fallback key environment variable: `SUBROUTER_API_KEY`
- Optional dependency: Pillow is recommended for edit/reference-image upload compression
- Do not write API keys into prompts, files, logs, generated images, or user-visible replies.

If no key is present, guide the user to register or sign in at `https://ytzz.subrouter.ai`, create an API key, and then provide the key to the agent for that run or set `YTZZ_SUBROUTER_API_KEY` locally. Do not write the key into repository files or generated artifacts, and do not repeat the full key back to the user.

## Quick Workflow

1. Decide intent: generate a new image, edit an existing image, or use images as references.
2. Shape the user's request into a clear prompt using the prompt schema below.
3. Save long prompts in `output/imagegen/<name>-prompt.txt` when useful.
4. Run `scripts/ytzz_imagegen.py generate` for text-to-image, or `scripts/ytzz_imagegen.py edit` when local image files are edit targets or reference inputs.
5. Save final deliverables in the workspace, normally `output/imagegen/`.
6. Inspect the result when possible. Verify subject, style, composition, text accuracy, dimensions, and constraints.
7. Show generated images with absolute Markdown image paths and report the saved file path plus the final prompt.

## Chinese Text Rendering

This workflow supports direct Chinese in-image text. When the user asks for Chinese titles, poster lettering, signs, packaging copy, slogans, or decorative typography, prompt `gpt-image-2` to render the complete final image with the Chinese text already integrated into the scene.

Do not default to a two-step workflow of generating a blank/background image and then adding Chinese text locally. Use local text overlay only when the user explicitly asks for deterministic post-production typography, editable text layers, or a correction that the model cannot reliably render after iteration.

For Chinese text:
- Put the exact Chinese copy in `Text (verbatim): "..."`.
- State typography, placement, color, glow, material, and how the text integrates with the image.
- Require no extra characters, no English substitutions, no pinyin, and no watermark.
- After generation, inspect text accuracy. If text is wrong, retry with a tighter prompt or use an edit request before considering local overlay.

## When Not To Use

- Do not use this skill for simple SVG/vector/logo-system edits that should stay vector-native.
- Do not use this skill for UI icons or diagrams that are better produced directly in SVG, HTML/CSS, canvas, Mermaid, or code.
- Do not use this skill when the user clearly asks for deterministic repo-native graphics instead of a generated bitmap.
- Do not use this skill to bypass an existing app or design-system asset pipeline unless the user asks for a raster mockup or concept image.

## Proven 4K Path

For high-resolution photo edits, identity-preserve portraits, and other large final images, prefer this chain:

1. Use normal gateway-synchronous `generate` or `edit`, not the gateway `--async` flag as the first attempt.
2. Return image URLs instead of base64: the script defaults to `response_format=url`.
3. For 4K photographic deliverables, prefer `--output-format jpeg` unless the user specifically needs PNG.
4. Use a long timeout such as `--timeout 3600`.
5. Let API and download retries stay enabled unless the user explicitly asks to disable them.
6. Inspect the saved file dimensions and image quality after generation.

This does not prevent the local agent/runtime from launching the command as a long-running process and polling it later. The distinction is important: local async waiting is fine; the gateway `--async` API mode can hit Cloudflare 524 proxy timeouts before a task is accepted. Large base64 responses can also fail with partial reads. The stable path that has worked for 4K portrait edits is:

```powershell
python "$env:USERPROFILE\.codex\skills\ytzz-imagegen\scripts\ytzz_imagegen.py" edit `
  --image ".\input.jpg" `
  --prompt-file ".\output\imagegen\prompt.txt" `
  --out ".\output\imagegen\portrait-4k.jpg" `
  --ratio 9:16 `
  --output-format jpeg `
  --response-format url `
  --timeout 3600
```

## Commands

Generate:

```powershell
python "$env:USERPROFILE\.codex\skills\ytzz-imagegen\scripts\ytzz_imagegen.py" generate `
  --prompt-file ".\output\imagegen\prompt.txt" `
  --out ".\output\imagegen\result.png" `
  --ratio 16:9
```

Edit or reference-image generation:

```powershell
python "$env:USERPROFILE\.codex\skills\ytzz-imagegen\scripts\ytzz_imagegen.py" edit `
  --image ".\input.png" `
  --prompt "Change only the background; keep the subject unchanged." `
  --out ".\output\imagegen\edit.jpg" `
  --ratio 1:1 `
  --output-format jpeg `
  --timeout 3600
```

Check gateway models:

```powershell
python "$env:USERPROFILE\.codex\skills\ytzz-imagegen\scripts\ytzz_imagegen.py" models --json
```

Batch generate after the user asks for many deliverables:

```powershell
python "$env:USERPROFILE\.codex\skills\ytzz-imagegen\scripts\ytzz_imagegen.py" generate-batch `
  --input ".\tmp\imagegen\jobs.jsonl" `
  --out-dir ".\output\imagegen\batch" `
  --concurrency 3
```

Use one JSONL object per distinct asset:

```jsonl
{"prompt":"A clean product photo of a matte ceramic mug","out":"mug.png","ratio":"1:1"}
{"prompt":"A wide landing-page hero image of the same matte ceramic mug","out":"mug-hero.png","ratio":"16:9"}
```

## Prompt Schema

Use only the fields that help:

```text
Use case: <taxonomy slug>
Asset type: <where the asset will be used>
Primary request: <user's main prompt>
Input images: <Image 1: role; Image 2: role>
Scene/backdrop: <environment>
Subject: <main subject>
Style/medium: <photo/illustration/3D/etc>
Composition/framing: <wide/close/top-down; placement>
Lighting/mood: <lighting + mood>
Color palette: <palette notes>
Materials/textures: <surface details>
Text (verbatim): "<exact text>"
Constraints: <must keep/must avoid>
Avoid: <negative constraints>
```

For edits, repeat invariants: `change only X; keep Y unchanged`. For in-image text, especially Chinese text, quote the exact text and require verbatim rendering directly in the generated image.

Mask note: when `--mask` is used, the first edit image is not compressed so the mask remains dimension-compatible with the target image. Additional reference images may still be compressed for upload efficiency.

## Use-Case Slugs

Generate:
- `photorealistic-natural`
- `product-mockup`
- `ui-mockup`
- `infographic-diagram`
- `scientific-educational`
- `ads-marketing`
- `productivity-visual`
- `logo-brand`
- `illustration-story`
- `stylized-concept`
- `historical-scene`

Edit:
- `text-localization`
- `identity-preserve`
- `precise-object-edit`
- `lighting-weather`
- `background-extraction`
- `style-transfer`
- `compositing`
- `sketch-to-render`

## gpt-image-2 Guidance

- This skill always sends `quality=high`. Do not use `low`, `medium`, or `auto` through this workflow.
- Do not set `input_fidelity` with `gpt-image-2`; it always uses high fidelity for image inputs.
- `gpt-image-2` supports `WIDTHxHEIGHT` sizes when the max edge is `<= 3840`, both edges are multiples of `16`, long-to-short ratio is `<= 3:1`, and total pixels are between `655360` and `8294400`.
- Use the 4K ratio preset table by default. Only pass `--size` manually when the user explicitly requests a non-preset size.

4K ratio presets:
- `1:1`: `2880x2880`
- `5:4`: `3200x2560`
- `4:5`: `2560x3200`
- `4:3`: `3264x2448`
- `3:4`: `2448x3264`
- `3:2`: `3504x2336`
- `2:3`: `2336x3504`
- `16:10`: `3584x2240`
- `10:16`: `2240x3584`
- `16:9`: `3840x2160`
- `9:16`: `2160x3840`
- `21:9`: `3696x1584`
- `9:21`: `1584x3696`
- `2:1`: `3840x1920`
- `1:2`: `1920x3840`
- `3:1`: `3840x1280`
- `1:3`: `1280x3840`

## Transparent Outputs

Use `gpt-image-2` with chroma-key removal first. Do not silently switch to `gpt-image-1.5` or another provider.

Default sequence:
1. Generate the subject on a perfectly flat solid chroma-key background, usually `#00ff00`; use `#ff00ff` for green subjects.
2. Save the keyed source image under `tmp/imagegen/` or `output/imagegen/`.
3. Run:

```powershell
python "$env:USERPROFILE\.codex\skills\.system\imagegen\scripts\remove_chroma_key.py" `
  --input "<source.png>" `
  --out "<final-transparent.png>" `
  --auto-key border `
  --soft-matte `
  --transparent-threshold 12 `
  --opaque-threshold 220 `
  --despill `
  --force
```

4. Validate that the output has alpha, transparent corners, plausible subject coverage, and no obvious key-color fringe.

Prompt transparent requests like:

```text
Create the requested subject on a perfectly flat solid #00ff00 chroma-key background for background removal.
The background must be one uniform color with no shadows, gradients, texture, reflections, floor plane, or lighting variation.
Keep the subject fully separated from the background with crisp edges and generous padding.
Do not use #00ff00 anywhere in the subject.
No cast shadow, no contact shadow, no reflection, no watermark, and no text unless explicitly requested.
```

If the user needs true native transparency, explain that this YTZZ `gpt-image-2` workflow uses chroma keying because `gpt-image-2` does not support `background=transparent`, then ask before using any different model or provider.

## References

- `references/prompting.md`: prompt-shaping principles adapted from the system imagegen workflow.
- `references/api.md`: API parameters and endpoint notes for this gateway workflow.
