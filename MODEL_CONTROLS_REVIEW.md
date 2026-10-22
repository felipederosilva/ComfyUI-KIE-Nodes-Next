# Model controls review — 2026-10-22

KIE Next should share a reliable transport, not an identical form for every model. The request schema must determine required media, supported settings and validation. Provider-specific editors should then make structured features pleasant to use.

## Sources checked

- KIE's live `/api/v1/models` catalog and each of its 230 model schema endpoints: 229 usable OpenAPI documents; `google/gemini-3-8-flash-tts` currently returns null.
- 240 English API pages in [KIE's documentation index](https://docs.kie.ai/llms.txt).
- Current ComfyUI `master`: [Kling partner nodes](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_api_nodes/nodes_kling.py), [Vidu partner nodes](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_api_nodes/nodes_vidu.py), and [Wan partner nodes](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_api_nodes/nodes_wan.py), plus the installed Desktop definitions. These are design references. KIE's own schemas determine KIE request fields and supported limits.

## Findings and changes delivered in v0.6.3

| Area | Comfy partner-node pattern | KIE Next v0.6.3 |
| --- | --- | --- |
| Input identity | Separate start frame, end frame and reference inputs | Corrects missing model IDs and exposes each model's actual fields; keyframe lists accept native IMAGE batches |
| Required fields | Vidu Q4 image-to-video requires an image while its prompt is optional | Explicit schema requirements take precedence over name-based assumptions |
| Model limits | Model-specific resolutions, duration and reference counts | Enums, bounds, defaults, and native VIDEO/AUDIO socket counts follow the model's schema |
| Alternative modes | Dynamic model/storyboard controls | Adds a documented input-mode selector for alternative schemas; submits only the selected branch and validates its requirements |
| Reference checks | Count, dimensions, duration and incompatible-reference checks | Schema count checks plus Kling 4 keyframe count and prompt-reference checks run before upload; existing Wan edit checks are retained |
| Refresh | Curated definitions distributed with Comfy | Bundles a verified snapshot and adds rate-limited Market schema discovery to live refresh |
| Workflow compatibility | Stable node identifiers | All 318 previous generated node IDs retained; 337 generated nodes in this release |

The combined catalog has 250 IDs including legacy IDs and provider versions, and 266 operations. This is distinct from KIE's 230 live Market entries. Missing live schemas are reported rather than treated as verified. No paid output quality or remote acceptance was tested during this release.

## Concrete examples

- **Kling 4 Keyframe:** prompt, 3–30-second duration, 720p/1080p, aspect ratio, optional first frame, middle-frame IMAGE batch and last frame. Total frame count must not exceed `min(duration + 1, 10)`; named prompt references must exist.
- **Vidu Q4 Image to Video:** required IMAGE; optional prompt; its own duration/resolution/audio settings. It does not inherit Kling's reference inputs or requirements.
- **Vidu Q4 Reference to Video:** required prompt and reference IMAGE batch, optional reference audio, and its own output controls. Native audio inputs follow the documented array limit.
- **Flux 3 Klein Edit:** required prompt and IMAGE references, with its documented size, output-format, image-count and seed fields.
- **Grok Image 2 Segment Map:** select an existing task or a new image. Each mode checks its own required input; neither format is silently mixed with the other.

## Next improvements, in order

1. **Dynamic layouts:** move guided Studio nodes to Comfy's modern schema API so choosing a mode reveals only relevant controls. Current legacy inputs remain visible; mode-specific submission and validation are implemented.
2. **Named reference trays:** add individual, ordered image/audio/video entries with counts, thumbnails and prompt-reference labels, using the exact KIE limits. IMAGE batches already work; expandable reference inputs are not yet implemented.
3. **Storyboard editor:** replace raw `multi_prompt` JSON with editable shot rows, per-shot durations and a total-duration meter. The present schema retains the array and validates documented fields; it is not a graphical shot editor.
4. **Characters and voices:** provide visual editors for Kling `elements` and `voices`, wired to saved character packs. These structured fields currently remain JSON controls where the provider exposes objects.
5. **Media-aware validation:** extend model-specific dimension, duration, aspect-ratio and audio constraints to Vidu, Kling and Wan before upload. Schema metadata alone does not establish every restriction written in prose.
6. **Reference-aware prompt guidance:** insert the provider's exact reference labels and explain which images/voices will be used, following Comfy's reference-node ergonomics.
7. **Cost estimates alongside actual receipts:** calculate estimates only where KIE exposes a sufficiently clear pricing rule, with model/resolution/duration context. Keep actual credits spent and remaining balance as the confirmed record.

The next Studio implementations should start with Kling 4 Keyframe, Vidu Q4 References and Kling multi-shot, each with focused validation and a real Desktop acceptance check before expanding across the catalog.
