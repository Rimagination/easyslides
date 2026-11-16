import hashlib
import json

from pptx import Presentation
from pptx.enum.text import MSO_ANCHOR
from pptx.util import Inches

from scripts.academic_native_gate import review_status, validate_native_geometry


def test_geometry_checks_actual_anchor_and_exported_center(tmp_path):
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(40/3), Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(2), Inches(.5))
    box.text = 'Chapter'
    box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    path = tmp_path/'test.pptx'
    prs.save(path)
    (tmp_path/'page.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"><text data-center-lock="true" data-pptx-box-x="96" data-pptx-box-y="96" data-pptx-box-w="192" data-pptx-box-h="48">Chapter</text></svg>')
    (tmp_path/'render_manifest.json').write_text(json.dumps({'assignments':[{'svg':'page.svg'}]}))
    assert validate_native_geometry(path, tmp_path)['status'] == 'pass'
    box.text_frame.vertical_anchor = MSO_ANCHOR.TOP
    prs.save(path)
    assert validate_native_geometry(path, tmp_path)['status'] == 'fail'
    box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    box.left += Inches(.1)
    prs.save(path)
    assert validate_native_geometry(path, tmp_path)['status'] == 'fail'


def test_rendering_is_not_review_and_receipt_needs_full_coverage(tmp_path):
    pptx = tmp_path/'test.pptx'
    pptx.write_bytes(b'test fixture')
    digest = hashlib.sha256(pptx.read_bytes()).hexdigest()
    receipt = tmp_path/'render.json'
    receipt.write_text(json.dumps({'status':'pass','pptx_identity':{'sha256':digest},'slide_count':1,'render_identities':[]}))
    review = {'status':'pass','reviewer':'image_model','pptx_sha256':digest,'reviewed_slides':[1]}
    assert review_status(pptx,receipt,None,'available')['status'] == 'needs_visual_review'
    assert review_status(pptx,receipt,review,'available')['status'] == 'needs_visual_review'
    image = tmp_path/'slide.png'
    image.write_bytes(b'render fixture')
    receipt.write_text(json.dumps({'status':'pass','pptx_identity':{'sha256':digest},'slide_count':1,
                                 'render_identities':[{'path':str(image),'sha256':hashlib.sha256(image.read_bytes()).hexdigest()}]}))
    assert review_status(pptx,receipt,review,'unavailable')['status'] == 'needs_visual_review'
    assert review_status(pptx,receipt,review,'available')['status'] == 'pass'
    image.write_bytes(b'changed render')
    assert review_status(pptx,receipt,review,'available')['status'] == 'needs_visual_review'
