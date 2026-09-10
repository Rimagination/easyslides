"""Test01 hybrid: traced detail, connected tree groups, reviewed text, regular buildings.

Reuses existing figure-specific annotations and architecture. Timings exclude
their original creation; this is not an unannotated-image recognition benchmark.
"""
from pathlib import Path
import json
import sys
import time


def trace_worker(jobs_file, packages):
    sys.path.insert(0, packages)
    import vtracer
    jobs=json.loads(Path(jobs_file).read_text(encoding='utf-8'))
    timings={}
    for job in jobs:
        start=time.perf_counter()
        vtracer.convert_image_to_svg_py(job['input'],job['output'],colormode='color',
            hierarchical='stacked',mode='spline',filter_speckle=2,color_precision=8,
            layer_difference=6,corner_threshold=60,length_threshold=4.0,
            max_iterations=10,splice_threshold=45,path_precision=3)
        timings[job['name']]=round(time.perf_counter()-start,4)
    Path(jobs_file).with_name('trace_times.json').write_text(json.dumps(timings,indent=2),encoding='utf-8')


if len(sys.argv)>1 and sys.argv[1]=='--trace-worker':
    trace_worker(sys.argv[2],sys.argv[3])
    raise SystemExit

import argparse
from copy import deepcopy
import subprocess
import xml.etree.ElementTree as ET

import cv2
import numpy as np
from pptx import Presentation
from pptx.oxml import parse_xml
from pptx.util import Emu

from rebuild_bitmap_figure import add_label, scaled_box
from svg_to_pptx.drawingml_converter import convert_svg_to_slide_shapes

NS='http://www.w3.org/2000/svg'
PX=9525
ET.register_namespace('',NS)


def save_pixels(path,pixels):
    if not cv2.imwrite(str(path),pixels):
        raise OSError(path)


