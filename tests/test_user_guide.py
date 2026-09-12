import json
from pathlib import Path

import pytest

from scripts.confirm_ui import build_confirmation_package
from test_image_reconstruction_pipeline import complete_project


def test_pilot_compares_bound_sources_and_actual_renders(tmp_path):
    project = complete_project(tmp_path)
    report = build_confirmation_package(project, tmp_path/'review', pilot_pages=[1])
    assert report['pilot']['state'] == 'needs_review'
    assert (tmp_path/'review'/report['pilot']['pages'][0]['source']).is_file()
    text = (tmp_path/'review/index.html').read_text(encoding='utf8')
    assert '实际渲染' in text and '不会自动提交' in text


def test_pilot_rejects_stale_render(tmp_path):
    project = complete_project(tmp_path)
    with (project/'reports/rendered_png/slide_001.png').open('ab') as stream:
        stream.write(b'changed')
    with pytest.raises(ValueError, match='stale'):
        build_confirmation_package(project, tmp_path/'review', pilot_pages=[1])


def test_pilot_does_not_turn_qa_failure_into_acceptance(tmp_path):
    project = complete_project(tmp_path)
    (project/'reports/image_reconstruction_pipeline_report.json').write_text(json.dumps({'visual_status':'fail','delivery_ready':False}))
    report = build_confirmation_package(project, tmp_path/'review', pilot_pages=[1])
    assert report['pilot']['state'] == 'needs_repair'
    assert report['status'] == 'needs_confirmation'


def test_renamed_pptx_needs_explicit_selection(tmp_path):
    project = complete_project(tmp_path)
    renamed = project/'pptx/renamed.pptx'
    (project/'pptx/output.pptx').rename(renamed)
    with pytest.raises(ValueError, match='receipt'):
        build_confirmation_package(project, tmp_path/'review', pilot_pages=[1])
    assert build_confirmation_package(project, tmp_path/'review', pilot_pages=[1], pptx=renamed)['pilot']['pages']


def test_offline_guide_has_no_implicit_selection_or_network():
    page = (Path(__file__).resolve().parents[1]/'assets/guide/index.html').read_text(encoding='utf8')
    assert '非实际 PPT 输出' in page
    assert 'type="submit" id="generate" disabled' in page
    assert ' checked' not in page
    assert 'fetch(' not in page and 'localStorage' not in page
    assert all(name in page for name in ('direct_editable','image_full_rebuild','image_partial_rebuild'))


def test_missing_mode_cannot_claim_full_vector(tmp_path):
    project = complete_project(tmp_path)
    path = project/'image_reconstruction_run.json'
    data = json.loads(path.read_text())
    data['decisions'].pop('reconstruction_mode')
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        build_confirmation_package(project, tmp_path/'review', pilot_pages=[1])


def test_invalid_later_page_does_not_replace_earlier_preview(tmp_path):
    project = complete_project(tmp_path)
    output = tmp_path/'review'
    old = output/'pilot/source_001.png'
    old.parent.mkdir(parents=True)
    old.write_bytes(b'previous preview')
    with pytest.raises(ValueError):
        build_confirmation_package(project, output, pilot_pages=[1,99])
    assert old.read_bytes() == b'previous preview'
