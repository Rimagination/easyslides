# Institutional logos

[ScanSci Logos](https://www.scansci.com/logos/) is EasySlides' online resource
for university emblems and institutional brand marks. Its public read-only API
requires no login or API key. The authoritative interface is the
[OpenAPI specification](https://www.scansci.com/api/logos/openapi.json).

## Identification and lookup

Replace an institutional `LOGO` or degree-cap placeholder only after the user's
institution is identified from an explicit statement, an institution field in
the brief, or an unambiguous presenter affiliation in supplied material. A
paper-author affiliation is usable only when the user is clearly that author.
Template names (including `thu_speech`), palette, topic, example labels, and
institutions mentioned in references provide no affiliation evidence. Preserve
the placeholder when multiple presenter affiliations conflict.

Prefer an institution-matching logo supplied by the user. Otherwise run:

```powershell
python scripts/easyslides.py logo <project> --institution "清华大学" --variant emblem
```

An official domain such as `tsinghua.edu.cn` also works. Pass the identified
name/domain, rather than a complete brief or a list of guessed institutions.
The helper calls `/api/logos/resolve`; it never selects the first search result.
Without `--institution`, it records a fallback and makes no network request.

## Intelligent matching during generation

Once the user's institution is identified, resolve and add its logo during
normal deck generation without a separate approval round. Prefer existing logo
frames; choose the mark from the frame proportions and page role:

- Compact or square badge / degree-cap placeholder: use `emblem` for a
  university, or `brand` for another institution.
- Wide cover or header frame that includes the institution name: prefer
  `lockup_horizontal`; use `wordmark` when the frame calls for the name only.
- Tall or stacked identity frame: prefer `lockup_vertical`.
- No logo frame: a cover or ending may use clear space inside the template's
  safe margins. Content pages use an established header logo position when
  available. Preserve title/body size, scientific figures, citations and counters;
  leave the logo out when no placement fits.

Choose a transparent, reviewed asset with enough resolution. Preserve its
colors and aspect ratio. On a dark or busy background, use an available reviewed
contrast-compatible asset or a quiet backing within the frame. Never redraw a
seal, fabricate a lockup, stretch, crop, or recolor the mark to match a palette.

A user-locked variant remains exact. If the agent-selected variant is missing,
it may call the helper once without `--variant` to obtain the provider's default
mark for the same institution; use it only when it fits the frame. Unknown or
ambiguous identity, unavailable images, or network failure keep the placeholder.

Use one institution ID throughout the deck, with a recorded role-to-asset map
(cover, header, footer, ending). Repeat the same asset and placement within each
role; different roles may use different reviewed variants from that institution.
Save each resolved result in the existing asset inventory before another lookup
updates `institution_logo.json`. The cache retains every downloaded revision.

Template logos identify the source template. In a new deck, replace that mark
with the identified user's institution, or normalize it to the neutral
placeholder when no user institution is known. Preserve original references.
For identity-preserving edits, follow the user's permitted change scope.

| Need | Variant |
| --- | --- |
| University emblem / degree-cap replacement | `emblem` |
| Company or other institution's brand mark | `brand` |
| Wide logo with name | `lockup_horizontal` |
| Stacked logo with name | `lockup_vertical` |
| Name-only mark | `wordmark` |

Omitting `--variant` uses the provider's default emblem/brand selection. An
user-specified variant must exist; a different variant is never silently
substituted. Each 404, 409, missing image/variant, unreviewed asset, timeout, or
invalid-image lookup records `status: fallback`; its output keeps the placeholder.
409 candidates are recorded for later identification, without downloading one.

## Asset handoff and placement

Read `<project>/assets/logos/institution_logo.json`. A `resolved` result gives a
project-relative `asset_path` to the original transparent PNG/WebP, actual pixel
dimensions, institution identity, variant, and the provider's source/license
metadata. Downloaded images are validated before an atomic write and reused
for the same published revision. Native SVG availability remains in
`metadata.svg_url`; preserve the supplied metadata and source attribution.
Record affiliation evidence and the selected asset in `design_spec.md` or the
existing asset/provenance inventory.

- SVG/native construction: place the asset in the template's existing `LOGO`
  frame with aspect ratio preserved (`contain` / `xMidYMid meet`). Replace the
  full placeholder group or hide its degree-cap drawing and sample label.
  A text-kind `LOGO` slot needs an image element in that frame; writing the
  filename into the text slot does not insert a logo. Keep source templates
  unchanged and apply the replacement in the generated deck.
- ImageGen schemes: include the downloaded logo as an actual reference image
  alongside the selected template; specify its frame, original colors, and
  exact institution. Use that asset in editable reconstruction too. Preserve
  approved original reference images and record any logo normalization.
- Native PPTX template fill: replace the corresponding logo picture/placeholder
  in the deck copy using the existing native route, preserving its frame.
  Reconstruction/beautification that preserves a supplied deck's identity only
  changes a logo when that edit is within the user's requested scope.

Apply the recorded institution and role-to-asset map to the deck's institutional
logo slots. Generic education icons inside content diagrams retain their
semantic role. Inspect the rendered logo for aspect ratio, contrast, cropping,
and any leftover degree-cap or sample label. Preserve the deck-wide pagination
contract and existing footer validation.
