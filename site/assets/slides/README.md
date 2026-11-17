Put exported PPT page images here when the real decks are ready.

Recommended structure:

```text
assets/slides/work-01/slide-01.png
assets/slides/work-01/slide-02.png
assets/slides/work-02/slide-01.png
```

Current real deck:

```text
assets/slides/work-01/slide-01.jpg  literature_minimal
assets/slides/work-01/slide-02.jpg
...
assets/slides/work-01/slide-16.jpg

assets/slides/work-02/slide-01.jpg  defense_leftnav
assets/slides/work-02/slide-02.jpg
...
assets/slides/work-02/slide-29.jpg

assets/slides/work-03/slide-01.jpg  defense_topnav
assets/slides/work-03/slide-02.jpg
...
assets/slides/work-03/slide-29.jpg

assets/slides/work-04/slide-01.jpg  nsfc_defense
assets/slides/work-04/slide-02.jpg
...
assets/slides/work-04/slide-14.jpg

assets/slides/work-05/slide-01.jpg  thu_speech
assets/slides/work-05/slide-02.jpg
...
assets/slides/work-05/slide-16.jpg

assets/slides/work-06/slide-01.jpg  zdyf_blue
assets/slides/work-06/slide-02.jpg
...
assets/slides/work-06/slide-12.jpg

assets/slides/work-07/slide-01.jpg  nsfc_green — plant functional ecology
...
assets/slides/work-07/slide-14.jpg

assets/slides/work-08/slide-01.jpg  nsfc_bright_blue_white — multimodal traffic
...
assets/slides/work-08/slide-12.jpg

assets/slides/work-09/slide-01.jpg  academic_general — biodiversity and productivity
...
assets/slides/work-09/slide-16.jpg

assets/slides/work-10/slide-01.jpg  academic_general — global soil bacteria
...
assets/slides/work-10/slide-14.jpg
```

The two new galleries use actual PowerPoint renders of their downloadable PPTX
files. The traffic public copy removes local machine path prefixes from speaker
notes only; slide XML and media are unchanged. Original paper citations remain.
Its five source-comparison threshold failures are disclosed in the gallery.

The native `academic_general` case in `work-09` uses the 16 PowerPoint-rendered
pages from `projects/ecology_high_density_green_20261116/academic_general`.
Its download, `assets/decks/biodiversity-productivity-2017-native.pptx`, is an
unchanged copy of `biodiversity_productivity_2017.pptx`. The public previews are
1600 × 900 JPEG conversions of the corresponding rendered PNGs.

The native `academic_general` case in `work-10` is the 14-page blue (#0046A5) soil-bacteria report. Its public previews are 1600 × 900 JPEG conversions of its PowerPoint renders.

Register page paths in `slideAssets` inside `index.html`. Each matching
`copy.*.works` item ends with the template ID and PPTX download path. Keep both
language arrays and `workRoutes` in the same stable index order; use
`workDisplayOrder` to feature new work without changing published detail links.
Routes are `native` (原生生成) and `rebuild` (生图重建). The detail page places
the selected image inside the photo screen area.

Scene photo screen regions are defined as CSS percentages in `index.html`:

```text
seminar   assets/scenes-16x9/seminar-hall.webp x 24.04%, y 17.95%, w 52.16%, h 47.86%
classroom assets/scenes-16x9/classroom.webp    x 22.24%, y 18.59%, w 54.57%, h 49.57%
meeting   assets/scenes-16x9/meeting-room.webp x 24.04%, y 17.73%, w 52.04%, h 47.86%
display   assets/scenes-16x9/meeting-room.webp x 23.43%, y 22.44%, w 53.00%, h 52.99%
```

The `assets/scenes-16x9` images are center-cropped from the originals to `1664x936`, a strict 16:9 ratio. Public pages should load the `.webp` variants first and keep PNG only as a fallback.
