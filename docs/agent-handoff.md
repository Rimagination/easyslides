# Agent handoff

Read this entry before continuing development. The architecture and workflow
documents linked below remain authoritative for their respective scopes.

- Entry points: `SKILL.md`, `ARCHITECTURE.md`, `workflows/routing.md`.
- Current base: release 1.2.0. Inspect Git status before edits and preserve
  unrelated staged and unstaged work.
- Image reconstruction: `workflows/slide-image-to-editable-pptx.md`. Native
  tables must retain row/column semantics, not become collections of cells
  drawn as independent rectangles and text boxes.
- Verified 2026-09-13: the alignment reader uses `a:gridCol@w` for table column
  widths. The former `cx` lookup yielded zero-width cells and false drift
  failures. `tests/test_alignment_contract.py` covers unequal column widths,
  a multiline cell, and a real column-width drift.
- Focused checks: `python -m unittest tests.test_alignment_contract
  tests.test_validate_image_reconstruction_pptx` (14 tests passed).
- Keep source cell rectangles and source ink bounds distinct. Group complete
  cell text in the geometry inventory and retain its individual paragraphs in
  `source_text_lines`. Render and exercise table edits before delivery.
- Private generated projects, source papers, images, and local runtime caches
  stay outside source commits. Do not publish them through maintenance work.

Further table transformations should be driven by explicit semantic table
regions. Automatic conversion of arbitrary cards or page panels is outside the
current contract and needs a separately defined recognition task.
