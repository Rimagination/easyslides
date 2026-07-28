# EasySlides Component Packs

This directory documents the community component pack format. A pack is a small,
versioned, declarative asset bundle that can be installed into
`templates/components/installed/<pack_id>/`.

```text
my-pack/
  pack.json
  README.md
  assets/
    asset_manifest.json
  components/
    my_component/
      component.json
      stories/
        default.json
        dense.json
        overflow.json
```

The pack manifest uses `easyslides.component_pack.v1`:

```json
{
  "schema_version": "easyslides.component_pack.v1",
  "pack_id": "environment-kit",
  "version": "0.1.0",
  "display_name": "Environment Kit",
  "description": "Reusable environmental science slide components.",
  "license": "MIT",
  "trust": {
    "mode": "declarative_only",
    "permissions": [],
    "code_execution": false
  },
  "dependencies": {
    "component_packs": []
  },
  "design_tokens": {
    "mode": "self_contained",
    "source": "assets/design_tokens.json",
    "required": [
      "color.accent",
      "surface.panel",
      "text.primary"
    ]
  },
  "components": [
    {
      "component_id": "my_component",
      "path": "components/my_component"
    }
  ]
}
```

`design_tokens.required` is a fail-closed list of semantic token paths. A
`self_contained` pack must ship those values in its local JSON file. A
`template_inherit` pack may omit a local source, but its host template must
provide the required token contract. Dependencies are declarative only: each
entry in `dependencies.component_packs` declares a `pack_id`, a version range,
and optionality. Component packs cannot download code or execute it at install
time.

`component.json` must include an `input_schema` using
`easyslides.component_input_schema.v1`. The schema validates story payloads
before renderer-specific capacity checks. It supports only objects, arrays,
strings, numbers, integers, booleans, bounds, required fields, and the explicit
`additional_properties` switch; executable JSON-schema features are excluded.

`component.json` may set `renderer_id` to one of the built-in renderers such as
`evidence_stack`, `three_card_summary`, or `kpi_row_3`. This lets a community pack
add a domain-specific component id and stories while keeping SVG/PPTX output
editable and center-aligned. A new renderer is a core EasySlides change and is
not shipped as executable code inside a pack.

Validate and install a local pack:

```bash
python scripts/easyslides.py component validate <pack-directory>
python scripts/easyslides.py component install <pack-directory>
python scripts/easyslides.py component list
python scripts/easyslides.py component update <pack-directory>
python scripts/easyslides.py component rollback <pack-id>
python scripts/easyslides.py component remove <pack-id>
```

GitHub sources are supported with `github:owner/repository` and an optional
`@tag` or `@branch`. The pack itself cannot contain executable code. New renderer
backends must be implemented and reviewed in EasySlides before a pack can use
them; this keeps component installation separate from code execution.

## Marketplace And Choice Review

`templates/components/marketplace.json` is a small, reviewable marketplace
catalog. It does not bypass the pack contract and it cannot publish executable
plugins. Search or install a verified entry with:

```bash
python scripts/easyslides.py component-market search research --tag academic
python scripts/easyslides.py component-market install research-core
```

For a deck plan, the component workflow produces a choice-review JSON and HTML
page with a recommended component and alternatives for every slide:

```bash
python scripts/easyslides.py component-workflow deck_plan.json --out build/component_workflow
```

To lock a reviewed candidate, add this semantic field to the relevant slide:

```json
{
  "component_requirements": {
    "selected_asset_id": "component_package/three_card_summary"
  }
}
```

The lock remains subject to template affinity and the declared input/capacity
contract; it is not a way to force an arbitrary component into a page.

The bundled `research-core` pack is the reference implementation. Its six
components are stored under `templates/components/packages/research-core/` and
are available to the registry without a separate installation step.

During installation EasySlides generates `assets/asset_manifest.json` with stable
asset ids, MIME types, byte sizes, and SHA-256 hashes. The installed pack also
receives `pack.lock.json`, recording the requested source, resolved Git commit
when applicable, and the pack content hash. Previous versions are archived under
`.archive/` and do not participate in active component selection.
