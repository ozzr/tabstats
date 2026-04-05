"""
tabstat/config.py
─────────────────
Configuration dataclasses for TabStat.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Union


@dataclass
class TestOverrideConfig:
    """
    Hierarchical statistical-test override configuration.

    Priority (highest → lowest):
    ┌─────────────────────────────────────────────────────────────┐
    │ 1. per_variable  {'CREAT': 'mannwhitneyu'}                  │
    │ 2. per_group     {'outcome': 'never_parametric'}            │
    │ 3. per_type      {'numeric': 'auto', 'categorical': 'auto'} │
    │ 4. default       'auto'                                     │
    └─────────────────────────────────────────────────────────────┘

    Valid test tokens
    -----------------
    Numeric    : 'auto' | 'mannwhitneyu' | 'ttest' | 'welch' |
                 'kruskal' | 'anova' |
                 'never_parametric' | 'always_parametric'
    Categorical: 'auto' | 'chi2' | 'fisher'
    """

    per_variable: Dict[str, str] = field(default_factory=dict)
    per_group:    Dict[str, str] = field(default_factory=dict)
    per_type:     Dict[str, str] = field(default_factory=dict)
    default:      str = "auto"

    @classmethod
    def preset(cls, name: str) -> "TestOverrideConfig":
        """
        Named presets for common study designs.

        'clinical_descriptive'
            Conservative defaults for descriptive studies.
            Numeric  → non-parametric always.
            Categ.   → Fisher/Chi² (auto expected-cell rule).

        'conservative'
            Non-parametric for everything (safest for small n).

        'parametric'
            Parametric for numeric (use only when normality is confirmed).
        """
        presets: Dict[str, "TestOverrideConfig"] = {
            "clinical_descriptive": cls(
                per_type={"numeric": "never_parametric", "categorical": "auto"},
                default="auto",
            ),
            "conservative": cls(default="never_parametric"),
            "parametric": cls(
                per_type={"numeric": "always_parametric"},
                default="auto",
            ),
        }
        if name not in presets:
            raise ValueError(
                f"Unknown preset '{name}'. Available: {list(presets)}"
            )
        return presets[name]


@dataclass
class TabStatConfig:
    """
    Master configuration for TabStatGenerator.

    All fields have sensible defaults appropriate for clinical
    descriptive tables (e.g., section 'Characteristics of the cohort').
    """

    # ── Numeric formatting ──────────────────────────────────────────────────
    decimals:             int = 1    # decimal places for statistics
    p_decimals:           int = 3    # decimal places for p-values

    # ── Display toggles ─────────────────────────────────────────────────────
    display_overall:      bool = True
    overall_position:     str  = "last"   # 'first' | 'last'
    display_p_values:     bool = True
    display_test_name:    bool = True
    display_smd:          bool = False    # Standardized Mean Difference
    display_missing:      bool = True     # Missing-data sub-row per variable

    # ── Total column mode ───────────────────────────────────────────────────
    # 'n'              → raw total N
    # 'n_valid'        → non-missing N
    # 'n_valid_percent'→ non-missing N (%)
    total_mode:           str  = "n_valid_percent"

    # ── Percentage denominator for categorical variables ─────────────────────
    # 'group'        → % of the column (group) non-missing total  [default, standard]
    # 'total'        → % of grand total N (all subjects in the table)
    # 'parent_group' → for ≥2 grouping variables, % within the first-level group.
    #                  Example: "CASECLASSIF + FATAL" → % within Compatible or Confirmed.
    #                  Falls back to 'group' for single grouping variable.
    pct_denominator:      str  = "group"

    # ── Symbols / indentation ───────────────────────────────────────────────
    missing_value_symbol: str  = "NA"
    indent_char:          str  = "\u2800"   # Braille blank (visually safe)
    indent_width:         int  = 3

    # ── Binary variable collapsing ──────────────────────────────────────────
    # When True, a variable with exactly 2 categories is condensed to 1 row
    # (e.g. "Female, n (%)" instead of header + Male row + Female row).
    collapse_binary:       bool = False
    collapse_binary_level: str  = "last"    # 'first' | 'last' category shown

    # ── Render type overrides ───────────────────────────────────────────────
    # Force a variable to be rendered as numeric or categorical:
    #   {'score': 'mean_sd', 'grade': 'n_percent', 'default_numeric': 'median_iqr'}
    render_config: Dict[str, str] = field(default_factory=dict)

    # ── Custom continuous statistics rendering ──────────────────────────────
    # List[str]  → global, applies to ALL numeric variables
    #   ['Median [IQR] = median [p25, p75]', 'Mean (SD) = mean (± std)']
    #
    # Dict[str, List[str]] → per-variable; key '__default__' is the fallback
    #   {
    #       'CREAT': ['Median [IQR] = median [p25, p75]'],
    #       '__default__': ['Median [IQR] = median [p25, p75]', 'Mean (SD) = mean (± std)'],
    #   }
    render_continuous: Union[List[str], Dict[str, List[str]]] = field(
        default_factory=list
    )

    # ── Data quality checks ─────────────────────────────────────────────────
    check_outliers:   bool = False   # Tukey far-outlier detection
    check_multimodal: bool = False   # Hartigan Dip Test (requires diptest)

    # ── Statistical test override hierarchy ─────────────────────────────────
    test_overrides: TestOverrideConfig = field(
        default_factory=TestOverrideConfig
    )
