"""Regressions for wrong-generation and visually unfaithful deliveries."""
import json
from pathlib import Path

import pytest
from PIL import Image

from scripts.image_reconstruction_pipeline import _default_pptx, qa_project
from scripts.image_acquisition import validate_image_manifest, write_host_native_request
from test_image_reconstruction_pipeline import complete_project, fixture_render_receipt


def test_default_reconstruction_does_not_accept_visually_different_deck(tmp_path):
    project = complete_project(tmp_path)
    report = qa_project(project)
    assert report['status'] != 'pass'
    assert report['delivery_ready'] is False


def test_ambiguous_outputs_require_explicit_selection(tmp_path):
    (tmp_path/'pptx').mkdir()
    for name in ('output.pptx', 'new_revision.pptx'):
        (tmp_path/'pptx'/name).write_bytes(b'PPTX')
    with pytest.raises(ValueError, match='--pptx'):
        _default_pptx(tmp_path)


def test_analysis_reset_cannot_replace_sources_using_another_extension(tmp_path):
    from scripts.image_reconstruction_pipeline import init_project
    first = tmp_path/'first.png'
    replacement = tmp_path/'replacement.jpg'
    Image.new('RGB', (320,180), 'white').save(first)
    Image.new('RGB', (320,180), 'red').save(replacement)
    project = tmp_path/'project'
    choices = dict(production_scheme='image_full_rebuild', reconstruction_mode='preserve_complex_images')
    init_project(project, [first], **choices)
    with pytest.raises(FileExistsError, match='locked'):
        init_project(project, [replacement], overwrite_analysis=True, **choices)


def test_split_asset_checks_include_later_pages(tmp_path):
    project = complete_project(tmp_path)
    assets = project/'pages/page_002/assets'
    assets.mkdir(parents=True)
    (assets/'split_manifest.json').write_text(json.dumps({'assets':[
        {'name':'missing scientific figure', 'path':'missing.png'}]}), encoding='utf8')
    report = qa_project(project, mode='faithful-practical')
    assert any(gate['name'].startswith('split_assets') and gate['blocking_count'] for gate in report['gates'])


def test_slide_generation_rejects_background_only_contract():
    manifest = dict(purpose='slide_reconstruction', reference_image='reference.png',
                    acquisition={'path':'host-native'}, items=[dict(
                        id='s01', filename='slide_001.png', prompt='Topic',
                        aspect_ratio='16:9', status='Pending', text_policy='none')])
    with pytest.raises(ValueError, match='embedded'):
        validate_image_manifest(manifest)


def test_host_request_contains_real_image_reference_arguments(tmp_path):
    reference=tmp_path/'ref.png'
    Image.new('RGB',(100,60)).save(reference)
    manifest=dict(purpose='slide_reconstruction', reference_image=str(reference),
                  acquisition={'path':'host-native'}, items=[dict(
                      id='s01', filename='slide_001.png', prompt='Full page title and content',
                      aspect_ratio='16:9', status='Pending', text_policy='embedded')])
    path=write_host_native_request(tmp_path/'images.json', manifest)
    request=json.loads(path.read_text(encoding='utf8'))['items'][0]
    assert request['tool_arguments']['referenced_image_paths']==[str(reference)]
    assert 'Full page title and content' in request['tool_arguments']['prompt']


def generation_fixture(root, *, evidence=False):
    from scripts.image_generation_contract import tool_arguments
    root.mkdir(parents=True, exist_ok=True)
    reference = root/'reference.png'
    Image.new('RGB',(320,180),'green').save(reference)
    manifest = dict(purpose='slide_reconstruction', reference_image='reference.png',
                    acquisition={'path':'host-native'}, items=[dict(
                        id='s01', filename='slide_001.png', prompt='Title: Plant ecology',
                        aspect_ratio='16:9', status='Pending', text_policy='embedded')])
    if evidence:
        Image.new('RGB',(320,180),'blue').save(root/'figure.png')
        manifest['items'][0]['evidence_required'] = True
        manifest['items'][0]['evidence_images'] = [{'path':'figure.png','figure_id':'Fig. 2','citation':'Original paper DOI'}]
    path=root/'image_prompts.json'
    path.write_text(json.dumps(manifest),encoding='utf8')
    Image.new('RGB',(320,180),'white').save(root/'slide_001.png')
    call={'tool_name':'image_gen.imagegen','tool_arguments':tool_arguments(path,manifest,manifest['items'][0])}
    write_host_native_request(path, manifest)
    return path, call


def test_reference_change_between_preparation_and_recording_is_blocked(tmp_path):
    from scripts.image_generation_contract import record_result
    path, call = generation_fixture(tmp_path)
    Image.new('RGB', (320,180), 'red').save(tmp_path/'reference.png')
    with pytest.raises(ValueError, match='prepar'):
        record_result(path, 's01', tmp_path/'slide_001.png', call)


def test_missing_project_run_cannot_disable_provenance_checks(tmp_path):
    project = complete_project(tmp_path)
    (project/'image_reconstruction_run.json').unlink()
    report = qa_project(project, mode='faithful-practical')
    assert report['blocking_count'] > 0


