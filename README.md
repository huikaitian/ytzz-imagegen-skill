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
- Local file outputs under `output/imagegen/`
- No API keys stored in the skill or repository

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
