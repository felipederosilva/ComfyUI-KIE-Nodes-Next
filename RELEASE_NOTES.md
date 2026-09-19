# v0.4.3 Topaz Video Compatibility Repair

- Re-encodes ComfyUI VIDEO inputs specifically for Topaz as 8-bit SDR/sRGB H.264 MP4 before upload.
- Stops preserving 10-bit/HDR characteristics on the Topaz path, which can be rejected by stricter remote decoders.
- Verifies the materialized MP4 is non-empty before upload/task submission.
- Prints the canonical Topaz upload size to the ComfyUI log for provider-limit diagnosis.
- Keeps the single narrow provider-internal-error retry from v0.4.1.

# v0.4.2 Install Integrity Repair

- Adds a build marker to the generated node module and verifies it against the package version at startup.
- Refuses to run mixed installations where __init__.py was updated but nodes/generated.py stayed stale.
- Keeps Topaz v0.4.1 retry/validation repair intact.
- Restores compatibility with callers that pass the generated payload_model keyword.

# v0.4.1 Topaz Reliability Repair

- Normalizes Topaz Video Upscale payloads before task submission.
- Rejects missing video inputs and unsupported upscale factors locally before spending credits.
- Retries exactly once when KIE accepts a Topaz task and the remote provider returns the narrow terminal "internal error / please try again later" failure signature.
- Preserves single-submit behavior for all other models and all non-transient errors.
- Returns a Topaz-specific diagnostic with task IDs when the provider fails again.

# v0.4.0 Studio Direction

- Refreshes the official KIE catalog to 165 model IDs and 234 operations, with 182 schema-enriched operations.
- Adds newly documented Claude, GPT Image 2.5, and Suno V6 model variants.
- Removes deprecated Flux Kontext model IDs from the selectable model inventory.
- Repairs stale Kling 2.6 identifiers embedded in Kling 3.0 Omni documentation pages.
- Adds Camera Director and six-shot sequence-builder nodes.
- Adds purpose-built Kling 3.0 Omni Studio and Seedance Studio generation nodes with mode-aware validation and native ComfyUI media inputs.

# v0.3.6 Result Delivery Repair

- Keeps polling briefly when KIE reports `state=success` before its generated URL has been persisted.
- Supports `response`, direct result URL fields, and double-encoded JSON in addition to the unified `resultJson` response shape.
- Ignores echoed request/input media URLs so an uploaded source is never mistaken for generated output.
- Adds regression coverage for delayed results and provider-specific response envelopes.

# v0.3.5 Catalog Cache Repair

- Merges live catalog discoveries with bundled schemas instead of letting a stale user cache replace them.
- Automatically restores model-specific controls after upgrading from pre-schema catalog releases.

# v0.3.4 Schema-Driven Model Controls

- Extracts the OpenAPI request schema embedded in KIE's model documentation.
- Generates model-specific ComfyUI controls from required fields, types, enums, defaults, ranges, and media references.
- Keeps expert JSON only as an optional advanced override.

# v0.3.3 Complete Catalog Release

- Ships the complete KIE catalog captured from official documentation: 149 model IDs across 227 documented operations.
- Generates individual ComfyUI nodes for every discovered model/version on first launch; no initial network refresh is required.
- Adapts catalog extraction to KIE's current Apidog/HTML documentation format and retains live refresh for future catalog changes.

# v0.3.2 Installer Reliability Release

- Rebuilds the Windows one-click installer from scratch.
- Validates the selected ComfyUI root before installing and reports the exact destination.
- Keeps the v0.3.1 repair behavior: existing KIE copies are quarantined outside `custom_nodes` before installation.

# v0.3.1 Repair Release

- Fixes the Windows installer backup bug that left old KIE Next copies inside `custom_nodes`, causing ComfyUI to import v0.2 and v0.3 simultaneously.
- The installer now moves all prior KIE Next copies to `%LOCALAPPDATA%\KIE-Nodes-Next\backups\...`, fully outside ComfyUI's node scan path.
- Adds backend-reported plugin version and exact loaded folder path to Settings > KIE.ai Nodes Next > Diagnostics.
- Adds startup log: `[KIE Next] Loaded v0.3.1 from ...`.
- Installer verifies the installed package really reports v0.3.1 and that the legacy `Any KIE API` registration is absent.

---

# KIE.ai Nodes Next v0.3.0 — Individual Model Library

## Product change

The user-facing generic `Any KIE API` node has been removed. KIE Next now treats the model menu itself as the product: individual nodes are generated from KIE's official API documentation and organized by media type, provider, and model family.

Examples:

- `Video / ByteDance / Seedance / Seedance 2.5`
- `LLM / Claude / Opus / Claude Opus 5`
- `Audio / Suno / Music Generation / Generate Music · V5.5`

If one documented API exposes multiple explicit model versions, those versions are split into separate nodes instead of forcing a model dropdown.

## Model-specific UI

Nodes infer typed controls from KIE request examples and parameter documentation, then add family-specific adapters for richer ComfyUI inputs. Prompts are multiline and generation nodes open with a larger default footprint. Image/video/audio URL parameters are translated into native ComfyUI media sockets and uploaded automatically.

Seedance 2.0 family nodes include first/last frame, image/video/audio reference inputs, duration, resolution, aspect ratio, generated audio, return-last-frame and web-search controls. Invalid mixing of frame mode with multimodal-reference mode is rejected locally before spending credits.

LLM families are organized separately and receive LLM-specific controls. Claude nodes expose system prompt, history, tools, max tokens, stream and thinking. OpenAI/Codex-style reasoning endpoints expose reasoning effort, optional images, web search, tools and history where appropriate.

## API key UX

The API key is entered once under ComfyUI Settings. KIE Next validates a replacement key before saving it, preserves the old working key if validation fails, and shows persistent masked status afterward:

- `Saved in ComfyUI backend • ••••••••••••ABCD`
- `CONNECTED • ••••••••••••ABCD • <credits>`

The full saved key remains backend-only and is not returned in the public settings status or stored in workflow JSON.

## Live catalog

KIE Next bootstraps a small useful set offline, then syncs KIE's official English API documentation index and enriches every documented callable API page. Explicit model IDs and documented model enums are split into individual model nodes. Transient documentation failures do not remove an API from the library; unresolved pages stay as skeleton entries and are retried on demand.

## Advanced tools

Raw transport remains available only under `KIE Next / Advanced` for debugging and unusual workflows:

- Universal Market Task
- Inspect API Definition
- Advanced Connection Override

## Validation

- 22/22 offline tests pass
- 29 bootstrap nodes register successfully before live catalog expansion
- every bootstrap class passes INPUT_TYPES / FUNCTION / RETURN_TYPES validation
- `Any KIE API` is absent from registered nodes
- packaged ZIP imports and passes the complete offline test suite
- Windows installer is ASCII + CRLF (no UTF-8 BOM)
- installer embedded ZIP is byte-for-byte identical to the tested source ZIP

Paid KIE generations are intentionally not run by the offline test suite.

