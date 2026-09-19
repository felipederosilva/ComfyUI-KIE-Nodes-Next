> **v0.3.1 repair note:** This release fixes a v0.3.0 Windows-installer issue that stored old backups inside `custom_nodes`. Those backups could be imported by ComfyUI as active nodes. The v0.3.1 installer automatically quarantines them outside the ComfyUI node directory.

# KIE.ai Nodes Next for ComfyUI

**Current version: 0.4.4 — Topaz Diagnostic Hotfix**

The repository includes the current source, the complete change history from v0.3.1 through v0.4.4, and ready-to-download Windows installers and historical packages in [`dist/`](dist/).

- Latest package: [`ComfyUI-KIE-Nodes-Next-v0.4.4-TOPAZ-DIAGNOSTIC.zip`](dist/ComfyUI-KIE-Nodes-Next-v0.4.4-TOPAZ-DIAGNOSTIC.zip)
- Windows one-click installer: [`KIE-Nodes-Next-OneClick-Windows-v0.3.2.vbs`](dist/KIE-Nodes-Next-OneClick-Windows-v0.3.2.vbs)
- Full uninstaller: [`KIE-Nodes-Next-Full-Uninstall.vbs`](dist/KIE-Nodes-Next-Full-Uninstall.vbs)
- Release history: [`RELEASE_NOTES.md`](RELEASE_NOTES.md)

KIE.ai Nodes Next turns KIE's API catalog into a native ComfyUI model library. The normal workflow is no longer a generic API node: each KIE model/API is exposed as its own node, organized by media type, provider, and model family.

## Studio nodes

`KIE Next / Studio` adds a director-oriented layer for models whose capabilities do not fit a flat form:

- **Camera Director** builds reusable shot size, angle, movement, lens, speed, stabilization, and focus language.
- **Shot Sequence** plans up to six shots with validated durations.
- **Kling 3.0 Omni Studio** supports single-shot, automatic multi-shot, manual shot sequences, image-guided generation, audio, and 4K controls.
- **Seedance Studio** exposes explicit text, first-frame, first-and-last-frame, and multimodal-reference modes.

Examples:

```text
KIE Next
├─ Video
│  ├─ ByteDance
│  │  └─ Seedance
│  │     ├─ Seedance 1.5 Pro
│  │     ├─ Seedance 2.0
│  │     ├─ Seedance 2.0 Fast
│  │     ├─ Seedance 2.0 Mini
│  │     └─ Seedance 2.5
│  ├─ Kling
│  ├─ Wan
│  ├─ Runway
│  ├─ Google / Veo
│  └─ ...
├─ Image
│  ├─ ByteDance / Seedream
│  ├─ Google / Nano Banana
│  ├─ OpenAI / GPT Image
│  ├─ Black Forest Labs / Flux
│  └─ ...
├─ Audio
│  ├─ Suno
│  ├─ ElevenLabs
│  └─ Google / Gemini TTS
├─ LLM
│  ├─ Claude
│  │  ├─ Opus
│  │  ├─ Sonnet
│  │  ├─ Haiku
│  │  └─ Fable
│  ├─ OpenAI / GPT
│  ├─ OpenAI / Codex
│  ├─ Google / Gemini
│  └─ xAI / Grok
└─ Utility / Advanced
```

## Why v0.3 is different

### Individual model nodes

The old `Any KIE API` node is **not registered in v0.3**. It was useful as an engineering fallback, but it is not the experience this project is trying to deliver.

KIE Next now builds individual node classes from KIE's official API documentation. If one KIE endpoint publishes multiple explicit model versions, KIE Next splits those versions into separate nodes too — the model selector disappears from normal use. Each node gets the request fields documented for that model: prompt, aspect ratio, resolution, duration, seed, first/last frame, image references, video references, audio references, model modes, audio generation, web search, LLM reasoning/tools, Suno controls, and other model-specific parameters where KIE documents them.

The model factory combines:

1. KIE's request example JSON.
2. Request/parameter metadata from the model documentation.
3. Model-family adapters for media and LLM APIs.
4. A small expert override field as a last-resort escape hatch for newly added fields.

### Native ComfyUI media inputs

URL plumbing is hidden from normal workflows.

- Image URL fields become `IMAGE` sockets.
- Image URL arrays accept ComfyUI image batches.
- Video URL fields become `VIDEO` sockets.
- Plural video references become numbered `VIDEO` sockets.
- Audio URL fields become `AUDIO` sockets.
- Plural audio references become numbered `AUDIO` sockets.
- Suno two-track inputs such as `uploadUrlList` become two native audio inputs instead of JSON URL lists.

KIE Next uploads connected media automatically and sends the generated KIE URLs to the API.

### Better prompt UX

Generation and LLM nodes open wider/taller than utility nodes, and multiline prompt widgets get a useful editing area instead of a tiny one-line control.

### One-time API key with visible confirmation

Go to:

**ComfyUI → Settings → KIE.ai Nodes Next → Connection**

Paste your key into **Paste / replace KIE.ai API key**.

KIE Next validates the key against KIE.ai *before* replacing the saved key. After a successful save you get:

- a success notification;
- a permanent **Saved API key** row showing only a masked fingerprint such as `••••••••••••A1B2`;
- an explicit **✅ CONNECTED** status;
- the current KIE credit balance when available.

The full key is backend-only. It is not put into workflow JSON and is not left in the frontend settings field.

Settings also include one-shot toggles to **test the saved key** or **remove the saved key**.

