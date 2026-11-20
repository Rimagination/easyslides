"""Source-led academic body compositions for the existing SVG/DrawingML backend.

The model selects evidence and writes the argument. This module handles shared
geometry, explicit text frames and scientific structures, without card chrome.
It checks declared evidence/structure, not whether a scientific claim is true.
"""
from __future__ import annotations

import math
import posixpath
import re
from typing import Callable, Any
from xml.etree import ElementTree as ET

try:
    from scripts.layout_metrics import estimate_text_width_px
except ModuleNotFoundError:
    from layout_metrics import estimate_text_width_px


CONTRACT = 'academic_native.v1'
NS = 'http://www.w3.org/2000/svg'
KINDS = {
    'figure_analysis', 'figure_comparison', 'method_diagram', 'evidence_matrix',
    'evidence_atlas', 'bar_comparison', 'dot_comparison', 'paired_comparison', 'split_comparison',
    'data_convergence', 'method_model',
}
FUNCTIONAL_ROLES = {'cover', 'toc', 'chapter', 'ending', 'paper_identity', 'references', 'title'}
TEACHING_COPY = re.compile(r'如何解读|读图指南|这页告诉我们|一图看懂|给小白')


def resolve_composition(composition: dict) -> tuple[str, str | None]:
    """Resolve the author's reading task and evidence to a supported arrangement."""
    kind = composition.get('kind')
    if kind == 'auto':
        task = composition.get('reading_task')
        if task == 'merge_data' and composition.get('inputs') and composition.get('output'):
            kind = 'data_convergence'
        elif task == 'explain_method':
            if composition.get('matrix') and composition.get('formula') and not composition.get('stages'):
                kind = 'method_model'
            elif composition.get('stages') and not (composition.get('matrix') or composition.get('formula')):
                kind = 'method_diagram'
        elif task == 'read_result' and composition.get('figure') and composition.get('facts'):
            kind = 'figure_analysis'
        elif task == 'compare':
            has_figures, has_series, has_panels = (bool(composition.get(key)) for key in ('figures', 'series', 'panels'))
            if has_panels and not (has_figures or has_series):
                kind = 'split_comparison'
            elif has_figures and not (has_series or has_panels):
                kind = 'figure_comparison'
            elif has_series and not (has_figures or has_panels):
                rows = composition['series']
                if 'value_labels' in composition or any(isinstance(row, dict) and ('first' in row or 'second' in row) for row in rows):
                    kind = 'paired_comparison'
                else:
                    kind = 'dot_comparison' if composition.get('focus') == 'rank' else 'bar_comparison'
        elif task == 'lookup_values' and composition.get('headers') and composition.get('rows'):
            kind = 'evidence_matrix'
        elif task == 'show_coverage' and composition.get('metrics') and composition.get('figures'):
            kind = 'evidence_atlas'
        if kind == 'auto':
            raise ValueError(f'No layout matches reading_task={task!r} and its primary evidence; see scientific-composition.md')
    if not isinstance(kind, str) or kind not in KINDS:
        raise ValueError(f'Unknown scientific composition: {kind}')
    if kind != 'figure_analysis':
        return kind, None
    placement = composition.get('placement', 'auto' if composition.get('kind') == 'auto' else 'left')
    if placement == 'auto':
        aspect = _figure_aspect(composition['figure'])
        placement = 'above' if aspect >= 2.35 else 'left'
    if placement not in ('left', 'right', 'above'):
        raise ValueError('Figure analysis placement must be auto, left, right or above')
    return kind, placement


def _figure_aspect(figure: dict) -> float:
    aspect = float(figure.get('aspect_ratio', 1.5))
    if not math.isfinite(aspect) or aspect <= 0:
        raise ValueError('Figure aspect_ratio must be a positive width-to-height ratio')
    return aspect


def _node(parent: ET.Element | None, tag: str, **attrs) -> ET.Element:
    el = ET.Element(f'{{{NS}}}{tag}', {key.replace('_', '-'): str(value) for key, value in attrs.items()})
    if parent is not None:
        parent.append(el)
    return el


def _wrap(value: str, width: float, size: float) -> list[str]:
    result = []
    for paragraph in str(value).split('\n'):
        line = ''
        # Keep citations and grouped numbers together, including 1,302.5.
        for token in re.findall(r'\([^()\n]*\bet al\.[^()\n]*\)|\d{1,3}(?:,\d{3})+(?:\.\d+)?|[A-Za-z0-9_]+|\s+|.', paragraph):
            if line and estimate_text_width_px(line + token, size) > width - 6:
                if token in '、，。；：！？）】》”’' and re.search(r'[\u4e00-\u9fff]$', line) and len(line) > 1:
                    # Keep Chinese closing punctuation attached to a character.
                    result.append(line[:-1].rstrip()); line = line[-1] + token
                else:
                    result.append(line.rstrip()); line = token.lstrip()
            else:
                line += token
        result.append(line.rstrip())
    if len(result) > 1 and re.fullmatch(r'[\u4e00-\u9fff]{1,2}[。，；！？]?', result[-1]):
        # Avoid a one-character final line without splitting a Latin word.
        tail = re.search(r'[\u4e00-\u9fff]{3}$', result[-2])
        if tail:
            result[-1] = tail.group() + result[-1]
            result[-2] = result[-2][:-3]
    return result


