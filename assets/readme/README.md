# README preview assets

All images reuse existing EasySlides renders. No new image generation was used.

- `native-editable.png`: reviewed academic-general ecology report, page 4;
  original Grace et al. (2016) panels with source captions.
- `native-method.png`: the same report, page 6; source-supported editable
  analysis schematic for Duffy et al. (2017).
- `theme-*.jpg`: cover renders from the existing four-theme demonstration,
  using `academic_general/theme_palettes.json` and its discipline theme images.
  Refreshed with the template's lower single-line title placement.
  Theme/discipline combinations are examples, not restrictions.

Paper figures retain the author/year attribution visible in each slide.
Other showcase thumbnails link to the existing public gallery assets.

## Lightweight previews

Run `python scripts/build_readme_assets.py` from the repository root to rebuild
the README image derivatives. It needs Pillow and CairoSVG, and never modifies
the source illustrations, slide renders, or templates.

- `previews/*.webp` are the only large content images embedded by the README.
  Image links retain the full-size sources for on-demand viewing.
- `discipline-themes.jpg` contains the fourteen registered discipline images,
  in manifest order, arranged as two columns and seven rows. It has uniform
  white gutters and contains no added text, labels, numbers, or watermark.
- `template-academic-classic.png` and `template-academic-scqa.png` are example
  cover renders of the corresponding official SVG shells. Their sample text
  is illustrative. The other six template previews use actual deck renders.
- The native-template table uses 480-pixel previews displayed at 160 pixels.
  The original high-resolution figures are loaded only after following a link.
