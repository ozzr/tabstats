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


def test_nested_header_supports_three_group_levels():
    import io, sys
    import numpy as np
    from tabstat import tabstat

    np.random.seed(0)
    df = pd.DataFrame({
        "CASECLASSIF": np.random.choice(["A", "B"], size=24),
        "FATAL": np.random.choice(["Fatal", "Non-fatal"], size=24),
        "PCTDIC": np.random.choice(["Yes", "No"], size=24),
        "age": np.random.normal(50, 10, size=24),
    })

    old = sys.stdout
    sys.stdout = buf = io.StringIO()
    try:
        tabstat(df, "age | CASECLASSIF + FATAL + PCTDIC",
                tablefmt="grid", show=True)
    finally:
        sys.stdout = old

    output = buf.getvalue()
    assert "A  (n=" in output
    assert "B  (n=" in output
    assert "Fatal" in output
    assert "Non-fatal" in output
    assert "Yes" in output
    assert "No" in output
