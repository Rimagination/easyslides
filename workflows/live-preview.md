---
description: Start the browser SVG editor when it is not running, and apply submitted annotations after Step 7 export
---

# Live Preview Workflow

## Original imagegen preview and selective reconstruction

When the user wants to mark elements on the imagegen version, preview the original
generated images directly. Do not use reconstructed SVGs, editable PPTX renders,
or a revised layout as the annotation reference. This mode runs before PPT export
and does not require the Step 7 gate below.

```powershell
python scripts/svg_editor/server.py <project_path> --source-images <original_image_directory> --timeout 0
```

Use the Codex in-app browser's built-in annotations. The page is a read-only
original-image viewer with thumbnails, page navigation and zoom. Do not add a
second rectangle-drawing layer, annotation form, or submit button to the page.
Open a specific slide with `?slide=slide_012.png`; page navigation updates the URL
and document title so browser feedback identifies the source slide. The visible
`#original` image exposes `data-source-slide`, `data-source-version`,
`data-source-width` and `data-source-height`, and its `src` references the original
image bytes. Leave the image unobstructed for browser annotation targeting.

Built-in browser feedback arrives in the conversation. It is not automatically
written to `source_image_review.json`, and the preview does not trigger a rebuild.
The earlier JSON records and API remain compatible for already submitted work;
the new viewer never saves, deletes, or resets those records.

When the user asks to apply these annotations:

1. Read the submitted browser feedback, source-page URL and any attached screenshot
   or element context in the conversation. Resolve the exact original slide from
   the filename, not the currently active browser tab. For earlier custom-form
   submissions, run `python scripts/check_annotations.py <project_path>`. An empty
   JSON queue does not mean that no built-in browser feedback was submitted.
2. Inspect the original image and selected region. Use the note to determine the
   semantic object; a rectangle can contain background or neighboring objects
   that the user did not ask to rebuild. Compare source dimensions/version with
   the submitted context when present; ask again if the source changed. For
   screenshot-coordinate selections, account for the displayed image's position
   and scale before mapping to original pixels. Browser element selection may
   identify the whole slide image, so use the note and screenshot to locate the
   requested object. If the exact object remains ambiguous, ask one concise
   question; do not invent a bounding box or rebuild the whole page.
3. Reconstruct only requested objects with `scansci-svg`, preserving their
   original position, content and relationships. Unselected content remains from
   the original image, except necessary local background recovery. Do not reuse
   the previously simplified editable PPT as the visual reference.
4. Preview the local replacement against the original, disclosing necessary
   background recovery or simplification. For targets with unresolved boundaries,
   obtain clarification before replacing nearby content.
5. Assemble the accepted vectors/text with the retained image content using the
   existing native PPT export path. Verify the replacement is editable and that
   untouched areas have not changed. Report completion against the submitted
   browser notes and show a comparison separately, leaving the preview on the
   original. For legacy JSON records only, mark completed IDs as `applied` and
   advance the revision to prevent stale writes. Do not claim to resolve a native
   browser comment programmatically without a supported integration.

The existing SVG-element workflow below remains available for editing an already
constructed SVG. Its export prerequisite does not apply to original-image review.

> **Purpose**: (1) start/reopen the browser SVG editor when no preview service is currently running, and (2) apply user-submitted annotations after Step 7 export completes.
>
> **Not in scope**: Executor's mandatory auto-startup — that lives in [`SKILL.md`](../SKILL.md) Step 6. Do not re-launch a preview that is already running.

## When to Run

- **Start (Step 1)** — preview service is not currently running and the user wants to look at the deck or click an element. Typical cases: post-export re-entry in a fresh chat, or the user clicked **Exit preview** earlier and now wants it back.
- **Apply annotations (Step 2)** — Step 7 has produced at least one PPTX, and the user signals that submitted annotations should now be applied. Triggers include:
  - quoting the browser prompt (`Annotations saved. ... apply my annotations ...`)
  - saying `apply my annotations` / `apply my edits` / `应用注解` / `开始应用` / 等价表达

## When NOT to Run

- The preview service is already running → just give the user the URL; do not restart.
- The user gave a precise chat edit ("change page 3 title to X") → edit the SVG directly.
- The user wants a full regeneration → use the main workflow.
- Step 7 has never run for this project → annotations cannot be applied yet; finish the main pipeline first.

---

