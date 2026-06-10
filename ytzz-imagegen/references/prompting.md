# Prompting Notes

Use a production-oriented image brief, not a vague sentence, unless the user already gave a detailed prompt.

## Structure

Order the prompt as:

1. intended use
2. scene or backdrop
3. subject
4. style or medium
5. composition and framing
6. lighting and materials
7. exact text, if any
8. constraints and avoid list

## Specificity

- If the user is specific, preserve their choices and only normalize the prompt.
- If the user is generic, add practical details that improve the output: composition, framing, polish level, and intended use.
- Do not invent unrelated characters, objects, brands, slogans, or story beats.

## Edits

For edits, label inputs by role:

- `Image 1: edit target`
- `Image 2: style reference`
- `Image 3: object to composite`

Repeat invariants in every edit prompt:

```text
Change only <target change>. Keep <identity/product/layout/background/etc> unchanged.
```

## Text

For in-image text:

- quote exact copy
- state typography and placement
- require verbatim rendering
- generate the complete image with the text rendered natively by `gpt-image-2`
- do not default to generating a background first and adding text locally afterward
- use local text overlay only if the user explicitly asks for editable/deterministic typography or model retries fail
- for Chinese text, require no extra characters, no English substitutions, no pinyin, and no watermark
- use `quality=high`

Chinese prompt pattern:

```text
Text (verbatim): "深夜独醉"
Typography: large flamboyant Chinese lettering, neon calligraphy style, glowing wine-red and electric-cyan strokes, integrated into the upper part of the poster.
Constraints: render the Chinese text exactly as "深夜独醉"; no extra characters; no English; no pinyin; no watermark.
```

## Transparent Cutouts

Use a flat chroma-key background plus local removal for this `gpt-image-2` workflow. Ask before switching to any other model or provider for true native transparency.

Default prompt block:

```text
Create the requested subject on a perfectly flat solid #00ff00 chroma-key background for background removal.
The background must be one uniform color with no shadows, gradients, texture, reflections, floor plane, or lighting variation.
Keep the subject fully separated from the background with crisp edges and generous padding.
Do not use #00ff00 anywhere in the subject.
No cast shadow, no contact shadow, no reflection, no watermark, and no text unless explicitly requested.
```
