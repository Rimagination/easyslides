#!/usr/bin/env python3
"""Check actual native geometry and reviewed renders for academic delivery.

No image model is called here. Review evidence must come from an actual image
review or a human. A structural pass alone leaves delivery_ready false.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    from scripts.alignment_contract import _iter_pptx_text_frames, _normal_text
    from scripts.academic_qa_gate import run_academic_qa_file
    from scripts.validate_pptx_text_layout import validate_pptx_text_layout
except ModuleNotFoundError:
    from alignment_contract import _iter_pptx_text_frames, _normal_text
    from academic_qa_gate import run_academic_qa_file
    from validate_pptx_text_layout import validate_pptx_text_layout


def validate_native_geometry(pptx: Path, svg_dir: Path) -> dict:
    """Compare centre-locked frames after export, and verify header relations."""
    frames = _iter_pptx_text_frames(pptx)
    manifest = json.loads((svg_dir / 'render_manifest.json').read_text(encoding='utf-8'))
    issues, checked = [], 0
    from pptx import Presentation
    prs = Presentation(pptx)
    sx, sy = 1280/(prs.slide_width/9525), 720/(prs.slide_height/9525)
    for i, assignment in enumerate(manifest['assignments']):
        root = ET.parse(svg_dir / assignment['svg']).getroot()
        used = set()
        for el in root.iter():
            if el.tag.rsplit('}', 1)[-1] != 'text' or el.get('data-center-lock') != 'true':
                continue
            expected = ''.join(el.itertext())
            if not expected.strip(): continue
            checked += 1
            x,y,w,h = [float(el.get('data-pptx-box-'+k)) for k in ('x','y','w','h')]
            candidates = [(n,f) for n,f in enumerate(frames[i] if i<len(frames) else [])
                          if n not in used and _normal_text(f['text']) == _normal_text(expected)]
            if not candidates:
                issues.append({'code':'NATIVE-CENTER-TEXT-MISSING','severity':'blocking','slide_number':i+1,'text':expected})
                continue
            n,actual = min(candidates,key=lambda p:abs(p[1]['box'].cx*sx-x-w/2)+abs(p[1]['box'].cy*sy-y-h/2))
            used.add(n);box=actual['box']
            delta=max(abs(box.cx*sx-x-w/2),abs(box.cy*sy-y-h/2))
            if delta>1.5 or actual.get('vertical_anchor') not in ('ctr','middle','center'):
                issues.append({'code':'NATIVE-CENTER-DRIFT','severity':'blocking','slide_number':i+1,'text':expected,'delta_px':round(delta,3)})
            container_id=el.get('data-easyslides-center-container')
            if container_id:
                container=next((e for e in root.iter() if e.get('id')==container_id),None)
                if container is None or abs(y+h/2-float(container.get('y','0'))-float(container.get('height','0'))/2)>1:
                    issues.append({'code':'NATIVE-HEADER-CENTER','severity':'blocking','slide_number':i+1,'text':expected})
    if not checked:
        issues.append({'code':'NATIVE-CENTER-NOT-CHECKED','severity':'blocking','message':'No explicit centre relations were checked'})
    if len(manifest['assignments']) != len(frames):
        issues.append({'code':'NATIVE-SLIDE-COUNT','severity':'blocking','message':'Rendered source/PPTX page counts differ'})
    return {'status':'fail' if issues else 'pass','blocking_count':len(issues),'warning_count':0,
            'checked_center_lock_count':checked,'issues':issues}


def review_status(pptx: Path, render_receipt: Path, review: dict | None, image_input: str) -> dict:
    issues=[]
    digest=hashlib.sha256(pptx.read_bytes()).hexdigest()
    receipt=json.loads(render_receipt.read_text(encoding='utf-8')) if render_receipt.is_file() else {}
    identity=receipt.get('pptx_identity',{})
    if receipt.get('status')!='pass' or identity.get('sha256')!=digest:
        issues.append('Actual PPTX rendering receipt is absent or stale')
    rendered = receipt.get('render_identities') or []
    count = int(receipt.get('slide_count', 0))
    if count < 1 or len(rendered) != count or len({item.get('path') for item in rendered}) != count:
        issues.append('Rendering receipt must identify every page exactly once')
    # Never create or silently approve this record from pixel measurements.
    if not review or review.get('status')!='pass' or review.get('reviewer') not in {'human','image_model'}:
        issues.append('Rendered slides still need image-model or human review')
    else:
        if review.get('pptx_sha256')!=digest:issues.append('Review refers to another PPTX')
        if review.get('reviewer')=='image_model' and image_input!='available':issues.append('This host has no verified image input')
        expected=set(range(1,int(receipt.get('slide_count',0))+1))
        if not expected or set(review.get('reviewed_slides',[]))!=expected:issues.append('Review must cover every final rendered page')
        for item in rendered:
            p=Path(item.get('path',''))
            if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=item.get('sha256'):
                issues.append('A reviewed render is missing or changed');break
    return {'status':'needs_visual_review' if issues else 'pass','image_input':image_input,
            'reviewer':review.get('reviewer') if review else None,'issues':issues,'pptx_sha256':digest}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project',type=Path)
    parser.add_argument('--pptx',type=Path,required=True)
    parser.add_argument('--svg-dir',type=Path)
    parser.add_argument('--render-receipt',type=Path)
    parser.add_argument('--review',type=Path)
    parser.add_argument('--image-input',choices=('available','unavailable','unknown'),default='unknown')
    parser.add_argument('--report',type=Path)
    args=parser.parse_args(argv)
    project=args.project.resolve()
    plan=project/'deck_plan.json'
    svg_dir=args.svg_dir or project/'svg_output'
    geometry=validate_native_geometry(args.pptx,svg_dir)
    academic=run_academic_qa_file(plan,repo_root=Path(__file__).resolve().parents[1])
    text=validate_pptx_text_layout(args.pptx)
    review=json.loads(args.review.read_text(encoding='utf-8')) if args.review else None
    visual=review_status(args.pptx,args.render_receipt or project/'render_report.json',review,args.image_input)
    structural=all(r['status'] not in {'fail'} for r in (geometry,academic,text))
    ready=structural and visual['status']=='pass'
    report={'schema_version':'easyslides.academic_native_delivery.v1','status':'pass' if ready else 'needs_visual_review' if structural else 'fail',
            'delivery_ready':ready,'geometry':geometry,'academic':academic,'text_layout':text,'visual_review':visual}
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if ready else 1


if __name__=='__main__':
    raise SystemExit(main())
