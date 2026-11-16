import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { Context } from '@deepseek-ai/cordis';
import * as skillService from '@deepseek-ai/dsh-skill';
import yaml from 'js-yaml';
import { apply, createSkillProvider, inject } from '../dsh/index.mjs';

const runtime = new URL('../', import.meta.url);
const expected = ['easyslides', 'easyslides-clarify', 'easyslides-distill'];

test('bundle patch resolves the package entry without overriding host services', async () => {
  const manifest = JSON.parse(await readFile(new URL('../package.json', import.meta.url), 'utf8'));
  const patch = yaml.load(await readFile(new URL(`../${manifest.dsh.bundle.patch}`, import.meta.url), 'utf8'));
  assert.deepEqual(patch, [{ insert: [{ id: 'easyslides', name: manifest.name }] }]);
  assert.deepEqual(inject, ['skills']);
});

test('all three skills load their existing instructions and resolve local resources', async () => {
  const provider = createSkillProvider(runtime);
  const candidates = await provider.list();
  assert.deepEqual(candidates.map(row => row.name).sort(), expected);
  for (const candidate of candidates) {
    const loaded = await provider.get(candidate);
    assert.equal(loaded.source, 'bundled');
    assert.equal(loaded.rank, skillService.BUNDLED_SKILL_RANK);
    assert.ok(loaded.description.length <= 500);
    assert.ok(!loaded.content.startsWith('---'));
    assert.ok(loaded.content.includes('deepseek-harness.md'));
    assert.equal(loaded.resourceBase.path, fileURLToPath(new URL(`skills/${loaded.name}/`, runtime)));
    await readFile(loaded.path, 'utf8');
  }
  const main = await provider.get(candidates.find(row => row.name === 'easyslides'));
  assert.match(main.content, /academic_general/u);
  assert.match(main.content, /theme_image_source/u);
  assert.match(main.content, /MUST ask which production scheme/u);
  assert.equal(await provider.get({ name: '../outside' }), undefined);
});

test('official DSH registry discovers, loads and disposes the plugin skills', async () => {
  const ctx = new Context();
  await ctx.plugin(skillService.default);
  // Use the checkout as the runtime here; the tarball smoke test checks its physical copy.
  const plugin = { name: 'easyslides-test', inject, apply(target) {
    target.skills.registerProvider(() => createSkillProvider(runtime));
  } };
  const fork = ctx.plugin(plugin);
  try {
    const snapshot = await ctx.skills.snapshot({ cwd: fileURLToPath(runtime) });
    assert.equal(snapshot.complete, true);
    assert.deepEqual(snapshot.skills.map(row => row.name), expected);
    for (const skill of snapshot.skills) {
      const loaded = await ctx.skills.get(skill.name);
      assert.equal(loaded.name, skill.name);
      assert.match(skillService.renderSkillContent(loaded), /<skill_instructions>/u);
    }
    // A workspace skill wins over our bundled provider; disposing it restores the package.
    const removeOverride = ctx.skills.register({ name: 'easyslides', description: 'Workspace override', content: 'local', source: 'project-dsh' });
    assert.equal((await ctx.skills.get('easyslides')).content, 'local');
    removeOverride();
    assert.match((await ctx.skills.get('easyslides')).content, /Academic PPTX/u);
    await fork.dispose();
    assert.deepEqual(await ctx.skills.list(), []);
  } finally {
    await ctx.fiber.dispose();
  }
});

test('production apply registers exactly one provider', () => {
  const providers = [];
  apply({ skills: { registerProvider(factory) { providers.push(factory()); } } });
  assert.equal(providers.length, 1);
  assert.equal(providers[0].name, 'easyslides');
});
