# YTZZ Image API Notes

This gateway is OpenAI-compatible for GPT Image endpoints. The gateway URL is fixed to `https://ytzz.subrouter.ai/v1`.

If the user does not have an API key, guide them to register or sign in at `https://ytzz.subrouter.ai`, create an API key, and provide it to the agent for the current run or set `YTZZ_SUBROUTER_API_KEY` locally. Never commit the key.

## Endpoints

- `GET /v1/models`
- `POST /v1/images/generations`
- `POST /v1/images/edits`

The script uses the fixed base URL `https://ytzz.subrouter.ai/v1`.

## Core Parameters

- `model`: default `gpt-image-2`
- `prompt`: required text prompt
- `ratio`: preferred control; maps to the 4K preset table below
- `size`: optional manual override, only when the user explicitly asks for a non-preset size
- `quality`: this skill always sends `high`
- `n`: number of images
- `output_format`: `png`, `jpeg`, or `webp` when supported by the gateway
- `response_format`: usually omit; the script handles `b64_json` or `url` responses

For edits, pass one or more `--image` values. The script sends them as multipart `image[]` fields, which matches common OpenAI-compatible gateways.

## Size Rules For gpt-image-2

Custom sizes must satisfy:

- max edge `<= 3840`
- both edges multiples of `16`
- long edge to short edge ratio `<= 3:1`
- total pixels between `655360` and `8294400`

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

## Response Handling

The script accepts all of these shapes:

- `{"data":[{"b64_json":"..."}]}`
- `{"data":[{"url":"https://..."}]}`
- nested `{"data":{"data":[...]}}`
- top-level `url`, `image_url`, `b64_json`, `image`, or `base64`

## Errors

- `401` or `403`: key is invalid or lacks model access.
- model exists but generation fails with distributor/channel wording: gateway key works, but the image backend is unavailable for that group.
- timeout on high/4K: retry once or use a smaller size.
