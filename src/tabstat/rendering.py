"""
tabstat/rendering.py
─────────────────────
Text-table rendering with:

  ┌─────────────────────────────────────────────────────────────────────────┐
  │  Title (optional)                                                       │
  ├──────────────────┬──────────────────────────┬──────────────────────────┤
  │                  │  Compatible  (n=173)      │  Confirmed  (n=397)      │
  │  Characteristic  ├═════════════╦═════════════╬═════════════╦═══════════╡...
  │                  │  No         │  Yes        │  No         │  Yes      │
  │                  │  (n=136)    │  (n=37)     │  (n=301)    │  (n=96)   │
  ╞══════════════════╪═════════════╪═════════════╪═════════════╪═══════════╡
  │  ...data rows...                                                        │
  ├──────────────────┼─────────────┼─────────────┼─────────────┼───────────┤
  │  N (subjects)    │  136        │  37         │  301        │  96       │
  └──────────────────┴─────────────┴─────────────┴─────────────┴───────────┘
  Footnote (optional)

ColLayout tracks which column index holds each logical role (Characteristic,
Total, P-value, Test, SMD, group columns).  render_text_table() uses it plus
the group structure to build the multi-row header independently of the
DataFrame's MultiIndex representation.
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
    """
    Maps logical column roles to their flat integer indices.

    group_idxs : ordered 1-to-1 with the `groups` list passed at render time.
    """
    n_cols:    int
    char_idx:  int                   = 0
    total_idx: Optional[int]         = None
    group_idxs: List[int]            = field(default_factory=list)
    p_idx:     Optional[int]         = None
    test_idx:  Optional[int]         = None
    smd_idx:   Optional[int]         = None


def build_col_layout(
    group_cols:          List[str],
    groups:              List[Any],
    display_overall:     bool,
    overall_position:    str,
    display_p_values:    bool,
    display_test_name:   bool,
    display_smd:         bool,
) -> ColLayout:
    """Compute ColLayout by mirroring the column-ordering logic in _build_columns."""
    layout = ColLayout(n_cols=0)
    idx = 1                                          # 0 = Characteristic

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
# Low-level text helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_col_widths(sep_line: str) -> List[int]:
    """
    Return per-column segment widths (including 2 padding spaces) from a
    tabulate separator line such as '+---+======+----+'.
    """
    inner = sep_line.strip()
    if inner.startswith("+"):
        inner = inner[1:]
    if inner.endswith("+"):
        inner = inner[:-1]
    return [len(p) for p in inner.split("+")]


def _make_separator(widths: List[int], char: str = "-") -> str:
    """Plain separator: '+---+---+'."""
    return "+" + "+".join(char * w for w in widths) + "+"


def _make_label_separator(
    cells: List[str], widths: List[int], fill_char: str = "="
) -> str:
    """
    Separator where *non-empty* cells render as a label and
    empty cells render as fill_char repeats.

    Example:
        cells  = ['Characteristic', '', '', 'Total', 'P-value', 'Test']
        result = '+ Characteristic +====+====+ Total + P-value + Test +'
    """
    parts = []
    for cell, w in zip(cells, widths):
        s = str(cell).strip() if cell else ""
        if s:
            cw = w - 2
            parts.append(f" {s[:cw].center(cw)} ")
        else:
            parts.append(fill_char * w)
    return "+" + "+".join(parts) + "+"


def _make_row(
    cells: List[str], widths: List[int], first_align: str = "l"
) -> str:
    """Data row '| cell | cell |'. First column left-aligned, rest centered."""
    parts = []
    for i, (cell, w) in enumerate(zip(cells, widths)):
        cw = w - 2
        s  = str(cell) if cell is not None else ""
        if i == 0 and first_align == "l":
            parts.append(f" {s[:cw].ljust(cw)} ")
        else:
            parts.append(f" {s[:cw].center(cw)} ")
    return "|" + "|".join(parts) + "|"


def _make_spanning_row(
    spans: List[Tuple[int, int, str]], widths: List[int]
) -> str:
    """
    Row where some cells span multiple columns.

    spans : list of (start_col_idx, span_count, content_str)
            Must partition all columns without gaps.
            Content is centered in the combined column width.
    """
    parts = []
    for start, count, content in spans:
        # Combined segment width = sum of individual widths + (count-1) for internal '+' signs
        seg_w = sum(widths[start : start + count]) + (count - 1)
        cw    = seg_w - 2
        s     = str(content) if content else ""
        parts.append(f" {s[:cw].center(cw)} ")
    return "|" + "|".join(parts) + "|"


# ─────────────────────────────────────────────────────────────────────────────
# Title / Footnote renderers
# ─────────────────────────────────────────────────────────────────────────────

def _render_title(title: str, table_width: int) -> str:
    """Title box above the table (same width as the table)."""
    inner = table_width - 4          # 2 border chars + 2 spaces
    lines = ["+" + "=" * (table_width - 2) + "+"]
    for part in textwrap.wrap(title, width=inner) or [""]:
        lines.append("| " + part.center(inner) + " |")
    lines.append("+" + "=" * (table_width - 2) + "+")
    return "\n".join(lines)


def _render_footnote(footnote: str, table_width: int) -> str:
    """Footnote box below the table."""
    inner = table_width - 4
    lines = ["+" + "-" * (table_width - 2) + "+"]
    for part in textwrap.wrap(footnote, width=inner) or [""]:
        lines.append("| " + part.ljust(inner) + " |")
    lines.append("+" + "-" * (table_width - 2) + "+")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Nested-header builders
# ─────────────────────────────────────────────────────────────────────────────

def _header_no_groups(widths: List[int]) -> List[str]:
    """
    No grouping column — single label-separator row:
    '+ Characteristic + Total +'
    (All cells are special labels.)
    """
    # The caller must pass a flat_df with sensible column names; we derive
    # them from the widths positions by naming slots.  Since this is the
    # no-group case, the label separator row has Characteristic at 0 and
    # Total at 1 (if present).
    # We simply return an empty list and let generate() handle it via tabulate
    # normally.
    return []


def _header_single_level(
    col_layout:    ColLayout,
    group_cols:    List[str],
    groups:        List[Any],
    group_counts:  Dict[Any, int],
    n_total:       int,
    widths:        List[int],
) -> List[str]:
    """
    3-row header for a single grouping variable:

    Row 1 (spanning): | | FATAL (n=140) spanning all group cols | | | |
    Row 2 (label sep):+ Characteristic +=====+=====+ Total + P-value + Test +
    Row 3 (values):   | | Survivor (n=105) | Fatal (n=35) | (n=140) | | |
    """
    gc_name       = group_cols[0]
    n_grp_total   = sum(group_counts.get(g, 0) for g in groups)

    # ── Row 1 — spanning ─────────────────────────────────────────────────
    spans: List[Tuple[int, int, str]] = []

    # Columns before the group block
    pre_idxs = sorted(
        i for i in [col_layout.char_idx,
                     col_layout.total_idx if col_layout.total_idx is not None else None]
        if i is not None and i < col_layout.group_idxs[0]
    )
    for i in pre_idxs:
        spans.append((i, 1, ""))

    # The group block itself
    g_start = col_layout.group_idxs[0]
    g_count = len(col_layout.group_idxs)
    spans.append((g_start, g_count, f"{gc_name}  (n={n_grp_total})"))

    # Columns after the group block
    post_idxs = sorted(
        i for i in [
            col_layout.total_idx if col_layout.total_idx is not None and
                                    col_layout.total_idx > col_layout.group_idxs[-1] else None,
            col_layout.p_idx,
            col_layout.test_idx,
            col_layout.smd_idx,
        ]
        if i is not None
    )
    for i in post_idxs:
        spans.append((i, 1, ""))

    row1 = _make_spanning_row(spans, widths)

    # ── Row 2 — label separator ───────────────────────────────────────────
    label_cells = [""] * col_layout.n_cols
    label_cells[col_layout.char_idx] = "Characteristic"
    if col_layout.total_idx is not None:
        label_cells[col_layout.total_idx] = "Total"
    if col_layout.p_idx is not None:
        label_cells[col_layout.p_idx] = "P-value"
    if col_layout.test_idx is not None:
        label_cells[col_layout.test_idx] = "Test"
    if col_layout.smd_idx is not None:
        label_cells[col_layout.smd_idx] = "SMD"
    row2 = _make_label_separator(label_cells, widths, fill_char="=")

    # ── Row 3 — group values with n ──────────────────────────────────────
    cells3 = [""] * col_layout.n_cols
    for j, g in enumerate(groups):
        n   = group_counts.get(g, "?")
        cells3[col_layout.group_idxs[j]] = f"{g}  (n={n})"
    if col_layout.total_idx is not None:
        cells3[col_layout.total_idx] = f"(n={n_total})"
    row3 = _make_row(cells3, widths)

    return [row1, row2, row3]


def _header_multi_level(
    col_layout:    ColLayout,
    group_cols:    List[str],
    groups:        List[Any],
    group_counts:  Dict[Any, int],
    n_total:       int,
    widths:        List[int],
) -> List[str]:
    """
    4-row header for ≥2 grouping variables:

    Row 1: | | Compatible (n=173) spanning | Confirmed (n=397) spanning | | | |
    Row 2: + Characteristic +=====+=====+=====+=====+ Total + P-value + Test +
    Row 3: | | No   | Yes  | No   | Yes  | (n=570) | | |
    Row 4: | | (n=136) | (n=37) | (n=301) | (n=96) | | | |
    """
    # ── Level-0 (outermost group variable) aggregation ────────────────────
    # Maintain insertion order for deterministic output
    l0_groups: "OrderedDict[Any, List[int]]" = OrderedDict()
    for j, g in enumerate(groups):
        key = g[0]
        l0_groups.setdefault(key, []).append(j)   # j = position in groups list

    l0_counts: Dict[Any, int] = {
        key: sum(group_counts.get(groups[j], 0) for j in idxs)
        for key, idxs in l0_groups.items()
    }

    # ── Row 1 — level-0 spanning ─────────────────────────────────────────
    spans: List[Tuple[int, int, str]] = []

    # Char col (and Total if 'first')
    pre_idxs = sorted(
        i for i in [col_layout.char_idx,
                     col_layout.total_idx if col_layout.total_idx is not None else None]
        if i is not None and i < col_layout.group_idxs[0]
    )
    for i in pre_idxs:
        spans.append((i, 1, ""))

    # Spanning blocks for each l0 value
    for l0_val, j_idxs in l0_groups.items():
        col_start = col_layout.group_idxs[j_idxs[0]]
        col_count = len(j_idxs)
        n         = l0_counts[l0_val]
        spans.append((col_start, col_count, f"{l0_val}  (n={n})"))

    # Post-group columns
    post_idxs = sorted(
        i for i in [
            col_layout.total_idx if col_layout.total_idx is not None and
                                    col_layout.total_idx > col_layout.group_idxs[-1] else None,
            col_layout.p_idx,
            col_layout.test_idx,
            col_layout.smd_idx,
        ]
        if i is not None
    )
    for i in post_idxs:
        spans.append((i, 1, ""))

    row1 = _make_spanning_row(spans, widths)

    # ── Row 2 — label separator ───────────────────────────────────────────
    label_cells = [""] * col_layout.n_cols
    label_cells[col_layout.char_idx] = "Characteristic"
    if col_layout.total_idx is not None:
        label_cells[col_layout.total_idx] = "Total"
    if col_layout.p_idx is not None:
        label_cells[col_layout.p_idx] = "P-value"
    if col_layout.test_idx is not None:
        label_cells[col_layout.test_idx] = "Test"
    if col_layout.smd_idx is not None:
        label_cells[col_layout.smd_idx] = "SMD"
    row2 = _make_label_separator(label_cells, widths, fill_char="=")

    # ── Row 3 — level-1 values (innermost group variable) ────────────────
    cells3 = [""] * col_layout.n_cols
    for j, g in enumerate(groups):
        # g is a tuple: display the last level as the column value
        val = str(g[-1]) if isinstance(g, tuple) else str(g)
        cells3[col_layout.group_idxs[j]] = val
    if col_layout.total_idx is not None:
        cells3[col_layout.total_idx] = f"(n={n_total})"
    row3 = _make_row(cells3, widths)

    # ── Row 4 — n per group ───────────────────────────────────────────────
    cells4 = [""] * col_layout.n_cols
    for j, g in enumerate(groups):
        n = group_counts.get(g, "?")
        cells4[col_layout.group_idxs[j]] = f"(n={n})"
    row4 = _make_row(cells4, widths)

    return [row1, row2, row3, row4]


def _build_header_lines(
    col_layout:    ColLayout,
    group_cols:    List[str],
    groups:        List[Any],
    group_counts:  Dict[Any, int],
    n_total:       int,
    widths:        List[int],
) -> List[str]:
    """Dispatch to the appropriate header builder."""
    n_levels = len(group_cols)
    if n_levels == 0 or not groups:
        return _header_no_groups(widths)
    if n_levels == 1:
        return _header_single_level(
            col_layout, group_cols, groups, group_counts, n_total, widths
        )
    return _header_multi_level(
        col_layout, group_cols, groups, group_counts, n_total, widths
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def render_text_table(
    flat_df:       pd.DataFrame,
    col_layout:    ColLayout,
    group_cols:    List[str],
    groups:        List[Any],
    group_counts:  Dict[Any, int],
    n_total:       int,
    tablefmt:      str                = "grid",
    title:         Optional[str]      = None,
    footnote:      Optional[str]      = None,
    subtotals_row: Optional[List[Any]] = None,
) -> str:
    """
    Render a complete text table with nested headers, optional title/footnote
    and optional subtotals row.

    Parameters
    ----------
    flat_df       : DataFrame with flat (non-MultiIndex) columns — used to
                    generate the table body and compute column widths.
    col_layout    : ColLayout object describing which column index holds each role.
    group_cols    : list of grouping column names (from the formula).
    groups        : ordered list of unique group keys (same order as col_layout.group_idxs).
    group_counts  : {group_key: n_observations} mapping.
    n_total       : total observations in the DataFrame.
    tablefmt      : tabulate format string ('grid' | 'simple' | 'pipe' | …).
    title         : optional table title rendered above.
    footnote      : optional footnote rendered below.
    subtotals_row : optional pre-built row list for column totals.
    """
    from tabulate import tabulate as _tabulate

    # ── Step 1: generate raw table body (no header) via tabulate ─────────
    raw = _tabulate(flat_df, headers=[""] * len(flat_df.columns),
                    tablefmt=tablefmt, showindex=False)
    lines = raw.split("\n")

    # Locate the header-separator line (uses '=', contrasting with data '-')
    header_sep_idx = next(
        (i for i, ln in enumerate(lines)
         if i > 0 and ln.startswith("+") and "=" in ln),
        None,
    )
    if header_sep_idx is None:
        # Fallback: tablefmt doesn't use '=' (e.g. 'simple', 'pipe')
        # Return as-is with title/footnote only
        out_parts = []
        if title:
            out_parts.append(f"\n{title}\n{'─' * max(len(title), 40)}")
        out_parts.append(raw)
        if footnote:
            out_parts.append(f"{'─' * max(len(footnote), 40)}\n{footnote}")
        return "\n".join(out_parts)

    top_border   = lines[0]          # '+---+---+'
    header_sep   = lines[header_sep_idx]   # '+===+===+'
    data_lines   = lines[header_sep_idx + 1:]   # data rows + bottom border

    # ── Step 2: parse column widths from the top border ──────────────────
    widths = _parse_col_widths(top_border)

    # ── Step 3: build nested header rows ─────────────────────────────────
    header_lines = _build_header_lines(
        col_layout, group_cols, groups, group_counts, n_total, widths
    )

    # ── Step 4: inject subtotals row before the bottom border ────────────
    if subtotals_row is not None:
        sub_sep  = _make_separator(widths, char="-")
        sub_row  = _make_row(
            [str(v) if v is not None else "" for v in subtotals_row],
            widths, first_align="l",
        )
        # Remove bottom border, append subtotals, re-append border
        if data_lines and data_lines[-1].startswith("+"):
            bottom = data_lines.pop()
            data_lines.extend([sub_sep, sub_row, bottom])
        else:
            data_lines.extend([sub_sep, sub_row])

    # ── Step 5: assemble ─────────────────────────────────────────────────
    table_width = len(top_border)
    out_parts: List[str] = []

    if title:
        out_parts.append(_render_title(title, table_width))

    out_parts.append(top_border)
    out_parts.extend(header_lines)
    out_parts.append(header_sep)          # +===+===+ final separator
    out_parts.extend(data_lines)

    if footnote:
        out_parts.append(_render_footnote(footnote, table_width))

    return "\n".join(out_parts)
