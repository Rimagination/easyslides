"""Regression cases from the Harness density/layout audit."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from xml.etree import ElementTree as ET

from scripts.body_variant_adapter import validate_body_variant_payload

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'templates/layouts/academic_general'


def test_figure_interpretations_preserve_content_and_separate_text_groups():
    from scripts.academic_composition import render_composition
    ns = {'s': 'http://www.w3.org/2000/svg'}
    facts = [{'heading': h, 'text': '景观中不同要素之间具有动态联系，变化需要结合时空尺度观察。'}
             for h in ['符号结构', '取象', '观察方式', '解释边界']]
    composition = {'kind': 'figure_analysis', 'figure': {'path': 'f.png', 'caption': '示意图', 'aspect_ratio': 1}, 'facts': facts}
    root = render_composition(composition, image_resolver=lambda _: 'f.png', colors={})
    texts = [node for node in root.findall('.//s:text', ns) if node.get('data-text-role') != 'caption']
    assert len(texts) == 8
    for index, fact in enumerate(facts):
        heading, body = texts[2 * index:2 * index + 2]
        assert ''.join(heading.itertext()) == fact['heading']
        assert ''.join(body.itertext()) == fact['text']
        assert heading.get('data-pptx-textbox') == body.get('data-pptx-textbox') == 'true'
        if index:
            previous = texts[2 * index - 1]
            assert float(heading.get('data-pptx-box-y')) - (float(previous.get('data-pptx-box-y')) + float(previous.get('data-pptx-box-h'))) >= 16 - 0.01


def test_dense_facts_use_spaced_inline_groups_when_stacked_cannot_fit():
    from scripts.academic_composition import render_composition
    ns = {'s': 'http://www.w3.org/2000/svg'}
    facts = [{'heading': h, 'text': '景观中不同要素之间具有动态联系，变化需要结合时空尺度观察。'}
             for h in ['符号结构', '取象', '观察方式', '解释边界']]
    c = {'kind': 'figure_analysis', 'figure': {'path': 'f.png', 'caption': '示意图', 'aspect_ratio': 1}, 'facts': facts}
    root = render_composition(c, image_resolver=lambda _: 'f.png', colors={})
    texts = [n for n in root.findall('.//s:text', ns) if n.get('data-text-role') != 'caption']
    for i, fact in enumerate(facts):
        heading, body = texts[2*i:2*i+2]
        assert ''.join(body.itertext()) == fact['text']
        assert float(heading.get('data-pptx-box-y')) == float(body.get('data-pptx-box-y'))
        assert float(heading.get('data-pptx-box-x')) < float(body.get('data-pptx-box-x'))
        if i:
            prev = texts[2*i-1]
            assert float(body.get('data-pptx-box-y')) - (float(prev.get('data-pptx-box-y')) + float(prev.get('data-pptx-box-h'))) >= 16 - 0.01


def test_comma_separated_numbers_never_break_across_lines():
    from scripts.academic_composition import _wrap
    text = '面积由约 308 增至 1,302 平方千米。'
    for width in (100, 130, 160, 190, 220):
        lines = _wrap(text, width, 24)
        assert any('1,302' in line for line in lines)


def test_inline_fact_layout_rejects_unfittable_text_instead_of_shrinking():
    import pytest
    from scripts.academic_composition import render_composition
    composition = {'kind': 'figure_analysis', 'figure': {'path': 'f.png', 'caption': '示意图', 'aspect_ratio': 1},
                   'fact_layout': 'inline', 'facts': [{'heading': '条件', 'text': '说明' * 500}]}
    with pytest.raises(ValueError, match='capacity'):
        render_composition(composition, image_resolver=lambda _: 'f.png', colors={})


def test_mixed_fact_groups_also_get_visible_separation():
    from scripts.academic_composition import render_composition
    ns = {'s': 'http://www.w3.org/2000/svg'}
    c = {'kind': 'figure_analysis', 'figure': {'path': 'f.png', 'caption': '示意图', 'aspect_ratio': 1},
         'facts': ['景观尺度决定观测范围。', {'heading': '条件', 'text': '同时观察空间配置。'},
                   {'value': '308', 'label': '平方千米'}]}
    root = render_composition(c, image_resolver=lambda _: 'f.png', colors={})
    texts = [n for n in root.findall('.//s:text', ns) if n.get('data-text-role') != 'caption']
    def gap(first, second):
        return float(second.get('data-pptx-box-y')) - float(first.get('data-pptx-box-y')) - float(first.get('data-pptx-box-h'))
    assert gap(texts[0], texts[1]) >= 16 - .01
    assert gap(texts[2], texts[3]) >= 16 - .01


def test_braces_require_real_groups_and_keep_all_text_editable():
    import pytest
    from scripts.academic_composition import render_composition
    ns = {'s': 'http://www.w3.org/2000/svg'}
    facts = [{'heading': h, 'text': '观测自然现象并解释景观变化。', 'group': group}
             for h, group in [('结构', '传统表达'), ('取象', '传统表达'), ('观察', '课堂运用'), ('边界', '课堂运用')]]
    composition = {'kind': 'figure_analysis', 'figure': {'path': 'f.png', 'caption': '示意图', 'aspect_ratio': 1}, 'facts': facts, 'fact_layout': 'braced'}
    root = render_composition(composition, image_resolver=lambda _: 'f.png', colors={})
    assert len(root.findall('.//s:path[@data-fact-brace]', ns)) == 2
    text = ''.join(''.join(node.itertext()) for node in root.findall('.//s:text', ns))
    assert all(fact['heading'] in text and fact['text'] in text for fact in facts)
    assert all(node.get('data-pptx-textbox') == 'true' for node in root.findall('.//s:text', ns))
    composition['facts'][1]['group'] = '课堂运用'
    with pytest.raises(ValueError, match='contiguous|group'):
        render_composition(composition, image_resolver=lambda _: 'f.png', colors={})


def test_wrapped_chinese_punctuation_does_not_start_a_line():
    from scripts.academic_composition import _wrap
    text = '阳爻为连续线，阴爻为断线；不同组合形成乾、坤、震、巽、坎、离、艮、兑。'
    lines = _wrap(text, 650, 24)
    assert ''.join(lines) == text
    assert len(lines) > 1
    assert not any(line.startswith(('、', '，', '。', '；', '：', '！', '？', '）', '”')) for line in lines)


def test_braced_composition_is_limited_to_one_page_across_the_deck():
    from scripts.academic_composition import validate_academic_authoring
    plan = plan_fixture()
    figure = {'kind': 'figure_analysis', 'figure': {'path': 'f.png', 'source_id': 'paper', 'caption': '示意图'},
              'facts': [{'heading': '结构', 'text': '内容', 'group': '第一组'}], 'fact_layout': 'braced'}
    first = deepcopy(plan['slides'][0])
    first['composition'] = figure
    second = deepcopy(first)
    plan['slides'] = [first, {'role': 'chapter'}, second]
    codes = {issue['code'] for issue in validate_academic_authoring(plan)}
    assert 'NATIVE-BRACE-REPETITION' in codes
    second['composition']['fact_layout'] = 'stacked'
    assert 'NATIVE-BRACE-REPETITION' not in {issue['code'] for issue in validate_academic_authoring(plan)}


def plan_fixture():
    return {
        'authoring_contract': 'academic_native.v1', 'template_id': 'academic_general',
        'academic_brief': {'source_policy': 'supplied_only'},
        'source_map': [{'id': 'paper', 'type': 'pdf', 'path': 'paper.pdf'}],
        'slides': [{
            'role': 'methods', 'action_title': '控制环境变量后比较多样性的独立关联',
            'claim': '统计控制用于分离观测变量间的关联。',
            'page_brief': {'question': '怎样分离环境关联？', 'information_gain': '区分输入、条件效应和验证。',
                           'visual_rationale': '矩阵表示输入，公式表示模型，分组表示输出。'},
            'evidence_sources': [{'source_id': 'paper', 'locator': 'Methods', 'kind': 'paper_section'}],
            'composition': {'kind': 'method_diagram', 'caption': '条件关联的分析路径 (Example et al., 2025)',
                'stages': [
                    {'title': '输入', 'visual': {'type': 'matrix', 'rows': ['地点 A', '地点 B'], 'columns': ['丰富度', '生产力', '环境']}, 'facts': ['地点与变量构成观测矩阵']},
                    {'title': '统计控制', 'visual': {'type': 'formula', 'lines': ['Y ~ S + E']}, 'facts': ['估计环境条件下的丰富度关联']},
                    {'title': '输出', 'visual': {'type': 'groups', 'labels': ['条件效应', '不确定性', '稳健性']}, 'facts': ['以原文检验方式评估估计']}]
            }
        }]
    }


def test_legacy_layout_slots_resolve_from_the_layout_source_of_truth():
    layout = __import__('json').loads((TEMPLATE / 'layouts.json').read_text(encoding='utf-8'))['layouts']
    row = next(x for x in layout if x['layout_id'] == 'background')
    payload = {x['slot_id']: 'x' for x in row['slots'] if x.get('required', True) and x.get('value_policy') != 'automatic_slide_index'}
    report = validate_body_variant_payload(TEMPLATE, {'layout_id': 'background', 'slot_payload': payload})
    assert report.status == 'pass', report.issues
    report = validate_body_variant_payload(TEMPLATE, {'layout_id': 'background', 'slot_payload': {**payload, 'INVENTED_SLOT': 'x'}})
    assert 'INVENTED_SLOT' in report.extra_slots


def test_native_contract_rejects_teaching_copy_prose_diagrams_and_missing_briefs():
    from scripts.academic_composition import validate_academic_authoring
    plan = plan_fixture()
    assert not validate_academic_authoring(plan)
    bad = deepcopy(plan)
    bad['slides'][0]['slot_payload'] = {'PAGE_TITLE': '如何解读这篇论文'}
    bad['slides'][0]['page_brief'].pop('information_gain')
    bad['slides'][0]['composition']['stages'][1].pop('visual')
    codes = {x['code'] for x in validate_academic_authoring(bad)}
    assert {'NATIVE-PAGE-BRIEF', 'NATIVE-AUDIENCE-LANGUAGE', 'NATIVE-METHOD-VISUAL'} <= codes
    assert not validate_academic_authoring({'slides': bad['slides']})  # scoped legacy compatibility


def test_new_compositions_use_explicit_native_text_and_one_closed_arrow():
    from scripts.academic_composition import render_composition
    root = render_composition(plan_fixture()['slides'][0]['composition'], image_resolver=lambda _: '', colors={})
    ns = {'s': 'http://www.w3.org/2000/svg'}
    texts = root.findall('.//s:text', ns)
    assert texts and all(x.get('data-pptx-textbox') == 'true' for x in texts)
    arrows = root.findall('.//s:path', ns)
    assert len(arrows) == 2
    assert all(x.get('d').endswith('Z') for x in arrows)
    assert not root.findall('.//s:rect[@data-card]', ns)


def test_native_contract_checks_visual_sources_and_repeated_composition():
    from scripts.academic_composition import validate_academic_authoring
    p = plan_fixture()
    p['slides'][0]['composition'] = {'kind': 'figure_comparison', 'figures': [
        {'path': 'f.png', 'source_id': 'unknown', 'caption': '关系 (Example et al., 2025)'},
        {'path': 'g.png', 'source_id': 'paper', 'caption': '关系 (Example et al., 2025)'}]}
    p['slides'] *= 3
    codes = {x['code'] for x in validate_academic_authoring(p)}
    assert 'NATIVE-VISUAL-SOURCE' in codes
    assert 'NATIVE-LAYOUT-REPETITION' in codes


def test_two_panel_comparison_uses_free_space_and_keeps_captions_with_images():
    from scripts.academic_composition import render_composition
    figures = [
        {'path': 'before.png', 'caption': '2000 年 8 月', 'aspect_ratio': 1},
        {'path': 'after.png', 'caption': '2014 年 8 月', 'aspect_ratio': 1},
    ]
    ns = {'s': 'http://www.w3.org/2000/svg'}
    root = render_composition({'kind': 'figure_comparison', 'figures': figures},
                              image_resolver=str, colors={})
    images = root.findall('s:image', ns)
    captions = root.findall("s:text[@data-text-role='caption']", ns)
    assert len(images) == len(captions) == 2
    for image, caption in zip(images, captions):
        assert float(image.get('y')) == 204
        assert float(image.get('height')) > 276
        assert image.get('preserveAspectRatio') == 'xMidYMax meet'
        assert float(caption.get('data-pptx-box-y')) == float(image.get('y')) + float(image.get('height')) + 9


def test_researched_plan_flags_reuse_of_the_same_file_across_pages():
    from scripts.academic_composition import validate_academic_authoring
    plan = plan_fixture()
    plan['academic_brief']['source_policy'] = 'research'
    first = plan['slides'][0]
    first['composition'] = {'kind': 'figure_analysis', 'facts': ['同一范围内的岸线'],
                            'figure': {'path': 'images/before.png', 'caption': '2000 年', 'source_id': 'paper'}}
    second = deepcopy(first)
    second['composition']['figure'].update(path='images/after.png', caption='2014 年')
    third = deepcopy(first)
    third['composition']['figure']['path'] = './images\\before.png'
    plan['slides'] = [first, second, third]
    reused = [issue for issue in validate_academic_authoring(plan) if issue['code'] == 'NATIVE-REUSED-FIGURE']
    assert len(reused) == 1
    assert reused[0]['severity'] == 'warning'
    assert reused[0]['path'].startswith('slides[2]')


def test_composition_text_never_silently_shrinks_or_overflows():
    import pytest
    from scripts.academic_composition import render_composition
    c = plan_fixture()['slides'][0]['composition']
    c['stages'][0]['facts'] = ['非常冗长的没有必要的重复说明' * 80]
    with pytest.raises(ValueError, match='fit|capacity'):
        render_composition(c, image_resolver=lambda _: '', colors={})


def test_figure_analysis_gives_nearly_square_source_figures_more_height():
    from scripts.academic_composition import render_composition

    fig = {'path': 'map.png', 'caption': '采样覆盖 (Example et al., 2025)', 'aspect_ratio': 1.03}
    root = render_composition({'kind': 'figure_analysis', 'figure': fig, 'facts': ['样本来自不同来源']}, image_resolver=str, colors={})
    result = root.find('{http://www.w3.org/2000/svg}image')
    assert min(float(result.get('width')) / fig['aspect_ratio'], float(result.get('height'))) >= 385


def test_bar_comparison_uses_a_common_zero_baseline_and_editable_values():
    from scripts.academic_composition import render_composition

    composition = {'kind': 'bar_comparison', 'unit': '个', 'caption': '按区域比较样本数 (Example et al., 2025)',
                   'series': [{'label': '甲', 'value': 120}, {'label': '乙', 'value': 60}, {'label': '丙', 'value': 0}]}
    root = render_composition(composition, image_resolver=str, colors={})
    ns = {'s': 'http://www.w3.org/2000/svg'}
    bars = root.findall('s:rect', ns)
    assert len(bars) == 2
    assert bars[0].get('x') == bars[1].get('x')
    assert float(bars[0].get('width')) == 2 * float(bars[1].get('width'))
    values = {''.join(node.itertext()) for node in root.findall('s:text', ns)}
    assert {'120', '60', '0'} <= values


def test_paired_comparison_encodes_shared_scale_and_keeps_values_editable(tmp_path):
    from scripts.academic_composition import render_composition
    from scripts.svg_to_pptx.drawingml_converter import convert_svg_to_slide_shapes

    composition = {
        'kind': 'paired_comparison', 'unit': '种',
        'value_labels': ['观测', '估计'],
        'caption': '各地区的树种估计 (Example et al., 2025)',
        'series': [{'label': '甲', 'first': 50, 'second': 100},
                   {'label': '乙', 'first': 0, 'second': 50}],
    }
    root = render_composition(composition, image_resolver=str, colors={})
    ns = {'s': 'http://www.w3.org/2000/svg'}
    circles = root.findall('s:circle', ns)[2:]
    assert float(circles[0].get('cx')) == float(circles[3].get('cx'))
    assert float(circles[2].get('cx')) < float(circles[0].get('cx')) < float(circles[1].get('cx'))
    texts = [''.join(node.itertext()) for node in root.findall('s:text', ns)]
    assert '50 / 100' in texts and '0 / 50' in texts
    svg = ET.Element('{http://www.w3.org/2000/svg}svg', {'viewBox': '0 0 1280 720', 'width': '1280', 'height': '720'})
    svg.append(root)
    svg_path = tmp_path / 'paired.svg'
    ET.ElementTree(svg).write(svg_path, encoding='utf-8')
    xml, _, _, _ = convert_svg_to_slide_shapes(svg_path)
    assert '50 / 100' in xml and '0 / 50' in xml


def test_paired_comparison_rejects_invalid_pairs():
    import pytest
    from scripts.academic_composition import render_composition

    composition = {'kind': 'paired_comparison', 'unit': '种', 'value_labels': ['观测', '估计'],
                   'caption': '比较 (Example et al., 2025)',
                   'series': [{'label': '甲', 'first': 1, 'second': 2},
                              {'label': '乙', 'first': -1, 'second': 2}]}
    with pytest.raises(ValueError, match='nonnegative'):
        render_composition(composition, image_resolver=str, colors={})


def test_paired_comparison_renders_through_semantic_template(tmp_path):
    from scripts.semantic_template_renderer import render_deck
    from scripts.svg_to_pptx.drawingml_converter import convert_svg_to_slide_shapes

    plan = plan_fixture()
    slide = plan['slides'][0]
    slide['layout_id'] = 'scientific_composition'
    slide['slot_payload'] = {'CHAPTER_LABEL': '结果', 'PAGE_TITLE': '比较地区估计', 'KEY_MESSAGE': '两项指标使用同一单位'}
    slide['composition'] = {'kind': 'paired_comparison', 'unit': '种',
                            'value_labels': ['观测', '估计'],
                            'series': [{'label': '甲', 'first': 12, 'second': 20},
                                       {'label': '乙', 'first': 30, 'second': 35}],
                            'caption': '地区比较 (Example et al., 2025)'}
    plan_path = tmp_path / 'deck_plan.json'
    plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding='utf-8')
    output = tmp_path / 'svg_output'
    render_deck(TEMPLATE, plan_path, output)
    xml, _, _, _ = convert_svg_to_slide_shapes(next(output.glob('*.svg')))
    assert '12 / 20' in xml and '30 / 35' in xml


def test_automatic_layouts_reach_semantic_render_and_native_export(tmp_path):
    from PIL import Image
    from scripts.semantic_template_renderer import render_deck
    from scripts.svg_to_pptx.drawingml_converter import convert_svg_to_slide_shapes

    plan = plan_fixture()
    slide = plan['slides'][0]
    slide['layout_id'] = 'scientific_composition'
    slide['slot_payload'] = {'CHAPTER_LABEL': '研究', 'PAGE_TITLE': '识别数据与分析的关系', 'KEY_MESSAGE': '依据样本与模型选择展示结构'}
    caption = '合成测试数据'
    Image.new('RGB', (600, 200)).save(tmp_path / 'result.png')
    fig = {'path': 'result.png', 'source_id': 'paper', 'caption': caption, 'aspect_ratio': 3}
    series = [{'label': '甲', 'value': 12}, {'label': '乙', 'value': 24}]
    cases = [
        ('merge_data', {'inputs': [{'title': '调查', 'metrics': [{'value': '1,200', 'label': '样点'},
                                                           {'value': '150', 'label': '样本'}]},
                                  {'title': '名录', 'metrics': [{'value': '250', 'label': '名称'}]}],
                        'output': {'title': '合并数据', 'metrics': [{'value': '800', 'label': '匹配记录'}]}},
         'data_convergence', '匹配记录'),
        ('explain_method', {'matrix': {'title': '输入矩阵', 'rows': ['样点甲'], 'columns': ['物种甲', '物种乙'],
                                       'cells': [[True, False]], 'note': '仅结构示意'},
                            'formula': {'title': '外推模型', 'lines': ['S = Sobs + Δ'], 'facts': ['Δ 为外推量']}},
         'method_model', 'S = Sobs + Δ'),
        ('read_result', {'figure': fig, 'facts': [{'value': '24', 'label': '总样点'},
                                                 {'heading': '覆盖边界', 'text': '样点集中在流域内'}]},
         'figure_analysis', '覆盖边界'),
        ('compare', {'series': series, 'unit': '份', 'focus': 'rank'}, 'dot_comparison', '24'),
        ('compare', {'series': series, 'unit': '份'}, 'bar_comparison', '12'),
        ('compare', {'panels': [{'title': '记录数量', 'unit': '份', 'series': series},
                                {'title': '覆盖比例', 'unit': '%', 'series': [{'label': '甲', 'value': 80},
                                                                            {'label': '乙', 'value': 90}]}]},
         'split_comparison', '独立量尺'),
    ]
    plan['slides'] = [dict(slide, composition=dict(fields, kind='auto', reading_task=task, caption=caption))
                      for task, fields, _, _ in cases]
    plan_path = tmp_path / 'deck_plan.json'
    plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding='utf-8')
    output = tmp_path / 'svg_output'
    manifest = render_deck(TEMPLATE, plan_path, output)
    ns = {'s': 'http://www.w3.org/2000/svg'}
    for assignment, (_, _, kind, value) in zip(manifest['assignments'], cases, strict=True):
        assert assignment['composition_kind'] == kind
        xml, _, _, _ = convert_svg_to_slide_shapes(output / assignment['svg'])
        assert value in xml
        body = ET.parse(output / assignment['svg']).find('s:g[@id="scientific-body"]', ns)
        if kind == 'data_convergence':
            assert len(body.findall('s:path', ns)) == 1
            centers = {''.join(node.itertext()): float(node.get('x'))
                       for node in body.findall('s:text', ns) if node.get('text-anchor') == 'middle'}
            assert (centers['1,200'] + centers['150']) / 2 == centers['调查']
            assert centers['250'] == centers['名录']
            assert centers['调查'] + centers['名录'] == 2*centers['合并数据']
            assert centers['800'] == centers['匹配记录'] == centers['合并数据']
        elif kind == 'method_model':
            assert len(body.findall('s:circle', ns)) == 1
        elif kind == 'figure_analysis':
            assert assignment['figure_placement'] == 'above'
            assert body.find('s:image', ns).get('width') == '1152'
        elif kind == 'dot_comparison':
            assert len(body.findall('s:circle', ns)) == 2
            assert xml.index('>乙<') < xml.index('>甲<')
        elif kind == 'split_comparison':
            bars = body.findall('s:rect', ns)
            assert bars[0].get('x') != bars[2].get('x')
            assert bars[1].get('width') == bars[3].get('width')  # distinct maxima use separate scales


def test_auto_layout_requires_evidence_for_the_requested_task():
    from scripts.academic_composition import validate_academic_authoring

    plan = plan_fixture()
    plan['slides'][0]['composition'] = {'kind': 'auto', 'reading_task': 'merge_data', 'rows': [['25', '30']]}
    assert {issue['code'] for issue in validate_academic_authoring(plan)} == {'NATIVE-COMPOSITION'}
