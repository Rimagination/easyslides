"""Reusable full-slide handoff: stable chrome, exact batches, no silent regeneration."""
import json

import pytest

from scripts.image_generation_contract import generation_sources, record_result, tool_arguments
from scripts.image_reconstruction_pipeline import init_project
from test_reconstruction_delivery_safety import generation_fixture


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def pagination():
    return dict(total=12, omit_pages=[1], box=[1178, 694, 70, 22],
                font_family='Arial', font_size=14.5, color='#526575', align='right',
                format='{page:02d} / {total:02d}')


def test_pagination_is_in_actual_tool_prompt(tmp_path):
    path, _ = generation_fixture(tmp_path)
    data = read(path)
    data['pagination'] = pagination()
    item = data['items'][0]
    item['page'] = 2
    prompt = tool_arguments(path, data, item)['prompt']
    assert '02 / 12' in prompt and '1178' in prompt and '#526575' in prompt
    item['page'] = 1
    assert 'no page number' in tool_arguments(path, data, item)['prompt']


@pytest.mark.parametrize('change', [dict(total=0), dict(box=[1200, 700, 100, 30]),
                                   dict(font_size=float('nan')), dict(omit_pages=[13])])
def test_bad_pagination_stops_before_imagegen(tmp_path, change):
    path, _ = generation_fixture(tmp_path)
    data = read(path)
    data['pagination'] = {**pagination(), **change}
    data['items'][0]['page'] = 2
    with pytest.raises(ValueError, match='pagination'):
        tool_arguments(path, data, data['items'][0])


def selection_fixture(tmp_path):
    entries, images = [], []
    for n in (1, 2):
        path, call = generation_fixture(tmp_path / f'batch{n}')
        # Same actual reference, even though the batch manifests have different roots.
        if n == 2:
            from scripts.image_acquisition import write_host_native_request
            data = read(path)
            data['reference_image'] = str(tmp_path / 'batch1/reference.png')
            path.write_text(json.dumps(data), encoding='utf-8')
            call['tool_arguments'] = tool_arguments(path, data, data['items'][0])
            write_host_native_request(path, data)
        image = path.parent / 'slide_001.png'
        record_result(path, 's01', image, call)
        entries.append(dict(page=n, manifest=str(path.relative_to(tmp_path)), item_id='s01'))
        images.append(image)
    selection = tmp_path / 'selected.json'
    selection.write_text(json.dumps(dict(schema_version='easyslides.generation_selection.v1',
                                         pages=entries)), encoding='utf-8')
    return selection, images


def test_selected_batches_feed_existing_init(tmp_path):
    selection, images = selection_fixture(tmp_path)
    assert len(generation_sources(selection)) == 2
    report = init_project(tmp_path/'project', images, generation_manifest=selection,
                          production_scheme='image_full_rebuild', reconstruction_mode='preserve_complex_images')
    assert report['status'] == 'initialized'


@pytest.mark.parametrize('fault', ['order', 'duplicate', 'missing', 'mixed_reference'])
def test_selection_fails_closed(tmp_path, fault):
    selection, _ = selection_fixture(tmp_path)
    data = read(selection)
    if fault == 'order': data['pages'].reverse()
    if fault == 'duplicate': data['pages'][1].update(manifest=data['pages'][0]['manifest'])
    if fault == 'missing': data['pages'][1]['item_id'] = 'not_generated'
    if fault == 'mixed_reference':
        # Independently valid receipt for another reference must not mix styles.
        path, call = generation_fixture(tmp_path/'other')
        record_result(path, 's01', path.parent/'slide_001.png', call)
        data['pages'][1]['manifest'] = str(path)
    selection.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError):
        generation_sources(selection)


def test_selection_rechecks_original_receipt(tmp_path):
    selection, images = selection_fixture(tmp_path)
    with images[1].open('ab') as stream:
        stream.write(b'changed')
    with pytest.raises(ValueError, match='changed'):
        generation_sources(selection)


def test_catalog_preview_is_valid_transport_for_same_reference(tmp_path):
    from pathlib import Path
    path, _ = generation_fixture(tmp_path)
    data = read(path)
    library = Path(__file__).resolve().parents[1] / 'templates/image_references'
    selected = read(library/'registry.json')['templates'][0]
    data.update(reference_id=selected['id'], reference_image=str(library/selected['preview']))
    assert tool_arguments(path, data, data['items'][0])['referenced_image_paths'][0] == str((library/selected['preview']).resolve())
    data['reference_id'] = 'not_a_template'
    with pytest.raises(ValueError, match='exactly match'):
        tool_arguments(path, data, data['items'][0])


def test_direct_manifest_cannot_bypass_final_page_count(tmp_path):
    from scripts.image_acquisition import write_host_native_request
    path, call = generation_fixture(tmp_path)
    data = read(path)
    data['pagination'] = pagination()
    data['items'][0]['page'] = 2
    path.write_text(json.dumps(data), encoding='utf-8')
    write_host_native_request(path, data)
    call['tool_arguments'] = tool_arguments(path, data, data['items'][0])
    record_result(path, 's01', tmp_path/'slide_001.png', call)
    with pytest.raises(ValueError, match='consecutive pages'):
        generation_sources(path)