def _text(parent, x, y, w, h, value, *, role='body', bold=False, color='#17251F', align='left', valign='top'):
    size = {'body': 24, 'body_heading': 24, 'secondary': 64 / 3, 'caption': 56 / 3, 'display': 40, 'formula': 32}[role]
    lines = _wrap(value, w, size)
    step = size * 1.3
    if len(lines) * step > h + 1 or any(estimate_text_width_px(v, size) > w for v in lines):
        raise ValueError(f'Text exceeds {role} capacity; shorten or change composition, never shrink: {str(value)[:65]}')
    anchor, offset = {'left': ('start', 0), 'center': ('middle', w / 2), 'right': ('end', w)}[align]
    tx = x + offset
    baseline = y + size + ((h-len(lines)*step)/2 if valign == 'middle' else 0)
    font = {'caption': 'KaiTi, Times New Roman', 'formula': 'Cambria Math', 'display': 'Cambria'}.get(role, 'Microsoft YaHei')
    node = _node(parent, 'text', x=tx, y=y + size, font_family=font,
                 font_size=size, font_weight='700' if bold else '400', fill=color,
                 text_anchor=anchor,
                 data_pptx_textbox='true', data_pptx_box_x=x, data_pptx_box_y=y,
                 data_pptx_box_w=w, data_pptx_box_h=h, data_pptx_valign=valign,
                 data_pptx_no_wrap='true', data_pptx_line_height_ratio='1.3',
                 data_pptx_line_spacing_pct='130', data_text_role=role)
    for i, line in enumerate(lines):
        span = _node(node, 'tspan', x=tx, y=baseline + i * step)
        if role == 'caption':
            for run in re.findall(r'[\u2e80-\u9fff\uf900-\ufaff\u3000-\u303f\uff00-\uffef]+|[^\u2e80-\u9fff\uf900-\ufaff\u3000-\u303f\uff00-\uffef]+', line):
                font = 'KaiTi' if re.match(r'[\u2e80-\u9fff\uf900-\ufaff\u3000-\u303f\uff00-\uffef]', run) else 'Times New Roman'
                _node(span, 'tspan', font_family=font).text = run
        else:
            span.text = line
    return node


def _arrow(parent, x1, x2, y, color):
    # One closed silhouette: no overlapping shafts/triangles or exposed stubs.
    shoulder = x2 - min(13, (x2-x1)*.36)
    d = f'M {x1} {y-4} H {shoulder} V {y-10} L {x2} {y} L {shoulder} {y+10} V {y+4} H {x1} Z'
    _node(parent, 'path', d=d, fill=color, filter='url(#layout-arrow-shadow)', data_layout_arrow='solid-block')


def _figure(parent, box, figure, resolve, *, alignment='xMidYMid'):
    x, y, w, h = box
    if not figure.get('path') or not figure.get('caption'):
        raise ValueError('Scientific figure requires path and substantive caption with author/year')
    href = resolve(str(figure['path']))
    _node(parent, 'image', x=x, y=y, width=w, height=h, href=href,
          preserveAspectRatio=f'{alignment} meet', data_evidence_source=figure.get('source_id', ''))


