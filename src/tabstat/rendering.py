"""
tabstat/rendering.py
─────────────────────
Canvas/grid text-table renderer.

All rows (header + data) are first represented as structured cell objects.
Column widths are computed from ALL content — headers and data alike — so
header labels like "Alto Riesgo  (n=30)" can never be truncated by a narrow
data column.

P-value spanning
─────────────────
For categorical variables with ≥2 categories the p-value is injected into
the separator line between category rows (SPSS-style spanning).  In the
canvas model this is represented as a SCell with a label at the p/test
column positions of that separator row.
"""
from __future__ import annotations

import textwrap
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# Column Layout  (unchanged public API)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ColLayout:
    n_cols:          int
    char_idx:        int                  = 0
    total_idx:       Optional[int]        = None
    group_idxs:      List[int]            = field(default_factory=list)
    p_idx:           Optional[int]        = None
    test_idx:        Optional[int]        = None
    smd_idx:         Optional[int]        = None
    split_count_pct: bool                 = False


def build_col_layout(
    group_cols:        List[str],
    groups:            List[Any],
    display_overall:   bool,
    overall_position:  str,
    display_p_values:  bool,
    display_test_name: bool,
    display_smd:       bool,
    split_count_pct:   bool = False,
) -> ColLayout:
    layout = ColLayout(n_cols=0, split_count_pct=split_count_pct)
    idx = 1
    cols_per_group = 2 if split_count_pct else 1

    cols_per_total = 2 if split_count_pct else 1

    if display_overall and overall_position == "first":
        layout.total_idx = idx
        idx += cols_per_total

    if groups:
        layout.group_idxs = list(range(idx, idx + len(groups) * cols_per_group, cols_per_group))
        idx += len(groups) * cols_per_group

    if display_overall and overall_position == "last":
        layout.total_idx = idx
        idx += cols_per_total

    if group_cols and display_p_values:
        layout.p_idx = idx
        idx += 1
        if display_test_name:
            layout.test_idx = idx
            idx += 1

    if group_cols and display_smd:
        layout.smd_idx = idx
        idx += 1

    layout.n_cols = idx
    return layout


# ─────────────────────────────────────────────────────────────────────────────
# Canvas primitives
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class GCell:
    """Data cell.  colspan > 1 spans multiple columns."""
    content: str = ""
    colspan: int = 1
    align:   str = "c"    # "l" | "c"


@dataclass
class SCell:
    """Separator cell.  fill fills the width; optional label shown centred."""
    fill:    str = "-"
    label:   str = ""
    colspan: int = 1


AnyCell = Union[GCell, SCell]
_Row    = Tuple[str, List[AnyCell]]   # ("data"|"sep", cells)


# ─────────────────────────────────────────────────────────────────────────────
# Width computation
# ─────────────────────────────────────────────────────────────────────────────

def _compute_widths(rows: List[_Row], n_cols: int) -> List[int]:
    """
    Derive minimum column widths from all rows.

    Pass 1 – single-column cells set their column's floor.
    Pass 2 – spanning cells expand the last spanned column if needed.
    """
    widths = [3] * n_cols   # minimum: 1 content char + 2 padding

    # Pass 1: single-column cells
    for _rtype, row in rows:
        col = 0
        for cell in row:
            if cell.colspan == 1:
                text = cell.content if isinstance(cell, GCell) else cell.label
                if text:
                    widths[col] = max(widths[col], len(str(text)) + 2)
            col += cell.colspan

    # Pass 2: spanning cells
    for _rtype, row in rows:
        col = 0
        for cell in row:
            if cell.colspan > 1:
                text = cell.content if isinstance(cell, GCell) else cell.label
                if text:
                    needed = len(str(text)) + 2
                    avail  = sum(widths[col:col + cell.colspan]) + (cell.colspan - 1)
                    if needed > avail:
                        widths[col + cell.colspan - 1] += needed - avail
            col += cell.colspan

    return widths


# ─────────────────────────────────────────────────────────────────────────────
# Row rendering
# ─────────────────────────────────────────────────────────────────────────────

def _render_data_row(row: List[GCell], widths: List[int]) -> str:
    parts: List[str] = []
    col = 0
    for cell in row:
        w  = (widths[col] if cell.colspan == 1
              else sum(widths[col:col + cell.colspan]) + (cell.colspan - 1))
        cw = w - 2
        s  = str(cell.content) if cell.content is not None else ""
        parts.append(f" {s.ljust(cw)[:cw]} " if cell.align == "l"
                     else f" {s.center(cw)[:cw]} ")
        col += cell.colspan
    return "|" + "|".join(parts) + "|"


