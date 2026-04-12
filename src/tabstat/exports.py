"""
tabstat/exports.py
──────────────────
Export functions for Table 1 DataFrames.

Formats supported
─────────────────
  to_html_str()   → styled HTML string (Word-paste compatible)
  to_excel_file() → openpyxl workbook with header styling and alternating rows
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple, Union

import pandas as pd

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# HTML
# ─────────────────────────────────────────────────────────────────────────────

_HTML_CSS = """
<style>
  body   { font-family: Arial, sans-serif; font-size: 11pt; color: #1a1a1a; }
  table  { border-collapse: collapse; width: 100%; margin: 16px 0; }
  caption{
    font-size: 13pt; font-weight: bold;
    text-align: left; margin-bottom: 8px; padding: 4px 0;
  }
  th {
    background: #2c3e50; color: #ffffff;
    padding: 8px 12px; text-align: center;
    border: 1px solid #aab4bb; white-space: nowrap;
  }
  th:first-child { text-align: left; }
  td {
    padding: 5px 12px; border: 1px solid #d0d7de;
    vertical-align: top;
  }
  td:first-child  { text-align: left;   }
  td:not(:first-child) { text-align: center; }
  tr:nth-child(even) td { background: #f4f6f8; }
  tr:hover           td { background: #dceeff; }
  tfoot td { font-style: italic; font-size: 9pt; color: #555; border-top: 2px solid #2c3e50; }
</style>
"""


def to_html_str(
    df: pd.DataFrame,
    title: str = "Table 1. Characteristics of the study population",
    footnote: Optional[str] = None,
) -> str:
    """
    Convert a Table 1 DataFrame to a styled, self-contained HTML string.

    Parameters
    ----------
    df        : output of TabStatGenerator.generate()
    title     : table caption shown above the table
    footnote  : optional footnote rendered in <tfoot>

    Returns
    -------
    str — complete HTML document.
    """
    flat = _flatten(df)
    n_cols = len(flat.columns)

    # thead
    header_html = "<thead><tr>" + "".join(
        f"<th>{str(col).replace(chr(10), '<br>')}</th>" for col in flat.columns
    ) + "</tr></thead>"

    # tbody
    tbody_rows = []
    for _, row in flat.iterrows():
        cells = "".join(f"<td>{_safe(v)}</td>" for v in row)
        tbody_rows.append(f"<tr>{cells}</tr>")
    body_html = "<tbody>" + "\n".join(tbody_rows) + "</tbody>"

    # tfoot
    foot_html = ""
    if footnote:
        foot_html = (
            f'<tfoot><tr><td colspan="{n_cols}">{footnote}</td></tr></tfoot>'
        )

    table_html = (
        f'<table>\n'
        f'  <caption>{title}</caption>\n'
        f'  {header_html}\n'
        f'  {body_html}\n'
        f'  {foot_html}\n'
        f'</table>'
    )

    return (
        "<!DOCTYPE html>\n<html lang='en'>\n<head>\n"
        "<meta charset='UTF-8'>\n"
        f"<title>{title}</title>\n"
        f"{_HTML_CSS}"
        "</head>\n<body>\n"
        f"{table_html}\n"
        "</body>\n</html>"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Excel
# ─────────────────────────────────────────────────────────────────────────────

def to_excel_file(
    df_or_tables: Union[pd.DataFrame, List[Tuple[str, pd.DataFrame]]],
    path: str,
    title: Optional[str] = "Table 1",
    footnote: Optional[str] = None,
) -> None:
    """
    Export Table 1 to a styled Excel workbook.

    Requires
    --------
    openpyxl  (pip install openpyxl)

    Features
    --------
    - Title row (row 1)
    - Multi-level header rows (one row per MultiIndex level, if applicable)
    - Alternating-row fill
    - Auto-fitted column widths (capped at 40 characters)
    - Frozen top rows
    """
    try:
        import openpyxl
        from openpyxl.styles import (
            Alignment, Border, Font, PatternFill, Side,
        )
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise ImportError(
            "openpyxl is required for Excel export. "
            "Install with:  pip install openpyxl"
        ) from exc

    # ── Styles ────────────────────────────────────────────────────────────
    thin_side = Side(style="thin", color="BDC3C7")
    border    = Border(
        left=thin_side, right=thin_side,
        top=thin_side,  bottom=thin_side,
    )
    hdr_font   = Font(bold=True, size=11, name="Arial")
    body_font  = Font(size=11, name="Arial")
    center_aln = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_aln   = Alignment(horizontal="left",   vertical="top", wrap_text=True)

    def _write_table(
        ws,
        table_df: pd.DataFrame,
        table_title: Optional[str],
        table_footnote: Optional[str],
    ) -> None:
        flat_df   = _flatten(table_df)
        n_data_cols = len(flat_df.columns)

        if len(flat_df) > 0:
            first_row = flat_df.iloc[0].astype(str)
            if first_row.iloc[0].strip() and all(first_row.iloc[1:].str.strip() == ""):
                if table_title is None:
                    table_title = first_row.iloc[0]
                if str(first_row.iloc[0]).strip() == str(table_title).strip():
                    flat_df = flat_df.iloc[1:]
        if len(flat_df) > 0:
            last_row = flat_df.iloc[-1].astype(str)
            if last_row.iloc[0].strip() and all(last_row.iloc[1:].str.strip() == ""):
                if table_footnote is None:
                    table_footnote = last_row.iloc[0]
                if str(last_row.iloc[0]).strip() == str(table_footnote).strip():
                    flat_df = flat_df.iloc[:-1]

        current_row = 1

        if table_title:
            for col_idx in range(1, n_data_cols + 1):
                cell = ws.cell(current_row, col_idx)
                if col_idx == 1:
                    cell.value = table_title
                    cell.font = Font(bold=True, size=12, name="Arial")
                    cell.alignment = left_aln
                else:
                    cell.value = ""
                cell.border = border
            ws.merge_cells(
                start_row=current_row, start_column=1,
                end_row=current_row,   end_column=n_data_cols,
            )
            current_row += 1

        is_multi = isinstance(table_df.columns, pd.MultiIndex)
        if is_multi:
            n_levels = table_df.columns.nlevels
            for lvl in range(n_levels):
                row_vals = [str(col[lvl]) if str(col[lvl]).strip() else "" for col in table_df.columns]
                row_number = current_row
                for col_idx, val in enumerate(row_vals, start=1):
                    cell = ws.cell(row_number, col_idx)
                    cell.value     = val
                    cell.font      = hdr_font
                    cell.border    = border
                    cell.alignment = center_aln if col_idx > 1 else left_aln

                merge_start = None
                last_val = None
                for col_idx, val in enumerate(row_vals + [None], start=1):
                    if val and val == last_val:
                        if merge_start is None:
                            merge_start = col_idx - 1
                    else:
                        if merge_start is not None:
                            end_col = col_idx - 1
                            if end_col > merge_start:
                                ws.merge_cells(
                                    start_row=row_number, start_column=merge_start,
                                    end_row=row_number, end_column=end_col,
                                )
                            merge_start = None
                    last_val = val
                current_row += 1
        else:
            for col_idx, val in enumerate(flat_df.columns, start=1):
                cell = ws.cell(current_row, col_idx)
                cell.value     = val
                cell.font      = hdr_font
                cell.border    = border
                cell.alignment = center_aln if col_idx > 1 else left_aln
            current_row += 1

        p_col = flat_df.columns.get_loc("P-value") if "P-value" in flat_df.columns else None
        test_col = flat_df.columns.get_loc("Test") if "Test" in flat_df.columns else None
        data_rows = [list(row) for row in flat_df.itertuples(index=False)]
        merge_ranges = []

        if p_col is not None or test_col is not None:
            row_count = len(data_rows)
            idx = 0
            while idx < row_count:
                label = data_rows[idx][0]
                if isinstance(label, str) and label and not label.startswith("⠀"):
                    next_idx = idx + 1
                    if next_idx < row_count and isinstance(data_rows[next_idx][0], str) and data_rows[next_idx][0].startswith("⠀"):
                        last_cat = next_idx
                        while last_cat + 1 < row_count:
                            next_label = data_rows[last_cat + 1][0]
                            if not (isinstance(next_label, str) and next_label.startswith("⠀")):
                                break
                            next_label_text = str(next_label).replace("⠀", "").strip()
                            if next_label_text == "Missing":
                                break
                            last_cat += 1

                        if p_col is not None and data_rows[idx][p_col]:
                            data_rows[next_idx][p_col] = data_rows[idx][p_col]
                            data_rows[idx][p_col] = ""
                            if last_cat > next_idx:
                                merge_ranges.append((next_idx, last_cat, p_col))

                        if test_col is not None and data_rows[idx][test_col]:
                            data_rows[next_idx][test_col] = data_rows[idx][test_col]
                            data_rows[idx][test_col] = ""
                            if last_cat > next_idx:
                                merge_ranges.append((next_idx, last_cat, test_col))
                idx += 1

        ws.freeze_panes = ws.cell(current_row, 1)
        first_data_row = current_row

        for row_idx, row_data in enumerate(data_rows, start=first_data_row):
            for col_idx, value in enumerate(row_data, start=1):
                cell = ws.cell(row_idx, col_idx)
                cell.value = str(value) if value is not None else ""
                cell.border = border
                cell.font = body_font
                cell.alignment = left_aln if col_idx == 1 else center_aln
            current_row += 1

        for start_idx, end_idx, col_idx in merge_ranges:
            ws.merge_cells(
                start_row=first_data_row + start_idx,
                start_column=col_idx + 1,
                end_row=first_data_row + end_idx,
                end_column=col_idx + 1,
            )
            merged_cell = ws.cell(first_data_row + start_idx, col_idx + 1)
            merged_cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        if table_footnote:
            ws.append([table_footnote] + [""] * (n_data_cols - 1))
            ws.merge_cells(
                start_row=current_row, start_column=1,
                end_row=current_row,   end_column=n_data_cols,
            )
            footer_cell = ws.cell(current_row, 1)
            footer_cell.font      = Font(italic=True, size=10, name="Arial")
            footer_cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
            footer_cell.border    = Border(top=Side(style="thin", color="BDC3C7"))
            current_row += 1

        for col_idx in range(1, n_data_cols + 1):
            max_len    = 0
            col_letter = get_column_letter(col_idx)
            for row in ws.iter_rows(min_col=col_idx, max_col=col_idx):
                for cell in row:
                    if cell.value:
                        lines = str(cell.value).split("\n")
                        max_len = max(max_len, max(len(ln) for ln in lines))
            ws.column_dimensions[col_letter].width = min(max(max_len + 2, 10), 42)

    if isinstance(df_or_tables, list):
        if not df_or_tables:
            raise ValueError("No tables provided for Excel workbook export.")
        wb = openpyxl.Workbook()
        for idx, (sheet_name, table_df) in enumerate(df_or_tables):
            if idx == 0:
                ws = wb.active
                ws.title = sheet_name[:31]
            else:
                ws = wb.create_sheet(title=sheet_name[:31])
            _write_table(ws, table_df, table_title=None, table_footnote=None)
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Table 1"
        _write_table(ws, df_or_tables, table_title=title, table_footnote=footnote)

    wb.save(path)
    logger.info("Saved Excel file → %s", path)

# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns to single-level strings."""
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = [
            "\n".join(
                str(c) for c in col
                if c and str(c).strip() not in ("", " ")
            )
            for col in out.columns.values
        ]
    return out


def _safe(value: object) -> str:
    """Convert value to HTML-safe string."""
    s = str(value) if value is not None else ""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
