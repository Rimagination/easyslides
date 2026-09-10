# EasySlides project rules

## Official template policy (mandatory)

The official academic PPT template set is exactly these seven canonical IDs:

- `academic_general`
- `academic_scqa`
- `defense_leftnav`
- `defense_topnav`
- `literature_minimal`
- `nsfc_defense`
- `thu_speech`

Only these seven templates may be selected by default for a new deck or template
reuse task. `nsfc_defense` is official even though its internal QA/package
status may still say `review`; package review status does not change its project
classification. `thu_speech` is the official Tsinghua speech template and is
selected through its five-shell functional-page contract.

All other template directories, distilled variants, source-faithful candidates,
and style packs are development assets. They are not part of the default
template library and require an explicit user request before restoration or use.
Their current archive is documented outside the repository on F drive.

## Naming rule (mandatory)

Template IDs use one consistent lowercase `snake_case` naming rule. Preserve the
canonical IDs exactly; do not invent fuzzy aliases, rename official templates,
or select a development asset because its visual name appears similar.

The machine-readable source of truth is
`templates/template_policy.json`. The package registry and capability registry
must not be interpreted as permission to use a template outside the official
seven-item set.