def split_layers(source,data,output):
    h,w=source.shape[:2]
    gray=cv2.cvtColor(source,cv2.COLOR_BGR2GRAY)
    hsv=cv2.cvtColor(source,cv2.COLOR_BGR2HSV)
    text_mask=np.zeros((h,w),np.uint8)
    for label in data['labels']:
        for box in label.get('erase_boxes',[label['box']]):
            x,y,x2,y2=scaled_box(box,data['reference_size'],(w,h))
            tile=(gray[y:y2,x:x2]<145).astype(np.uint8)*255
            text_mask[y:y2,x:x2]|=cv2.dilate(tile,np.ones((3,3),np.uint8))
    # ponytail: figure-specific hue threshold; varied foliage needs segmentation.
    foliage=cv2.inRange(hsv,(44,45,0),(86,255,180))
    foliage[round(h*650/1388):]=0
    foliage=cv2.morphologyEx(foliage,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    count,labels,stats,_=cv2.connectedComponentsWithStats(foliage)
    tree_mask=np.zeros_like(foliage)
    trees=[]
    for i in range(1,count):
        x,y,cw,ch,area=stats[i]
        if area<100 or ch<25:
            continue
        x0,y0=max(0,x-3),max(0,y-3)
        x2,y2=min(w,x+cw+3),min(h,y+ch+3)
        alpha=(labels[y0:y2,x0:x2]==i).astype(np.uint8)*255
        alpha=cv2.dilate(alpha,np.ones((3,3),np.uint8))
        tree_mask[y0:y2,x0:x2]|=alpha
        rgba=cv2.cvtColor(source[y0:y2,x0:x2],cv2.COLOR_BGR2BGRA)
        rgba[:,:,3]=alpha
        name=f'Tree_region_{len(trees)+1:02d}'
        save_pixels(output/(name+'.png'),rgba)
        trees.append({'name':name,'x':int(x0),'y':int(y0),'width':int(x2-x0),'height':int(y2-y0)})
    building_mask=np.zeros_like(foliage)
    # Reuse three scene regions; only blue-gray building pixels are erased.
    b,g,r=cv2.split(source.astype(np.int16))
    building_color=((b>r+4)&(b>=g-3)&(hsv[:,:,1]<100)&(hsv[:,:,2]<250)).astype(np.uint8)*255
    for box in [(423,451,648,662),(806,555,1153,820),(1130,383,1516,593)]:
        x,y,x2,y2=scaled_box(box,(1792,1388),(w,h))
        building_mask[y:y2,x:x2]=building_color[y:y2,x:x2]
    building_mask=cv2.morphologyEx(building_mask,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
    contours,_=cv2.findContours(building_mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(building_mask,contours,-1,255,-1)
    building_mask=cv2.dilate(building_mask,np.ones((5,5),np.uint8))
    erase=text_mask|tree_mask|building_mask
    cleaned=cv2.inpaint(source,erase,3,cv2.INPAINT_TELEA)
    save_pixels(output/'cleaned_background.png',cleaned)
    save_pixels(output/'erase_mask.png',erase)
    return trees


def assemble(output,trees,semantic,size):
    w,h=size
    root=ET.Element('{'+NS+'}svg',width=str(w),height=str(h),viewBox=f'0 0 {w} {h}')
    def add_trace(file,name,transform=None):
        attrs={'id':name}
        if transform:
            attrs['transform']=transform
        group=ET.SubElement(root,'{'+NS+'}g',attrs)
        for node in ET.parse(file).getroot():
            group.append(deepcopy(node))
    add_trace(output/'background.svg','Traced_background_details')
    for tree in trees:
        add_trace(output/(tree['name']+'.svg'),tree['name'],f"translate({tree['x']},{tree['y']})")
    art=ET.parse(semantic).getroot()
    architecture_names={'Rear_service_buildings','Warehouse','Rear_office','Main_office_tower',
                        'Front_office','Industrial_plant'}
    for node in art:
        name=node.get('id','')
        if name in architecture_names or name.startswith('Town_'):
            wrapper=ET.SubElement(root,'{'+NS+'}g',id=name,transform=f'scale({w/1792},{h/1388})')
            copied=deepcopy(node)
            copied.attrib.pop('id',None)
            wrapper.extend(list(copied))
    ET.SubElement(root,'{'+NS+'}rect',id='Legend_border',x=str(1327*w/1792),
        y=str(167*h/1388),width=str(462*w/1792),height=str(124*h/1388),
        fill='none',stroke='#666666',**{'stroke-width':str(w/1792)})
    leaders=ET.SubElement(root,'{'+NS+'}g',id='Restored_annotation_leaders')
    for x,y1,y2 in ((632,1130,1241),(837,1205,1326)):
        ET.SubElement(leaders,'{'+NS+'}path',d=f'M{x*w/1792} {y1*h/1388} L{x*w/1792} {y2*h/1388}',
            fill='none',stroke='#606665',**{'stroke-width':str(1.3*w/1792)})
    path=output/'hybrid_geometry.svg'
    ET.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)
    return path,root


def make_deck(svg,data,size,output):
    xml,media,rels,targets=convert_svg_to_slide_shapes(svg)
    assert not media and not rels
    parsed=parse_xml(xml.encode())
    prs=Presentation()
    prs.slide_width,prs.slide_height=[Emu(n*PX) for n in size]
    slide=prs.slides.add_slide(prs.slide_layouts[6])
    names=dict(targets)
    for child in list(parsed.xpath('./p:cSld/p:spTree')[0])[2:]:
        slide.shapes._spTree.insert_element_before(deepcopy(child),'p:extLst')
    for shape in slide.shapes:
        if shape.shape_id in names:
            shape.name=names[shape.shape_id]
    slide.shapes[0].name='Traced_background_details'
    for label in data['labels']:
        add_label(slide,label,data,size)
    for i,node in enumerate(slide._element.xpath('.//p:cNvPr'),1):
        node.set('id',str(i))
    slide.notes_slide.notes_text_frame.text=('Hybrid experiment: VTracer details, connected foliage groups, '
        'existing manually reviewed text and prebuilt regular architecture. Dense connected forest is '
        'a group, not separated tree instances. Erased background is locally interpolated.')
    target=output/'test01_hybrid.pptx'
    prs.save(target)
    return target


def verify_and_demo(target,data,output):
    prs=Presentation(target)
    slide=prs.slides[0]
    shapes={s.name:s for s in slide.shapes}
    for label in data['labels']:
        assert shapes['Text_'+label['id']].text==label['text']
    assert not slide._element.xpath('.//p:pic')
    ids=slide._element.xpath('.//p:cNvPr/@id')
    assert len(ids)==len(set(ids))
    regions=[s for s in slide.shapes if s.name.startswith('Tree_region_')]
    # Isolated meadow tree, selected geometrically without a hand-maintained ID.
    sx=prs.slide_width/(1792*PX)
    tree=min(regions,key=lambda s:abs(s.left/PX/sx-875)+abs(s.top/PX/sx-315))
    tree.left+=round(90*PX*sx)
    shapes['Text_industry'].text_frame.paragraphs[0].runs[0].text='Editable text'
    prs.save(output/'test01_hybrid_edit_demo.pptx')
    return {'text_blocks':len(data['labels']),'tree_regions':len(regions),
            'top_level_objects':len(slide.shapes),'native_shapes':len(slide._element.xpath('.//p:sp')),
            'embedded_pictures':0,'moved_tree':tree.name}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','annotations','semantic','output','trace-python','packages'):
        p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args()
    started=time.perf_counter()
    output=args.output
    output.mkdir(parents=True,exist_ok=True)
    source=cv2.imread(str(args.source))
    if source is None:
        raise ValueError(args.source)
    size=source.shape[1],source.shape[0]
    data=json.loads(args.annotations.read_text(encoding='utf-8'))
    trees=split_layers(source,data,output)
    prepared=time.perf_counter()
    jobs=[{'name':'baseline','input':str(args.source),'output':str(output/'baseline.svg')},
          {'name':'background','input':str(output/'cleaned_background.png'),'output':str(output/'background.svg')}]
    jobs.extend({'name':t['name'],'input':str(output/(t['name']+'.png')),'output':str(output/(t['name']+'.svg'))} for t in trees)
    jobs_path=output/'trace_jobs.json'
    jobs_path.write_text(json.dumps(jobs),encoding='utf-8')
    subprocess.run([str(args.trace_python),str(Path(__file__).resolve()),'--trace-worker',str(jobs_path),str(args.packages)],check=True)
    traced=time.perf_counter()
    svg,root=assemble(output,trees,args.semantic,size)
    target=make_deck(svg,data,size,output)
    generated=time.perf_counter()
    report=verify_and_demo(target,data,output)
    trace_times=json.loads((output/'trace_times.json').read_text())
    report.update({'engine':'installed VTracer 0.6.15','source_pixels':size,
       'preparation_seconds':round(prepared-started,3),'baseline_trace_seconds':trace_times['baseline'],
       'hybrid_trace_seconds':round(sum(v for k,v in trace_times.items() if k!='baseline'),3),
       'assembly_and_pptx_seconds':round(generated-traced,3),
       'hybrid_generation_wall_seconds':round(generated-started-trace_times['baseline'],3),
       'excludes':'Existing text/building annotation creation; PowerPoint rendering; manual inspection.',
       'limitations':'Tree regions can contain multiple touching trees; source-specific segmentation and reused architecture.'})
    (output/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':
    main()
