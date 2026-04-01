"""
tabstat
───────
Publication-ready Table 1 for clinical and epidemiological research.

Quick start
-----------
>>> from tabstat import tabstat, TabStatConfig, TestOverrideConfig

>>> # Simplest call
>>> df_out = tabstat(df, "age + sex + creat | outcome")

>>> # With options
>>> df_out = tabstat(
...     df,
...     "age + sex + creat + plt | outcome",
...     tablefmt      = "grid",
...     display_smd   = True,
...     display_missing = True,
...     test_overrides = TestOverrideConfig.preset("clinical_descriptive"),
...     render_continuous = {
...         "creat": ["Median [IQR] = median [p25, p75]"],
...         "__default__": ["Median [IQR] = median [p25, p75]", "Mean (SD) = mean (± std)"],
...     },
...     column_labels = {"outcome": "Fatal Outcome"},
... )

Submodule layout
----------------
  tabstat.config     → TabStatConfig, TestOverrideConfig
  tabstat.normality  → NormalitySelector
  tabstat.resolver   → TestResolver
  tabstat.generator  → TabStatGenerator
  tabstat.exports    → to_html_str, to_excel_file
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

__version__ = "1.0.0"

logger = logging.getLogger(__name__)


def tabstat(
    df: pd.DataFrame,
    formula: str,
    *,
    paired:        bool = False,
    tablefmt:      str  = "df",     # 'df' | 'grid' | 'markdown' | 'latex' | 'html'
    column_labels: Optional[Dict[str, str]] = None,
    **kwargs,
) -> pd.DataFrame:
    """
    Generate a publication-ready Table 1.

    Parameters
    ----------
    df : pd.DataFrame
        Source data. Each row is one subject.
    formula : str
        R-style formula:
          "var1 + var2 | group"   — specific variables, one grouping column
          "~ . | group"           — all columns except group
          "~ ."                   — all columns, no stratification
    paired : bool
        Use paired tests (McNemar, Wilcoxon signed-rank, paired-t).
    tablefmt : str
        'df'       → return DataFrame only (no print)
        'grid'     → print grid, return DataFrame
        'markdown' → print markdown, return DataFrame
        'latex'    → print LaTeX tabular, return DataFrame
        'html'     → return HTML string (not printed)
    column_labels : dict, optional
        Rename variables or group values in the output.
        {'creat': 'Creatinine', 'outcome': 'Fatal outcome'}
    **kwargs
        Any field of TabStatConfig:
          decimals, p_decimals, display_smd, display_missing,
          collapse_binary, render_config, render_continuous,
          test_overrides (TestOverrideConfig instance or preset name), …

    Returns
    -------
    pd.DataFrame
        The Table 1 as a DataFrame (always returned regardless of tablefmt).

    Examples
    --------
    >>> from tabstat import tabstat, TestOverrideConfig
    >>> df_t1 = tabstat(
    ...     df, "~ . | outcome",
    ...     tablefmt       = "grid",
    ...     display_smd    = True,
    ...     test_overrides = TestOverrideConfig.preset("clinical_descriptive"),
    ... )
    """
    # ── Build config from kwargs ──────────────────────────────────────────
    known_fields = set(TabStatConfig.__dataclass_fields__.keys())
    config_kwargs = {}

    for k, v in kwargs.items():
        if k not in known_fields:
            logger.warning("Unknown TabStatConfig field ignored: '%s'", k)
            continue
        # Allow passing preset name as string for test_overrides
        if k == "test_overrides" and isinstance(v, str):
            v = TestOverrideConfig.preset(v)
        config_kwargs[k] = v

    config = TabStatConfig(**config_kwargs)
    gen    = TabStatGenerator(config)

    result_df = gen.generate(
        df, formula,
        output_format  = "df",
        column_labels  = column_labels,
        paired         = paired,
    )

    if tablefmt == "html":
        from .exports import to_html_str
        return to_html_str(result_df)

    if tablefmt != "df":
        formatted = gen.generate(
            df, formula,
            output_format  = tablefmt,
            column_labels  = column_labels,
            paired         = paired,
        )
        print(formatted)

    return result_df