def _facts(parent, x, y, w, height, facts, color, layout='stacked'):
    if not isinstance(facts, list) or not facts:
        raise ValueError('Figure analysis needs complementary facts, estimates or comparisons')
    if layout not in {'stacked', 'inline', 'braced'}:
        raise ValueError(f'Unknown figure fact layout: {layout}')
    headed = all(isinstance(f, dict) and 'heading' in f and 'text' in f for f in facts)
    if layout == 'braced':
        if not headed or any(not isinstance(f.get('group'), str) or not f['group'].strip() for f in facts):
            raise ValueError('Braced facts require a meaningful group on every headed fact')
        groups = []
        for fact in facts:
            if not groups or groups[-1][0] != fact['group']:
                if any(label == fact['group'] for label, _ in groups):
                    raise ValueError('Braced fact groups must be contiguous')
                groups.append((fact['group'], []))
            groups[-1][1].append(fact)
        if len(groups) < 2 or any(len(items) < 2 for _, items in groups):
            raise ValueError('Braced layout needs at least two groups with two or more facts each')
        label_w, brace_w, heading_w, gap = 56, 20, 110, 12
        body_x = x + label_w + brace_w + heading_w + gap
        body_w = x + w - body_x
        if body_w <= 0:
            raise ValueError('Braced layout lacks text capacity; use a wider region or another layout')
        group_heights = []
        for label, items in groups:
            row_heights = [max(len(_wrap(f['heading'], heading_w, 24)), len(_wrap(f['text'], body_w, 24))) * 31.2 for f in items]
            group_heights.append((max(sum(row_heights) + 16 * (len(items)-1), len(_wrap(label, label_w, 24))*31.2), row_heights))
        needed = sum(h for h, _ in group_heights) + 16 * (len(groups)-1)
        if needed > height + 0.01:
            raise ValueError('Braced facts exceed capacity; use a wider region or another layout')
        group_gap = min(28, (height - sum(h for h, _ in group_heights)) / (len(groups)-1))
        top = y
        for (label, items), (group_h, rows) in zip(groups, group_heights):
            _text(parent, x, top, label_w, group_h, label, bold=True, color=color, align='center', valign='middle')
            bx = x + label_w + 5
            mid, bottom = top + group_h/2, top + group_h
            d = (f'M {bx+15} {top} C {bx+2} {top} {bx+5} {top+12} {bx+5} {mid-12} '
                 f'C {bx+5} {mid-4} {bx} {mid} {bx-2} {mid} '
                 f'C {bx} {mid} {bx+5} {mid+4} {bx+5} {mid+12} '
                 f'C {bx+5} {bottom-12} {bx+2} {bottom} {bx+15} {bottom}')
            _node(parent, 'path', d=d, fill='none', stroke=color, stroke_width=1.5, data_fact_brace='group')
            row_y = top
            for fact, row_h in zip(items, rows):
                _text(parent, x+label_w+brace_w, row_y, heading_w, row_h, fact['heading'], role='body_heading', bold=True, color=color)
                _text(parent, body_x, row_y, body_w, row_h, fact['text'])
                row_y += row_h + 16
            top += group_h + group_gap
        return
    if layout == 'inline' and not headed:
        raise ValueError('Inline fact layout requires a heading and text for every fact')
    if headed:
        # Size each block from its real wrapped text; keep the title near its own
        # paragraph and distribute the remaining space between blocks.
        blocks = [(len(_wrap(f['heading'], w, 24))*31.2, len(_wrap(f['text'], w, 24))*31.2) for f in facts]
        needed = sum(h + 4 + b for h, b in blocks) + max(0, len(facts)-1)*16
        if layout == 'inline' or needed > height + 0.01:
            heading_w = min(140, max(72, max(estimate_text_width_px(f['heading'], 24) for f in facts) + 10))
            body_x = x + heading_w + 14
            body_w = w - heading_w - 14
            if body_w < 100:
                raise ValueError('Inline grouped facts exceed capacity; use a wider region or another layout')
            rows = [max(len(_wrap(f['heading'], heading_w, 24)), len(_wrap(f['text'], body_w, 24)))*31.2 for f in facts]
            if sum(rows) + max(0, len(rows)-1)*16 > height + 0.01:
                raise ValueError('Grouped facts exceed capacity; use a wider region or another layout')
            gap = min(28, (height - sum(rows))/(len(rows)-1)) if len(rows) > 1 else 0
            top = y
            for fact, row_h in zip(facts, rows):
                _text(parent, x, top, heading_w, row_h, fact['heading'], role='body_heading', bold=True, color=color)
                _text(parent, body_x, top, body_w, row_h, fact['text'])
                top += row_h + gap
            return
        group_gap = min(28, (height - sum(h + 4 + b for h, b in blocks)) / (len(facts)-1)) if len(facts) > 1 else 0
        top = y
        for fact, (heading_h, body_h) in zip(facts, blocks):
            _text(parent, x, top, w, heading_h, fact['heading'], role='body_heading', bold=True, color=color)
            _text(parent, x, top+heading_h+4, w, body_h, fact['text'])
            top += heading_h + 4 + body_h + group_gap
        return
    # Mixed plain statements, headed explanations and estimates still need
    # real inter-group spacing; measure their actual wrapped text, not slots.
    blocks = []
    for fact in facts:
        if isinstance(fact, str):
            blocks.append(('plain', len(_wrap(fact, w, 24))*31.2, 0))
        elif isinstance(fact, dict) and 'heading' in fact and 'text' in fact:
            blocks.append(('heading', len(_wrap(fact['heading'], w, 24))*31.2,
                           len(_wrap(fact['text'], w, 24))*31.2))
        elif isinstance(fact, dict) and 'value' in fact and 'label' in fact:
            blocks.append(('metric', len(_wrap(str(fact['value']), w, 40))*52,
                           len(_wrap(str(fact['label']), w, 64/3))*(64/3)*1.3))
        else:
            raise ValueError('A fact must be text, heading/text or value/label')
    heights = [first + (4 + second if kind != 'plain' else 0) for kind, first, second in blocks]
    if sum(heights) + max(0, len(facts)-1)*16 > height + 0.01:
        raise ValueError('Grouped facts exceed capacity; use a wider region or another layout')
    gap = min(28, (height-sum(heights))/(len(facts)-1)) if len(facts) > 1 else 0
    top = y
    for fact, (kind, first, second), block_h in zip(facts, blocks, heights):
        if kind == 'plain':
            _text(parent, x, top, w, first, fact)
        elif kind == 'heading':
            _text(parent, x, top, w, first, fact['heading'], role='body_heading', bold=True, color=color)
            _text(parent, x, top+first+4, w, second, fact['text'])
        else:
            _text(parent, x, top, w, first, str(fact['value']), role='display', bold=True, color=color)
            _text(parent, x, top+first+4, w, second, str(fact['label']), role='secondary')
        top += block_h + gap


def _metrics(parent, x, y, width, metrics, color):
    column = width / len(metrics)
    for i, metric in enumerate(metrics):
        left = x + i*column + 6
        _text(parent, left, y, column-12, 52, metric['value'], role='display', bold=True, color=color, align='center')
        _text(parent, left, y+57, column-12, 56, metric['label'], role='secondary', align='center')


