Use functional_page_variants.json to select one source-faithful variant per functional role. Use body_variants.json for content pages. Preserve source geometry and do not silently merge variant pages.

Before selection, run the EasySlides named-slot geometry gate on the functional registry. Any overlap between editable text slots is blocking unless the variant explicitly declares an intentional pair in `allowed_slot_overlaps`.

Slides 07-10 are one transition series; only the sequence number and photo preset vary.

Source-faithful body pages with pre-drawn colored dots must mark each dot group with `data-easyslides-bullet-for` and `data-easyslides-bullet-index`. The renderer keeps only as many dots as the bound text has visible lines; a one-line payload must never retain a second decorative dot.
