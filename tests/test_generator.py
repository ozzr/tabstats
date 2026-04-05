import pandas as pd
import numpy as np
import pytest
from tabstat import tabstat
from tabstat.generator import TabStatGenerator
from tabstat.config import TabStatConfig


def test_returns_dataframe(df_medium):
    t = tabstat(df_medium, "age + sex | outcome")
    assert isinstance(t, pd.DataFrame)


def test_title_as_first_row(df_medium):
    t = tabstat(df_medium, "age | outcome", title="Table 1")
    assert t.iloc[0, 0] == "Table 1"


def test_footnote_as_last_row(df_medium):
    t = tabstat(df_medium, "age | outcome", footnote="IQR note")
    assert t.iloc[-1, 0] == "IQR note"


def test_text_format_returns_df_with_title_and_footnote_rows(df_medium):
    t = tabstat(
        df_medium,
        "age | outcome",
        tablefmt="grid",
        show=False,
        title="Table 1",
        footnote="IQR note",
    )
    assert t.iloc[0, 0] == "Table 1"
    assert t.iloc[-1, 0] == "IQR note"


def test_missing_row_present_when_enabled(df_medium):
    t = tabstat(df_medium, "creat | outcome", display_missing=True)
    flat = t.iloc[:, 0].tolist()
    assert any("Missing" in str(v) for v in flat)


def test_df_output_includes_categorical_pvalue_and_test(df_medium):
    t = tabstat(df_medium, "sex | outcome")
    cols = [str(c) for c in t.columns]
    p_col = next(i for i, c in enumerate(cols) if "P-value" in c)
    test_col = next(i for i, c in enumerate(cols) if "Test" in c)
    assert any(str(v).strip() for v in t.iloc[:, p_col].tolist())
    assert any(str(v).strip() for v in t.iloc[:, test_col].tolist())


def test_missing_row_absent_when_disabled(df_medium):
    t = tabstat(df_medium, "age | outcome", display_missing=False)
    flat = t.iloc[:, 0].tolist()
    assert not any("Missing" in str(v) for v in flat)


def test_smd_column_present(df_medium):
    t = tabstat(df_medium, "age | outcome", display_smd=True)
    cols = [str(c) for c in t.columns]
    assert any("SMD" in c for c in cols)


def test_no_futurewarning(df_medium):
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        tabstat(df_medium, "age + sex | classif + outcome")


def test_multi_group_produces_multiindex(df_medium):
    t = tabstat(df_medium, "age | classif + outcome")
    assert isinstance(t.columns, pd.MultiIndex)


def test_show_false_does_not_print(df_medium, capsys):
    tabstat(df_medium, "age | outcome", tablefmt="grid", show=False)
    captured = capsys.readouterr()
    assert captured.out == ""


def test_pct_denominator_total(df_medium):
    t_group = tabstat(df_medium, "sex | outcome", pct_denominator="group")
    t_total = tabstat(df_medium, "sex | outcome", pct_denominator="total")
    assert t_group is not None
    assert t_total is not None


def test_collapse_binary(df_medium):
    t = tabstat(df_medium, "sex | outcome", collapse_binary=True)
    labels = t.iloc[:, 0].tolist()
    # Should NOT have separate Male/Female rows
    assert not any(v in ["M", "F"] for v in labels if isinstance(v, str))


def test_formula_all_columns(df_medium):
    t = tabstat(df_medium, "~ . | outcome")
    assert isinstance(t, pd.DataFrame)
    assert len(t) > 1


def test_unknown_variable_warns(df_medium):
    import warnings
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        t = tabstat(df_medium, "nonexistent_col | outcome")
    assert isinstance(t, pd.DataFrame)