def _render_sep_row(row: List[SCell], widths: List[int]) -> str:
    parts: List[str] = []
    col = 0
    for cell in row:
        w = (widths[col] if cell.colspan == 1
             else sum(widths[col:col + cell.colspan]) + (cell.colspan - 1))
        if cell.label:
            cw = w - 2
            parts.append(f" {str(cell.label).center(cw)} ")
        else:
            parts.append(cell.fill * w)
        col += cell.colspan
    return "+" + "+".join(parts) + "+"


# ─────────────────────────────────────────────────────────────────────────────
# Title / Footnote boxes
# ─────────────────────────────────────────────────────────────────────────────

def _render_title(title: str, table_width: int) -> str:
    inner = table_width - 4
    lines = ["+" + "=" * (table_width - 2) + "+"]
    for part in textwrap.wrap(title, width=inner) or [""]:
        lines.append("| " + part.center(inner) + " |")
    lines.append("+" + "=" * (table_width - 2) + "+")
    return "\n".join(lines)


def _render_footnote(footnote: str, table_width: int) -> str:
    inner = table_width - 4
    lines = ["+" + "-" * (table_width - 2) + "+"]
    for part in textwrap.wrap(footnote, width=inner) or [""]:
        lines.append("| " + part.ljust(inner) + " |")
    lines.append("+" + "-" * (table_width - 2) + "+")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Header builders — return List[_Row]
# ─────────────────────────────────────────────────────────────────────────────

def _label_sep_row(lay: ColLayout, n_total: int,
                   fill: str = "=", total_show_n: bool = False) -> List[SCell]:
    """Standard label-separator: Characteristic / Total / p-val / etc."""
    cells: List[SCell] = []
    col = 0
    while col < lay.n_cols:
        if col == lay.char_idx:
            cells.append(SCell(fill, "Characteristic")); col += 1
        elif lay.total_idx is not None and col == lay.total_idx:
            lbl = f"Total (n={n_total})" if total_show_n else "Total"
            span = 2 if lay.split_count_pct else 1
            cells.append(SCell(fill, lbl, span)); col += span
        elif lay.p_idx is not None and col == lay.p_idx:
            cells.append(SCell(fill, "p-val")); col += 1
        elif lay.test_idx is not None and col == lay.test_idx:
            cells.append(SCell(fill, "Test")); col += 1
        elif lay.smd_idx is not None and col == lay.smd_idx:
            cells.append(SCell(fill, "SMD")); col += 1
        else:
            cells.append(SCell(fill)); col += 1
    return cells


def _build_header_rows(
    lay:          ColLayout,
    group_cols:   List[str],
    groups:       List[Any],
    group_counts: Dict[Any, int],
    n_total:      int,
) -> List[_Row]:
    """
    Build all header rows as (rtype, cells) pairs.
    Does NOT include the final === data-start separator.
    """
    n_levels = len(group_cols)
    if n_levels == 0 or not groups:
        # No grouping: single label-sep row with n= in Total column
        return [("sep", _label_sep_row(lay, n_total, "=", total_show_n=True))]
    if n_levels == 1:
        return _header_single_level(lay, group_cols, groups, group_counts, n_total)
    return _header_multi_level(lay, group_cols, groups, group_counts, n_total)


