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

__version__ = "1.0.1"

logger = logging.getLogger(__name__)


def tabstat(
    df: pd.DataFrame,
    formula: str,
    *,
    paired:         bool = False,
    tablefmt:       str  = "df",
    column_labels:  Optional[Dict[str, str]] = None,
    title:          Optional[str] = None,
    footnote:       Optional[str] = None,
    show_subtotals: bool = False,
    **kwargs,
) -> Union[pd.DataFrame, str]:
    """
    Generate a publication-ready Table 1.

    Parameters
    ----------
    df : pd.DataFrame
    formula : str
        "var1 + var2 | group"  /  "~ . | group"  /  "~ ."
    paired : bool
    tablefmt : str
        'df' → DataFrame only (no print)
        'grid' | 'markdown' | 'latex' → print + return DataFrame
        'html' → return HTML string
    column_labels : dict
        Rename variables or group values: {'creat': 'Creatinine', 0: 'Survivor'}
    title : str
        Optional table title (shown above in text/HTML output).
    footnote : str
        Optional footnote (shown below in text/HTML output).
    show_subtotals : bool
        If True, append a 'N (subjects)' row at the bottom with counts per column.
    **kwargs
        Any TabStatConfig field:
          decimals, p_decimals, display_smd, display_missing,
          collapse_binary, render_config, render_continuous,
          test_overrides (TestOverrideConfig or preset string), …

    Returns
    -------
    pd.DataFrame  (always), or str for 'html' tablefmt.
    """
    known_fields = set(TabStatConfig.__dataclass_fields__.keys())
    config_kwargs = {}
    for k, v in kwargs.items():
        if k not in known_fields:
            logger.warning("Unknown TabStatConfig field ignored: '%s'", k)
            continue
        if k == "test_overrides" and isinstance(v, str):
            v = TestOverrideConfig.preset(v)
        config_kwargs[k] = v

    config = TabStatConfig(**config_kwargs)
    gen    = TabStatGenerator(config)

    if tablefmt == "html":
        return gen.generate(
            df, formula,
            output_format  = "html",
            column_labels  = column_labels,
            paired         = paired,
            title          = title,
            footnote       = footnote,
        )

    if tablefmt != "df":
        # Print formatted + return DataFrame
        formatted = gen.generate(
            df, formula,
            output_format  = tablefmt,
            column_labels  = column_labels,
            paired         = paired,
            title          = title,
            footnote       = footnote,
            show_subtotals = show_subtotals,
        )
        print(formatted)

    return gen.generate(
        df, formula,
        output_format  = "df",
        column_labels  = column_labels,
        paired         = paired,
    )
