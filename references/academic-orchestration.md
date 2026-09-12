# Academic Orchestration

Use this reference for every academic deck before content planning, regardless
of template or production scheme. For edits, apply only within the requested
scope. An approved image deck being reconstructed retains its content, order
and geometry; narrative redesign requires separate user authorization.

## Academic intake: adaptive, evidence-aware

Inspect messages and accessible materials first, then ask one consequential
native-popup question at a time. No browser onboarding. A supplied file does
not establish its intended role, permission to supplement it, or the audience.
Read the file to discover its contents; ask the user about intent and priorities.

Keep a compact `academic_brief` in the existing project requirements notes;
after clarification, carry it into `deck_plan.json`. Record each fact's origin
(user message or inspected file locator), unresolved items and conflicts.
Initialize new academic content work using `clarify init --academic`. Store
answers in the existing clarification state; `clarify next` chooses unresolved
academic questions and source-inspection work, and `clarify require` blocks
incomplete records. Its `decisions` become the plan's `academic_brief`.
The brief is agent-maintained; the validator checks recorded completeness,
not semantic truth or whether an agent really inspected a cited file.

| Required understanding | Inspect or ask | Consequence |
|---|---|---|
| Topic, occasion, outcome | Ask what the audience should understand, evaluate or decide; distinguish review, defense, proposal and teaching | Choose scenario and central question |
| Evidence acquisition | Ask supplied-materials only, agent research, or supplied materials plus authorized supplementation, unless explicit | Select extraction/research/hybrid workflow; no silent external supplementation |
| Material contents and roles | Inspect text, figures, tables, captions, methods, results and references; distinguish primary evidence, background, old deck and visual-only template | Inventory usable evidence; a template is not a scientific source |
| Audience | Ask discipline, familiarity and main concerns where unknown; committee membership alone does not imply subject expertise | Set explanation depth and anticipated objections |
| Duration and delivery | Ask speaking minutes, whether Q&A is included, live talk versus self-reading, and any hard page limit | Allocate time and main/backup pages; page count is not speaking time |
| Desired style | Ask visual tone and reference/template preference; inspect an explicit reference first | Choose design within the official template policy; no automatic blue palette |
| Content boundaries | Ask must-include findings/figures, excluded or confidential content, and permission to reorder/condense | Preserve source meaning, figures and explicit outline |
| Production and editability | Reuse the existing production-scheme and reconstruction-mode questions and cost disclosure | Lock the actual generation/reconstruction route |

Ask only missing information that changes the result. Do not force all rows
into one form or demand a preference the user has explicitly delegated.
Record a delegated choice as delegated, with the chosen value and reason.
Free-text answers retain their exact meaning; the option catalog is not exhaustive.

Conditional follow-ups:

- Research or hybrid: clarify the research question, discipline boundary,
  literature time range/recency, desired breadth and source restrictions.
  Offer a concrete bounded search scope for user acceptance if unspecified.
  Use `workflows/topic-research.md`; record searches, primary sources and figure
  provenance. Label the limits of a rapid review; do not claim systematic coverage.
- Supplied files: inventory each file's role, readable sections, source-located
  claims and reusable original figures. Report missing captions, unreadable
  scans, absent supplements or contradictory versions. Request only the missing
  material needed for the agreed claims. Never ask the user to summarize a file
  the agent can read, or imply inspecting a file based on its name alone.
- Scientific figures: preserve original axes, legends, units and relevant
  captions; link to paper/figure/page. Generated explanatory illustrations are
  labeled as illustrations and cannot substitute for measured results.
- Time/content conflict: offer main-talk plus backup, reduced coverage or more
  time. Do not quietly omit protected evidence or promise exhaustive coverage.
- Fixed outline or approved image pages: preserve it; ask only about actual gaps
  within scope, not permission to repeat already approved creative decisions.

## Internal orchestration and handoffs

1. **Intake:** inspect available sources, fill the brief and resolve material
   ambiguities. No generation while outcome, evidence acquisition or relevant
   fidelity boundaries are unresolved. State the agreed brief once; no repeated
   confirmation of explicit answers.
2. **Evidence preparation:** route to supplied-source extraction, authorized
   topic research, or both. Reuse `source_map`, paper intake and figure manifests.
   Record source locations and distinguish reported findings, synthesis and
   unverified hypotheses. Missing evidence returns to a focused material question.
