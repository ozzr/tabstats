import pandas as pd
import numpy as np
from tabstat import tabstat


def test_pvalue_appears_in_separator(df_medium):
    """P-value for binary categorical should appear in a separator line."""
    import io, sys
    old = sys.stdout
    sys.stdout = buf = io.StringIO()
    tabstat(df_medium, "sex | outcome", tablefmt="grid", show=True)
    sys.stdout = old
    output = buf.getvalue()
    # The p-value column value should appear in a '+' line, not a '|' line
    separator_lines = [ln for ln in output.split("\n") if ln.startswith("+")]
    has_pval_in_sep = any(
        any(c.isdigit() for c in ln)
        for ln in separator_lines
    )
    assert has_pval_in_sep


def test_title_box_rendered(df_medium):
    import io, sys
    old = sys.stdout
    sys.stdout = buf = io.StringIO()
    tabstat(df_medium, "age | outcome",
            tablefmt="grid", title="My Title", show=True)
    sys.stdout = old
    output = buf.getvalue()
    assert "My Title" in output


def test_footnote_box_rendered(df_medium):
    import io, sys
    old = sys.stdout
    sys.stdout = buf = io.StringIO()
    tabstat(df_medium, "age | outcome",
            tablefmt="grid", footnote="My footnote", show=True)
    sys.stdout = old
    output = buf.getvalue()
    assert "My footnote" in output


def test_nested_header_contains_group_name(df_medium):
    import io, sys
    old = sys.stdout
    sys.stdout = buf = io.StringIO()
    tabstat(df_medium, "age | outcome", tablefmt="grid", show=True)
    sys.stdout = old
    output = buf.getvalue()
    assert "outcome" in output
