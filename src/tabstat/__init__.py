"""
tabstat  v1.1.1
───────────────
Publication-ready Table 1 for clinical and epidemiological research.

Quick start
-----------
>>> from tabstat import tabstat, TabStatConfig, TestOverrideConfig
>>>
>>> t = tabstat(
...     df,
...     "CREAT + GENDER + AGE | CASECLASSIF + FATAL",
...     title          = "Table 1. Cohort characteristics",
...     footnote       = "IQR = interquartile range.",
...     display_missing = True,
...     pct_denominator = "parent_group",
...     test_overrides  = TestOverrideConfig.preset("clinical_descriptive"),
... )

Package layout
--------------
  tabstat.config    → TabStatConfig, TestOverrideConfig
  tabstat.normality → NormalitySelector
  tabstat.resolver  → TestResolver
  tabstat.generator → TabStatGenerator
  tabstat.rendering → render_text_table, ColLayout, build_col_layout
  tabstat.exports   → to_html_str, to_excel_file
"""
from __future__ import annotations

import logging
from typing import Dict, Optional, Union

import pandas as pd

from .config    import TabStatConfig, TestOverrideConfig
from .normality import NormalitySelector
from .resolver  import TestResolver
from .generator import TabStatGenerator

__all__ = [
    "tabstat",
    "TabStatGenerator",
    "TabStatConfig",
    "TestOverrideConfig",
    "NormalitySelector",
    "TestResolver",
]

__version__ = "1.1.1"

logger = logging.getLogger(__name__)


def tabstat(
    df: pd.DataFrame,
    formula: str,
    *,
    # ── Output control ────────────────────────────────────────────────────
    paired:         bool                        = False,
    tablefmt:       str                         = "df",
    show:           bool                        = True,
    column_labels:  Optional[Dict[str, str]]    = None,
    title:          Optional[str]               = None,
    footnote:       Optional[str]               = None,
    # ── TabStatConfig fields (forwarded via **kwargs) ─────────────────────
    **kwargs,
) -> Union[pd.DataFrame, str]:
    """
    Generate a publication-ready Table 1.  Analysis runs exactly once.

    Parameters
    ----------
    df : pd.DataFrame
        Source data.  Each row is one subject.
    formula : str
        R-style formula:
          ``"var1 + var2 | group"``   — specific variables, one grouping column
          ``"~ . | group"``           — all columns except group
          ``"~ ."``                   — all columns, no stratification
    paired : bool
        Use paired tests (McNemar, Wilcoxon signed-rank, paired-t).
    tablefmt : str
        ``'df'``       → return DataFrame (title/footnote as rows; no print).
        ``'grid'``     → print grid + return DataFrame.
        ``'markdown'`` → print markdown + return DataFrame.
        ``'latex'``    → print LaTeX + return DataFrame.
        ``'html'``     → return HTML string.
    show : bool
        Print text output to stdout when tablefmt is a text format (default True).
        Set to False to suppress printing and just receive the DataFrame.
    column_labels : dict, optional
        Rename variables or group values: ``{'CREAT': 'Creatinine', 0: 'Survivor'}``.
    title : str, optional
        Table title.  For text formats: rendered as a box above the table.
        For 'df': prepended as a row in the Characteristic column.
    footnote : str, optional
        Table footnote.  For text formats: rendered as a box below the table.
        For 'df': appended as a row in the Characteristic column.
    **kwargs : TabStatConfig fields
        Any field of :class:`TabStatConfig`:

        ================== ============ ======================================
        Field              Default      Description
        ================== ============ ======================================
        decimals           1            Decimal places for statistics
        p_decimals         3            Decimal places for p-values
        display_overall    True         Show Total column
        overall_position   'last'       'first' or 'last'
        display_p_values   True         Show P-value column
        display_test_name  True         Show Test column
        display_smd        False        Show SMD column
        display_missing    True         Show Missing sub-row per variable
        total_mode         'n_valid_%'  'n' | 'n_valid' | 'n_valid_percent'
        pct_denominator    'group'      'group' | 'total' | 'parent_group'
        collapse_binary    False        Single row for dichotomous variables
        render_config      {}           Force numeric/categorical per variable
        render_continuous  []           Custom stats specs (List or Dict)
        test_overrides     auto         :class:`TestOverrideConfig` or preset str
        ================== ============ ======================================

        ``test_overrides`` can be a :class:`TestOverrideConfig` instance or
        one of the preset strings: ``'clinical_descriptive'``,
        ``'conservative'``, ``'parametric'``.

    Returns
    -------
    pd.DataFrame
        Table 1 as a DataFrame (title/footnote rows included if provided).
    str
        HTML string when ``tablefmt='html'``.

    Examples
    --------
    Basic:

    >>> t = tabstat(df, "age + sex | outcome")

    With options:

    >>> from tabstat import tabstat, TestOverrideConfig
    >>> t = tabstat(
    ...     df,
    ...     "CREAT + PLT + LDH + GPT + NEUTROS | outcome",
    ...     tablefmt       = "grid",
    ...     display_smd    = True,
    ...     display_missing = True,
    ...     pct_denominator = "group",
    ...     test_overrides  = TestOverrideConfig.preset("clinical_descriptive"),
    ...     render_continuous = {
    ...         "CREAT": ["Median [IQR] = median [p25, p75]"],
    ...         "__default__": ["Median [IQR] = median [p25, p75]",
    ...                         "Mean (SD)    = mean (± std)"],
    ...     },
    ...     title    = "Table 1. RMSF Cohort Characteristics",
    ...     footnote = "IQR = interquartile range.",
    ... )
    """
    # ── Build config ──────────────────────────────────────────────────────
    known = set(TabStatConfig.__dataclass_fields__.keys())
    cfg_kwargs: Dict = {}
    for k, v in kwargs.items():
        if k not in known:
            logger.warning("Unknown TabStatConfig field ignored: '%s'", k)
            continue
        if k == "test_overrides" and isinstance(v, str):
            v = TestOverrideConfig.preset(v)
        cfg_kwargs[k] = v

    config = TabStatConfig(**cfg_kwargs)
    gen    = TabStatGenerator(config)

    # ── Single generate() call handles everything ─────────────────────────
    return gen.generate(
        df,
        formula,
        output_format  = tablefmt,
        column_labels  = column_labels,
        paired         = paired,
        title          = title,
        footnote       = footnote,
        show           = show,
    )
