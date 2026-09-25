# KIE.ai Nodes Next Roadmap

## The 22 feature commitments

This is the product backlog agreed with the user. A checked item means a working local implementation has been verified; it does not imply Desktop visual acceptance or a paid provider check.

1. [x] Visual Camera Director with keyframed paths and presets (draggable top view and isolated Comfy graph verified; Desktop visual acceptance pending).
2. [ ] Documented capability metadata for every generated model operation.
3. [ ] No-spend preflight of inputs, limits, and incompatible modes (generated/Studio adapters and basic chat structure checked locally; unstructured provider rules and exhaustive media validation remain).
4. [x] Editable script/brief-to-storyboard planning (local deterministic draft and review; creative interpretation pending).
5. [x] Storyboard contact sheet and reference-frame preview (local rendering and Comfy server graph verified; visual frontend check pending).
6. [ ] Timecoded video event analysis (local visual markers, sparse labelled frames and an editor-reviewed semantic timeline work; full motion/audio interpretation and provider-backed vision acceptance remain).
7. [ ] Event-based music briefing and provider-backed soundtrack generation where supported.
8. [ ] Scene-aware sound design and ambience (approved timed cues and an explicit adapter to KIE Suno Sounds exist; semantic detection, live SFX generation and mix QA remain).
9. [ ] Assisted assembly of takes, audio, and transitions (local hard-cut take concatenation, music, dialogue ducking and two timed SFX work; transition styles and listening QA remain).
10. [x] Reusable Elements library for characters, places, props, and styles (local versioned library; desktop UI acceptance pending).
11. [x] Character identity with controlled wardrobe/appearance variants (approved variant images tied to immutable packs; generation consistency remains model-dependent).
12. [ ] Model-aware adapters for image, video, and audio references (many generated operations already have native sockets; Wan 2.7 Video Edit reference IMAGE fixed; exhaustive per-operation review remains).
13. [x] Side-by-side visual consistency testing (persistent local board for human review; no automatic identity score).
14. [ ] Batch variations with comparable prompts and outputs (four controlled prompts plus persistent result-comparison board; automatic paid batching and settings lock remain).
15. [ ] Localized video edits when a selected model supports them (Wan 2.7 Video Edit can be fed a Comfy VideoTrim clip and now validates source/reference media before spend; spatial masks and timeline round-trip remain).
16. [x] Freeze and reuse completed results without resubmitting paid tasks (task-ID reuse with no `createTask`; live provider check pending).
17. [ ] Task queue, status, failure, and result dashboard (local task-ID journal, Settings summary and live read-only Task Board work; account-wide discovery, async queue control and full frontend dashboard remain).
18. [ ] Credit transparency: estimate where documented, confirmed spend, and live balance.
19. [x] Reproducible generation recipe with inputs, model, task ID, and cost (immutable local receipt; automatic capture from every model node pending).
20. [ ] Guided templates for common production goals (four graph JSON starters with structural and KIE socket-contract checks; actual Desktop import/UX acceptance pending).
21. [x] Playable Preview Video and persistent Save Video nodes.
22. [x] Favorite KIE nodes with remappable keyboard shortcuts.

The first development increment implements items 21 and 22 in the local source. They need a Comfy Desktop UI check before packaging. Item 18 has confirmed-spend receipts and an on-demand balance query in the local source; cost estimation remains open.

Further local development adds an interactive top-view Camera Path (dragging start/end/look-at and keyframed orbit, dolly, crane, custom paths), visual-change and sparse-frame analysis, editor-reviewed music and sound briefs, immutable Elements/character looks/recipes, result reuse by task ID, a consistency board, a four-take Variation Matrix, four guided graph templates, and local hard-cut assembly with music, dialogue ducking, and two timed effects. The audio briefs and variation matrix **do not** trigger KIE generation; native camera conditioning, automatic semantic recognition, paid batch operation, advanced audio mixing, and transition styles remain open. The camera-path graph executed on an isolated ComfyUI 0.37.2 instance; frontend browser acceptance and paid KIE end-to-end checks remain open.

