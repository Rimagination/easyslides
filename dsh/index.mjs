/** Packaged EasySlides skills; all presentation work uses the shared Python runtime. */
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

export const name = 'easyslides';
export const inject = ['skills'];

const skills = [
  {
    name: 'easyslides',
    description: 'Create, edit, render and review editable academic PPTX presentations with EasySlides. Confirm native editable or image reconstruction production, theme color and theme image source; use academic_general by default for native production. Also supports template reuse and slide image reconstruction. 论文汇报、答辩PPT、可编辑幻灯片。',
  },
  {
    name: 'easyslides-distill',
    description: 'Distill a source PPTX into factual OOXML evidence, reusable semantic layouts, components and symbols with EasySlides. 蒸馏PPT、提取无内容模板、拆分组件与符号资产。',
  },
  {
    name: 'easyslides-clarify',
    description: 'Resolve result-affecting choices before EasySlides production: production scheme, theme color, theme image source and unresolved presentation requirements. Reuse explicit answers and wait for unresolved blocking choices. 制作前澄清需求。',
  },
  {
    name: 'video',
    description: 'Replay PowerPoint slides step by step, record the PowerPoint window to MP4, and edit speed, music, and credits. 逐步演示、录屏、倍速、配乐和花字水印。',
  },
];

/** A bundled provider leaves workspace and user skill overrides at their normal priority. */
export function createSkillProvider(runtimeRoot = new URL('../runtime/', import.meta.url)) {
  const rootPath = fileURLToPath(runtimeRoot);
  const candidates = skills.map(skill => {
    const directory = new URL(`skills/${skill.name}/`, runtimeRoot);
    return {
      ...skill,
      path: fileURLToPath(new URL('SKILL.md', directory)),
      provider: name,
      source: 'bundled',
      rank: 600, // DSH's documented BUNDLED_SKILL_RANK; no second copy of the host service.
      invocation: { modelInvocable: true, userInvocable: true },
      resourceBase: { kind: 'directory', path: fileURLToPath(directory) },
      locator: skill.name,
    };
  });
  return {
    name,
    async list() { return candidates; },
    async get(candidate) {
      const own = candidates.find(row => row.name === candidate.name);
      if (!own) return undefined;
      const text = await readFile(own.path, 'utf8');
      const body = text.replace(/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)/u, '');
      return {
        ...own,
        content: `EasySlides runtime directory: ${rootPath}\nRead ${rootPath}references/deepseek-harness.md for host-specific setup and tools.\n` +
          (own.name === 'easyslides' ? `\nFor a new native academic deck, load ${rootPath}references/academic-native-authoring.md before planning. Use authoring_contract="academic_native.v1", a page_brief (question/information_gain/visual_rationale) per content page, and the registered scientific_composition body with composition.kind="auto", the reading_task and the corresponding evidence from the scientific-composition reference. Density means complementary evidence, comparisons and mechanisms, never filling a character quota. Use source-supported academic judgments; no reading-guide headings or repeated paraphrases. Render the actual PPTX and review its images. If the host model cannot read images, record visual review as unavailable; pixel/ink counts cannot replace it. Preserve user's source permissions; never invent supplied_only, research permission, presenter or timing. Keep package files read-only.\n` : '') +
          `\n${body}`,
      };
    },
  };
}

/** Cordis owns this registration's disposal when the bundle is disabled or removed. */
export function apply(ctx) {
  ctx.skills.registerProvider(() => createSkillProvider());
}
