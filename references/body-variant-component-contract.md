# Body Variant Component Contract

EasySlides separates page structure from reusable visual modules:

```text
shell -> body variant regions -> ordered component_refs -> component assets
```

- A shell owns fixed page chrome and the open content region.
- A body variant owns page-level composition, named regions, selection, and
  variant slots.
- A component owns one reusable visual module, its renderer, local slots,
  capacity, geometry, and QA.
- Charts, icons, symbols, and media are lower-level component dependencies.

New body variants use `component_refs`. The legacy string-only `components`
field remains readable but is not written by new distillation output.

```json
{
  "variant_id": "evidence_triptych",
  "composition_mode": "ordered_component_refs",
  "slots": ["CLAIM", "FIGURE_1", "FIGURE_2", "FIGURE_3"],
  "component_refs": [
    {
      "asset_id": "component/nsfc_defense/key_point_bar",
      "instance_id": "claim_bar",
      "role": "claim",
      "order": 1,
      "required": true,
      "region": "claim",
      "slot_bindings": {
        "text": "CLAIM"
      }
    }
  ]
}
```

`region` resolves the component instance to one body-variant frame.
`slot_bindings` maps a component-local slot to a body-variant slot. Empty
bindings are valid only for fixed or decorative components that own no
required material slots.

Rules:

- `asset_id` must resolve through the global component registry or the
  template's `component_catalog.json`.
- `instance_id` must be unique inside one body variant.
- `order` starts at 1 and is contiguous.
- Composable variants must declare positive-size regions. Every component
  instance must resolve through `region` or an explicit `placement`.
- Required references fail closed when unresolved.
- Component-local and body-variant target slots must exist when bindings are
  declared.
- Every required component-local slot must be bound.
- Component order and dependencies must survive into `component_plan.json`.
- A body variant with no component dependencies declares an empty
  `component_refs` list and an explicit open-composition mode.

Validate a template with:

```powershell
python scripts/body_variant_contract.py templates/layouts/<template_id> --json
python scripts/template_compiler.py templates/layouts/<template_id> --write --json
python scripts/slide_compiler.py deck_plan.json --template <template_id> --out slide_ir.json --svg-out rendered_svg --pptx-out output.pptx
```
