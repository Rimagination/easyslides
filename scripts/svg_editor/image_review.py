"""Read-only source-image preview and persisted, pixel-coordinate annotations."""
import json
import math
import os
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlsplit

from flask import abort, jsonify, request, send_file
from PIL import Image

SCHEMA = 'easyslides.source_image_review.v1'
REVIEW_FILE = 'source_image_review.json'
SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp'}


def register_image_review(app, source_dir):
    root = Path(source_dir).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Source image path must be a directory')
    project = app.config['PROJECT_PATH']
    destination = project / REVIEW_FILE
    lock = threading.Lock()
    app.config['SOURCE_IMAGES'] = root

    def inventory():
        slides = []
        for path in sorted(root.iterdir()):
            if path.suffix.lower() not in SUFFIXES or not path.is_file():
                continue
            if not path.resolve().is_relative_to(root):
                continue
            with Image.open(path) as im:
                width, height = im.size
            stat = path.stat()
            slides.append({'name': path.name, 'width': width, 'height': height,
                           'version': f'{stat.st_size}:{stat.st_mtime_ns}'})
        return slides

    def load():
        if not destination.exists():
            return {'schema_version': SCHEMA, 'revision': 0, 'annotations': []}
        data = json.loads(destination.read_text(encoding='utf-8'))
        if data.get('schema_version') != SCHEMA or data.get('source_directory') != str(root):
            raise ValueError('Saved annotations belong to a different source directory or schema')
        return data

    @app.before_request
    def guard_review_requests():
        if not request.path.startswith('/api/source-review'):
            return
        if request.host.split(':')[0] not in {'localhost', '127.0.0.1', '[::1]'}:
            abort(403)
        if request.method == 'POST':
            origin = request.headers.get('Origin')
            if request.headers.get('X-Source-Review') != '1':
                abort(403)
            if origin and urlsplit(origin).netloc != request.host:
                abort(403)
            if request.content_length and request.content_length > 1024 * 1024:
                abort(413)

    @app.get('/api/source-review')
    def get_review():
        try:
            with lock:
                data = load()
            return jsonify({**data, 'slides': inventory(), 'project': project.name,
                            'source_kind': 'imagegen_original'})
        except (ValueError, OSError) as exc:
            return jsonify(error=str(exc)), 409

    @app.get('/api/source-review/image/<name>')
    def get_source_image(name):
        if name not in {s['name'] for s in inventory()}:
            abort(404)
        return send_file(root / name, conditional=True)

    @app.post('/api/source-review')
    def save_review():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or type(payload.get('revision')) is not int:
            return jsonify(error='A review revision is required'), 400
        annotations = payload.get('annotations')
        if not isinstance(annotations, list) or len(annotations) > 500:
            return jsonify(error='Expected at most 500 annotations'), 400
        slides = {s['name']: s for s in inventory()}
        cleaned, ids = [], set()
        for item in annotations:
            if not isinstance(item, dict):
                return jsonify(error='Invalid annotation'), 400
            name, ident, note = item.get('slide'), item.get('id'), item.get('annotation')
            if not isinstance(name, str) or name not in slides:
                return jsonify(error='Unknown source image'), 400
            if not isinstance(ident, str) or not ident or len(ident) > 100 or ident in ids:
                return jsonify(error='Invalid or duplicate annotation ID'), 400
            if not isinstance(note, str) or not note.strip() or len(note) > 10000:
                return jsonify(error='A nonempty annotation of at most 10000 characters is required'), 400
            box = item.get('box')
            if not isinstance(box, list) or len(box) != 4 or any(type(v) not in (float, int) or abs(v) > 100000000 or not math.isfinite(v) for v in box):
                return jsonify(error='Expected finite [x, y, width, height] pixel coordinates'), 400
            x, y, w, h = box
            source = slides[name]
            if x < 0 or y < 0 or w < 2 or h < 2 or x+w > source['width'] or y+h > source['height']:
                return jsonify(error='Selection lies outside the original image'), 400
            if item.get('source_version') != source['version']:
                return jsonify(error='Source image changed; reload and reselect its region'), 409
            ids.add(ident)
            cleaned.append({'id': ident, 'slide': name, 'source_image': str(root / name),
                            'source_version': source['version'], 'source_size': [source['width'], source['height']],
                            'box': box, 'coordinate_space': 'source_image_pixels',
                            'annotation': note.strip(), 'action': 'reconstruct_region',
                            'status': 'pending', 'reference': 'imagegen_original',
                            'preserve_unselected': True})
        with lock:
            try:
                current = load()
            except (ValueError, OSError) as exc:
                return jsonify(error=str(exc)), 409
            if payload['revision'] != current['revision']:
                return jsonify(error='Annotations changed in another window; reload before saving'), 409
            existing = {a['id']: a for a in current['annotations']}
            for item in cleaned:
                prior = existing.get(item['id'], {})
                if prior.get('status') == 'applied' and all(prior.get(k) == item[k] for k in ('slide', 'source_version', 'box', 'annotation')):
                    item['status'] = 'applied'
            data = {'schema_version': SCHEMA, 'revision': current['revision']+1,
                    'source_directory': str(root), 'source_kind': 'imagegen_original',
                    'reconstruction_basis': 'source_image_not_editable_pptx',
                    'preserve_unselected': True, 'annotations': cleaned}
            # Commit one complete snapshot; an interrupted write cannot truncate prior work.
            fd, temp = tempfile.mkstemp(dir=project, prefix='.source-review-', suffix='.tmp')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    json.dump(data, stream, ensure_ascii=False, indent=2)
                    stream.write('\n')
                os.replace(temp, destination)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)
        return jsonify(status='saved', revision=data['revision'], count=len(cleaned),
                       pending_count=sum(a['status'] == 'pending' for a in cleaned), file=REVIEW_FILE)