`KIE_API_KEY` is still supported for servers/headless installs and takes priority over the locally saved key.

## Complete KIE catalog coverage

KIE changes frequently. Hard-coding a release-time list would recreate the same maintenance problem this project was built to solve.

On startup, KIE Next reads KIE's official English API documentation index and builds a node for every callable API/model page in that catalog. It then enriches each node from the model's own documentation page.

The package includes a polished offline bootstrap for key models so useful nodes are present immediately. The first automatic deep catalog sync then expands the model library to the complete current KIE API documentation catalog, splits documented model/version variants into individual nodes, and reloads the ComfyUI frontend once.

After that, KIE Next checks for catalog changes at most once every 24 hours by default. New KIE model/API pages can therefore become individual ComfyUI nodes without waiting for a new plugin release.

If KIE's docs are temporarily unavailable, the cached model library remains usable.

## Included bootstrap nodes

The first-launch bootstrap currently includes polished definitions for:

- Seedance 1.5 Pro
- Seedance 2.0
- Seedance 2.0 Fast
- Seedance 2.0 Mini
- Seedance 2.5
- Claude Opus 5
- GPT 5.6 Sol
- Suno Generate Music
- Veo 3.1 Generate Video

The live catalog expands beyond this list automatically.

## Seedance 2 workflow support

Seedance 2.0 / Fast / Mini expose first-class controls for:

- prompt;
- first frame;
- last frame;
- reference images;
- up to three reference videos;
- up to three reference audio clips;
- return last frame;
- generated audio;
- resolution;
- aspect ratio;
- duration;
- web search.

KIE documents First Frame / First+Last Frames and Multimodal Reference as mutually exclusive scenarios. KIE Next validates this before sending the request so an invalid mixed workflow fails locally with a useful error.

## LLM nodes

LLMs are individual nodes as well. For example:

```text
KIE Next / LLM / Claude / Opus / Claude Opus 5
```

Claude-family nodes expose normal chat controls such as prompt, system prompt, message history, tools, max tokens, streaming, and thinking where applicable.

OpenAI/Codex-style reasoning nodes expose prompt, optional image input, reasoning effort, web search, tools, history and streaming where supported by the endpoint adapter.

LLM output is normal `STRING` text plus raw response, usage and KIE credit information.

## Outputs

Image/video/audio generation nodes return native Comfy media plus:

- primary result URL;
- JSON containing all result URLs;
- KIE task ID;
- raw provider response;
- credits consumed where KIE reports them.

Keeping all result URLs is useful for APIs that generate multiple images, multiple Suno tracks, last-frame artifacts, or additional outputs.

## Advanced tools

Normal users should use individual model nodes. A few lower-level tools remain under **KIE Next / Advanced** for debugging and unusual workflows:

- Universal Market Task
- Inspect API Definition
- Advanced Connection Override

Task status/wait and upload/download helpers remain under Utility.

`Any KIE API` is intentionally absent from the registered node menu.

## Installation

### Recommended: one-click Windows installer

Download the v0.3 one-click installer and double-click it. It:

- detects common ComfyUI Desktop, Portable and manual installations;
- understands ComfyUI Desktop's configured user data/base path;
- falls back to a Windows folder picker if necessary;
- backs up an older `ComfyUI-KIE-Nodes-Next` folder;
- installs the node pack into `custom_nodes`;
- uses ComfyUI's Python environment when available for dependency setup;
- does not require opening a command prompt.

Restart ComfyUI after installation.

### Comfy Registry / Manager

The project metadata and publishing workflow are prepared for Comfy Registry publication. Once the public repository/publisher release is completed, installation/update through ComfyUI's manager should become the preferred route.

### Manual fallback

Extract the source ZIP as:

```text
ComfyUI/custom_nodes/ComfyUI-KIE-Nodes-Next/
```

Then install `requirements.txt` in the same Python environment ComfyUI uses.

## Topaz Video Upscale troubleshooting

KIE Next sends Topaz Video Upscale through the documented `topaz/video-upscale` Market model with `video_url` and a string `upscale_factor`. Native ComfyUI video inputs are converted to an 8-bit SDR H.264 MP4 before upload.

If KIE accepts a job but Topaz immediately returns `internal error, please try again later`, KIE Next retries that narrow provider failure once and reports both task IDs. This is a remote provider failure, not a local CUDA or VRAM error. Failed jobs observed with `costTime: 0` reported `creditsConsumed: 0.0`.

To isolate source compatibility, test a 3–5 second H.264 MP4 using `yuv420p`, constant 24/30 fps, 720p or 1080p, and 2x upscale. If that also fails immediately, keep the task IDs and contact KIE support.

## Security notes

- Saved API keys live in the ComfyUI user/config area, not the workflow.
- The local settings file is written with restrictive permissions where the OS supports them.
- A replacement key is validated before overwriting a previously working saved key.
- The frontend only receives a masked fingerprint, never the stored full key.

## Validation

v0.4.4 passes 30 offline tests covering:

- result URL parsing;
- SSE normalization;
- catalog indexing and fallback behavior;
- query/path parameter extraction;
- media conversion;
- credential persistence;
- individual node registration;
- Seedance folder/media inputs;
- Claude/GPT model folders;
- removal of the user-facing `Any KIE API` node;
- Studio direction controls and model-specific generation modes;
- Topaz payload normalization and result-delivery edge cases.

Paid generation calls are not run automatically by the test suite.

## License

MIT.

