#!/usr/bin/env python3
"""Extract detected scientific regions, using parser coordinates, not eye-picked crops.

MinerU Precision identifies layout regions. PyMuPDF exports those regions from
the original PDF at print resolution and retains a PDF copy of each region.
Parser regions are not automatically equivalent to a complete published figure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values(): yield from _walk(child)
    elif isinstance(value, list):
        for child in value: yield from _walk(child)


def extract_layout_regions(pdf: Path, layout: Path, output: Path, *, dpi=300, padding=2) -> dict:
    import pymupdf
    payload = json.loads(layout.read_text(encoding='utf-8'))
    pages = payload.get('pdf_info') if isinstance(payload, dict) else None
    if not isinstance(pages, list):
        raise ValueError('Expected MinerU middle/layout JSON with pdf_info, page_size and page_idx; Markdown is insufficient')
    output.mkdir(parents=True, exist_ok=True)
    assets = []
    with pymupdf.open(pdf) as document:
        for page_record in pages:
            page_idx = page_record.get('page_idx')
            if not isinstance(page_idx, int) or not 0 <= page_idx < len(document):
                raise ValueError('Parser page index is outside the source PDF')
            page = document[page_idx]
            size = page_record.get('page_size')
            if not size or len(size) != 2 or min(size) <= 0:
                raise ValueError('Layout coordinates need an explicit page size; do not guess units')
            # MinerU middle JSON uses page coordinates, unlike normalized content_list.
            sx, sy = page.rect.width/size[0], page.rect.height/size[1]
            blocks = page_record.get('preproc_blocks', page_record.get('para_blocks', []))
            for block in blocks:
                if block.get('type') not in {'image', 'chart', 'table'}: continue
                nodes = list(_walk(block))
                bodies = [n for n in nodes if n.get('type') in {'image_body', 'chart_body', 'table_body'} and n.get('bbox')]
                if not bodies: bodies = [block]
                paths = [n['image_path'] for n in nodes if n.get('image_path')]
                if not paths and block.get('type') != 'table': continue
                for body in bodies:
                    bbox = body.get('bbox')
                    if not isinstance(bbox, list) or len(bbox) != 4: raise ValueError('Detected region needs four coordinates')
                    raw = pymupdf.Rect(bbox[0]*sx, bbox[1]*sy, bbox[2]*sx, bbox[3]*sy)
                    if raw.is_empty or not page.rect.contains(raw): raise ValueError('Detected region is outside the source page')
                    clip = (raw+(-padding,-padding,padding,padding)) & page.rect
                    region_id = f'region-p{page_idx+1:02d}-{len(assets)+1:03d}'
                    png, region_pdf = output/(region_id+'.png'), output/(region_id+'.pdf')
                    page.get_pixmap(dpi=dpi, clip=clip, alpha=False).save(png)
                    with pymupdf.open() as cut:
                        dest = cut.new_page(width=clip.width, height=clip.height)
                        dest.show_pdf_page(dest.rect, document, page_idx, clip=clip)
                        cut.save(region_pdf)
                    captions = [n for n in nodes if str(n.get('type','')).endswith('_caption')]
                    caption = ' '.join(str(n.get('content','')) for c in captions for n in _walk(c) if n.get('content'))
                    assets.append({'id':region_id,'type':block['type'],'scope':'detected_region',
                                   'page_number':page_idx+1,'source_bbox_pdf_points':list(raw),
                                   'render_bbox_pdf_points':list(clip),'coordinate_source':str(layout.resolve()),
                                   'caption_candidate':caption,'figure_number':None,
                                   'parser_asset_paths':paths,'path':str(png.resolve()),'pdf_path':str(region_pdf.resolve()),
                                   'dpi':dpi,'needs_review':True})
    if not assets: raise ValueError('Parser returned no scientific regions; no manual-crop or text-only fallback was used')
    report = {'schema_version':'easyslides.scientific_figures.v1','status':'needs_review',
              'backend':'mineru_precision_layout','source_pdf':str(pdf.resolve()),
              'source_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),
              'layout_json':str(layout.resolve()),'asset_count':len(assets),'assets':assets,
              'review_requirements':['Confirm published figure/panel identity from caption and PDF text',
                                     'Check axes, units, legend, uncertainty and multipart completeness',
                                     'Region ordinals are asset IDs, never published figure numbers']}
    (output/'figures_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf',type=Path)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--layout',type=Path,help='Reuse an existing MinerU middle/layout JSON; no new upload')
    parser.add_argument('--backend',choices=('auto','mineru','pdffigures2'),default='auto')
    parser.add_argument('--dpi',type=int,default=300)
    args=parser.parse_args(argv)
    if not args.pdf.is_file() or args.dpi<150 or args.dpi>600: parser.error('Need an existing PDF and DPI between 150 and 600')
    try:
        layout=args.layout
        if layout is None:
            from source_to_md.mineru_preprocess import extract_precision, _get_token, MinerUError
            # Explicit Precision only: never downgrade to the text-only Agent API.
            import tempfile
            args.out.mkdir(parents=True,exist_ok=True)
            raw=Path(tempfile.mkdtemp(prefix='parser-',dir=args.out))
            backend = args.backend
            if backend == 'auto': backend = 'mineru' if _get_token() else 'pdffigures2'
            if backend == 'pdffigures2':
                from source_to_md.pdffigures2_preprocess import extract_pdf
                result=extract_pdf(args.pdf.resolve(),raw)
                index=json.loads(Path(result['asset_index_json']).read_text(encoding='utf-8'))
                report={'schema_version':'easyslides.scientific_figures.v1','status':'needs_review',
                        'backend':'pdffigures2','source_pdf':str(args.pdf.resolve()),
                        'source_sha256':hashlib.sha256(args.pdf.read_bytes()).hexdigest(),
                        'asset_count':index['asset_count'],'assets':index['assets'],
                        'parser_manifest':result['manifest_path'],
                        'review_requirements':['Verify published figure number, complete axes and legends against the retained raw parser JSON']}
                (args.out/'figures_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                print(json.dumps({'status':'needs_review','asset_count':index['asset_count'],'manifest':str(args.out/'figures_manifest.json')}))
                return 0
            try:
                extract_precision(args.pdf.resolve(),raw)
            except MinerUError as exc:
                raise RuntimeError(str(exc)) from exc
            layout=next(raw.rglob('layout.json'),None)
            if layout is None: raise ValueError('Precision response lacks layout coordinates; preserve raw output and resolve extraction')
        report=extract_layout_regions(args.pdf,layout,args.out,dpi=args.dpi)
        print(json.dumps({'status':report['status'],'asset_count':report['asset_count'],
                          'manifest':str((args.out/'figures_manifest.json').resolve())},ensure_ascii=False))
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(f'Figure extraction failed: {exc}')
        return 1


if __name__=='__main__': raise SystemExit(main())
