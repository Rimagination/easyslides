# University Emblem PNG Assets

This folder contains school emblem images exported from:

`D:\PPT skill\PPT模版\赠送校徽资料\大学校徽.pptx`

## Contents

- `png/`: 124 unique transparent PNG emblem assets.
- `manifest.json`: asset metadata, source media names, slide/shape first occurrence, and all PPT occurrence records.
- `school_index.json`: manually identified school-name index for the exported PNG assets.
- `_catalog/contact_sheet.png`: visual contact sheet for quick browsing.
- `_originals/png/`: backups for assets that were cropped or recomposed after export.

## Naming

Assets are named by first visual occurrence order in the source deck:

`png/university_emblem_001.png` through `png/university_emblem_124.png`

The source PPT contains 140 picture occurrences; duplicated image blobs are stored once and tracked through `occurrence_count` and `occurrences` in `manifest.json`.

`university_emblem_124.png` is a transparent web-fallback addition for East
China Normal University, recorded with its source URL in `manifest.json` and
`school_index.json` because it was not present in the original PPT-exported set.
`svg/ecnu_logo_wordmark.svg` is a later user-supplied ECNU horizontal wordmark;
`png/ecnu_logo_wordmark.png` is its transparent PNG render for PPT pipelines that
consume raster images.

## School Name Index

`school_index.json` maps each exported PNG id to a Chinese and English school
name. The mapping was read from the visible text in the logo images, so treat it
as a practical lookup index rather than an official trademark verification.

Some source PNGs contained multiple logo variants in one image. Processed assets
are marked in `manifest.json` with `processed: true`, a `processing_note`, and
an `original_backup` path.
