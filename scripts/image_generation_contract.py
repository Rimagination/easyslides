"""Full-slide ImageGen input/output contract, above the existing acquisition module.

Host-call receipts are recorded evidence, not cryptographic proof of a remote
tool invocation. They prevent accidental request/source drift and stale reuse.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

from PIL import Image

try:
    from scripts.artifact_receipt import fingerprint, matches
except ModuleNotFoundError:
    from artifact_receipt import fingerprint, matches

PURPOSE = 'slide_reconstruction'
SELECTION_SCHEMA = 'easyslides.generation_selection.v1'


def pagination_text(contract: Mapping, page: int) -> str:
    """Physical slide counters in a single 1280x720 chrome contract."""
    try:
        total = contract['total']
        omitted = contract.get('omit_pages', [])
        box = contract['box']
        size = contract['font_size']
        formats = ('{page} / {total}', '{page:02d} / {total:02d}')
        if (type(total) is not int or total < 1 or type(page) is not int or not 1 <= page <= total
                or not isinstance(omitted, list) or any(type(n) is not int or not 1 <= n <= total for n in omitted)
                or not isinstance(box, list) or len(box) != 4
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in box)
                or box[0] < 0 or box[1] < 0 or min(box[2:]) <= 0
                or box[0] + box[2] > 1280 or box[1] + box[3] > 720
                or type(size) not in (int, float) or not math.isfinite(size) or size <= 0
                or not isinstance(contract['font_family'], str) or not contract['font_family'].strip()
                or not isinstance(contract['color'], str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', contract['color'])
                or contract['align'] not in ('left', 'center', 'right') or contract['format'] not in formats):
            raise ValueError('invalid pagination contract')
        return '' if page in omitted else contract['format'].format(page=page, total=total)
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError('invalid pagination contract') from exc


def _image(value: str, root: Path) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError('a reference/evidence image path is required')
    path = Path(value)
    path = (path if path.is_absolute() else root / path).resolve()
    with Image.open(path) as image:
        image.verify()
    return path


def tool_arguments(manifest_path: str | Path, manifest: Mapping, item: Mapping) -> dict[str, Any]:
    if item.get('text_policy') != 'embedded':
        raise ValueError('full-slide reconstruction requires text_policy=embedded')
    root = Path(manifest_path).resolve().parent
    reference = _image(manifest.get('reference_image'), root)
    if manifest.get('reference_id'):
        library = Path(__file__).resolve().parents[1] / 'templates/image_references'
        catalog = json.loads((library / 'registry.json').read_text(encoding='utf-8'))
        selected = next((row for row in catalog['templates'] if row['id'] == manifest['reference_id']), None)
        if selected is None or reference not in {
            (library / selected[key]).resolve() for key in ('image', 'preview') if selected.get(key)
        }:
            raise ValueError('reference_id must exactly match the selected image-reference catalog file')
    evidence = item.get('evidence_images', [])
    if not isinstance(evidence, list):
        raise ValueError('evidence_images must be a list')
    if item.get('evidence_required') and not evidence:
        raise ValueError('scientific evidence page requires original evidence_images')
    references = [str(reference)]
    citations = []
    for row in evidence:
        if not isinstance(row, Mapping) or not all(isinstance(row.get(k), str) and row[k].strip() for k in ('path', 'citation', 'figure_id')):
            raise ValueError('original evidence requires path, citation and figure_id')
        references.append(str(_image(row['path'], root)))
        citations.append(f"{row['figure_id']}: {row['citation']}")
    prompt = (
        'Generate ONE COMPLETE presentation slide, including all supplied text and graphics. '
        f"Canvas aspect ratio: {item['aspect_ratio']}. "
        'Use reference image 1 as the strict visual template: retain its palette, typography hierarchy, '
        'page chrome and layout language. Do not copy its old topic or invent a different template. '
        'This output is the full content slide used as the sole visual source for editable reconstruction. '
        'Keep text legible, aligned and clear of graphics; do not return an empty background. '
        'Additional reference images are original scientific evidence: preserve their data, axes, '
        'labels and relationships; never invent or redraw observations. Clearly separate conceptual '
        'illustrations from evidence.\n\nSlide content:\n' + str(item['prompt'])
    )
    if citations:
        prompt += '\n\nOriginal figure citations:\n' + '\n'.join(citations)
    # Legacy prompts remain byte-for-byte stable so existing receipts stay valid.
    if 'pagination' in manifest:
        counter = pagination_text(manifest['pagination'], item.get('page'))
        prompt += ('\n\nLocked deck pagination (coordinates/font size in 1280x720 pixels): '
                   + json.dumps(manifest['pagination'], ensure_ascii=False, sort_keys=True)
                   + '\nThis slide: ' + (counter or 'no page number')
                   + '. Use this exact counter only. Reserve this box for pagination; keep all '
                   'body text, figures and citations outside it. Do not copy reference page numbers.')
    return {'prompt': prompt, 'referenced_image_paths': references}


def record_result(manifest_path: str | Path, item_id: str, image_path: str | Path,
                  call: Mapping, *, output_dir: str | Path | None = None) -> dict[str, Any]:
    # Reuse the acquisition filename policy and writer; no second generator.
    try:
        from scripts.image_acquisition import load_image_resource_manifest, output_path_for_item, save_manifest
    except ModuleNotFoundError:
        from image_acquisition import load_image_resource_manifest, output_path_for_item, save_manifest
    manifest = load_image_resource_manifest(manifest_path)
    if output_dir is not None and Path(output_dir).resolve() != Path(manifest_path).resolve().parent:
        raise ValueError('complete slide outputs must be beside their generation manifest')
    if manifest.get('purpose') != PURPOSE:
        raise ValueError('record-result requires purpose=slide_reconstruction')
    items = [item for item in manifest['items'] if item['id'] == item_id]
    if len(items) != 1:
        raise ValueError('item id must identify exactly one slide')
    item = items[0]
    expected = tool_arguments(manifest_path, manifest, item)
    if not isinstance(call, Mapping) or call.get('tool_arguments') != expected or call.get('tool_name') not in ('image_gen', 'image_gen.imagegen', 'image_gen__imagegen'):
        raise ValueError('recorded ImageGen call differs from the prepared tool_arguments')
    request_path = Path(call.get('request_path') or Path(manifest_path).with_name('image_acquisition_request.json'))
    try:
        request = json.loads(request_path.read_text(encoding='utf-8'))
        prepared = next(row for row in request['items'] if row['id'] == item_id)
        references = prepared['reference_identities']
        if (prepared['tool_arguments'] != expected or len(references) != len(expected['referenced_image_paths'])
                or any(not matches(row, path) for row, path in zip(references, expected['referenced_image_paths']))):
            raise ValueError('reference images or request changed since preparation')
    except (OSError, KeyError, StopIteration, TypeError) as exc:
        raise ValueError('matching prepared ImageGen request is required before recording') from exc
    image = _image(str(image_path), Path.cwd())
    target = output_path_for_item(manifest_path, item, output_dir=output_dir)
    if image != target:
        raise ValueError(f'copy the generated output to its declared path before recording: {target}')
    with Image.open(image) as result:
        width, height = result.size
    try:
        rw, rh = (float(v) for v in item['aspect_ratio'].split(':'))
        if not all(math.isfinite(v) and v > 0 for v in (rw, rh)) or abs(width / height - rw / rh) > 0.02:
            raise ValueError('generated slide aspect ratio differs from request')
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError('generated slide aspect ratio differs from request') from exc
    item['generation_receipt'] = {
        'verification': 'recorded_host_call', 'tool_name': call['tool_name'],
        'tool_arguments': expected,
        'references': references,
        'output': fingerprint(image),
    }
    item['status'] = 'Generated'
    item.pop('last_error', None)
    save_manifest(str(manifest_path), manifest)
    return item['generation_receipt']


def validate_result(manifest_path: str | Path, manifest: Mapping, item: Mapping, output: Path) -> None:
    expected = tool_arguments(manifest_path, manifest, item)
    receipt = item.get('generation_receipt')
    if (not isinstance(receipt, dict) or receipt.get('tool_arguments') != expected
            or receipt.get('verification') != 'recorded_host_call'
            or receipt.get('tool_name') not in ('image_gen', 'image_gen.imagegen', 'image_gen__imagegen')):
        raise ValueError('matching ImageGen call receipt is missing; file existence is not generation evidence')
    refs = receipt.get('references', [])
    if not isinstance(refs, list) or len(refs) != len(expected['referenced_image_paths']) or any(
        not matches(row, path) for row, path in zip(refs, expected['referenced_image_paths'])
    ):
        raise ValueError('reference/evidence image changed since ImageGen generation')
    if not matches(receipt.get('output'), output):
        raise ValueError('generated slide changed since its recorded ImageGen result')


def generation_sources(manifest_path: str | Path) -> list[dict[str, Any]]:
    try:
        from scripts.image_acquisition import load_image_resource_manifest, output_path_for_item
    except ModuleNotFoundError:
        from image_acquisition import load_image_resource_manifest, output_path_for_item
    path = Path(manifest_path).resolve()
    raw = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(raw, dict) and raw.get('schema_version') == SELECTION_SCHEMA:
        pages = raw.get('pages')
        if not isinstance(pages, list) or not pages:
            raise ValueError('generation selection requires ordered pages')
        outputs, seen, styles, contracts = [], set(), set(), set()
        batches = {}
        library = Path(__file__).resolve().parents[1] / 'templates/image_references'
        catalog = json.loads((library/'registry.json').read_text(encoding='utf-8'))['templates']
        for index, row in enumerate(pages, 1):
            if (not isinstance(row, dict) or type(row.get('page')) is not int or row['page'] != index
                    or not isinstance(row.get('manifest'), str) or not row['manifest'].strip()
                    or not isinstance(row.get('item_id'), str) or not row['item_id'].strip()):
                raise ValueError('generation selection requires consecutive pages, manifest and item_id')
            batch = (path.parent / row['manifest']).resolve()
            key = (batch, row['item_id'])
            if key in seen:
                raise ValueError('duplicate generation selection')
            seen.add(key)
            if batch not in batches:
                batches[batch] = load_image_resource_manifest(batch)
            manifest = batches[batch]
            if manifest.get('purpose') != PURPOSE:
                raise ValueError('selected batch must declare purpose=slide_reconstruction')
            items = [i for i in manifest['items'] if i['id'] == row['item_id']]
            if len(items) != 1:
                raise ValueError('selected item must identify exactly one generated slide')
            item = items[0]
            if manifest.get('pagination') is not None:
                if item.get('page') != index or manifest['pagination'].get('total') != len(pages):
                    raise ValueError('selected page order differs from generated pagination')
                contracts.add(json.dumps(manifest['pagination'], sort_keys=True))
            else:
                contracts.add('legacy')
            reference = (batch.parent / manifest['reference_image']).resolve()
            style = next((r['id'] for r in catalog if reference in {
                (library / r[k]).resolve() for k in ('image', 'preview') if r.get(k)}), str(reference))
            styles.add(style)
            if len(styles) > 1 or len(contracts) > 1:
                raise ValueError('selected pages must share one reference style and pagination contract')
            output = output_path_for_item(batch, item)
            validate_result(batch, manifest, item, output)
            outputs.append(dict(item['generation_receipt']['output']))
        return outputs
    manifest = load_image_resource_manifest(path)
    if manifest.get('purpose') != PURPOSE:
        raise ValueError('generation manifest must declare purpose=slide_reconstruction')
    outputs = []
    for index, item in enumerate(manifest['items'], 1):
        if 'pagination' in manifest:
            pagination_text(manifest['pagination'], item.get('page'))
            if item['page'] != index or manifest['pagination']['total'] != len(manifest['items']):
                raise ValueError('final generation manifest must contain consecutive pages and matching pagination total; use a selection for batches')
        output = output_path_for_item(manifest_path, item)
        validate_result(manifest_path, manifest, item, output)
        outputs.append(dict(item['generation_receipt']['output']))
    return outputs
