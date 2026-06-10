# YTZZ Imagegen Skill

Codex skill for generating and editing raster images through the fixed YTZZ SubRouter gateway:

```text
https://ytzz.subrouter.ai/v1
```

The skill uses `gpt-image-2`, always requests `quality=high`, and defaults to 4K aspect-ratio presets.

## Features

- Fixed YTZZ gateway URL
- `gpt-image-2` image generation and edits
- High-quality-only requests
- 4K ratio presets from `1:1` through `3:1` and `1:3`
- Native Chinese in-image text rendering; no background-first text-overlay workflow required
- URL image responses by default for more reliable 4K transfers
- Automatic retries for retryable API failures such as `429`, `5xx`, and `524`
- Automatic retries for URL image downloads
- Mask-safe edit handling: the first image is not compressed when a mask is used
- Local file outputs under `output/imagegen/`
- No API keys stored in the skill or repository

## Optional Dependency

The skill uses only Python standard library for basic requests. Install Pillow for more reliable large image edits because it enables upload compression for reference images:

```powershell
python -m pip install pillow
```

## Install

Copy the skill folder into your Codex skills directory:

```powershell
Copy-Item -Recurse -Force ".\ytzz-imagegen" "$env:USERPROFILE\.codex\skills\ytzz-imagegen"
```

Then restart or refresh Codex so it can discover the skill.

## API Key

If you do not have a key, register or sign in at:

```text
https://ytzz.subrouter.ai
```

Create an API key there, then either give it to your agent for the current run or set it locally:

```powershell
[Environment]::SetEnvironmentVariable("YTZZ_SUBROUTER_API_KEY", "YOUR_KEY_HERE", "User")
```

Do not commit your API key. Do not paste it into prompts, docs, or generated files.

## Usage

Generate a 4K landscape image:

```powershell
python "$env:USERPROFILE\.codex\skills\ytzz-imagegen\scripts\ytzz_imagegen.py" generate `
  --ratio 16:9 `
  --prompt "A cinematic futuristic glass observatory above a quiet ocean at sunrise" `
  --out ".\output\imagegen\observatory.png"
```

Generate a 4K vertical image:

```powershell
python "$env:USERPROFILE\.codex\skills\ytzz-imagegen\scripts\ytzz_imagegen.py" generate `
  --ratio 9:16 `
  --prompt "A rain-slick neon alley with one warm lantern reflected in the pavement" `
  --out ".\output\imagegen\neon-alley.png"
```

Generate a complete Chinese poster directly:

```powershell
python "$env:USERPROFILE\.codex\skills\ytzz-imagegen\scripts\ytzz_imagegen.py" generate `
  --ratio 9:16 `
  --prompt "A cinematic rain-slick neon alley poster. Text (verbatim): \"深夜独醉\". Typography: large flamboyant Chinese neon calligraphy, wine-red and electric-cyan glow, integrated into the upper poster. Constraints: render exactly \"深夜独醉\"; no extra characters; no English; no pinyin; no watermark." `
  --out ".\output\imagegen\shen-ye-du-zui.jpg" `
  --output-format jpeg `
  --timeout 3600
```

For Chinese titles, signs, slogans, packaging copy, and decorative poster lettering, prompt the model to render the complete final image directly. Do not default to generating a blank/background image and adding text locally afterward unless the user explicitly asks for deterministic post-production text or editable text layers.

Stable 4K photo edit path:

```powershell
python "$env:USERPROFILE\.codex\skills\ytzz-imagegen\scripts\ytzz_imagegen.py" edit `
  --image ".\input\portrait.jpg" `
  --prompt-file ".\output\imagegen\portrait-prompt.txt" `
  --ratio 9:16 `
  --output-format jpeg `
  --response-format url `
  --api-retries 4 `
  --timeout 3600 `
  --out ".\output\imagegen\portrait-4k.jpg"
```

For large photographic edits, use normal gateway-synchronous mode first. The local agent/runtime may still run the command as a long-lived process and poll it; that is different from the gateway `--async` flag. The gateway async entry can hit a Cloudflare 524 timeout before it returns a task id, while large base64 responses can fail mid-transfer. URL responses plus JPEG output have proven more reliable for 4K deliverables.

When using `--mask`, keep the mask dimensions identical to the first input image. The script will avoid compressing that first image so the mask remains compatible.

Check connectivity:

```powershell
python "$env:USERPROFILE\.codex\skills\ytzz-imagegen\scripts\ytzz_imagegen.py" models --json
```

## 4K Ratio Presets

| Ratio | Size |
| --- | ---: |
| `1:1` | `2880x2880` |
| `5:4` | `3200x2560` |
| `4:5` | `2560x3200` |
| `4:3` | `3264x2448` |
| `3:4` | `2448x3264` |
| `3:2` | `3504x2336` |
| `2:3` | `2336x3504` |
| `16:10` | `3584x2240` |
| `10:16` | `2240x3584` |
| `16:9` | `3840x2160` |
| `9:16` | `2160x3840` |
| `21:9` | `3696x1584` |
| `9:21` | `1584x3696` |
| `2:1` | `3840x1920` |
| `1:2` | `1920x3840` |
| `3:1` | `3840x1280` |
| `1:3` | `1280x3840` |

## Security

This repository intentionally contains no API keys. The script reads keys from runtime input or local environment variables:

- `YTZZ_SUBROUTER_API_KEY`
- `SUBROUTER_API_KEY` as a compatibility fallback

If you accidentally committed a key in your own fork, revoke it immediately at the gateway and rotate it.

## License

MIT