def _header_single_level(
    lay: ColLayout,
    group_cols: List[str],
    groups: List[Any],
    group_counts: Dict[Any, int],
    n_total: int,
) -> List[_Row]:
    n           = lay.n_cols
    gc_name     = group_cols[0]
    n_grp_total = sum(group_counts.get(g, 0) for g in groups)
    cpt         = 2 if lay.split_count_pct else 1   # cols per group
    gi0         = lay.group_idxs[0]
    total_span  = cpt * len(groups)

    # Row 1: spanning group-variable name
    cells1: List[GCell] = []
    col = 0
    while col < n:
        if col == gi0:
            cells1.append(GCell(f"{gc_name}  (n={n_grp_total})", total_span))
            col += total_span
        else:
            cells1.append(GCell("", 1))
            col += 1

    # Row 2: label separator
    cells2 = _label_sep_row(lay, n_total, "=", total_show_n=False)

    rows: List[_Row] = [("data", cells1), ("sep", cells2)]

    if lay.split_count_pct:
        # Row 3: group names spanning n+% each; Total spans 2 if split
        cells3: List[GCell] = []
        col = 0
        while col < n:
            if col in lay.group_idxs:
                j = lay.group_idxs.index(col)
                cells3.append(GCell(f"{groups[j]}  (n={group_counts.get(groups[j], '?')})", 2))
                col += 2
            elif lay.total_idx is not None and col == lay.total_idx:
                cells3.append(GCell(f"(n={n_total})", 2))
                col += 2
            else:
                cells3.append(GCell(""))
                col += 1
        rows.append(("data", cells3))

        # Row 4: n / % sub-column labels (groups + Total)
        cells4: List[GCell] = [GCell("") for _ in range(n)]
        for gi in lay.group_idxs:
            cells4[gi]     = GCell("n")
            cells4[gi + 1] = GCell("%")
        if lay.total_idx is not None:
            cells4[lay.total_idx]     = GCell("n")
            cells4[lay.total_idx + 1] = GCell("%")
        rows.append(("data", cells4))
    else:
        # Row 3: group leaf values with per-group n
        cells3_plain: List[GCell] = [GCell("") for _ in range(n)]
        for j, g in enumerate(groups):
            cells3_plain[lay.group_idxs[j]] = GCell(
                f"{g}  (n={group_counts.get(g, '?')})"
            )
        if lay.total_idx is not None:
            cells3_plain[lay.total_idx] = GCell(f"(n={n_total})")
        rows.append(("data", cells3_plain))

    return rows