def test_existing_image_alone_does_not_claim_imagegen_completion(tmp_path):
    from scripts.image_acquisition import reconcile_manifest
    path,_=generation_fixture(tmp_path)
    report=reconcile_manifest(path)
    assert report['items'][0]['status'] == 'Pending'
    assert 'receipt' in report['items'][0]['last_error']


def test_recorded_generation_binds_reference_evidence_and_output(tmp_path):
    from scripts.image_generation_contract import record_result,generation_sources
    path,call=generation_fixture(tmp_path,evidence=True)
    assert len(call['tool_arguments']['referenced_image_paths'])==2
    record_result(path,'s01',tmp_path/'slide_001.png',call)
    assert len(generation_sources(path))==1
    Image.new('RGB',(320,180),'red').save(tmp_path/'figure.png')
    with pytest.raises(ValueError,match='changed'):
        generation_sources(path)


def test_unattached_reference_call_cannot_be_recorded(tmp_path):
    from scripts.image_generation_contract import record_result
    path,call=generation_fixture(tmp_path)
    call['tool_arguments']['referenced_image_paths']=[]
    with pytest.raises(ValueError,match='differs'):
        record_result(path,'s01',tmp_path/'slide_001.png',call)


def test_evidence_pages_block_missing_original_figure(tmp_path):
    from scripts.image_generation_contract import tool_arguments
    path,_=generation_fixture(tmp_path)
    manifest=json.loads(path.read_text())
    manifest['items'][0]['evidence_required']=True
    with pytest.raises(ValueError,match='original'):
        tool_arguments(path,manifest,manifest['items'][0])


def test_changed_slide_prompt_invalidates_generated_output(tmp_path):
    from scripts.image_generation_contract import record_result,generation_sources
    path,call=generation_fixture(tmp_path)
    record_result(path,'s01',tmp_path/'slide_001.png',call)
    data=json.loads(path.read_text())
    data['items'][0]['prompt']='Different topic'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='receipt'):
        generation_sources(path)


def test_imagegen_sources_are_bound_at_reconstruction_init(tmp_path):
    from scripts.image_generation_contract import record_result
    from scripts.image_reconstruction_pipeline import init_project
    path,call=generation_fixture(tmp_path/'generation')
    image=path.parent/'slide_001.png'
    record_result(path,'s01',image,call)
    choices=dict(production_scheme='image_full_rebuild',reconstruction_mode='preserve_complex_images')
    project=tmp_path/'project'
    init_project(project,[image],generation_manifest=path,**choices)
    assert json.loads((project/'analysis/_analysis.json').read_text())['generation_manifest']==str(path.resolve())
    Image.new('RGB',(320,180),'red').save(image)
    with pytest.raises(FileExistsError,match='changed'):
        init_project(project,[image],overwrite_analysis=True,**choices)


def test_full_slide_images_cannot_be_bound_as_background(tmp_path):
    from scripts.image_acquisition import apply_manifest_to_slide_ir,prepare_acquisition
    path,_=generation_fixture(tmp_path)
    with pytest.raises(ValueError,match='image-reconstruct'):
        apply_manifest_to_slide_ir({'slides':[]},path)
    with pytest.raises(ValueError,match='cannot fall back'):
        prepare_acquisition(path,explicit_path='api')


@pytest.mark.parametrize('changed', ['pptx', 'render', 'missing_receipt', 'source'])
def test_delivery_blocks_stale_or_unbound_artifacts(tmp_path,changed):
    project=complete_project(tmp_path)
    rendered=project/'reports/rendered_png'
    Image.new('RGB',(320,180),'white').save(rendered/'slide_001.png')
    fixture_render_receipt(project)
    assert qa_project(project)['delivery_ready'] is True
    if changed=='pptx':
        with (project/'pptx/output.pptx').open('ab') as stream: stream.write(b'revision')
    elif changed=='render':
        Image.new('RGB',(320,180),'red').save(rendered/'slide_001.png')
    elif changed=='missing_receipt':
        (rendered/'render_receipt.json').unlink()
    else:
        Image.new('RGB',(320,180),'blue').save(project/'sources/slide_001.png')
    assert qa_project(project)['delivery_ready'] is False


def test_diagnostic_mode_does_not_authorize_unfaithful_delivery(tmp_path):
    report=qa_project(complete_project(tmp_path),mode='faithful-practical')
    assert report['status']=='pass'
    assert report['visual_status']=='fail'
    assert report['delivery_ready'] is False


def test_changed_decisions_cannot_bypass_initialized_route(tmp_path):
    project=complete_project(tmp_path)
    path=project/'analysis/_analysis.json'
    inventory=json.loads(path.read_text())
    inventory['reconstruction_mode']='full_vector'
    path.write_text(json.dumps(inventory))
    report=qa_project(project)
    assert report['delivery_ready'] is False


def test_duplicate_source_paths_are_rejected_before_copy(tmp_path):
    from scripts.image_reconstruction_pipeline import init_project
    Image.new('RGB',(32,18)).save(tmp_path/'source.png')
    with pytest.raises(ValueError,match='unique'):
        init_project(tmp_path/'project',[tmp_path/'source.png']*2,
                     production_scheme='image_full_rebuild',reconstruction_mode='preserve_complex_images')
    assert not (tmp_path/'project/sources/slide_001.png').exists()
