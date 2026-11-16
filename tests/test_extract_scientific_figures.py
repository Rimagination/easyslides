import hashlib
import json

import pymupdf
import pytest

from scripts.extract_scientific_figures import extract_layout_regions


def test_exports_from_machine_layout_with_provenance_and_original_pdf_content(tmp_path):
    pdf = tmp_path/'paper.pdf'
    with pymupdf.open() as doc:
        page=doc.new_page(width=600,height=800)
        page.draw_line((100,200),(300,200))
        page.insert_text((110,190),'Original axis and units')
        doc.save(pdf)
    layout=tmp_path/'layout.json'
    layout.write_text(json.dumps({'pdf_info':[{'page_idx':0,'page_size':[600,800],
        'preproc_blocks':[{'type':'chart','bbox':[90,170,320,220],
            'blocks':[{'type':'chart_body','bbox':[90,170,320,220],
                       'lines':[{'spans':[{'type':'chart','image_path':'chart.jpg'}]}]}]}]}]}))
    out=tmp_path/'figures'
    report=extract_layout_regions(pdf,layout,out)
    assert report['source_sha256']==hashlib.sha256(pdf.read_bytes()).hexdigest()
    assert report['status']=='needs_review'
    region=report['assets'][0]
    assert region['figure_number'] is None  # ordinal must never fabricate a paper figure number
    assert region['source_bbox_pdf_points']==[90,170,320,220]
    assert region['dpi']==300 and region['needs_review']
    with pymupdf.open(region['pdf_path']) as doc:
        assert 'Original axis and units' in doc[0].get_text()
    assert (out/'figures_manifest.json').is_file()


def test_text_only_or_ambiguous_coordinate_outputs_are_not_figure_success(tmp_path):
    pdf=tmp_path/'paper.pdf'
    with pymupdf.open() as doc:
        doc.new_page();doc.save(pdf)
    layout=tmp_path/'layout.json'
    layout.write_text('{}')
    with pytest.raises(ValueError,match='Markdown is insufficient'):
        extract_layout_regions(pdf,layout,tmp_path/'figures')
    layout.write_text(json.dumps({'pdf_info':[{'page_idx':0,'preproc_blocks':[]}]}))
    with pytest.raises(ValueError,match='do not guess units'):
        extract_layout_regions(pdf,layout,tmp_path/'figures')