def _header_multi_level(
    lay: ColLayout,
    group_cols: List[str],
    groups: List[Any],
    group_counts: Dict[Any, int],
    n_total: int,
) -> List[_Row]:
    n        = lay.n_cols
    n_levels = len(group_cols)
    cpt      = 2 if lay.split_count_pct else 1

    # Column indices that belong to the group block
    group_col_set: set = set()
    for gi in lay.group_idxs:
        group_col_set.add(gi)
        if lay.split_count_pct:
            group_col_set.add(gi + 1)

    rows: List[_Row] = []

    for lvl in range(n_levels - 1):
        # Collect unique prefixes at this level
        prefixes: OrderedDict = OrderedDict()
        for j, g in enumerate(groups):
            prefix = g[:lvl + 1] if isinstance(g, tuple) else (g,)
            prefixes.setdefault(prefix, []).append(j)

        # Spanning data row for this level
        cells_data: List[GCell] = []
        col = 0
        while col < n:
            matched = False
            for prefix, idxs in prefixes.items():
                start_col = lay.group_idxs[idxs[0]]
                span_w    = cpt * len(idxs)
                if col == start_col:
                    count = sum(group_counts.get(groups[j], 0) for j in idxs)
                    cells_data.append(GCell(f"{prefix[-1]}  (n={count})", span_w))
                    col += span_w
                    matched = True
                    break
            if not matched:
                cells_data.append(GCell(""))
                col += 1
        rows.append(("data", cells_data))

        # Separator after this spanning row
        if n_levels == 2 or lvl == n_levels - 3:
            rows.append(("sep", _label_sep_row(lay, n_total, "-", total_show_n=False)))
        else:
            sep_cells: List[SCell] = [
                SCell("-") if i in group_col_set else SCell(" ")
                for i in range(n)
            ]
            rows.append(("sep", sep_cells))

    if lay.split_count_pct:
        # Last header row: leaf group values spanning 2 each; Total spans 2
        cells_last: List[GCell] = []
        col = 0
        while col < n:
            if col in lay.group_idxs:
                j = lay.group_idxs.index(col)
                g = groups[j]
                leaf = g[-1] if isinstance(g, tuple) else g
                cells_last.append(GCell(f"{leaf}  (n={group_counts.get(g, '?')})", 2))
                col += 2
            elif lay.total_idx is not None and col == lay.total_idx:
                cells_last.append(GCell(f"(n={n_total})", 2))
                col += 2
            else:
                cells_last.append(GCell(""))
                col += 1
        rows.append(("data", cells_last))

        cells_np: List[GCell] = [GCell("") for _ in range(n)]
        for gi in lay.group_idxs:
            cells_np[gi]     = GCell("n")
            cells_np[gi + 1] = GCell("%")
        if lay.total_idx is not None:
            cells_np[lay.total_idx]     = GCell("n")
            cells_np[lay.total_idx + 1] = GCell("%")
        rows.append(("data", cells_np))
    else:
        # Last header row: leaf group values with n
        cells_leaf: List[GCell] = [GCell("") for _ in range(n)]
        for j, g in enumerate(groups):
            leaf = g[-1] if isinstance(g, tuple) else g
            cells_leaf[lay.group_idxs[j]] = GCell(
                f"{leaf}  (n={group_counts.get(g, '?')})"
            )
        if lay.total_idx is not None:
            cells_leaf[lay.total_idx] = GCell(f"(n={n_total})")
        rows.append(("data", cells_leaf))

    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def render_text_table(
    flat_df:           pd.DataFrame,
    col_layout:        ColLayout,
    group_cols:        List[str],
    groups:            List[Any],
    group_counts:      Dict[Any, int],
    n_total:           int,
    tablefmt:          str                                   = "grid",
    title:             Optional[str]                         = None,
    footnote:          Optional[str]                         = None,
    pvalue_injections: Optional[List[Tuple[int, str, str, bool]]] = None,
) -> str:
    """
    Render a complete text table.

    For 'grid' format uses the canvas/grid renderer (column widths derived
    from all content).  Other formats fall back to tabulate directly.
    """
    if tablefmt != "grid":
        from tabulate import tabulate as _tabulate
        body = _tabulate(flat_df, headers="keys", tablefmt=tablefmt, showindex=False)
        parts = []
        if title:    parts.append(title)
        parts.append(body)
        if footnote: parts.append(footnote)
        return "\n".join(parts)

    lay    = col_layout
    n_cols = lay.n_cols

    # ── Build p-value lookup ──────────────────────────────────────────────
    # pval_map[k]  → (p_str, test_str)  inject into sep AFTER data row k
    # blank_set[k] → open (space) the p/test columns in sep after row k
    pval_map:  Dict[int, Tuple[str, str]] = {}
    blank_set: set                         = set()
    if pvalue_injections:
        for k, p_str, test_str, is_middle in pvalue_injections:
            if is_middle:
                pval_map[k] = (p_str, test_str)
            else:
                blank_set.add(k)

    # ── Collect all rows for width computation ────────────────────────────
    header_rows = _build_header_rows(lay, group_cols, groups, group_counts, n_total)

    all_rows: List[_Row] = list(header_rows)
    for row_vals in flat_df.values:
        data_cells: List[GCell] = [
            GCell(str(v) if v is not None else "", 1, "l" if i == 0 else "c")
            for i, v in enumerate(row_vals)
        ]
        all_rows.append(("data", data_cells))

    widths = _compute_widths(all_rows, n_cols)

    # ── Render ────────────────────────────────────────────────────────────
    lines: List[str] = []

    # Top border
    lines.append(_render_sep_row([SCell("-") for _ in range(n_cols)], widths))

    # Header rows (consecutive data rows get a "-" separator between them)
    prev_was_data = False
    for rtype, cells in header_rows:
        if rtype == "data" and prev_was_data:
            lines.append(_render_sep_row([SCell("-") for _ in range(n_cols)], widths))
        if rtype == "data":
            lines.append(_render_data_row(cells, widths))   # type: ignore[arg-type]
        else:
            lines.append(_render_sep_row(cells, widths))    # type: ignore[arg-type]
        prev_was_data = (rtype == "data")

    # === separator (header / data boundary)
    lines.append(_render_sep_row([SCell("=") for _ in range(n_cols)], widths))

    # Data rows
    for k, row_vals in enumerate(flat_df.values):
        data_cells = [
            GCell(str(v) if v is not None else "", 1, "l" if i == 0 else "c")
            for i, v in enumerate(row_vals)
        ]
        lines.append(_render_data_row(data_cells, widths))

        # Separator after this row (with optional p-value injection)
        sep_cells: List[SCell] = [SCell("-") for _ in range(n_cols)]
        if k in pval_map:
            p_str, test_str = pval_map[k]
            if lay.p_idx    is not None: sep_cells[lay.p_idx]    = SCell("-", p_str)
            if lay.test_idx is not None: sep_cells[lay.test_idx] = SCell("-", test_str)
        elif k in blank_set:
            if lay.p_idx    is not None: sep_cells[lay.p_idx]    = SCell(" ")
            if lay.test_idx is not None: sep_cells[lay.test_idx] = SCell(" ")
        lines.append(_render_sep_row(sep_cells, widths))

    table_str   = "\n".join(lines)
    table_width = len(lines[0])

    out_parts: List[str] = []
    if title:
        out_parts.append(_render_title(title, table_width))
    out_parts.append(table_str)
    if footnote:
        out_parts.append(_render_footnote(footnote, table_width))

    return "\n".join(out_parts)
