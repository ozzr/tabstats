"""
tabstat/rendering.py
─────────────────────
Text-table rendering with nested headers, title, footnote, and
SPSS-style p-value spanning for categorical variables.

P-value spanning
─────────────────
For categorical variables with ≥2 categories the p-value is NOT
placed inside a data cell.  Instead it is injected into the
separator line between the middle category rows:

    | ⠀   No   | 86 (63.2%)  |  ...  |        |               |
    +----------+-------------+-------+ <0.001 + Chi-Squared   +
    | ⠀   Yes  | 50 (36.8%)  |  ...  |        |               |

This matches SPSS's spanning display and is produced by
_inject_pvalue_into_separator() called from render_text_table().
"""
from __future__ import annotations

import textwrap
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# Column Layout
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ColLayout:
    n_cols:     int
    char_idx:   int                  = 0
    total_idx:  Optional[int]        = None
    group_idxs: List[int]            = field(default_factory=list)
    p_idx:      Optional[int]        = None
    test_idx:   Optional[int]        = None
    smd_idx:    Optional[int]        = None


def build_col_layout(
    group_cols:        List[str],
    groups:            List[Any],
    display_overall:   bool,
    overall_position:  str,
    display_p_values:  bool,
    display_test_name: bool,
    display_smd:       bool,
) -> ColLayout:
    layout = ColLayout(n_cols=0)
    idx = 1

    if display_overall and overall_position == "first":
        layout.total_idx = idx
        idx += 1

    if groups:
        layout.group_idxs = list(range(idx, idx + len(groups)))
        idx += len(groups)

    if display_overall and overall_position == "last":
        layout.total_idx = idx
        idx += 1

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
# P-value separator injection
# ─────────────────────────────────────────────────────────────────────────────

def _inject_pvalue_into_separator(
    sep_line: str,
    col_layout: ColLayout,
    p_str: str,
    test_str: str,
) -> str:
    """
    Replace the dash segments at p_idx (and test_idx) of a separator line
    with the p-value and test name, centered in the available width.

    Input:  '+-------+-------+-------+-------+'
    Output: '+-------+-------+ 0.001 + Chi2  +'
    """
    # Split on '+' — result[0] and result[-1] are empty strings from the edges
    parts = sep_line.split("+")[1:-1]   # inner segments (dashes)

    def _replace(parts, idx, text):
        if idx is None or idx >= len(parts):
            return
        if text == "":          # ← dejar guiones intactos (test en filas no-middle)
            return
        w = len(parts[idx])
        inner = w - 2
        display = str(text).strip()[:inner]
        parts[idx] = f" {display.center(inner)} "

    _replace(parts, col_layout.p_idx,    p_str)
    _replace(parts, col_layout.test_idx, test_str)

    return "+" + "+".join(parts) + "+"


# ─────────────────────────────────────────────────────────────────────────────
# Low-level text helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_col_widths(sep_line: str) -> List[int]:
    inner = sep_line.strip().strip("+")
    return [len(p) for p in inner.split("+")]


def _make_separator(widths: List[int], char: str = "-") -> str:
    return "+" + "+".join(char * w for w in widths) + "+"


def _make_label_separator(cells: List[str], widths: List[int], fill_char="=") -> str:
    parts = []
    for cell, w in zip(cells, widths):
        s = str(cell).strip() if cell else ""
        if s:
            cw = w - 2
            parts.append(f" {s.center(cw)} ")
        else:
            parts.append(fill_char * w)
    return "+" + "+".join(parts) + "+"


def _make_row(cells: List[str], widths: List[int], first_align: str = "l") -> str:
    parts = []
    for i, (cell, w) in enumerate(zip(cells, widths)):
        cw = w - 2
        s  = str(cell) if cell is not None else ""
        if i == 0 and first_align == "l":
            parts.append(f" {s[:cw].ljust(cw)} ")
        else:
            parts.append(f" {s[:cw].center(cw)} ")
    return "|" + "|".join(parts) + "|"