## Step 1: Start / reopen the editor

**Precondition**: no preview service running on this project.

```bash
python3 ${SKILL_DIR}/scripts/svg_editor/server.py <project_path>
```

(Plain mode — no `--live`. The `--live` flag is reserved for Step 6's auto-startup.)

The server binds `127.0.0.1:5050`, opens the browser on a local desktop, and edits `<project_path>/svg_output/` in place. After it prints `SVG Editor running at http://localhost:5050`, tell the user in their language, in one short message:

- editor is at `http://localhost:5050`
- click an element → write the change → click **Submit annotations** → return to the chat and say `apply my annotations` (or quote the browser prompt)
- to skip the editor, just describe the change in chat

Do not wait for confirmation before launching — the user already asked for preview, so launching is the response. Port conflicts → `--port <other>` and report the new URL. Remote access → see the appendix.

---

## Step 2: Apply submitted annotations

🚧 **GATE**: `<project_path>/exports/` contains at least one `*.pptx` (Step 7 has completed). If not, do not apply annotations — tell the user to finish the main pipeline first.

Triggered by the user signals listed in "When to Run".

1. Discover annotations:
   ```bash
   python3 ${SKILL_DIR}/scripts/check_annotations.py <project_path>
   ```
   The output already lists each pending change as `file → element_id → annotation text → content preview`. Use it directly as the to-do list; no need to re-parse SVG attributes yourself.
2. If the output says no annotations: tell the user, stop.
3. For each listed annotation:
   - Edit the targeted element in `<project_path>/svg_output/<file>` per the annotation text.
   - Remove `data-edit-target` and `data-edit-annotation` from that element.
4. Re-export:
   ```bash
   python3 ${SKILL_DIR}/scripts/finalize_svg.py <project_path>
   python3 ${SKILL_DIR}/scripts/svg_to_pptx.py <project_path>
   ```
5. Tell the user (in their language): annotations applied, new PPTX exported, preview is still running. If the browser still shows the old slide, refresh or reselect the page.
6. Loop: more annotations submitted → repeat from step 1. User signals done or "stop preview" → end.

---

## Notes (editor invariants — referenced from SKILL.md Step 6)

- **UI**: bilingual (EN/中); auto-detects from `navigator.language`, persists in `localStorage`, toggled via the **中 / EN** button on the right panel. Slide navigation: first/prev/next/last buttons at the top of the center panel, plus `←` / `→` / `Home` / `End` (suppressed while typing in the annotation textarea).
- **Buttons**: `Add annotation` stages locally; `Submit annotations` writes to disk and keeps the service running; `Exit preview` is the only UI action that stops Flask.
- **Stop conditions**: once started, the service runs until the user clicks **Exit preview** in the browser, or asks in chat to stop it.
- **Port**: default `5050`; override with `--port <other>`.
- **Idle timeout**: plain mode `900s`, `--live` mode `0` (disabled); override with `--timeout <seconds>`.
- **Transient ids**: each element gets a temporary `_edit_N` id while the editor is running. On save, only annotated elements keep their id; unannotated `_edit_N` ids are stripped before write-back.
- **Browser preview**: the server inlines `<use data-icon>` placeholders and serves `images/*` so SVG renders correctly; the on-disk SVG is unchanged by this preview.

---

## Appendix: Remote access

If the project lives on a remote Linux server, run with `--no-browser`:

```bash
python3 ${SKILL_DIR}/scripts/svg_editor/server.py <project_path> --no-browser
# or for Step 6's auto-startup on a remote host:
python3 ${SKILL_DIR}/scripts/svg_editor/server.py <project_path> --live --no-browser
```

- **VS Code / Cursor Remote-SSH**: open the **PORTS** panel (`Ctrl+Shift+P` → `Ports: Focus on Ports View`), click **Forward a Port**, enter `5050`. The workspace remembers it.
- **Termius**: open the **Port Forwarding** module from the left sidebar (top-level, not nested). Add a rule with **Type = Local**, Host = your remote, Binding `127.0.0.1:5050`, Destination `127.0.0.1:5050`. Save, then start the rule (▶ button).
- **Plain SSH**: `ssh -L 5050:127.0.0.1:5050 <user>@<host>` (or add `LocalForward 5050 127.0.0.1:5050` to `~/.ssh/config`).

Then open `http://localhost:5050` in your local browser.