def _convergence(parent, composition, color, accent):
    inputs, output = composition['inputs'], composition['output']
    if not 2 <= len(inputs) <= 3 or not 1 <= len(output['metrics']) <= 3 or not composition.get('caption'):
        raise ValueError('Data convergence needs 2–3 inputs, 1–3 output metrics and a sourced caption')
    width = (1152 - 40*(len(inputs)-1)) / len(inputs)
    centers = []
    for i, source in enumerate(inputs):
        x = 64 + i*(width+40)
        centers.append(x+width/2)
        metrics = source['metrics']
        if not 1 <= len(metrics) <= 2:
            raise ValueError('Each converging input needs 1–2 measured quantities')
        _text(parent, x, 204, width, 35, source['title'], role='body_heading', bold=True, color=color, align='center')
        _metrics(parent, x, 249, width, metrics, color)
        if source.get('note'):
            _text(parent, x, 362, width, 57, source['note'], role='secondary', align='center')
        _node(parent, 'line', x1=centers[-1], x2=centers[-1], y1=423, y2=440, stroke=accent, stroke_width=2)
    _node(parent, 'line', x1=centers[0], x2=centers[-1], y1=440, y2=440, stroke=accent, stroke_width=2)
    _node(parent, 'path', d='M 636 440 H 644 V 455 H 651 L 640 467 L 629 455 H 636 Z', fill=accent,
          filter='url(#layout-arrow-shadow)', data_layout_arrow='solid-block')
    _text(parent, 64, 478, 1152, 36, output['title'], role='body_heading', bold=True, color=color, align='center')
    _metrics(parent, 64, 516, 1152, output['metrics'], color)
    _text(parent, 64, 632, 1152, 30, composition['caption'], role='caption', align='center')


def _method_model(parent, composition, color, accent):
    matrix, formula = composition['matrix'], composition['formula']
    rows, cols = matrix['rows'], matrix['columns']
    cells = matrix.get('cells')
    if not 1 <= len(rows) <= 5 or not 1 <= len(cols) <= 5 or not 1 <= len(formula['lines']) <= 3:
        raise ValueError('Method model supports up to a 5 × 5 matrix and up to three formula lines')
    if cells is not None and (len(cells) != len(rows) or not matrix.get('note') or any(
        len(row) != len(cols) or any(type(value) is not bool for value in row) for row in cells
    )):
        raise ValueError('Matrix cells must match the dimensions, use booleans and include a source or schematic note')
    _text(parent, 64, 204, 540, 36, matrix['title'], role='body_heading', bold=True, color=color)
    _text(parent, 691, 204, 525, 36, formula['title'], role='body_heading', bold=True, color=color)
    cw = 420 / len(cols)
    for j, label in enumerate(cols):
        _text(parent, 180+j*cw, 250, cw, 58, label, role='secondary', align='center')
    for i, label in enumerate(rows):
        yy = 314+i*42
        _text(parent, 64, yy, 108, 38, label, role='secondary', valign='middle')
        for j in range(len(cols)):
            x = 180+j*cw
            _node(parent, 'rect', x=x+3, y=yy, width=cw-6, height=36, fill=color, fill_opacity='.10')
            if cells is not None and cells[i][j]:
                _node(parent, 'circle', cx=x+cw/2, cy=yy+18, r=6, fill=color)
    if matrix.get('note'):
        _text(parent, 64, 545, 540, 64, matrix['note'], role='secondary')
    _arrow(parent, 611, 673, 400, accent)
    _text(parent, 691, 259, 525, 133, '\n'.join(formula['lines']), role='formula', color=color)
    for i, fact in enumerate(formula.get('facts', [])):
        if i == 3:
            raise ValueError('Method model accepts at most three variable definitions or qualifications')
        _text(parent, 691, 401+i*65, 525, 62, fact)
    _text(parent, 64, 632, 1152, 30, composition['caption'], role='caption', align='center')


