# KIE.ai Nodes Next Roadmap

## v0.5.0 — Director and Storyboard (in development)

The first directing increment builds on the existing `KIE • Shot Sequence` → `KIE • Kling 3.0 Omni Studio` graph rather than creating a separate app surface.

- [x] Add a shared visual setup and per-shot camera movement/focus controls to Shot Sequence.
- [x] Carry the structured camera plan through the `shot_sequence_json` socket.
- [x] Adapt manual Kling multi-shot requests into per-shot prompt guidance while retaining the KIE API's `prompt` + `duration` contract.
- [ ] Add hero-frame inputs and a storyboard contact-sheet/preview node.
- [ ] Add a reusable Elements library for characters, locations, and props, backed by ComfyUI files and workflow references.
- [x] Start the Character Pack library: immutable versioned manifests, approved reference views, and Comfy user-data persistence.
- [x] Add graph nodes to save/load packs and route selected reference views into model operations that support image references.
- [x] Add an eight-case, no-spend consistency-test plan for front/profile/wide shots, camera angle, and scene/wardrobe variation.
- [ ] Add explicit model capability metadata and a preflight warning when a chosen operation cannot accept character references.
- [ ] Add a side-by-side consistency check workflow covering profile, wide/full-body, lighting, and wardrobe variation.
- [ ] Add controlled wardrobe/appearance variants as named child records without changing immutable identity anchors.
- [ ] Add a script-to-shot-list planner that proposes JSON for user review; never submit generations automatically.
- [ ] Add model capability metadata so the Director distinguishes native API controls from prompt-only guidance.
- [ ] Add generation recipe metadata (prompt, model, references, camera plan, task ID, credit receipt) to saved results.

### Comfy Desktop implementation contract

1. **Stay inside the Comfy graph.** Inputs, outputs, and Comfy media types remain the source of truth; ordinary nodes continue to work in API-format workflows.
2. **Keep a provider-neutral plan.** A Director plan stores the creative intent (shot size, angle, movement, lens/look, focus, duration, references) independently of any one model's request schema.
3. **Adapt only documented capabilities.** The adapter maps plan fields to native API fields only when the selected operation documents them. Unsupported controls become clearly labeled prompt text; never imply physical camera enforcement where there is none.
4. **Review before spending.** A planner produces an editable storyboard/JSON proposal. Only an explicit connected generation node submits paid KIE jobs.
5. **Preserve provenance.** A generated shot should retain its actual provider/model, exact prompt, references, camera plan, task ID, and live credit receipt so variants can be compared and recreated.
6. **Treat character identity as durable, versioned data.** Character Packs live in Comfy's per-user KIE data folder, outside the extension install. Approved references and identity notes are immutable per pack version; updates create a new version. Identity traits stay separate from wardrobe/scene variations.
7. **Never claim universal identity lock.** A Character Reference node supplies approved image(s) and an identity brief; the selected model/operation must document reference support. Prompt guidance and reference inputs are not a guarantee of cross-generation identity.
8. **Respect likeness rights.** When a pack is marked as depicting a real person, require explicit confirmation of permission before saving it.

### Character Pack first slice

- `KIE • Save Character Pack`: stores a required canonical portrait, optional full-body/profile/expression-sheet views, identity description, visual style, continuity rules, and wardrobe notes. Identical saves are idempotent; changed content cannot overwrite a version.
- `KIE • Load Character Pack`: selects a saved version and emits its pack record and reusable identity prompt.
- `KIE • Character Reference`: selects one saved approved view and returns an IMAGE plus an identity prompt with an optional scene/wardrobe variation.
- Packs are stored under `<Comfy user directory>/KIE-Nodes-Next/character_packs/` so they survive extension updates and can be reused by separate workflows in the same Comfy user profile.
- This slice does not train an identity model, create a character sheet, or guarantee consistency. It provides reusable source-of-truth references; model-specific reference adapters and a consistency QA graph are next.

Current slice: Shot Sequence emits a per-shot camera plan. Kling Omni's manual multi-shot adapter converts it to prompt guidance because that endpoint accepts per-shot prompt and duration, not an independent lens/movement parameter set.

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

