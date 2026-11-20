# EasySlides Image Acquisition Contract

EasySlides follows PPTMaster's resource-first image workflow. The deck plan
declares image resources; the acquisition layer chooses a provider; the
Executor consumes files from `project/images/` without knowing which provider
created them.

## Research-led visual variety

1. **Plan the image around the page.** In the existing `page_brief.visual_rationale`
   or source ledger, name what the audience should see or compare and what the
   text adds. Verify the subject, location, observed time, units and scope
   that matter to that claim. Label context photographs and teaching diagrams
   by their role. A single photograph can show a state. A claim about change
   needs comparable observations across time or another traceable source.
2. **Search by observation.** Within the agreed source scope, gather a set
   of independently useful candidate visuals before freezing layouts. Search
   for the needed observation, viewpoint or comparison. Consider field
   photographs, archival material, maps, surveys, satellite imagery, charts
   and diagrams according to the content. Record page, visual purpose, subject,
   observation date when known, creator, source locator, original URL and terms
   in the existing ledger. Keep observation and publication dates distinct.
3. **Choose the frame for the figure.** Use the visible image after aspect-ratio
   fitting as the measure of its size. Check the feature the audience needs
   to see, plus relevant labels, axis, scale and legend. If it is too small,
   try a larger frame, a different composition, fewer panels or a relevant
   detail with the source context preserved. Keep comparative panels at
   comparable scale when the comparison depends on it.
4. **Check the final renders.** Scan the whole deck for exact reuse and
   visually near-identical images, including nonadjacent pages and crops.
   Review the actual slides at presentation size for figure-to-content fit,
   visible scale and caption proximity. Shared cover and section theme art
   serves the template. Keep repeated evidence when comparing or revisiting
   it adds a specific observation. Aligned images of the same area at different
   dates remain a valid comparison. After a replacement, update the caption,
   source credit and notes together. See the
   [visual review workflow](../workflows/visual-review.md#review-scope).

Use native text for standalone explanations. A miniature slide or a chain
of text cards with generic arrows is a poor substitute for evidence. Use an
editable diagram when shapes show a specific spatial relationship, comparison,
mechanism or operation. Preserve the meaningful information when replacing a
graphic. Keep points needed for reading on the slide and move supporting
explanation to the notes as appropriate.

## Resource manifest

Create a starter manifest with:

```bash
python scripts/easyslides.py image-acquire scaffold \
  project/images/image_prompts.json \
  --topic "研究主题"
```

Each cover or ending background is a `hero_page` item. Keep text in SVG/PPTX
slots and use `text_policy: none` for background images. A manifest can also
declare `local` illustrations or decorative assets with an explicit placement
frame; this lets the Strategist choose a full-bleed atmosphere, a right-side
visual, or a small framed inset according to the selected template:

Use `--template-dir` and `--palette-id` with `image-acquire scaffold` when the
manifest should inherit a template's semantic colors. Those tokens are reused
by prompts, safe-area readability checks, and runtime SVG/PPTX theme
replacement.

```json
{
  "id": "cover_background",
  "filename": "cover_bg.png",
  "slide_role": "cover",
  "page_role": "hero_page",
  "asset_role": "background",
  "text_policy": "none",
  "aspect_ratio": "16:9",
  "background": {
    "fit": "slice",
    "scrim_fill": "#FFFFFF",
    "scrim_opacity": 0.2
  },
  "status": "Pending"
}
```

For a local illustration, use `page_role: "local"`, `asset_role:
"illustration"`, and a placement frame in canvas pixels:

```json
{
  "id": "cover_illustration",
  "filename": "cover_illustration.png",
  "purpose": "Right-side cover illustration",
  "slide_role": "cover",
  "page_role": "local",
  "asset_role": "illustration",
  "placement": {
    "frame": {"x": 860, "y": 145, "width": 330, "height": 380},
    "fit": "contain",
    "opacity": 0.92,
    "corner_radius": 18
  },
  "text_policy": "none",
  "aspect_ratio": "4:5",
  "status": "Pending",
  "prompt": "No text; compact academic illustration with calm space around it."
}
```

Add the manifest path to the deck plan when the deck should consume it:

```json
{
  "template_id": "academic_classic",
  "image_manifest": "images/image_prompts.json",
  "slides": [
    {
      "page": "P01",
      "role": "cover",
      "image_resource_id": "cover_background"
    }
  ]
}
```

`image_manifest` is opt-in. Existing decks without it retain their template
backgrounds unchanged.

## Deterministic path selection

```text
explicit api       -> image_gen.py --manifest
explicit host-native -> host image tool request
explicit manual    -> prompt sidecar + Needs-Manual
auto + IMAGE_BACKEND -> api
auto + host native   -> host-native
auto otherwise       -> manual
```

`CODEX_HOME/skills/.system/imagegen/SKILL.md` is detected as a host-native
capability when present (or set `EASYSLIDES_IMAGEGEN_SKILL` explicitly). API
configuration still takes precedence. `image-acquire capabilities` and
`doctor --json` expose the same normalized capability record, and a host
request is never marked as generated until the file is reconciled.

Commands:

```bash
python scripts/easyslides.py image-acquire resolve project/images/image_prompts.json
python scripts/easyslides.py image-acquire prepare project/images/image_prompts.json
python scripts/easyslides.py image-acquire prepare project/images/image_prompts.json --path api --execute-api
python scripts/easyslides.py image-acquire prepare project/images/image_prompts.json --path host-native
python scripts/easyslides.py image-acquire reconcile project/images/image_prompts.json
```

The host-native command writes `image_acquisition_request.json`. A host agent
places generated files at the declared `output_path`, then `reconcile` marks
them `Generated`. A missing file never remains falsely marked `Generated`.

Each handoff item carries its page, asset role, visual-use policy, safe area,
and source policy. `source_policy: generated_decorative_only` is the explicit
guard used by planner-created AI visuals.

## Rendering and fallback

Generated `hero_page` items for `cover`, `chapter`, `transition`, and `ending`
are attached to Slide IR as `background_asset`. Local resources are attached as
`image_assets` and are rendered using their declared frame. The SVG renderer
places all generated images after the shell's base canvas and before the shell
chrome/text. If a resource is pending, failed, missing, or unreadable, no image
is inserted and the template shell remains visible; the slide records an
`image_fallback` entry for review.

Template-owned decorative illustrations may declare
`placement.layer: shell_overlay`; these are placed above shell chrome but below
editable shell text. Source/evidence images remain underlays unless they
explicitly declare another placement layer.

When a generated background is present, its declared safe area is sampled. The
renderer chooses light or dark editable text, adds a local scrim for mixed or
low-contrast imagery, and records `reports/readability_report.json`. A failed
readability check keeps the fallback shell visible for review instead of
shipping unreadable text over the image.

If an opaque template band owns the visible contrast, set
`background.readability_mode` to `template_shell` and provide a semantic
`background.text_color`; the renderer will keep the shell's light/dark text
contract instead of sampling an image that is hidden below the band.

Slides may override placement or select multiple assets explicitly:

```json
{
  "role": "cover",
  "image_bindings": [
    {"resource_id": "cover_background"},
    {"resource_id": "cover_illustration", "placement": {
      "frame": {"x": 860, "y": 145, "width": 330, "height": 380}
    }}
  ]
}
```

The generated image should be quiet, wide, palette-consistent, and free of
text, logos, watermarks, and dense detail. Cover and ending images may share a
visual family, but should be separate resources so the ending can feel more
spacious and reflective.
