# KIE.ai Nodes Next for ComfyUI

**Current version: 0.6.0 — Local Production Tools.** This release includes the verified local tools described below; it does not complete all 22 [roadmap commitments](ROADMAP.md). Paid provider workflows still require model-specific validation.

- Latest package: [`ComfyUI-KIE-Nodes-Next-v0.6.0.zip`](dist/ComfyUI-KIE-Nodes-Next-v0.6.0.zip)
- Release history: [`RELEASE_NOTES.md`](RELEASE_NOTES.md)

### Input checks and model controls

Right-click a generation or Studio node and choose **KIE Next · Check inputs & model controls** to inspect cached documented fields, limits, and camera-control support without uploading media or submitting a generation. Unknown capabilities are labeled rather than inferred as supported. Connected values are checked during execution, not evaluated by this menu.

Generated non-chat and Studio nodes also run local input checks before uploads. Chat nodes check prompt presence, history/tools/override JSON, token bounds, and reasoning level before connection or image upload. These checks do not guarantee provider acceptance: media dimensions/content, prose-only restrictions, and some conditional schemas still require provider validation.

### Storyboard review

Connect `KIE • Shot Sequence` to `KIE • Storyboard Contact Sheet`. Attach `hero_frame_1` through `hero_frame_6` from Load Image or another image node when available. The node renders a persistent contact sheet in ComfyUI's output folder and returns an `IMAGE` plus JSON notes for all planned shots. It runs locally and does not submit a generation.

For a written script, use `KIE • Script to Shot Draft` → `KIE • Shot Plan Review` → `KIE • Storyboard Contact Sheet`. Split on blank paragraphs or one line per shot, choose a target duration and optional visual rhythm, then run the draft. The neutral default preserves existing behavior; cinematic reveal, documentary observer, product detail, action build, and interview coverage offer editable camera suggestions. Right-click the draft to view its JSON or copy it into the connected Review node's `edited_json` field. Edit prompts, duration, or camera settings there and run Review. Review outputs the same `shot_sequence_json` accepted by Storyboard and Kling Omni Studio. For Kling Omni manual multi-shot, keep the total duration within that model's documented 3–15 seconds; preflight checks this before upload. Source text is preserved, and camera directions are translated to prompt guidance for Kling Omni. The planner does not infer story meaning or invent new shots.

### Reusable production references

`KIE • Save Element` stores a versioned location, prop, or style in Comfy's per-user KIE library. Locations and props require one approved reference image; styles may be text only. `KIE • Load Element` retrieves the continuity brief, and `KIE • Element Reference` retrieves an image when one was saved. A changed image or description requires a new version.

`KIE • Save Character Variant` attaches an approved outfit or appearance to one immutable Character Pack version. `KIE • Load Character Variant` returns that image and a prompt combining the identity anchors with the selected look. The variant is stored separately from the parent pack and cannot silently replace it. `KIE • Consistency Board` displays an approved reference beside up to four candidate outputs in a persistent local image for human review; it does not assign a misleading identity score.

### Local production helpers

`KIE • Camera Path` offers a draggable top-view path with dolly, orbit, crane, and custom presets and stores a preview image. Its direction is **prompt guidance**, not native camera conditioning unless the selected model documents a matching control. `KIE • Variation Matrix` prepares four prompts with one deliberate change per take; connect only the desired takes to paid generation nodes.
`KIE • Variation Board` then places up to four generated IMAGE results alongside their deliberate changes on a persistent 2×2 contact sheet. It is visual human review; it does not auto-generate or assign a synthetic quality score.