def _method(parent, composition, color):
    stages = composition.get('stages', [])
    if not 2 <= len(stages) <= 4:
        raise ValueError('Method diagram requires 2–4 meaningful stages')
    gap = 54
    w = (1152 - gap * (len(stages)-1)) / len(stages)
    parallel = composition.get('flow') == 'parallel'
    title_y, visual_y = (280, 356) if parallel else (204, 286)
    if parallel:
        _text(parent, 64, 204, 1152, 64, composition.get('input', ''), bold=True, color=color)
    for i, stage in enumerate(stages):
        x = 64 + i * (w+gap)
        _text(parent, x, title_y, w, 64, stage['title'], role='body_heading', bold=True, color=color)
        visual = stage.get('visual', {})
        kind = visual.get('type')
        if kind == 'matrix':
            rows, columns = visual.get('rows', []), visual.get('columns', [])
            if not rows or not columns or len(rows) > (3 if parallel else 5) or len(columns) > 4:
                raise ValueError('Matrix needs actual row/column labels, at most 5 × 4')
            left = min(94, w*.30); cw = (w-left)/len(columns); rh = 36
            for j, label in enumerate(columns):
                _text(parent, x+left+j*cw, visual_y, cw, 62, label, role='secondary', align='center')
            for r, label in enumerate(rows):
                yy = visual_y + 68 + r*rh
                _text(parent, x, yy, left-4, rh, label, role='secondary')
                for j in range(len(columns)):
                    _node(parent, 'rect', x=x+left+j*cw+4, y=yy+3, width=cw-8, height=rh-6,
                          fill=color, fill_opacity='.12', stroke=color, stroke_width='.5')
        elif kind == 'formula':
            formulas = visual.get('lines', [])
            if not formulas or len(formulas) > 3:
                raise ValueError('Formula stage needs source-supported expressions')
            for j, formula in enumerate(formulas):
                _text(parent, x, visual_y+24+j*54, w, 54, str(formula), color=color)
        elif kind == 'groups':
            labels = visual.get('labels', [])
            if not 1 <= len(labels) <= (3 if parallel else 4):
                raise ValueError('Output groups need 1–4 source-supported labels')
            for j, label in enumerate(labels):
                _text(parent, x, visual_y+14+j*48, w, 42, str(label), bold=True, color=color)
                _node(parent, 'line', x1=x, x2=x+w, y1=visual_y+56+j*48, y2=visual_y+56+j*48, stroke=color, stroke_opacity='.25')
        else:
            raise ValueError('NATIVE-METHOD-VISUAL: stages need a matrix, formula or meaningful output grouping; prose plus arrows is insufficient')
        _text(parent, x, 548, w, 76, '\n'.join(stage.get('facts', [])), role='secondary')
        if i < len(stages)-1 and not parallel:
            _arrow(parent, x+w+9, x+w+gap-9, 410, color)
    _text(parent, 64, 632, 1152, 30, composition.get('caption', ''), role='caption', align='center')


def _table(parent, x, y, width, height, headers, rows, color):
    if not headers or not rows or len(rows) > 6 or len(headers) > 5:
        raise ValueError('Comparison table needs 1–6 actual rows and at most 5 columns')
    table = _node(parent, 'g', data_pptx_table='true', data_pptx_table_x=x, data_pptx_table_y=y,
                  data_pptx_table_w=width, data_pptx_table_h=height)
    rh, cw = height/(len(rows)+1), width/len(headers)
    for r, values in enumerate([headers, *rows]):
        if len(values) != len(headers):
            raise ValueError('Comparison table row width must match headers')
        for c, value in enumerate(values):
            cell = _node(table, 'g', data_pptx_table_cell='true', data_pptx_table_row=r+1, data_pptx_table_col=c+1)
            _node(cell, 'rect', x=x+c*cw, y=y+r*rh, width=cw, height=rh, fill='#FFFFFF', stroke='#D3E4DA', stroke_width='.5')
            _text(cell, x+c*cw+10, y+r*rh+6, cw-20, rh-12, str(value), bold=r==0, color=color if r==0 else '#17251F')


def _comparison_rows(parent, series, x, width, top, height, color, accent, *, rank=False):
    if not 2 <= len(series) <= 6:
        raise ValueError('A comparison needs 2–6 source values in a common unit')
    values = [item['value'] for item in series]
    if any(type(value) not in (int, float) or value < 0 or (isinstance(value, float) and not math.isfinite(value))
           for value in values):
        raise ValueError('Comparison requires finite, nonnegative numeric values')
    maximum = max(values)
    if rank:
        series = sorted(series, key=lambda item: item['value'], reverse=True)
    category_width, value_width = (224, 176) if width >= 800 else (116, 112)
    axis = x+category_width+20
    bar_width = width-category_width-value_width-44
    step = height/len(series)
    _node(parent, 'line', x1=axis, y1=top, x2=axis, y2=top+height, stroke='#B7C1C8', stroke_width=1)
    for i, item in enumerate(series):
        value = item['value']
        cy = top + (i+.5)*step
        label_height = min(step-4, 58)
        _text(parent, x, cy-label_height/2, category_width, label_height, item['label'],
              role='body' if width >= 800 else 'secondary', valign='middle')
        if rank:
            endpoint = axis + bar_width*(value/(maximum or 1))
            _node(parent, 'line', x1=axis, x2=endpoint, y1=cy, y2=cy, stroke=accent, stroke_width=2)
            _node(parent, 'circle', cx=endpoint, cy=cy, r=7, fill=color)
        elif value:
            _node(parent, 'rect', x=axis, y=cy-13, width=bar_width*(value/maximum), height=26,
                  fill=color if value==maximum else accent)
        _text(parent, x+width-value_width, cy-22, value_width, 44, f'{value:,}', role='secondary',
              align='right', valign='middle', bold=value==maximum, color=color)


def _bar_comparison(parent, composition, color, accent, *, rank=False):
    if not composition.get('unit') or not composition.get('caption'):
        raise ValueError('Comparison needs a common unit and a sourced caption')
    _text(parent, 308, 204, 908, 36, f"单位：{composition['unit']}", role='secondary')
    _comparison_rows(parent, composition['series'], 64, 1152, 250, 350, color, accent, rank=rank)
    _text(parent, 64, 616, 1152, 48, composition['caption'], role='caption', align='center')