3. **Narrative planning:** apply audience-state transfer and the chosen scenario
   profile. Build the core question, supported answer, evidence chain and limits.
   Preserve user outlines first. Literature reviews organize comparisons around
   research questions; defenses connect contributions to evidence; proposals
   distinguish hypotheses from results. SCQA is optional, not a universal outline.
4. **Page planning:** use the existing `deck_plan.json` and content/design plans.
   Each content page records its question, claim, source-located evidence,
   contribution to the audience goal and approximate speaking time. Account for
   transitions and Q&A separately; split main and backup pages when agreed.
5. **Visual production:** select the permitted template after the content need is
   understood, respecting a template already selected by the user. Follow the
   locked route. ImageGen receives actual reference images; the approved complete
   page image becomes the reconstruction source, without template substitution.
6. **Verification:** use existing academic and route-specific QA; check claims,
   citations, original-figure fidelity, information density, timing plausibility,
   native editability, alignment, overlap and consistent pagination. Content
   failures return to evidence/planning; visual failures return to rendering.
   A brief or catalog marked complete cannot waive visual QA.

The machine brief uses grouped free-text fields `academic_goal`, `talk_timing`,
`style_intent`, `content_boundaries`, plus `audience`, `source_policy`, conditional
`material_inventory`/`research_scope` and existing route decisions. Preserve the
confirmed decisions verbatim in `academic_brief`; keep derived timing, narrative,
unresolved questions and conflicts in planning notes, not silently rewritten
answers. Answer provenance is retained in the clarification record's
`answer_origins`; prefilled facts should include locators in the project notes.
Use explicit “not applicable”, “no hard limit” or user-delegated values where
appropriate; never fabricate precision.

The principle is adapted from LearnPrompt's Humanize PPT / AST framing:
a deck is not an information container; it is an audience-state transfer
artifact. EasySlides keeps that idea as a planning contract, then renders the
deck through its own SVG-to-PPTX path.

## Audience-State-Transfer

Before choosing slides, answer:

| AST item | Academic planning question |
|---|---|
| Audience | Who is listening, what do they already know, and what do they resist or overlook? |
| Initial state | What would they believe, miss, or be unsure about before the deck? |
| Desired state | What should they understand, trust, or decide after the deck? |
| Core tension | What gap, puzzle, limitation, or disagreement makes the talk worth hearing? |
| Transfer path | How does each slide move the audience one step from initial state to desired state? |

Every newly authored main-talk content slide should create one audience-state shift.
Preserve required reference/backup pages and protected source pages; flag weak
progression rather than silently rewriting content outside the authorized scope.

## SCQA For Academic Decks

SCQA is one available narrative spine for general academic material. The user's
outline and scenario-specific story spine take precedence:

| Phase | Academic role |
|---|---|
| Situation | Establish shared context: field state, research object, known method, dataset, or practical need. |
| Complication | Name the gap: unresolved mechanism, limitation, contradiction, missing evidence, or operational bottleneck. |
| Question | Condense the scientific or technical question into a testable decision point. |
| Answer | Present method, evidence, result, implication, and next step. |

SCQA is a spine, not a table of contents. A phase may span several pages, and
the Answer phase usually needs the most space. For source-faithful academic
work, keep the source's claims and evidence intact while using SCQA only to
arrange the audience path.

## Human-Facing Language

Slide text faces the audience, not the generator. Avoid developer-facing
language such as template, slot, placeholder, executor, renderer, generation,
pipeline, or implementation unless the talk is explicitly about software
development.

Rule phrase for downstream checks: avoid developer-facing language in visible
slide text and speaker-facing plans.

Use:
- claim titles instead of topic labels;
- evidence captions instead of internal notes;
- speaker-intent notes instead of process traces;
- concrete nouns and verbs instead of filler summary voice.

## Template Roles

`academic_general` is the neutral general academic base. It should handle broad
academic talks, course reports, research progress, thesis-adjacent summaries,
and scholarly exchanges when no stronger scenario template is selected.

`academic_scqa` is the structured argument variant. Use it when the material
benefits from visible SCQA progression, technical-report density, method/result
evidence blocks, or a more institutional blue-cyan identity.

Both templates must preserve source faithfulness for papers, theses, and mature
reports. External material can support missing context only when the user asks
for research or supplementation.
