import json

import pytest
from PIL import Image

from scripts.check_annotations import scan_directory
from scripts.svg_editor.server import create_app


@pytest.fixture
def review(tmp_path):
    sources = tmp_path / 'originals'
    sources.mkdir()
    Image.new('RGB', (800, 450), 'blue').save(sources / 'slide_001.png')
    app = create_app(str(tmp_path), idle_timeout=0, source_images=str(sources))
    app.config['TESTING'] = True
    return tmp_path, sources, app.test_client()


def payload(client):
    source = client.get('/api/source-review').json['slides'][0]
    return {'revision': 0, 'annotations': [{'id': 'region-1', 'slide': source['name'],
        'source_version': source['version'], 'box': [200, 100, 150, 90],
        'annotation': '只重建光纤，保留周围图像'}]}


def post(client, data, **kwargs):
    return client.post('/api/source-review', json=data, headers={'X-Source-Review':'1', **kwargs})


def test_roundtrip_original_bytes_and_checker(review):
    project, sources, client = review
    original = (sources / 'slide_001.png').read_bytes()
    assert 'image_review.js' in client.get('/').text
    assert client.get('/api/source-review/image/slide_001.png').data == original
    result = post(client, payload(client))
    assert result.status_code == 200 and result.json['revision'] == 1
    saved = json.loads((project / 'source_image_review.json').read_text(encoding='utf-8'))
    assert saved['reconstruction_basis'] == 'source_image_not_editable_pptx'
    item = saved['annotations'][0]
    assert item['box'] == [200, 100, 150, 90]
    assert item['coordinate_space'] == 'source_image_pixels'
    assert item['source_size'] == [800,450] and item['preserve_unselected'] is True
    assert (sources / 'slide_001.png').read_bytes() == original
    assert not (project / 'svg_output').exists()
    assert scan_directory(project)['imagegen original: slide_001.png'][0]['tag'] == 'source-region'
    reopened = create_app(str(project), idle_timeout=0, source_images=str(sources)).test_client()
    assert reopened.get('/api/source-review').json['annotations'][0]['annotation'] == item['annotation']


def test_viewer_is_read_only_and_keeps_legacy_records(review):
    project, _, client = review
    assert post(client, payload(client)).status_code == 200
    path = project / 'source_image_review.json'
    before = path.read_bytes()
    page = client.get('/?slide=slide_001.png').text
    assert 'id="original"' in page
    for removed in ('id="overlay"', 'id="submit"', 'id="note"', 'id="exit"', '<aside'):
        assert removed not in page
    script = client.get('/static/image_review.js').text
    assert "url.searchParams.set('slide', slide.name)" in script
    assert 'image.dataset.sourceVersion = slide.version' in script
    assert 'POST' not in script and 'pointerdown' not in script and '/api/shutdown' not in script
    assert client.get('/api/source-review').json['revision'] == 1
    assert path.read_bytes() == before


@pytest.mark.parametrize('box', [[-1,0,5,5],[0,0,900,10],[0,0,5,451],[0,0,0,5], [True,0,5,5], [0,0,float('nan'),5], [0,0,float('inf'),5], [0,0,10**400,5], 'wrong'])
def test_invalid_coordinates_never_write(review, box):
    project, _, client = review
    data = payload(client); data['annotations'][0]['box'] = box
    assert post(client,data).status_code == 400
    assert not (project / 'source_image_review.json').exists()


def test_version_and_concurrency_conflict(review):
    project, _, client = review
    data = payload(client)
    assert post(client,data).status_code == 200
    assert post(client,data).status_code == 409
    data['revision'] = 1
    data['annotations'][0]['source_version'] = 'old-image'
    assert post(client,data).status_code == 409
    assert json.loads((project/'source_image_review.json').read_text(encoding='utf-8'))['revision'] == 1


def test_delete_and_pending_status(review):
    project, _, client = review
    assert post(client,payload(client)).status_code == 200
    assert post(client,{'revision':1,'annotations':[]}).status_code == 200
    assert scan_directory(project) == {}


def test_cross_origin_and_unknown_source(review):
    _, _, client = review
    data = payload(client)
    assert client.post('/api/source-review',json=data).status_code == 403
    assert post(client,data, Origin='http://untrusted.example').status_code == 403
    assert client.get('/api/source-review', headers={'Host':'attacker.example'}).status_code == 403
    data['annotations'][0]['slide'] = '..\\secret.png'
    assert post(client,data).status_code == 400
    assert client.get('/api/source-review/image/secret.png').status_code == 404


def test_original_svg_mode_unchanged(tmp_path):
    (tmp_path/'svg_output').mkdir()
    (tmp_path/'svg_output/one.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"><text id="t">Hello</text></svg>')
    client = create_app(str(tmp_path), idle_timeout=0).test_client()
    assert 'image_review.js' not in client.get('/').text
    assert client.get('/api/slides').json['slides'][0]['name'] == 'one.svg'
    assert client.post('/api/slide/one.svg/annotate',json={'element_id':'t','annotation':'Change text'}).status_code == 200
    assert client.post('/api/save-all').status_code == 200
    assert scan_directory(tmp_path)['one.svg'][0]['annotation'] == 'Change text'


def test_applied_annotations_only_requeue_when_changed(review):
    project, _, client = review
    data = payload(client)
    assert post(client,data).status_code == 200
    path = project/'source_image_review.json'
    saved = json.loads(path.read_text(encoding='utf-8'))
    saved['annotations'][0]['status'] = 'applied'
    saved['revision'] = 2
    path.write_text(json.dumps(saved),encoding='utf-8')
    data['revision'] = 2
    assert post(client,data).json['pending_count'] == 0
    assert scan_directory(project) == {}
    data['revision'] = 3
    data['annotations'][0]['annotation'] = 'Changed reconstruction request'
    assert post(client,data).json['pending_count'] == 1