def _make_spanning_row(spans: List[Tuple[int, int, str]], widths: List[int]) -> str:
    parts = []
    for start, count, content in spans:
        seg_w = sum(widths[start:start + count]) + (count - 1)
        cw    = seg_w - 2
        s     = str(content) if content else ""
        parts.append(f" {s[:cw].center(cw)} ")
    return "|" + "|".join(parts) + "|"


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
# Nested header builders
# ─────────────────────────────────────────────────────────────────────────────

def _label_cells(col_layout: ColLayout, n_cols: int) -> List[str]:
    """Return a cell list where known roles have their label, rest empty."""
    cells = [""] * n_cols
    cells[col_layout.char_idx] = "Characteristic"
    if col_layout.total_idx   is not None: cells[col_layout.total_idx]  = "Total"
    if col_layout.p_idx       is not None: cells[col_layout.p_idx]      = "p-val"
    if col_layout.test_idx    is not None: cells[col_layout.test_idx]   = "Test"
    if col_layout.smd_idx     is not None: cells[col_layout.smd_idx]    = "SMD"
    return cells


def _pre_post_spans(col_layout, groups):
    """Helper: build span tuples for columns before and after the group block."""
    pre  = sorted(i for i in [col_layout.char_idx,
                               col_layout.total_idx if col_layout.total_idx is not None
                               and col_layout.total_idx < col_layout.group_idxs[0]
                               else None]
                  if i is not None)
    post = sorted(i for i in [
        col_layout.total_idx if col_layout.total_idx is not None
        and col_layout.total_idx > col_layout.group_idxs[-1] else None,
        col_layout.p_idx, col_layout.test_idx, col_layout.smd_idx,
    ] if i is not None)
    return pre, post


def _header_single_level(col_layout, group_cols, groups, group_counts, n_total, widths):
    gc_name     = group_cols[0]
    n_grp_total = sum(group_counts.get(g, 0) for g in groups)
    pre, post   = _pre_post_spans(col_layout, groups)

    # Row 1 — spanning
    spans = ([(i, 1, "") for i in pre]
             + [(col_layout.group_idxs[0], len(groups),
                 f"{gc_name}  (n={n_grp_total})")]
             + [(i, 1, "") for i in post])
    row1  = _make_spanning_row(spans, widths)

    # Row 2 — label separator
    row2 = _make_label_separator(_label_cells(col_layout, col_layout.n_cols),
                                 widths, fill_char="=")

    # Row 3 — group values with n
    cells3 = [""] * col_layout.n_cols
    for j, g in enumerate(groups):
        cells3[col_layout.group_idxs[j]] = f"{g}  (n={group_counts.get(g, '?')})"
    if col_layout.total_idx is not None:
        cells3[col_layout.total_idx] = f"(n={n_total})"
    row3 = _make_row(cells3, widths)

    return [row1, row2, row3]


def _header_multi_level(col_layout, group_cols, groups, group_counts, n_total, widths):
    # Level-0 aggregation (first group_col value)
    l0_groups: OrderedDict = OrderedDict()
    for j, g in enumerate(groups):
        key = g[0]
        l0_groups.setdefault(key, []).append(j)
    l0_counts = {k: sum(group_counts.get(groups[j], 0) for j in idxs)
                 for k, idxs in l0_groups.items()}

    pre, post = _pre_post_spans(col_layout, groups)

    # Row 1 — level-0 spanning
    spans = ([(i, 1, "") for i in pre]
             + [(col_layout.group_idxs[idxs[0]], len(idxs),
                 f"{k}  (n={l0_counts[k]})")
                for k, idxs in l0_groups.items()]
             + [(i, 1, "") for i in post])
    row1  = _make_spanning_row(spans, widths)

    # Row 2 — label separator
    row2 = _make_label_separator(_label_cells(col_layout, col_layout.n_cols),
                                 widths, fill_char="=")

    # Row 3 — level-1 values
    cells3 = [""] * col_layout.n_cols
    for j, g in enumerate(groups):
        cells3[col_layout.group_idxs[j]] = str(g[-1]) if isinstance(g, tuple) else str(g)
    if col_layout.total_idx is not None:
        cells3[col_layout.total_idx] = f"(n={n_total})"
    row3 = _make_row(cells3, widths)

    # Row 4 — n per group
    cells4 = [""] * col_layout.n_cols
    for j, g in enumerate(groups):
        cells4[col_layout.group_idxs[j]] = f"(n={group_counts.get(g, '?')})"
    row4 = _make_row(cells4, widths)

    return [row1, row2, row3, row4]


