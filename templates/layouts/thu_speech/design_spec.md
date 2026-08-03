# thu_speech

This is the official source-faithful THU speech template rebuilt from the 29-slide source PPTX.

## Functional-page selection

The source deck has four functional page roles with variants:

- cover: source slides 1-3
- toc: source slides 4-6
- transition: source slides 7-10, represented as one shared transition series
- ending: source slides 27-29

Slides 07-10 share one transition layout; only the sequence number and photo preset vary.

Generation selects one explicit variant from each requested role. No source page is promoted as the only canonical form. See `functional_page_variants.json`.

Content slides 11-21 and 23-26 remain source-faithful body variants under `04_content.svg`. Source slide 22 is excluded per project review.

## Fidelity rules

Preserve source photo crops, purple/blue palette, title treatment, rotated labels, card geometry, and page-specific cover/ending compositions. Do not redesign a functional page into a generic card layout.

## Selection and overflow

Choose a functional variant first, then bind declared slots. For content, choose a body variant after the shared header. If text does not fit, select another source page variant or split the material before shrinking typography.