def _split_comparison(parent, composition, color, accent):
    panels = composition['panels']
    if len(panels) != 2 or not composition.get('caption'):
        raise ValueError('Split comparison needs two labeled panels and a sourced caption')
    for i, panel in enumerate(panels):
        if not panel.get('title') or not panel.get('unit'):
            raise ValueError('Each independent panel needs a measure title and unit')
        x = 64 + i*604
        _text(parent, x, 204, 548, 36, panel['title'], role='body_heading', bold=True, color=color)
        _text(parent, x, 248, 548, 56, f"单位：{panel['unit']} · 独立量尺", role='secondary')
        _comparison_rows(parent, panel['series'], x, 548, 312, 285, color, accent, rank=panel.get('focus') == 'rank')
    _node(parent, 'line', x1=640, x2=640, y1=204, y2=600, stroke='#D8E1D9', stroke_width=1)
    _text(parent, 64, 616, 1152, 48, composition['caption'], role='caption', align='center')


def _paired_comparison(parent, composition, color, accent):
    series = composition.get('series', [])
    labels = composition.get('value_labels', [])
    unit, caption = composition.get('unit'), composition.get('caption')
    if not 2 <= len(series) <= 6 or len(labels) != 2 or not unit or not caption:
        raise ValueError('Paired comparison needs 2–6 pairs, two value labels, a common unit and a sourced caption')
    values = [value for item in series for value in (item.get('first'), item.get('second'))]
    if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in values):
        raise ValueError('Paired comparison requires finite, nonnegative numeric values')
    maximum = max(values) or 1
    axis, width, top, height = 310, 670, 270, 320
    _node(parent, 'circle', cx=72, cy=223, r=7, fill=accent)
    _text(parent, 88, 204, 220, 38, labels[0], role='secondary')
    _node(parent, 'circle', cx=320, cy=223, r=7, fill=color)
    _text(parent, 336, 204, 220, 38, labels[1], role='secondary')
    _text(parent, 576, 204, 640, 38, f'单位：{unit}', role='secondary')
    step = height / len(series)
    for i, item in enumerate(series):
        cy = top + (i + .5) * step
        first = axis + width * item['first'] / maximum
        second = axis + width * item['second'] / maximum
        _text(parent, 64, cy - 22, 220, 44, item['label'], valign='middle')
        _node(parent, 'line', x1=axis, x2=axis + width, y1=cy, y2=cy, stroke='#D8E1D9', stroke_width=1)
        _node(parent, 'line', x1=first, x2=second, y1=cy, y2=cy, stroke=accent, stroke_width=4)
        _node(parent, 'circle', cx=first, cy=cy, r=7, fill=accent)
        _node(parent, 'circle', cx=second, cy=cy, r=7, fill=color)
        _text(parent, 1000, cy - 22, 216, 44, f"{item['first']:,} / {item['second']:,}", role='secondary', align='right', valign='middle')
    _text(parent, 64, 616, 1152, 48, caption, role='caption', align='center')


def _figure_analysis(parent, composition, placement, resolve, color):
    fig, facts = composition['figure'], composition.get('facts')
    fact_layout = composition.get('fact_layout', 'stacked')
    if placement == 'above':
        if fact_layout != 'stacked':
            raise ValueError('Inline or braced facts require a figure beside the text')
        if not isinstance(facts, list) or not 1 <= len(facts) <= 4:
            raise ValueError('Full-width figure analysis needs 1–4 complementary facts')
        _figure(parent, (64, 197, 1152, 298), fig, resolve)
        _text(parent, 64, 501, 1152, 50, fig['caption'], role='caption', align='center')
        width = (1152 - 30*(len(facts)-1)) / len(facts)
        for i, fact in enumerate(facts):
            _facts(parent, 64+i*(width+30), 555, width, 109, [fact], color)
        return

    # Aspect-informed width avoids squeezing compact figures into a banner.
    w = max(460, min(760, _figure_aspect(fig)*330+40))
    if 'figure_width' in composition:
        w = float(composition['figure_width'])
        if not math.isfinite(w) or not 460 <= w <= 760:
            raise ValueError('Figure width must be between 460 and 760 canvas pixels')
    caption_h = 88 if len(_wrap(fig['caption'], w, 56/3)) > 2 else 54
    caption_y = 662-caption_h
    figure_x, facts_x = (1216-w, 64) if placement == 'right' else (64, 64+w+42)
    _figure(parent, (figure_x, 204, w, caption_y-212), fig, resolve)
    _text(parent, figure_x, caption_y, w, caption_h, fig['caption'], role='caption', align='center')
    _facts(parent, facts_x, 212, 1110-w, 428, facts, color, layout=fact_layout)


def _comparison_band_height(values, width, size):
    return math.ceil(max((len(_wrap(value, width, size)) for value in values if value), default=0) * size * 1.3)