An equivalent no-spend graph for the event-led soundtrack template executed end-to-end against isolated ComfyUI 0.37.2 with a synthetic two-second video, producing reviewable music and sound briefs. The labelled-frame contact sheet was saved and visually inspected; a corrected, editor-attested event JSON then reached music and sound briefs in a second isolated graph. This validates the plumbing, not the quality of an actual vision-model interpretation. Provider-backed music/SFX generation and listening QA remain open.

## Director and Storyboard development history

Second increment: items 2 and 3 gained cached capability inspection and pre-upload validation for generated and Studio adapters. Basic chat validation was added later. Full per-model coverage, media-content checks, and visual UI acceptance remain open. `Storyboard Contact Sheet` renders and saves up to six planned shots with optional hero frames; its Comfy Desktop visual check is pending.

2026-09-25 catalog audit: a fresh isolated sync of KIE's official index scanned 223 English documentation entries, with one fetch failure, and returned 167 model IDs / 241 operations—no new model IDs relative to the bundled source snapshot. The bundled snapshot has parameter metadata for 184 of 241 operations, leaving 57 without full field metadata; an automatic refresh alone therefore cannot satisfy the every-model capability commitment. The isolated fresh catalog was not copied over the richer bundled source data.

Third increment: Script to Shot Draft preserves up to six source paragraphs or lines and proposes exact shot durations with neutral camera defaults. Shot Plan Review accepts edited JSON and validates it before passing it to the storyboard or manual Kling sequence. The three-node chain completed on an isolated ComfyUI 0.37.2 server and saved an inspected PNG. This is deterministic preparation; creative interpretation and visual frontend acceptance remain open.

Fourth increment: visual rhythm presets now propose shot coverage (size, angle, lens, movement) and give each shot an editorial intent visible on the contact sheet. Neutral remains the default for existing workflows. Presets provide position-based editorial suggestions; semantic scene analysis and native provider camera mapping are separate work.

The first directing increment builds on the existing `KIE • Shot Sequence` → `KIE • Kling 3.0 Omni Studio` graph rather than creating a separate app surface.

- [x] Add a shared visual setup and per-shot camera movement/focus controls to Shot Sequence.
- [x] Carry the structured camera plan through the `shot_sequence_json` socket.
- [x] Adapt manual Kling multi-shot requests into per-shot prompt guidance while retaining the KIE API's `prompt` + `duration` contract.
- [x] Add hero-frame inputs and a storyboard contact-sheet/preview node (local source; desktop UI acceptance pending).
- [x] Add a reusable Elements library for characters, locations, props, and styles, backed by ComfyUI user data and workflow references.
- [x] Start the Character Pack library: immutable versioned manifests, approved reference views, and Comfy user-data persistence.
- [x] Add graph nodes to save/load packs and route selected reference views into model operations that support image references.
- [x] Add an eight-case, no-spend consistency-test plan for front/profile/wide shots, camera angle, and scene/wardrobe variation.
- [ ] Add explicit model capability metadata and a preflight warning when a chosen operation cannot accept character references.
- [x] Add a side-by-side consistency board accepting approved references and up to four candidate outputs, including profile, lighting, and wardrobe tests chosen by the editor.
- [x] Add controlled wardrobe/appearance variants as named child records without changing immutable identity anchors.
- [x] Add a local script-to-shot-list draft and editable JSON review; never submit generations automatically (creative planner and desktop UI acceptance remain open).
- [ ] Add model capability metadata so the Director distinguishes native API controls from prompt-only guidance.
- [x] Add a versioned local generation recipe record (prompt, model, references, camera plan, task ID, credit receipt); automatic capture by every model node remains open.
- [x] Persist KIE-reported spend per ComfyUI profile and provide an on-demand live balance refresh in Settings and the browser console.

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

