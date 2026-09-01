# KIE.ai Nodes Next Roadmap

## v0.3.0 — Individual Model Library

- [x] Remove `Any KIE API` from registered user-facing nodes.
- [x] Generate individual nodes from KIE's official API/model documentation.
- [x] Category → provider → model-family hierarchy.
- [x] Video / ByteDance / Seedance family.
- [x] LLM / Claude / Opus-Sonnet-Haiku-Fable family hierarchy.
- [x] Typed controls inferred from KIE request examples and parameter metadata.
- [x] Native IMAGE / VIDEO / AUDIO reference sockets.
- [x] Multiple native VIDEO/AUDIO reference inputs instead of URL JSON.
- [x] Larger prompt-centric model-node UI.
- [x] One-time API key with masked saved-key fingerprint.
- [x] Validate a replacement key before saving it.
- [x] Connected / invalid / unreachable status and credits feedback.
- [x] Automatic live model catalog refresh.
- [x] Preserve cached nodes when KIE docs are unavailable.
- [x] Query/path parameter discovery for direct APIs.
- [x] JSON, text and SSE response normalization.
- [x] Native image/video/audio outputs plus all result URLs.

## v0.3.x — Model polish passes

The live factory provides immediate coverage. Model polish passes will add conditional UI and purpose-built adapters where a provider has rules that cannot be represented elegantly by a flat request schema.

- Conditional Seedance mode UI: Text / First Frame / First+Last / Multimodal Reference.
- Kling element/reference builders and multi-shot UI.
- Wan reference/video-edit helpers.
- PixVerse transition/reference builders.
- Gemini Omni multimodal builders.
- OmniHuman detection/subject selection helpers.
- Suno custom/non-custom conditional controls and native multi-track outputs.
- ElevenLabs voice selection helpers.
- LLM tool-definition builder nodes.
- Better display of per-model character/time/file-size limits.

## v0.4 — Distribution and updates

- Publish public GitHub repository.
- Publish to Comfy Registry.
- Install/update directly through ComfyUI Manager.
- Signed/versioned release artifacts.
- Automated catalog snapshot CI to detect KIE API changes before users do.
- Regression fixtures for every documented KIE model family.

## Longer term

- Per-model examples and starter workflows.
- Favorites/recent models sidebar integration if Comfy frontend APIs allow it cleanly.
- Cost estimate / credit estimate before submission where KIE exposes reliable pricing metadata.
- Task queue dashboard.
- Batch/parallel generation orchestration.

