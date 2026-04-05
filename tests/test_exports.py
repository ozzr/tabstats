import os
import tempfile
import pandas as pd
from tabstat import tabstat
from tabstat.generator import TabStatGenerator
from tabstat.config import TabStatConfig


def test_html_returns_string(df_medium):
    html = tabstat(df_medium, "age | outcome", tablefmt="html")
    assert isinstance(html, str)
    assert "<table" in html.lower()


def test_html_contains_title(df_medium):
    html = tabstat(df_medium, "age | outcome",
                   tablefmt="html", title="Test Title")
    assert "Test Title" in html


def test_excel_creates_file(df_medium):
    gen = TabStatGenerator(TabStatConfig())
    result = gen.generate(df_medium, "age + sex | outcome")
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    try:
        gen.to_excel(result, path, title="Table 1")
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0
    finally:
        os.unlink(path)


def test_excel_merges_title_and_footnote_rows(df_medium):
    gen = TabStatGenerator(TabStatConfig())
    result = gen.generate(df_medium, "age + sex | outcome", title="Table 1", footnote="IQR note")
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    try:
        gen.to_excel(result, path, title="Table 1", footnote="IQR note")
        import openpyxl
        from openpyxl.utils import get_column_letter
        wb = openpyxl.load_workbook(path)
        ws = wb.active
        merged = [str(r) for r in ws.merged_cells.ranges]
        title_range = f"A1:{get_column_letter(ws.max_column)}1"
        assert title_range in merged
        assert ws["A1"].value == "Table 1"
        assert ws.cell(ws.max_row, 1).value == "IQR note"
    finally:
        os.unlink(path)


def test_excel_merges_repeated_multiindex_headers(df_medium):
    gen = TabStatGenerator(TabStatConfig())
    result = gen.generate(df_medium, "age + sex | outcome")
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    try:
        gen.to_excel(result, path, title="Table 1")
        import openpyxl
        wb = openpyxl.load_workbook(path)
        ws = wb.active
        merged = [str(r) for r in ws.merged_cells.ranges]
        assert "B2:C2" in merged
        assert ws["B2"].value == "outcome"
    finally:
        os.unlink(path)


def test_excel_workbook_multiple_tables(df_medium):
    gen = TabStatGenerator(TabStatConfig())
    result1 = gen.generate(df_medium, "age + sex | outcome", title="Table 1")
    result2 = gen.generate(df_medium, "creat | outcome", title="Table 2")
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    try:
        gen.to_excel_workbook([
            ("Table1", result1),
            ("Table2", result2),
        ], path)
        import openpyxl
        wb = openpyxl.load_workbook(path)
        assert wb.sheetnames == ["Table1", "Table2"]
        assert wb["Table1"].cell(1, 1).value == "Table 1"
        assert wb["Table2"].cell(1, 1).value == "Table 2"
    finally:
        os.unlink(path)
