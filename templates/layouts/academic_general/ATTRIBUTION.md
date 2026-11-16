# Attribution & Licensing

Academic PPT Master combines an MIT-licensed PPT generation engine with an academic presentation
layer for paper reading, journal clubs, thesis defense, and group reports. The academic layer defines
a five-module research-report structure, academic visual styles, academic brands, page layouts, and
deck presets. Output is produced as natively editable PPTX through the SVG → DrawingML pipeline.

## Base engine — PPT Master
- Project: **ppt-master** by Hugo He — https://github.com/hugohe3/ppt-master
- License: **MIT**
- The whole engine (`scripts/`, `references/`, `templates/`, `workflows/`, `SKILL.md`) is PPT Master, used under MIT.

## Academic layer — original work
- The academic 5-module preset (mode, visual styles, brands, layouts, decks) is **newly authored
  original content** for this edition. It encodes a paper-reading / journal-club structure
  (研究背景与目的 · 技术路径 · 研讨成果 · 研究结论与讨论 · 展望与借鉴) and established
  presentation-design principles (assertion-evidence, one-message-per-slide, signal-to-noise,
  figure-first), in two density profiles (minimal report · dense defense). Distributable under MIT.

If you redistribute or build on this edition, retain the MIT notice for the PPT Master engine above.

## Additional table-of-contents reference

An earlier contents layout used **Pepentation**, by Plotnikov Daniil, as a
reference: https://github.com/Pepengu/pepentation. Its MIT notice is retained in
`LICENSE.pepentation.txt`. The current contents layout follows the arrangement
of the reference screenshot supplied by the user, while its visible picture is
selected from the presentation's existing cover-image assets and cropped natively.

## Files added beyond the upstream PPT Master engine
Academic layer:
- `references/modes/academic.md`; `references/visual-styles/academic-clean.md`, `academic-defense.md`
- `templates/brands/academic-blue/`, `academic-graphite/`, `academic-navy/`
- `templates/layouts/academic_paper_report/`, `academic_defense_deck/`
- `templates/decks/academic_paper/`, `academic_defense/`

Registrations in `references/visual-styles/_index.md`, `references/modes/_index.md`,
`templates/brands/brands_index.json`, `templates/layouts/layouts_index.json`,
`templates/decks/decks_index.json`; plus `ACADEMIC-EDITION.md`, this file, and
`.claude-plugin/plugin.json`.