def _figure_comparison(parent, composition, resolve, color):
    figures = composition.get('figures', [])
    if not 2 <= len(figures) <= 4:
        raise ValueError('Figure comparison requires 2–4 complementary panels')
    legend = composition.get('legend')
    if legend:
        _text(parent, 64, 204, 1152, 34, legend, role='secondary')
    if len(figures) == 4:
        if any(fig.get('note') for fig in figures):
            raise ValueError('Use fewer panels when each figure needs an interpretation note')
        for i, fig in enumerate(figures):
            x = 64+(i % 2)*592
            y = (248+(i // 2)*204) if legend else (204+(i // 2)*224)
            _text(parent, x, y, 560, 34, fig.get('title', ''), bold=True, color=color)
            _figure(parent, (x, y+40, 560, 108 if legend else 130), fig, resolve)
            _text(parent, x, y+(154 if legend else 176), 560, 50, fig['caption'], role='caption', align='center')
        return

    width = (1152-32*(len(figures)-1))/len(figures)
    title_y = 248 if legend else 204
    title_h = _comparison_band_height((fig.get('title') for fig in figures), width, 24)
    caption_h = _comparison_band_height((fig['caption'] for fig in figures), width, 56/3)
    note_h = _comparison_band_height((fig.get('note') for fig in figures), width, 64/3)
    figure_y = title_y + (title_h+8 if title_h else 0)
    figure_h = 662-note_h-caption_h-(9 if note_h else 0)-9-figure_y
    if figure_h <= 0:
        raise ValueError('Comparison text leaves no room for the figures; shorten captions or split the comparison')
    if all('aspect_ratio' in fig for fig in figures):
        # Stop at the tallest natural fit. A width-limited image gains nothing
        # from a taller frame, which only pushes its caption away from the image.
        figure_h = min(figure_h, max(width/_figure_aspect(fig) for fig in figures))
    caption_y = figure_y+figure_h+9
    note_y = caption_y+caption_h+9
    for i, fig in enumerate(figures):
        x = 64+i*(width+32)
        if fig.get('title'):
            _text(parent, x, title_y, width, title_h, fig['title'], bold=True, color=color)
        _figure(parent, (x, figure_y, width, figure_h), fig, resolve, alignment='xMidYMax')
        _text(parent, x, caption_y, width, caption_h, fig['caption'], role='caption', align='center')
        if fig.get('note'):
            _text(parent, x, note_y, width, note_h, fig['note'], role='secondary')


def render_composition(composition: dict, *, image_resolver: Callable[[str], str], colors: dict) -> ET.Element:
    kind, placement = resolve_composition(composition)
    parent = _node(None, 'g', id='scientific-body', data_composition_kind=kind)
    color = colors.get('primary', '#194A37')
    accent = colors.get('accent', '#54786B')
    if kind == 'method_diagram':
        _method(parent, composition, color)
    elif kind == 'method_model':
        _method_model(parent, composition, color, accent)
    elif kind == 'data_convergence':
        _convergence(parent, composition, color, accent)
    elif kind in {'bar_comparison', 'dot_comparison'}:
        _bar_comparison(parent, composition, color, accent, rank=kind == 'dot_comparison')
    elif kind == 'paired_comparison':
        _paired_comparison(parent, composition, color, accent)
    elif kind == 'split_comparison':
        _split_comparison(parent, composition, color, accent)
    elif kind == 'figure_analysis':
        _figure_analysis(parent, composition, placement, image_resolver, color)
    elif kind == 'figure_comparison':
        _figure_comparison(parent, composition, image_resolver, color)
    elif kind == 'evidence_atlas':
        metrics, figures = composition.get('metrics', []), composition.get('figures', [])
        if not 2 <= len(metrics) <= 4 or not 1 <= len(figures) <= 3:
            raise ValueError('Evidence atlas needs 2–4 linked metrics and 1–3 evidence panels')
        sequential = composition.get('sequential', composition.get('kind') != 'auto')
        mw = (1152-42*(len(metrics)-1))/len(metrics)
        for i, metric in enumerate(metrics):
            x = 64+i*(mw+42)
            _text(parent, x, 204, mw, 56, str(metric['value']), role='display', bold=True, color=color)
            _text(parent, x, 266, mw, 54, metric['label'], role='secondary')
            if sequential and i < len(metrics)-1:
                _arrow(parent, x+mw+5, x+mw+37, 242, color)
        w = (1152-28*(len(figures)-1))/len(figures)
        for i, fig in enumerate(figures):
            x = 64+i*(w+28)
            _figure(parent, (x, 330, w, 210), fig, image_resolver)
            _text(parent, x, 552, w, 100, fig['caption'], role='caption', align='center')
    elif kind == 'evidence_matrix':
        figures = composition.get('figures', [])
        table_y = 204
        if figures:
            if len(figures) > 3: raise ValueError('Use at most three evidence columns')
            aligned = len(composition['headers']) == len(figures)+1
            cw = 1152/len(composition['headers'])
            w = cw-20 if aligned else (1152-30*(len(figures)-1))/len(figures)
            if aligned and composition.get('figure_label'):
                _text(parent, 64, 244, cw-20, 114, composition['figure_label'], bold=True, color=color)
            for i, fig in enumerate(figures):
                x = 64+(i+1)*cw+10 if aligned else 64+i*(w+30)
                _figure(parent, (x, 204, w, 150), fig, image_resolver)
                _text(parent, x, 364, w, 70, fig['caption'], role='caption', align='center')
            table_y = 442
        _table(parent, 64, table_y, 1152, 654-table_y, composition['headers'], composition['rows'], color)
    return parent


def _copy_text(value: Any) -> list[str]:
    if isinstance(value, str): return [value]
    if isinstance(value, list): return [s for v in value for s in _copy_text(v)]
    if isinstance(value, dict):
        return [s for k,v in value.items() if k not in {'path','source_id','source_ids','kind','type','aspect_ratio'} for s in _copy_text(v)]
    return []


def validate_academic_authoring(plan: dict) -> list[dict]:
    if plan.get('authoring_contract') != CONTRACT:
        return []  # existing edits and other production schemes keep their contract
    issues = []
    def fail(code, message, path, severity='error'):
        issues.append(dict(code=code, severity=severity, message=message, path=path))
    source_map = plan.get('source_map', [])
    source_ids = {str(x.get('id')) for x in source_map if isinstance(x, dict)} if isinstance(source_map, list) else set(source_map)
    source_policy = (plan.get('academic_brief') or {}).get('source_policy')
    if source_policy not in {'supplied_only','research','hybrid'}:
        fail('NATIVE-SOURCE-POLICY', 'Resolve evidence scope with the user; do not invent permission or supplied-only constraints', 'academic_brief.source_policy')
    recent = []
    first_braced_slide = None
    first_figure_slide = {}
    for i, slide in enumerate(plan.get('slides', [])):
        if not isinstance(slide, dict) or slide.get('role') in FUNCTIONAL_ROLES: continue
        loc = f'slides[{i}]'
        brief = slide.get('page_brief') or {}
        if not isinstance(brief, dict): brief = {}
        for key in ('question','information_gain','visual_rationale'):
            if not isinstance(brief.get(key), str) or not brief[key].strip():
                fail('NATIVE-PAGE-BRIEF', f'Every content page needs {key}, not a filler text quota', f'{loc}.page_brief.{key}')
        composition = slide.get('composition')
        payload = slide.get('slot_payload') or {}
        copy = [slide.get('action_title',''), *_copy_text(payload), *_copy_text(composition)]
        if any(TEACHING_COPY.search(s) for s in copy):
            fail('NATIVE-AUDIENCE-LANGUAGE', 'Use source-supported academic judgments, without teaching/meta reading labels', loc)
        title = re.sub(r'\W', '', str(payload.get('PAGE_TITLE', slide.get('action_title',''))))
        for key in ('KEY_MESSAGE','TAKEAWAY'):
            hint = re.sub(r'\W', '', ''.join(_copy_text(payload.get(key))))
            if len(title) >= 8 and title == hint:
                fail('NATIVE-REPEATED-COPY', 'Page title and hint must add complementary information', f'{loc}.slot_payload.{key}')
        if not isinstance(composition, dict):
            if not payload.get('FIGURE') and not str(slide.get('layout_id','')).endswith('result_table'):
                fail('NATIVE-SCIENTIFIC-VISUAL', 'Provide scientific evidence, a model/analysis diagram or a visual comparison; prose/arrow lists do not suffice', loc)
            continue
        if str(slide.get('layout_id', 'scientific_composition')).split('/')[-1] != 'scientific_composition':
            fail('NATIVE-COMPOSITION-ROUTE', 'Scientific composition must use its registered renderer, not a legacy text layout', f'{loc}.layout_id')
        try:
            kind, placement = resolve_composition(composition)
        except (KeyError, TypeError, ValueError) as exc:
            fail('NATIVE-COMPOSITION', str(exc), f'{loc}.composition')
            recent.clear()
            continue
        if kind == 'figure_analysis' and composition.get('fact_layout') == 'braced':
            if first_braced_slide is not None:
                fail('NATIVE-BRACE-REPETITION', f'Use the braced composition on at most one page per deck; first used at slides[{first_braced_slide}]', f'{loc}.composition.fact_layout')
            else:
                first_braced_slide = i
        recent.append((kind, placement))
        if len(recent) >= 3 and len(set(recent[-3:])) == 1:
            fail('NATIVE-LAYOUT-REPETITION', 'Three consecutive identical compositions require re-planning the visual argument', loc)
        refs = {x.get('source_id') for x in slide.get('evidence_sources', []) if isinstance(x, dict)}
        if not refs or not refs <= source_ids:
            fail('NATIVE-EVIDENCE', 'Page claims and explanatory diagrams need resolvable source references', f'{loc}.evidence_sources')
        figures = composition.get('figures') or []
        if not isinstance(figures, list):
            fail('NATIVE-VISUAL-SOURCE', 'figures must be a list of scientific image records', loc)
            figures = []
        figures = figures + ([composition['figure']] if composition.get('figure') else [])
        for j, fig in enumerate(figures):
            if not isinstance(fig, dict) or not fig.get('path') or not fig.get('caption') or fig.get('source_id') not in source_ids or fig.get('source_id') not in refs:
                fail('NATIVE-VISUAL-SOURCE', 'Scientific image requires a file, substantive caption and a source cited on this page', f'{loc}.composition.figures[{j}]')
            elif source_policy in {'research', 'hybrid'}:
                image_path = posixpath.normpath(str(fig['path']).replace('\\', '/'))
                first = first_figure_slide.setdefault(image_path, i)
                if first != i:
                    fail('NATIVE-REUSED-FIGURE',
                         f'Figure file also appears on slide {first+1}. Review whether this later use adds a comparison or interpretation.',
                         f'{loc}.composition.figures[{j}]', severity='warning')
        if kind == 'method_diagram':
            for stage in composition.get('stages', []):
                if (stage.get('visual') or {}).get('type') not in {'matrix','formula','groups'}:
                    fail('NATIVE-METHOD-VISUAL', 'Method stages need actual inputs, model/transform or outputs; words and arrows are insufficient', loc)
    return issues
