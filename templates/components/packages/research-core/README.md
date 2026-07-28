# Research Core

`research-core` is the first bundled EasySlides component pack. It provides
small, semantic content components instead of prescribing an entire slide.

Each component declares a strict `input_schema`, text capacity, a built-in
renderer id, story fixtures, and the error-level vertical-center invariant for
text inside visual containers. A deck plan should select these components by
content shape and evidence needs; it must not select by visual order alone.

The pack owns its design tokens in `assets/design_tokens.json`. Templates may
use the components as a fallback, but template-scoped components and source
derived body variants remain higher-fidelity choices for a locked template.
