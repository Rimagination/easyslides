"""Regression cases from the Harness density/layout audit."""
from copy import deepcopy
from pathlib import Path
import tempfile
from xml.etree import ElementTree as ET

from scripts.body_variant_adapter import validate_body_variant_payload

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'templates/layouts/academic_general'


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


def test_composition_text_never_silently_shrinks_or_overflows():
    import pytest
    from scripts.academic_composition import render_composition
    c = plan_fixture()['slides'][0]['composition']
    c['stages'][0]['facts'] = ['非常冗长的没有必要的重复说明' * 80]
    with pytest.raises(ValueError, match='fit|capacity'):
        render_composition(c, image_resolver=lambda _: '', colors={})