def _build_header_lines(col_layout, group_cols, groups, group_counts, n_total, widths):
    n_levels = len(group_cols)
    if n_levels == 0 or not groups:
        return []
    if n_levels == 1:
        return _header_single_level(col_layout, group_cols, groups, group_counts,
                                    n_total, widths)
    return _header_multi_level(col_layout, group_cols, groups, group_counts,
                               n_total, widths)


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
    tablefmt:          str                          = "grid",
    title:             Optional[str]                = None,
    footnote:          Optional[str]                = None,
    pvalue_injections: Optional[List[Tuple[int, str, str]]] = None,
) -> str:
    """
    Render a complete text table.

    Parameters
    ----------
    flat_df            : DataFrame with flat (non-MultiIndex) columns.
    col_layout         : ColLayout describing which column index holds each role.
    group_cols         : list of grouping column names (for header building).
    groups             : ordered list of group keys.
    group_counts       : {group_key: n_observations}.
    n_total            : total rows in the source DataFrame.
    tablefmt           : tabulate format string.
    title              : optional title box above.
    footnote           : optional footnote box below.
    pvalue_injections  : list of (row_k, p_str, test_str).
                         The separator AFTER flat_df row row_k gets the
                         p-value/test injected into its p/test column segments.
    """
    from tabulate import tabulate as _tabulate

    # ── Step 1: raw tabulate (blank header row) ───────────────────────────
    raw   = _tabulate(flat_df,
                      headers=[""] * len(flat_df.columns),
                      tablefmt=tablefmt,
                      showindex=False)
    lines = raw.split("\n")

    # Find the === separator (marks end of header, start of data)
    header_sep_idx = next(
        (i for i, ln in enumerate(lines) if i > 0 and ln.startswith("+") and "=" in ln),
        None,
    )
    if header_sep_idx is None:
        # Fallback for formats without === (simple, pipe, etc.)
        out_parts = []
        if title:    out_parts.append(f"\n{title}\n{'─'*max(len(title),40)}")
        out_parts.append(raw)
        if footnote: out_parts.append(f"{'─'*max(len(footnote),40)}\n{footnote}")
        return "\n".join(out_parts)

    # ── Step 2: parse column widths ───────────────────────────────────────
    widths = _parse_col_widths(lines[0])

    # ── Step 3: inject p-values into separator lines ─────────────────────
    # Separator after data row k is at line index: header_sep_idx + 2 + k*2
    if pvalue_injections and col_layout.p_idx is not None:
        for k, p_str, test_str, is_middle in pvalue_injections:
            sep_line_idx = header_sep_idx + 2 + k * 2
            if 0 <= sep_line_idx < len(lines):
                if is_middle:
                    # Reemplaza p-col y test-col con valor real
                    lines[sep_line_idx] = _inject_pvalue_into_separator(
                        lines[sep_line_idx], col_layout, p_str, test_str
                    )
                else:
                    # Solo abre (blanquea) la columna p, test queda con guiones
                    lines[sep_line_idx] = _inject_pvalue_into_separator(
                        lines[sep_line_idx], col_layout, " ", ""
                    )

    # ── Step 4: build nested header rows ─────────────────────────────────
    header_lines = _build_header_lines(
        col_layout, group_cols, groups, group_counts, n_total, widths
    )

    # ── Step 5: assemble ─────────────────────────────────────────────────
    table_width   = len(lines[0])
    top_border    = lines[0]
    header_sep    = lines[header_sep_idx]
    data_lines    = lines[header_sep_idx + 1:]

    out_parts: List[str] = []

    if title:
        out_parts.append(_render_title(title, table_width))

    out_parts.append(top_border)
    if header_lines:
        out_parts.extend(header_lines)
    out_parts.append(header_sep)
    out_parts.extend(data_lines)

    if footnote:
        out_parts.append(_render_footnote(footnote, table_width))

    return "\n".join(out_parts)
