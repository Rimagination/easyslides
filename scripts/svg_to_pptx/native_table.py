"""Convert explicitly marked SVG table regions into native DrawingML tables.

The table marker is deliberately explicit. A row of cards or panels can look
like a table while carrying different editing semantics, so the reconstruction
inventory must identify a table before this converter promotes it to an
``a:tbl`` object.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from xml.sax.saxutils import escape as xml_escape
from xml.etree import ElementTree as ET

from .drawingml_context import ConvertContext, ShapeResult
from .drawingml_elements import convert_text
from .drawingml_styles import (
    build_fill_xml,
    build_stroke_xml,
    get_fill_opacity,
    get_stroke_opacity,
)
from .drawingml_utils import (
    _extract_inheritable_styles,
    ctx_h,
    ctx_w,
    ctx_x,
    ctx_y,
    px_to_emu,
)


TABLE_URI = "http://schemas.openxmlformats.org/drawingml/2006/table"
_NUMBER_RE = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
_TX_BODY_RE = re.compile(r"<p:txBody>.*?</p:txBody>", re.DOTALL)
_PARAGRAPH_RE = re.compile(r"<a:p>.*?</a:p>", re.DOTALL)


@dataclass
class _Cell:
    row: int
    col: int
    row_span: int
    col_span: int
    element: ET.Element
    rect: ET.Element | None
    text_nodes: list[ET.Element]


def _local_tag(elem: ET.Element) -> str:
    return elem.tag.split("}", 1)[-1] if isinstance(elem.tag, str) else ""


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def is_native_table(elem: ET.Element) -> bool:
    """Return whether *elem* carries the explicit native-table marker."""
    return _local_tag(elem) == "g" and _truthy(elem.get("data-pptx-table"))


def _positive_int(elem: ET.Element, *attrs: str) -> int | None:
    for attr in attrs:
        raw = elem.get(attr)
        if raw is None:
            continue
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"native table {attr} must be an integer") from exc
        if value <= 0:
            raise ValueError(f"native table {attr} must be positive")
        return value
    return None


def _lengths(elem: ET.Element, *attrs: str) -> list[float] | None:
    raw = None
    for attr in attrs:
        if elem.get(attr) is not None:
            raw = elem.get(attr)
            break
    if raw is None:
        return None
    values = [float(token) for token in _NUMBER_RE.findall(raw)]
    if not values or any(value <= 0 for value in values):
        raise ValueError("native table row/column lengths must be positive")
    return values


def _box(elem: ET.Element) -> tuple[float, float, float, float] | None:
    names = {
        "x": ("x", "data-pptx-box-x", "data-pptx-cell-x"),
        "y": ("y", "data-pptx-box-y", "data-pptx-cell-y"),
        "w": ("width", "data-pptx-box-w", "data-pptx-cell-w"),
        "h": ("height", "data-pptx-box-h", "data-pptx-cell-h"),
    }
    values: list[float] = []
    for key in ("x", "y", "w", "h"):
        raw = next((elem.get(name) for name in names[key] if elem.get(name) is not None), None)
        if raw is None:
            return None
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        if key in {"w", "h"} and value <= 0:
            return None
        values.append(value)
    return tuple(values)  # type: ignore[return-value]


def _cell_nodes(table: ET.Element) -> list[_Cell]:
    cells: list[_Cell] = []
    for child in table:
        if _local_tag(child) != "g" or not _truthy(child.get("data-pptx-table-cell")):
            continue
        row = _positive_int(child, "data-pptx-table-row", "data-row")
        col = _positive_int(child, "data-pptx-table-col", "data-col")
        if row is None or col is None:
            raise ValueError("native table cells must declare data-pptx-table-row and data-pptx-table-col")
        row -= 1
        col -= 1
        row_span = _positive_int(child, "data-pptx-table-row-span", "data-row-span") or 1
        col_span = _positive_int(child, "data-pptx-table-col-span", "data-col-span") or 1
        rect = next((node for node in child if _local_tag(node) == "rect"), None)
        text_nodes = [node for node in child.iter() if _local_tag(node) == "text"]
        cells.append(_Cell(row, col, row_span, col_span, child, rect, text_nodes))
    return cells


def _infer_lengths(cells: list[_Cell], count: int, axis: str, origin: float, total: float) -> list[float]:
    boundaries: set[float] = {origin, origin + total}
    for cell in cells:
        if cell.rect is None or cell.col_span != 1 or cell.row_span != 1:
            continue
        box = _box(cell.rect)
        if box is None:
            continue
        start = box[0] if axis == "x" else box[1]
        end = box[0] + box[2] if axis == "x" else box[1] + box[3]
        boundaries.update({start, end})
    ordered = sorted(value for value in boundaries if origin - 0.01 <= value <= origin + total + 0.01)
    if len(ordered) == count + 1:
        lengths = [ordered[index + 1] - ordered[index] for index in range(count)]
        if all(value > 0 for value in lengths):
            return lengths
    # ponytail: equal-size fallback keeps incomplete hand-authored markers
    # usable; measured cell geometry remains the upgrade path.
    return [total / count] * count


def _table_frame(
    table: ET.Element,
    cells: list[_Cell],
    col_lengths: list[float] | None,
    row_lengths: list[float] | None,
    columns: int,
    rows: int,
) -> tuple[float, float, float, float, list[float], list[float]]:
    rect_boxes = [_box(cell.rect) for cell in cells if cell.rect is not None and _box(cell.rect) is not None]
    explicit_x = table.get("data-pptx-table-x") or table.get("data-pptx-box-x")
    explicit_y = table.get("data-pptx-table-y") or table.get("data-pptx-box-y")
    explicit_w = table.get("data-pptx-table-w") or table.get("data-pptx-box-w")
    explicit_h = table.get("data-pptx-table-h") or table.get("data-pptx-box-h")

    if explicit_x is not None:
        x = float(explicit_x)
    elif rect_boxes:
        x = min(box[0] for box in rect_boxes)
    else:
        x = 0.0
    if explicit_y is not None:
        y = float(explicit_y)
    elif rect_boxes:
        y = min(box[1] for box in rect_boxes)
    else:
        y = 0.0

    inferred_w = sum(col_lengths or [])
    inferred_h = sum(row_lengths or [])
    if explicit_w is not None:
        width = float(explicit_w)
    elif rect_boxes:
        width = max(box[0] + box[2] for box in rect_boxes) - x
    elif inferred_w:
        width = inferred_w
    else:
        raise ValueError("native table needs a frame width or cell rectangles")
    if explicit_h is not None:
        height = float(explicit_h)
    elif rect_boxes:
        height = max(box[1] + box[3] for box in rect_boxes) - y
    elif inferred_h:
        height = inferred_h
    else:
        raise ValueError("native table needs a frame height or cell rectangles")
    if width <= 0 or height <= 0:
        raise ValueError("native table frame must have positive width and height")

    columns_widths = col_lengths or _infer_lengths(cells, columns, "x", x, width)
    rows_heights = row_lengths or _infer_lengths(cells, rows, "y", y, height)
    if len(columns_widths) != columns:
        raise ValueError("native table column length count does not match the table column count")
    if len(rows_heights) != rows:
        raise ValueError("native table row length count does not match the table row count")
    return x, y, width, height, columns_widths, rows_heights


def _side_line(stroke_xml: str, side: str) -> str:
    match = re.fullmatch(r"<a:ln(?P<attrs>[^>]*)>(?P<body>.*)</a:ln>", stroke_xml, re.DOTALL)
    if not match:
        return f"<a:ln{side}><a:noFill/></a:ln{side}>"
    return f"<a:ln{side}{match.group('attrs')}>{match.group('body')}</a:ln{side}>"


def _cell_margins(cell: ET.Element) -> str:
    attrs = []
    for name, fallback in (
        ("marL", "0"),
        ("marR", "0"),
        ("marT", "0"),
        ("marB", "0"),
    ):
        raw = cell.get(f"data-pptx-cell-{name}") or cell.get(f"data-pptx-{name}") or fallback
        try:
            value = max(0, int(float(raw)))
        except (TypeError, ValueError):
            value = 0
        attrs.append(f'{name}="{value}"')
    return " ".join(attrs)


def _cell_vertical_anchor(cell: _Cell) -> str | None:
    raw = cell.element.get("data-pptx-table-valign") or cell.element.get("data-pptx-valign")
    if raw is None:
        raw = next(
            (
                node.get("data-pptx-table-valign") or node.get("data-pptx-valign")
                for node in cell.text_nodes
                if node.get("data-pptx-table-valign") is not None or node.get("data-pptx-valign") is not None
            ),
            None,
        )
    return {
        "top": "t",
        "t": "t",
        "middle": "ctr",
        "center": "ctr",
        "ctr": "ctr",
        "bottom": "b",
        "b": "b",
    }.get(str(raw or "").strip().lower())


def _empty_tx_body() -> str:
    return "<a:txBody><a:bodyPr/><a:lstStyle/><a:p/></a:txBody>"


def _text_body(text_nodes: list[ET.Element], cell: ET.Element, text_ctx: ConvertContext) -> str:
    if not text_nodes:
        return _empty_tx_body()

    paragraphs: list[str] = []
    first_body: str | None = None
    for original in text_nodes:
        node = copy.deepcopy(original)
        align = cell.get("data-pptx-table-align") or cell.get("data-pptx-align")
        if align and node.get("text-anchor") is None:
            node.set("text-anchor", {"left": "start", "center": "middle", "right": "end"}.get(align.lower(), align))
        valign = cell.get("data-pptx-table-valign") or cell.get("data-pptx-valign")
        if valign and node.get("data-pptx-valign") is None:
            node.set("data-pptx-valign", valign)
        result = convert_text(node, text_ctx)
        if result is None:
            continue
        match = _TX_BODY_RE.search(result.xml)
        if not match:
            raise ValueError("native table cell text did not produce a text body")
        # convert_text emits the text-body wrapper used by a shape. A table
        # cell uses the DrawingML ``a:txBody`` wrapper under ``a:tc``.
        body = match.group(0).replace("<p:txBody>", "<a:txBody>").replace("</p:txBody>", "</a:txBody>")
        if first_body is None:
            first_body = body
        else:
            paragraphs.extend(_PARAGRAPH_RE.findall(body))
    if first_body is None:
        return _empty_tx_body()
    if paragraphs:
        first_body = first_body.replace("</a:txBody>", "\n" + "\n".join(paragraphs) + "</a:txBody>", 1)
    return first_body


def _cell_xml(
    cell: _Cell | None,
    anchor: _Cell | None,
    row: int,
    col: int,
    table_ctx: ConvertContext,
) -> str:
    if cell is None:
        merge_attrs = []
        if anchor is not None:
            if row > anchor.row:
                merge_attrs.append('vMerge="1"')
            if col > anchor.col:
                merge_attrs.append('hMerge="1"')
        merge = f" {' '.join(merge_attrs)}" if merge_attrs else ""
        return f"<a:tc{merge}>{_empty_tx_body()}<a:tcPr/></a:tc>"

    cell_ctx = table_ctx.child(style_overrides=_extract_inheritable_styles(cell.element))
    style = cell.rect
    if style is None:
        style = ET.Element("rect", {"fill": "none", "stroke": "none"})
    fill = build_fill_xml(style, cell_ctx, get_fill_opacity(style, cell_ctx))
    stroke = build_stroke_xml(style, cell_ctx, get_stroke_opacity(style, cell_ctx))
    body = _text_body(cell.text_nodes, cell.element, cell_ctx)
    table_ctx.sync_from_child(cell_ctx)

    row_span = cell.row_span if anchor is cell else 1
    col_span = cell.col_span if anchor is cell else 1
    merge_attrs = []
    if anchor is not None and anchor is not cell:
        if cell.row > anchor.row:
            merge_attrs.append('vMerge="1"')
        if cell.col > anchor.col:
            merge_attrs.append('hMerge="1"')
    if anchor is cell:
        if row_span > 1:
            merge_attrs.append(f'rowSpan="{row_span}"')
        if col_span > 1:
            merge_attrs.append(f'gridSpan="{col_span}"')
    border_xml = "".join(_side_line(stroke, side) for side in ("L", "R", "T", "B"))
    # DrawingML places cell borders before the cell fill inside tcPr.
    vertical_anchor = _cell_vertical_anchor(cell)
    anchor_attr = f' anchor="{vertical_anchor}"' if vertical_anchor else ""
    tc_pr = f"<a:tcPr{anchor_attr} {_cell_margins(cell.element)}>{border_xml}{fill}</a:tcPr>"
    return (
        f"<a:tc{' ' + ' '.join(merge_attrs) if merge_attrs else ''}>"
        f"{body}{tc_pr}</a:tc>"
    )


def convert_native_table(elem: ET.Element, ctx: ConvertContext) -> ShapeResult:
    """Convert an explicit ``data-pptx-table`` group to ``p:graphicFrame``."""
    if elem.get("transform") or ctx.use_transform_matrix:
        raise ValueError("native table coordinates must be absolute; remove the table/group transform")

    cells = _cell_nodes(elem)
    if not cells:
        raise ValueError("native table must contain at least one marked cell")
    columns = _positive_int(elem, "data-pptx-table-cols", "data-pptx-table-columns")
    rows = _positive_int(elem, "data-pptx-table-rows")
    if columns is None:
        columns = max(cell.col + cell.col_span for cell in cells)
    if rows is None:
        rows = max(cell.row + cell.row_span for cell in cells)

    for cell in cells:
        if cell.row < 0 or cell.col < 0 or cell.row + cell.row_span > rows or cell.col + cell.col_span > columns:
            raise ValueError("native table cell span is outside the declared table grid")

    occupied: dict[tuple[int, int], _Cell] = {}
    for cell in cells:
        for row in range(cell.row, cell.row + cell.row_span):
            for col in range(cell.col, cell.col + cell.col_span):
                if (row, col) in occupied:
                    raise ValueError("native table cells overlap")
                occupied[(row, col)] = cell

    col_lengths = _lengths(elem, "data-pptx-table-col-widths", "data-pptx-table-column-widths")
    row_lengths = _lengths(elem, "data-pptx-table-row-heights", "data-pptx-table-heights")
    x, y, width, height, col_lengths, row_lengths = _table_frame(
        elem, cells, col_lengths, row_lengths, columns, rows,
    )
    x = ctx_x(x, ctx)
    y = ctx_y(y, ctx)
    width = ctx_w(width, ctx)
    height = ctx_h(height, ctx)
    col_lengths = [ctx_w(value, ctx) for value in col_lengths]
    row_lengths = [ctx_h(value, ctx) for value in row_lengths]

    table_id = ctx.next_id()
    table_ctx = ctx.child(style_overrides=_extract_inheritable_styles(elem))
    rows_xml: list[str] = []
    for row in range(rows):
        row_cells: list[str] = []
        for col in range(columns):
            owner = occupied.get((row, col))
            if owner is None:
                row_cells.append(_cell_xml(None, None, row, col, table_ctx))
                continue
            if (owner.row, owner.col) == (row, col):
                row_cells.append(_cell_xml(owner, owner, row, col, table_ctx))
            else:
                row_cells.append(_cell_xml(None, owner, row, col, table_ctx))
        rows_xml.append(f'<a:tr h="{max(1, px_to_emu(row_lengths[row]))}">' + "".join(row_cells) + "</a:tr>")
    ctx.sync_from_child(table_ctx)

    grid_xml = "".join(f'<a:gridCol w="{max(1, px_to_emu(value))}"/>' for value in col_lengths)
    table_name = xml_escape(elem.get("data-pptx-table-name") or elem.get("id") or f"Table {table_id}")
    if ctx.depth == 0 and elem.get("id"):
        ctx.anim_targets.append((table_id, elem.get("id")))
    xml = f'''<p:graphicFrame>
<p:nvGraphicFramePr>
<p:cNvPr id="{table_id}" name="{table_name}"/>
<p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr>
<p:nvPr/>
</p:nvGraphicFramePr>
<p:xfrm><a:off x="{px_to_emu(x)}" y="{px_to_emu(y)}"/><a:ext cx="{max(1, px_to_emu(width))}" cy="{max(1, px_to_emu(height))}"/></p:xfrm>
<a:graphic><a:graphicData uri="{TABLE_URI}">
<a:tbl>
<a:tblPr firstRow="1" bandRow="0"/>
<a:tblGrid>{grid_xml}</a:tblGrid>
{"".join(rows_xml)}
</a:tbl>
</a:graphicData></a:graphic>
</p:graphicFrame>'''
    return ShapeResult(
        xml=xml,
        bounds_emu=(px_to_emu(x), px_to_emu(y), px_to_emu(x + width), px_to_emu(y + height)),
    )
