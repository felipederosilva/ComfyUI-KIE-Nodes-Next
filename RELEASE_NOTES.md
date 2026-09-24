# v0.5.0 — Character Packs and Live Model Refresh

- Adds versioned Character Packs, reusable approved reference views, and a no-spend eight-case consistency-test prompt plan.
- Updates the bundled model catalog from KIE's current English API index: 223 documentation entries scanned with zero fetch failures.
- Adds DeepSeek V4.1 Flash and Kimi K3 as individual nodes; refreshes KIE Responses API request handling for those documented `/openai/v1/responses` operations and refreshes Grok 4.7 schema metadata.
- The merged snapshot contains 167 model IDs and 241 operations. The fresh docs index alone yielded 146 model IDs; the merged count retains prior bundled model/schema records so workflows and older listed operations are not discarded.
- Promotes the Character Packs and refreshed catalog from development into the public v0.5.0 release.

# v0.4.16 Live Catalog and Credit Receipts

- Refreshes the bundled catalog from KIE's official live API index: 223 API documents scanned, 0 fetch failures, 165 distinct model IDs, and 241 operations. The refreshed docs add or enrich operations even where they do not introduce a new unique model ID.
- Adds a live **credits spent** and **credits left** receipt to generated model and Studio nodes, including the Advanced Universal Market Task and Wait for Task nodes.
- Adds `credits_left` output sockets while preserving the existing socket order and values; displays a compact receipt directly on the node after a successful run.
- Reads the post-generation balance from KIE's documented Common API endpoint and saves the latest balance for the Connection Settings display. If the balance endpoint is temporarily unavailable, generation still completes and the node shows `unavailable` rather than failing the job.
- Keeps the KIE-returned task consumption as the preferred spent value and uses the before/after account-balance difference when task metadata does not report consumption.

# v0.4.15 Market Model Payload Regression Fix

- Fixes Wan's rejection of an unsupported nested model field introduced by the Suno adapter.
- Ordinary Market requests now retain model only in the outer request envelope. Versioned Suno requests still include their declared input.model.
- Validates the Wan submission with its bundled schema without submitting paid generation requests.

# v0.4.14 Wan Workflow Widget Migration

- Repairs existing Wan 3.0 and Wan 3.0 Prime workflow nodes whose serialized widgets shifted when `audio` was corrected from an AUDIO socket to a boolean control.
- Detects the distinctive stale layout (`seed="randomize"`) and restores seed, control-after-generate, NSFW, timeout, and callback values when the workflow opens.
- Leaves newly created or already-corrected Wan nodes untouched and records the repaired layout on the next workflow save.

# v0.4.13 Schema-Aware Boolean Controls

- Fixes **Wan 3.0 Video Prime** and other generated nodes whose boolean `audio` toggle was incorrectly treated as an AUDIO media input.
- Gives explicit OpenAPI boolean types priority over media-like parameter names in both ComfyUI widgets and submitted payloads.
- Coerces legacy workflow values such as `"true"` and `"false"` back to real JSON booleans without changing genuine audio-file inputs.

# v0.4.12 Suno Non-Custom Payload Repair

- Completes the image-reference compatibility path by omitting `duration` and every other Custom-Mode-only control when image references require Generate Music to run with `custom_mode=false`.
- Prevents the follow-up provider error `duration is only supported when customMode is true` and the equivalent style, title, persona, and weight validation chain.
- Keeps `prompt`, image/audio references, and the selected Suno model version intact; text-only Custom Mode requests remain unchanged.

# v0.4.11 Suno Image-Reference Mode Repair

- Fixes existing **Generate Music** workflows that connect image references while retaining Custom Mode, a combination the provider rejects as `imageUrls is only supported when customMode is false`.
- Automatically submits that specific documented combination with `custom_mode=false`, retaining the connected images and avoiding a provider-side failed task.
- Leaves text-only Custom Mode generations unchanged.

# v0.4.10 Suno Market Envelope Repair

- Fixes existing generated Suno nodes, including **Generate Music · V6 WILD**, that incorrectly sent a provider version such as `V6_WILD` as KIE's outer Market model name.
- Sends KIE's documented `ai-music-api/...` envelope model while preserving the selected Suno version in the nested `input.model` payload.
- Covers Generate Music, Extend Music, Upload/Cover, Upload/Extend, Add Instrumental, Add Vocals, Mashup, Sounds, and Music Cover without changing any node IDs or workflow wiring.
- Does not submit, repeat, or charge for a failed task; affected existing workflows work after a ComfyUI restart.

# v0.4.9 Persistent Load Video

- Adds **KIE • Persistent Load Video**, a self-contained replacement for the core Load Video node.
- Reads nested input files and saved output files directly, including durable values such as `V6_00001_.mp4 [output]`.
- Stores the selected video in the workflow and draws a preview frame from the durable file on reopening.

# v0.4.8 Persistent Preview Image

- Adds **KIE • Persistent Preview Image**, a durable replacement for ComfyUI's temp-only Preview Image node.
- Saves incoming images under `output/KIE-Previews/` and records the output reference in the workflow.
- Restores and draws the saved thumbnail when the workflow is reopened, while continuing to pass the image downstream.

# v0.4.7 Output-Video Preview Repair

- Corrects `Load Video` previews for annotated `[output]` files, which core ComfyUI otherwise labels as input-folder media after workflow restoration.
- Keeps the v0.4.6 durable result archive and recursive media selector repair.

# v0.4.6 Persistent Result Media and Loader Repair

- Repairs stale `Load Video`, `Load Image`, and `Load Audio` selections by listing recursively discovered input files and existing annotated `[output]` media references.
- Preserves existing files in place; no media is copied, renamed, or removed to repair a workflow.
- Archives KIE-downloaded image, video, audio, and generic-file results under `output/KIE-Results/` using content-addressed filenames, so results survive temp-folder cleanup and app restarts.
- Keeps the former temp-file behavior as a fallback only when ComfyUI's output directory cannot be written.

# v0.4.5 Nested Pasted-Media Compatibility

- Fixes workflows whose `Load Image` values persist as `pasted/<filename>` after a ComfyUI reload.
- Extends the core image-node combo list with recursively discovered files under the configured input directory, including `input/pasted/`.
- Preserves ComfyUI's existing path-containment validation and leaves normal top-level input loading unchanged.
- Adds offline coverage for nested paths, forward-slash normalization, and symlinked-directory exclusion.

# v0.4.4 Topaz Diagnostic Hotfix

- Fixes a missing `os` import introduced by the v0.4.3 Topaz upload-size diagnostic.
- Keeps the v0.4.3 canonical 8-bit SDR H.264 Topaz input path unchanged.
- Syncs package metadata and runtime build markers to v0.4.4.

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