`KIE • Video Event Analysis` locally samples a connected VIDEO and returns timecoded visual-change candidates. It does not recognize scene actions, speech, or sounds. `KIE • Music Brief from Video` makes an instrumental brief using those markers or editor-described events; it exposes `suno_custom_mode=false` and `instrumental=true` for a compatible Suno operation. `KIE • Sound Cue Sheet` accepts only editor-described sound events as effects; visual changes stay in a separate review list. These planning nodes do not generate audio or spend credits.
For deeper review, `KIE • Sample Video Frames` makes a labelled contact sheet plus ordered IMAGE frames and timestamps. Connect either image output and its suggested prompt to a vision-capable model only when you intentionally want to pay for that model. Its description can miss action between frames or hallucinate. Watch the source video, correct the model's JSON, paste it into `KIE • Review Video Events`, and enable `editor_reviewed`. Only then do those descriptions flow into the music and sound-cue nodes as verified events.
`KIE • SFX Prompt from Cue` selects one approved event or the ambience bed and exposes a ≤500-character prompt, loop toggle, lyrics toggle, and cue time for a [KIE Suno Sounds](https://docs.kie.ai/suno-api/generate-sounds) node. Connecting it to that generated node is an explicit paid action; run and review each effect separately.

`KIE • Reuse Completed Image/Video/Audio` retrieves a successful KIE task by ID without resubmitting it. `KIE • Save Generation Recipe` saves a versioned, immutable local record of model, exact prompt, references, camera plan, task ID, result URLs, and confirmed spend; `KIE • Load Generation Recipe` reads it back. Record creation is currently explicit, not automatic for every generator.

`KIE • Task Board` refreshes the last 20 locally submitted task IDs automatically, or up to 20 IDs pasted by the editor, and shows success/failure, progress, result URLs, and provider-reported spend without resubmitting anything. The local journal stores IDs, model names, state and spend—not prompts or API keys. Settings → KIE.ai Nodes Next → Tasks shows the last five locally recorded IDs; this is not an account-wide task history. `KIE • Assemble Video + Music` joins up to four compatible VIDEO takes with hard cuts, fits one AUDIO music track, optionally lowers music under detected dialogue by an adjustable amount, mixes that dialogue plus two timed SFX inputs, and returns a VIDEO. Connect that VIDEO to `KIE • Save Video` to export. Short music can be padded with silence or looped with a crossfade; final mix is peak-protected. Source-video audio is replaced, so connect needed dialogue explicitly (for example, via ComfyUI's Get Video Components). The ducking uses audio level, not speech recognition; listen to the exported file to verify timing and levels. More than two effects and transition styles are not yet included.

For a bounded video edit, trim the source clip with ComfyUI's `VideoTrim` before connecting it to **Wan 2.7 - Video Edit** in KIE Next. The KIE node now accepts a native optional IMAGE reference and checks the documented 2–10-second source duration, dimensions, aspect ratio, and RGB reference shape before upload. The provider edits that selected clip as a whole; this is not a spatial mask editor. The node still submits a paid job when run. The [Wan 2.7 Video Edit API documentation](https://docs.kie.ai/market/wan/2-7-videoedit) defines the accepted fields and limits.

Four starter workflows are in [`templates/`](templates/): **review-video-events.json** samples and displays time-labelled frames, **video-to-music-and-sound-brief.json** reviews visual markers and editor-described audio cues, **finish-video-with-music.json** joins a selected video and local/generated AUDIO before saving an MP4, and **compare-character-consistency.json** saves a board comparing two candidate images with an approved reference. None invokes a paid model as supplied. Import the JSON into ComfyUI, select your own files in the loader nodes, and inspect/edit every prompt and cue before generating. `KIE • Review Text` displays the briefs inside the graph and persists the last reviewed text. These templates passed node/link and KIE socket-contract checks; visual import in Comfy Desktop still needs hands-on acceptance.

KIE.ai Nodes Next turns KIE's API catalog into a native ComfyUI model library. The normal workflow is no longer a generic API node: each KIE model/API is exposed as its own node, organized by media type, provider, and model family.

### Character Packs (v0.5.0)

Version 0.5.0 adds reusable, versioned Character Packs to the Comfy graph:

1. **KIE • Save Character Pack** stores an approved portrait and optional full-body/profile/expression references, plus identity, style, and continuity notes.
2. **KIE • Load Character Pack** selects a saved version and emits its identity prompt.
3. **KIE • Character Reference** loads a selected approved view as an `IMAGE` for a model operation that documents reference-image support.
4. **KIE • Character Consistency Test Plan** creates a reusable eight-case prompt matrix (front, profile, wide/full-body, high/low angles, and a changed-scene test) for manual/model-specific QA. It never submits generation jobs.

Packs are stored in Comfy's user data folder, outside the extension install, and immutable by name/version to protect reproducibility. Re-saving identical content is safe; changing a pack requires a new version. Keep identity anchors separate from wardrobe and scene variation. A reference image and prompt are not a universal identity lock; actual consistency depends on the selected model and operation. When marked as a real person's likeness, saving requires confirmation of permission.

Model-specific reference adapters, automatic identity scoring, and character-sheet generation remain follow-up work. Named wardrobe/appearance variants and a manual comparison board are included.

After each successful generation, model and Studio nodes display **credits spent** and the live **credits left** balance directly on the node. Both values are also available as output sockets. If KIE does not report task-level spend, the before/after balance difference is explicitly labeled an estimate and is not added to the confirmed local total; concurrent jobs could affect it. The latest account balance is saved for the Connection Settings status; if KIE's balance service is temporarily unavailable, the generation result is still returned and the node reports the balance as unavailable.

The **Connection → Credits** settings section shows the latest balance and cumulative KIE-reported spend by this ComfyUI profile. Use **Refresh balance now** to query KIE at any time without submitting a generation. In the browser developer console, `KIENextCredits()` performs the same refresh and returns/logs the balance and tracked spend. Tracking starts when this feature is installed; it is local to this ComfyUI profile and is not KIE's account-wide usage history.

Version 0.6.0 adds **KIE • Preview Video** and **KIE • Save Video** under `KIE Next / Utility / Media`. Connect any ComfyUI `VIDEO` output to play it inside the node. Preview files are kept in `output/KIE-Previews/`; saved exports use `output/KIE-Videos/` by default. Both nodes pass the `VIDEO` through and expose a `saved_file` value that can be selected by **KIE • Persistent Load Video** in a later workflow.

To set a favorite shortcut, right-click any KIE Next node and choose **KIE Next · Favorite shortcut slot**. Assign it to one of nine slots, then bind the corresponding **KIE Next: Insert favorite node 1–9** command in ComfyUI **Settings → Keybindings**. The command inserts that node at the center of the visible graph. Selecting the same node in its slot again removes the favorite. Favorites are stored in the current ComfyUI frontend profile; no shortcut overrides ComfyUI or browser defaults.

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

### Windows installer

There is no one-click installer for v0.6.0. Use the verified v0.6.0 ZIP or ComfyUI Manager once the matching Registry entry is available. Do not use an old v0.3 installer for this release.

### Comfy Registry / Manager

The project metadata and publishing workflow are prepared for Comfy Registry publication. Registry availability must be verified separately; the GitHub source and ZIP do not by themselves prove Manager availability.

### Manual fallback

Extract the source ZIP as:

```text
ComfyUI/custom_nodes/ComfyUI-KIE-Nodes-Next/
```

Then install `requirements.txt` in the same Python environment ComfyUI uses.

## Security notes

- Saved API keys live in the ComfyUI user/config area, not the workflow.
- The local settings file is written with restrictive permissions where the OS supports them.
- A replacement key is validated before overwriting a previously working saved key.
- The frontend only receives a masked fingerprint, never the stored full key.

## Validation

This release source passes 117 Python tests and six JavaScript UI tests. An actual ComfyUI `VIDEO` was saved and decoded as MP4 in an isolated runtime test; no paid API task ran. The checks cover:

- result URL parsing;
- SSE normalization;
- catalog indexing and fallback behavior;
- query/path parameter extraction;
- media conversion;
- credential persistence;
- individual node registration;
- Seedance folder/media inputs;
- Claude/GPT model folders;
- removal of the user-facing `Any KIE API` node.
- persistent video output and credit-usage deduplication.

In-app Desktop playback, save/reload behavior, and shortcut interaction still require hands-on visual acceptance; the automated checks do not prove those experiences.

Paid generation calls are not run automatically by the test suite.

## License

MIT.

