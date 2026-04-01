"""
tabstat/generator.py
────────────────────
Core Table 1 generator for clinical/epidemiological research.

Improvements over the original table1.py
─────────────────────────────────────────
  ✓ _get_group_mask()        — DRY helper (mask logic written once)
  ✓ NormalitySelector        — adaptive Shapiro / D'Agostino / Moment-based
  ✓ TestResolver             — 4-level hierarchical test override
  ✓ N per group in headers   — "(n=47)" appended to every group column
  ✓ Missing-data sub-rows    — per variable, skipped when 0 missing
  ✓ SMD column               — Cohen's d (numeric) / proportion SMD (binary)
  ✓ Binary variable collapse — single row for dichotomous variables
  ✓ Per-variable render specs— render_continuous as Dict or List
  ✓ Regex word-boundary fix  — prevents 'std' matching inside 'standard'
  ✓ Validation on entry      — duplicate cols, empty groups, all-NaN vars
  ✓ logging instead of warn  — standard Python logging
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from scipy.stats import (
    chi2_contingency,
    f_oneway,
    fisher_exact,
    kruskal,
    levene,
    mannwhitneyu,
    ttest_ind,
    ttest_rel,
    wilcoxon,
)
from tabulate import tabulate

from .config import TabStatConfig, TestOverrideConfig
from .normality import NormalitySelector
from .resolver import TestResolver

from scipy.stats import binom

logger = logging.getLogger(__name__)


def _mcnemar_exact(ct: pd.DataFrame) -> float:
    """
    Exact McNemar test for a 2×2 contingency table.
    Uses the binomial distribution on the discordant pairs (b, c).
    """
    b = int(ct.iloc[0, 1])
    c = int(ct.iloc[1, 0])
    n = b + c
    if n == 0:
        return np.nan
    # Two-sided exact p-value: P(X <= min(b,c)) * 2, capped at 1
    p = 2 * binom.cdf(min(b, c), n, 0.5)
    return float(min(p, 1.0))


class TabStatGenerator:
    """
    Generates publication-ready Table 1 for descriptive clinical studies.

    Basic usage
    -----------
    >>> gen = TabStatGenerator()
    >>> df_table = gen.generate(df, "age + sex + creat | outcome")
    """

    def __init__(self, config: Optional[TabStatConfig] = None) -> None:
        self.config = config or TabStatConfig()
        self.normality_selector = NormalitySelector()
        self.test_resolver = TestResolver(self.config.test_overrides)

    # =========================================================================
    # Public entry point
    # =========================================================================

    def generate(
        self,
        df: pd.DataFrame,
        formula: str,
        output_format: str = "df",   # 'df' | 'markdown' | 'latex' | 'grid' | 'html'
        column_labels: Optional[Dict[str, str]] = None,
        paired: bool = False,
    ) -> Union[pd.DataFrame, str]:
        """
        Generate Table 1.

        Formula syntax
        --------------
        "var1 + var2 | group"   specific variables, one grouping column
        "~ . | group"           all columns except group
        "~ ."                   all columns, no stratification

        Parameters
        ----------
        df             : source DataFrame
        formula        : R-style formula string
        output_format  : 'df' returns DataFrame; others print a formatted string
        column_labels  : rename variables or group levels in the output
        paired         : use paired tests (McNemar, Wilcoxon signed-rank, paired-t)
        """
        variables, group_cols = self._parse_formula(df, formula)
        self._validate_dataframe(df, variables, group_cols)

        # Pre-compute group structure once
        groups        = self._get_groups(df, group_cols)
        group_counts  = self._compute_group_counts(df, group_cols, groups)

        # Build rows
        rows: List[List[Any]] = []
        for var in variables:
            try:
                vtype = self._get_render_type(df, var)
                if vtype == "numeric":
                    var_rows = self._summarize_numeric(
                        df, var, group_cols, groups, paired=paired
                    )
                else:
                    var_rows = self._summarize_categorical(
                        df, var, group_cols, groups, paired=paired
                    )
                # Apply variable label remapping to first-row label
                if column_labels and var_rows:
                    key = var_rows[0][0]
                    var_rows[0][0] = column_labels.get(key, key)
                rows.extend(var_rows)
            except Exception as exc:
                logger.warning(
                    "Failed to summarize variable '%s': %s", var, exc
                )

        # Build column index
        columns = self._build_columns(df, group_cols, groups, group_counts)

        # Assemble DataFrame
        n_cols       = len(columns)
        norm_rows    = self._normalize_rows(rows, n_cols)
        result_df    = pd.DataFrame(norm_rows, columns=columns)

        # Remap column labels
        if column_labels:
            if isinstance(result_df.columns, pd.MultiIndex):
                result_df.columns = pd.MultiIndex.from_tuples(
                    [
                        tuple(column_labels.get(str(c), c) for c in col)
                        for col in result_df.columns
                    ]
                )
            else:
                result_df.rename(columns=column_labels, inplace=True)

        # Return / format
        if output_format == "df":
            return result_df

        if output_format == "html":
            from .exports import to_html_str
            return to_html_str(result_df)

        flat_df = self._flatten_multiindex_columns(result_df)
        return tabulate(
            flat_df, headers="keys", tablefmt=output_format, showindex=False
        )

    # ─── Export helpers (convenience wrappers) ────────────────────────────

    def to_html(
        self, df: pd.DataFrame, path: Optional[str] = None
    ) -> str:
        """Export to styled HTML. Optionally write to *path*."""
        from .exports import to_html_str
        html = to_html_str(df)
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(html)
            logger.info("HTML written to %s", path)
        return html

    def to_excel(
        self, df: pd.DataFrame, path: str, title: str = "Table 1"
    ) -> None:
        """Export to styled Excel workbook. Requires openpyxl."""
        from .exports import to_excel_file
        to_excel_file(df, path, title)
        logger.info("Excel written to %s", path)

    def to_latex(self, df: pd.DataFrame) -> str:
        """Return LaTeX tabular string."""
        flat = self._flatten_multiindex_columns(df)
        return tabulate(flat, headers="keys", tablefmt="latex", showindex=False)

    # =========================================================================
    # Formula Parsing & Validation
    # =========================================================================

    def _parse_formula(
        self, df: pd.DataFrame, formula: str
    ) -> Tuple[List[str], List[str]]:
        if "|" in formula:
            vars_part, group_part = formula.split("|", 1)
            group_cols = [g.strip() for g in group_part.split("+") if g.strip()]
        else:
            vars_part  = formula
            group_cols = []

        vars_part = vars_part.replace("~", "").strip()

        if vars_part == ".":
            exclude   = set(group_cols)
            variables = [c for c in df.columns if c not in exclude]
        else:
            variables = [t.strip() for t in vars_part.split("+") if t.strip()]

        valid_vars   = [v for v in variables  if v in df.columns]
        valid_groups = [g for g in group_cols if g in df.columns]

        missing_vars = set(variables) - set(valid_vars)
        if missing_vars:
            logger.warning("Variables not found in DataFrame: %s", missing_vars)
        missing_grps = set(group_cols) - set(valid_groups)
        if missing_grps:
            logger.warning("Group columns not found in DataFrame: %s", missing_grps)

        return valid_vars, valid_groups

    def _validate_dataframe(
        self,
        df: pd.DataFrame,
        variables: List[str],
        group_cols: List[str],
    ) -> None:
        if df.columns.duplicated().any():
            dupes = df.columns[df.columns.duplicated()].tolist()
            raise ValueError(f"Duplicate columns in DataFrame: {dupes}")

        for g in group_cols:
            n_unique = df[g].nunique(dropna=True)
            if n_unique < 2:
                logger.warning(
                    "Group '%s' has %d unique value(s). "
                    "Statistical tests will be skipped.",
                    g, n_unique,
                )

        for v in variables:
            if df[v].isna().all():
                logger.warning(
                    "Variable '%s' is entirely missing (all NaN).", v
                )

    # =========================================================================
    # Render-Type Detection
    # =========================================================================

    def _get_render_type(
        self, df: pd.DataFrame, var: str, max_cardinality: int = 5
    ) -> str:
        cfg = self.config.render_config
        if var in cfg:
            if cfg[var] in ("mean_sd", "median_iqr"):
                return "numeric"
            if cfg[var] == "n_percent":
                return "categorical"

        series = df[var]
        if pd.api.types.is_numeric_dtype(series):
            if (
                pd.api.types.is_integer_dtype(series)
                and series.nunique() <= max_cardinality
            ):
                return "categorical"
            return "numeric"
        return "categorical"

    # =========================================================================
    # Group Structure Helpers
    # =========================================================================

    def _get_groups(self, df: pd.DataFrame, group_cols: List[str]) -> List[Any]:
        """Return sorted list of unique group keys."""
        if not group_cols:
            return []
        if len(group_cols) == 1:
            unique = df[group_cols[0]].dropna().unique()
            try:
                return sorted(unique)
            except TypeError:
                return sorted(str(v) for v in unique)
        else:
            df_clean = df.dropna(subset=group_cols)
            grp = df_clean.groupby(group_cols)
            try:
                return sorted(grp.groups.keys())
            except TypeError:
                return sorted(
                    grp.groups.keys(),
                    key=lambda x: tuple(str(v) for v in x),
                )

    def _compute_group_counts(
        self,
        df: pd.DataFrame,
        group_cols: List[str],
        groups: List[Any],
    ) -> Dict[Any, int]:
        """Count observations per group (non-missing rows in group_cols)."""
        if not group_cols:
            return {}
        return {
            g: int(self._get_group_mask(df, group_cols, g).sum())
            for g in groups
        }

    def _get_group_mask(
        self,
        df: pd.DataFrame,
        group_cols: List[str],
        g_tuple: Any,
    ) -> pd.Series:
        """
        Boolean mask selecting rows that belong to *g_tuple*.
        Works for both single and multi-level grouping.
        """
        mask = pd.Series(True, index=df.index)
        for i, col in enumerate(group_cols):
            val = g_tuple if len(group_cols) == 1 else g_tuple[i]
            mask &= df[col] == val
        return mask

    # =========================================================================
    # Render-Spec Resolution (per-variable vs. global render_continuous)
    # =========================================================================

    def _get_render_specs(self, var: str) -> List[str]:
        """
        Return the list of 'Label = formula' specs for *var*.

        Lookup order: per-variable key → '__default__' key → [] (use default).
        """
        rc = self.config.render_continuous
        if isinstance(rc, dict):
            if var in rc:
                return rc[var]
            return rc.get("__default__", [])
        if isinstance(rc, list):
            return rc
        return []

    # =========================================================================
    # Numeric Summarization
    # =========================================================================

    def _summarize_numeric(
        self,
        df: pd.DataFrame,
        var: str,
        group_cols: List[str],
        groups: List[Any],
        paired: bool = False,
    ) -> List[List[Any]]:
        cfg     = self.config
        rows: List[List[Any]] = []

        overall_hdr   = self._calc_overall_header(df, var)
        resolved_test = self.test_resolver.resolve(var, group_cols, "numeric")
        specs         = self._get_render_specs(var)

        # ── Header row (variable name + N row) ───────────────────────────
        row_main = self._make_header_row(var, overall_hdr, group_cols, groups)
        rows.append(row_main)

        # ── Stats sub-rows ────────────────────────────────────────────────
        if specs:
            group_series_cache: Optional[List[pd.Series]] = None

            for idx, spec in enumerate(specs):
                if " = " not in spec:
                    logger.warning("Invalid render spec (no ' = '): %s", spec)
                    continue

                label_text, formula = spec.split(" = ", 1)
                row_s = [self._indent(label_text.strip())]

                val_overall = self._compute_stat(df[var].dropna(), formula)
                if cfg.display_overall and cfg.overall_position == "first":
                    row_s.append(val_overall)

                group_series: List[pd.Series] = []
                for g_tuple in groups:
                    mask   = self._get_group_mask(df, group_cols, g_tuple)
                    subset = df.loc[mask, var].dropna()
                    group_series.append(subset)
                    row_s.append(
                        self._compute_stat(subset, formula)
                        if len(subset) > 0
                        else cfg.missing_value_symbol
                    )

                if cfg.display_overall and cfg.overall_position == "last":
                    row_s.append(val_overall)

                # Cache first spec's group series for p-value / SMD
                if idx == 0:
                    group_series_cache = group_series

                # P-value on first spec row only
                if group_cols and cfg.display_p_values:
                    if idx == 0:
                        p, test = self._calculate_pvalue_numeric(
                            group_series, resolved_test, paired
                        )
                        row_s.append(self._format_p(p))
                        if cfg.display_test_name:
                            row_s.append(test)
                    else:
                        row_s.append("")
                        if cfg.display_test_name:
                            row_s.append("")

                # SMD on first spec row only (2 groups only)
                if group_cols and cfg.display_smd:
                    if idx == 0 and len(groups) == 2:
                        row_s.append(
                            self._compute_smd_numeric(
                                group_series[0], group_series[1]
                            )
                        )
                    else:
                        row_s.append("")

                rows.append(row_s)
        else:
            # Default: median_iqr or mean_sd based on render_config
            metric = cfg.render_config.get(
                var, cfg.render_config.get("default_numeric", "median_iqr")
            )
            label  = "Mean (SD)" if metric == "mean_sd" else "Median [IQR]"
            row_s  = [self._indent(label)]

            val_overall = self._format_numeric_stats(df[var].dropna(), metric)
            if cfg.display_overall and cfg.overall_position == "first":
                row_s.append(val_overall)

            group_series: List[pd.Series] = []
            for g_tuple in groups:
                mask   = self._get_group_mask(df, group_cols, g_tuple)
                subset = df.loc[mask, var].dropna()
                group_series.append(subset)
                row_s.append(
                    self._format_numeric_stats(subset, metric)
                    if len(subset) > 0
                    else cfg.missing_value_symbol
                )

            if cfg.display_overall and cfg.overall_position == "last":
                row_s.append(val_overall)

            if group_cols and cfg.display_p_values:
                p, test = self._calculate_pvalue_numeric(
                    group_series, resolved_test, paired
                )
                row_s.append(self._format_p(p))
                if cfg.display_test_name:
                    row_s.append(test)

            if group_cols and cfg.display_smd:
                if len(groups) == 2:
                    row_s.append(
                        self._compute_smd_numeric(group_series[0], group_series[1])
                    )
                else:
                    row_s.append("")

            rows.append(row_s)

        # ── Missing sub-row ───────────────────────────────────────────────
        if cfg.display_missing:
            miss = self._make_missing_row(df, var, group_cols, groups)
            if miss is not None:
                rows.append(miss)

        return rows

    # =========================================================================
    # Categorical Summarization
    # =========================================================================

    def _summarize_categorical(
        self,
        df: pd.DataFrame,
        var: str,
        group_cols: List[str],
        groups: List[Any],
        paired: bool = False,
    ) -> List[List[Any]]:
        cfg        = self.config
        rows: List[List[Any]] = []

        categories   = sorted(df[var].dropna().unique())
        is_binary    = len(categories) == 2
        overall_hdr  = self._calc_overall_header(df, var)

        resolved_test = self.test_resolver.resolve(var, group_cols, "categorical")

        # Compute p-value once
        p_value, test_name = np.nan, ""
        if group_cols:
            p_value, test_name = self._calculate_pvalue_categorical(
                df, var, group_cols, resolved_test, paired
            )

        # SMD (binary, 2-group only)
        smd_str = ""
        if group_cols and cfg.display_smd and is_binary and len(groups) == 2:
            ref_cat = categories[-1]
            s1 = df.loc[self._get_group_mask(df, group_cols, groups[0]), var].dropna()
            s2 = df.loc[self._get_group_mask(df, group_cols, groups[1]), var].dropna()
            p1 = (s1 == ref_cat).sum() / len(s1) if len(s1) > 0 else 0.0
            p2 = (s2 == ref_cat).sum() / len(s2) if len(s2) > 0 else 0.0
            smd_str = self._compute_smd_binary(p1, p2)

        # ── Binary collapse: single row ───────────────────────────────────
        if is_binary and cfg.collapse_binary:
            cat = (
                categories[-1]
                if cfg.collapse_binary_level == "last"
                else categories[0]
            )
            label = f"{var}, {cat}"
            row   = [label]

            n_total = int(df[var].count())
            n_cat   = int((df[var] == cat).sum())
            pct     = (n_cat / n_total * 100) if n_total > 0 else 0.0
            val_ov  = f"{n_cat} ({pct:.{cfg.decimals}f}%)"

            if cfg.display_overall and cfg.overall_position == "first":
                row.append(val_ov)

            for g_tuple in groups:
                mask  = self._get_group_mask(df, group_cols, g_tuple)
                sub   = df.loc[mask, var]
                n_g   = int(sub.count())
                n_gc  = int((sub == cat).sum())
                p_g   = (n_gc / n_g * 100) if n_g > 0 else 0.0
                row.append(f"{n_gc} ({p_g:.{cfg.decimals}f}%)")

            if cfg.display_overall and cfg.overall_position == "last":
                row.append(val_ov)

            if group_cols and cfg.display_p_values:
                row.append(self._format_p(p_value))
                if cfg.display_test_name:
                    row.append(test_name)

            if group_cols and cfg.display_smd:
                row.append(smd_str)

            rows.append(row)

            if cfg.display_missing:
                miss = self._make_missing_row(df, var, group_cols, groups)
                if miss is not None:
                    rows.append(miss)

            return rows

        # ── Standard multi-row (header + one row per category) ───────────
        row_main = self._make_header_row(var, overall_hdr, group_cols, groups)
        rows.append(row_main)

        first_cat = True
        for cat in categories:
            label   = self._indent(str(cat))
            row_cat = [label]

            n_total   = int(df[var].count())
            n_cat_tot = int((df[var] == cat).sum())
            pct_tot   = (n_cat_tot / n_total * 100) if n_total > 0 else 0.0
            val_ov    = f"{n_cat_tot} ({pct_tot:.{cfg.decimals}f}%)"

            if cfg.display_overall and cfg.overall_position == "first":
                row_cat.append(val_ov)

            for g_tuple in groups:
                mask  = self._get_group_mask(df, group_cols, g_tuple)
                sub   = df.loc[mask, var]
                n_g   = int(sub.count())
                n_gc  = int((sub == cat).sum())
                p_g   = (n_gc / n_g * 100) if n_g > 0 else 0.0
                row_cat.append(f"{n_gc} ({p_g:.{cfg.decimals}f}%)")

            if cfg.display_overall and cfg.overall_position == "last":
                row_cat.append(val_ov)

            if group_cols and cfg.display_p_values:
                if first_cat:
                    row_cat.append(self._format_p(p_value))
                    if cfg.display_test_name:
                        row_cat.append(test_name)
                else:
                    row_cat.append("")
                    if cfg.display_test_name:
                        row_cat.append("")

            if group_cols and cfg.display_smd:
                row_cat.append(smd_str if first_cat else "")

            rows.append(row_cat)
            first_cat = False

        if cfg.display_missing:
            miss = self._make_missing_row(df, var, group_cols, groups)
            if miss is not None:
                rows.append(miss)

        return rows

    # =========================================================================
    # Row Builders
    # =========================================================================

    def _make_header_row(
        self,
        label: str,
        overall_hdr: str,
        group_cols: List[str],
        groups: List[Any],
    ) -> List[Any]:
        """Main 'variable name' row — carries N but no statistics."""
        cfg = self.config
        row: List[Any] = [label]
        if cfg.display_overall and cfg.overall_position == "first":
            row.append(overall_hdr)
        if group_cols:
            row.extend([""] * len(groups))
        if cfg.display_overall and cfg.overall_position == "last":
            row.append(overall_hdr)
        if group_cols and cfg.display_p_values:
            row.append("")
            if cfg.display_test_name:
                row.append("")
        if group_cols and cfg.display_smd:
            row.append("")
        return row

    def _make_missing_row(
        self,
        df: pd.DataFrame,
        var: str,
        group_cols: List[str],
        groups: List[Any],
    ) -> Optional[List[Any]]:
        """
        Sub-row showing missing data counts.
        Returns None when there are no missing values (row omitted).
        """
        cfg          = self.config
        n_miss_total = int(df[var].isna().sum())
        if n_miss_total == 0:
            return None

        n_total   = len(df)
        pct_total = (n_miss_total / n_total * 100) if n_total > 0 else 0.0
        val_ov    = f"{n_miss_total} ({pct_total:.{cfg.decimals}f}%)"

        row: List[Any] = [self._indent("Missing")]

        if cfg.display_overall and cfg.overall_position == "first":
            row.append(val_ov)

        for g_tuple in groups:
            mask    = self._get_group_mask(df, group_cols, g_tuple)
            sub     = df.loc[mask, var]
            n_g     = len(sub)
            n_miss_g = int(sub.isna().sum())
            pct_g   = (n_miss_g / n_g * 100) if n_g > 0 else 0.0
            row.append(f"{n_miss_g} ({pct_g:.{cfg.decimals}f}%)")

        if cfg.display_overall and cfg.overall_position == "last":
            row.append(val_ov)

        if group_cols and cfg.display_p_values:
            row.append("")
            if cfg.display_test_name:
                row.append("")

        if group_cols and cfg.display_smd:
            row.append("")

        return row

    # =========================================================================
    # Column Index Construction
    # =========================================================================

    def _build_columns(
        self,
        df: pd.DataFrame,
        group_cols: List[str],
        groups: List[Any],
        group_counts: Dict[Any, int],
    ) -> pd.Index:
        cfg = self.config

        # ── No grouping ───────────────────────────────────────────────────
        if not group_cols:
            cols = ["Characteristic"]
            if cfg.display_overall:
                cols.append(f"Total (n={len(df)})")
            return pd.Index(cols)

        final_cols: List[tuple] = []

        # ── Single grouping variable ───────────────────────────────────────
        if len(group_cols) == 1:
            grp_name = group_cols[0]
            final_cols.append(("Characteristic", ""))

            if cfg.display_overall and cfg.overall_position == "first":
                final_cols.append(("Total", f"(n={len(df)})"))

            for g_val in groups:
                n = group_counts.get(g_val, "?")
                final_cols.append((grp_name, f"{g_val} (n={n})"))

            if cfg.display_overall and cfg.overall_position == "last":
                final_cols.append(("Total", f"(n={len(df)})"))

            if cfg.display_p_values:
                final_cols.append(("P-value", ""))
                if cfg.display_test_name:
                    final_cols.append(("Test", ""))

            if cfg.display_smd:
                final_cols.append(("SMD", ""))

        # ── Multiple grouping variables ────────────────────────────────────
        else:
            pad = ("",) * len(group_cols)
            final_cols.append(("Characteristic",) + pad)

            if cfg.display_overall and cfg.overall_position == "first":
                final_cols.append(("Total",) + pad)

            for g_tuple in groups:
                n     = group_counts.get(g_tuple, "?")
                label = g_tuple + (f"(n={n})",)
                final_cols.append(label)

            if cfg.display_overall and cfg.overall_position == "last":
                final_cols.append(("Total",) + pad)

            if cfg.display_p_values:
                final_cols.append(("P-value",) + pad)
                if cfg.display_test_name:
                    final_cols.append(("Test",) + pad)

            if cfg.display_smd:
                final_cols.append(("SMD",) + pad)

        return pd.MultiIndex.from_tuples(final_cols)

    # =========================================================================
    # Statistical Tests — Numeric
    # =========================================================================

    def _calculate_pvalue_numeric(
        self,
        groups_data: List[pd.Series],
        resolved_test: str,
        paired: bool = False,
    ) -> Tuple[float, str]:
        valid = [g.dropna() for g in groups_data if len(g.dropna()) > 1]
        if len(valid) < 2:
            return np.nan, "N/A (insufficient data)"

        # ── Explicit test tokens ──────────────────────────────────────────
        if resolved_test == "mannwhitneyu":
            if len(valid) == 2:
                _, p = mannwhitneyu(*valid, alternative="two-sided")
                return p, "Mann-Whitney U"
            _, p = kruskal(*valid)
            return p, "Kruskal-Wallis"

        if resolved_test in ("ttest", "student"):
            if len(valid) == 2:
                _, p = ttest_ind(*valid, equal_var=True)
                return p, "Student's t-test"
            _, p = f_oneway(*valid)
            return p, "ANOVA"

        if resolved_test == "welch":
            if len(valid) == 2:
                _, p = ttest_ind(*valid, equal_var=False)
                return p, "Welch's t-test"
            _, p = f_oneway(*valid)
            return p, "ANOVA"

        if resolved_test == "kruskal":
            _, p = kruskal(*valid)
            return p, "Kruskal-Wallis"

        if resolved_test == "anova":
            _, p = f_oneway(*valid)
            return p, "ANOVA"

        # ── Auto / never_parametric / always_parametric ───────────────────
        if resolved_test == "never_parametric":
            is_normal = False
        elif resolved_test == "always_parametric":
            is_normal = True
        else:  # "auto" or unknown token
            is_normal = self.normality_selector.all_normal(valid)

        # Paired tests
        if paired and len(valid) == 2:
            if is_normal:
                _, p = ttest_rel(valid[0], valid[1])
                return p, "Paired t-test"
            _, p = wilcoxon(valid[0], valid[1])
            return p, "Wilcoxon Signed-Rank"

        # 2 independent groups
        if len(valid) == 2:
            if is_normal:
                lev_p    = levene(*valid)[1]
                eq_var   = lev_p >= 0.05
                _, p     = ttest_ind(valid[0], valid[1], equal_var=eq_var)
                name     = "Student's t-test" if eq_var else "Welch's t-test"
                return p, name
            _, p = mannwhitneyu(*valid, alternative="two-sided")
            return p, "Mann-Whitney U"

        # >2 groups
        if is_normal:
            _, p = f_oneway(*valid)
            return p, "ANOVA"
        _, p = kruskal(*valid)
        return p, "Kruskal-Wallis"

    # =========================================================================
    # Statistical Tests — Categorical
    # =========================================================================

    def _calculate_pvalue_categorical(
        self,
        df: pd.DataFrame,
        var: str,
        group_cols: List[str],
        resolved_test: str,
        paired: bool = False,
    ) -> Tuple[float, str]:
        tmp = df.copy()
        if len(group_cols) == 1:
            g_col = group_cols[0]
        else:
            g_col = "_grp_combined_"
            tmp[g_col] = tmp[group_cols].astype(str).agg("_".join, axis=1)

        ct = pd.crosstab(tmp[var], tmp[g_col])
        if ct.size == 0:
            return np.nan, "N/A"

        if paired:
            if ct.shape == (2, 2):
                return _mcnemar_exact(ct), "McNemar Test (exact)"
            return np.nan, "McNemar (not applicable for >2×2)"

        # Explicit overrides
        if resolved_test == "chi2":
            _, p, _, _ = chi2_contingency(ct)
            return p, "Chi-Squared"

        if resolved_test == "fisher":
            if ct.shape == (2, 2):
                _, p = fisher_exact(ct)
                return p, "Fisher Exact"
            # Fisher not defined for >2×2; fall back to Chi-Squared
            _, p, _, _ = chi2_contingency(ct)
            return p, "Chi-Squared (Fisher N/A for >2×2)"

        # Auto: apply expected-cell rule (standard epidemiological criterion)
        if ct.shape == (2, 2):
            _, p_chi, _, expected = chi2_contingency(ct)
            if expected.min() < 5 or (expected < 1).any():
                _, p = fisher_exact(ct)
                return p, "Fisher Exact"
            return p_chi, "Chi-Squared"

        _, p, _, _ = chi2_contingency(ct)
        return p, "Chi-Squared"

    # =========================================================================
    # SMD Calculations
    # =========================================================================

    def _compute_smd_numeric(self, g1: pd.Series, g2: pd.Series) -> str:
        """
        Cohen's d with pooled SD (equal weight, unbiased).
        Applicable only to 2-group comparisons.
        """
        g1, g2 = g1.dropna(), g2.dropna()
        if len(g1) < 2 or len(g2) < 2:
            return ""
        pooled_sd = np.sqrt((g1.var(ddof=1) + g2.var(ddof=1)) / 2.0)
        if pooled_sd == 0:
            return "0.00"
        return f"{abs(g1.mean() - g2.mean()) / pooled_sd:.2f}"

    def _compute_smd_binary(self, p1: float, p2: float) -> str:
        """SMD for binary proportions (Cohen's h simplified)."""
        p_avg = (p1 + p2) / 2.0
        denom = np.sqrt(p_avg * (1.0 - p_avg)) if 0.0 < p_avg < 1.0 else 0.0
        if denom == 0:
            return ""
        return f"{abs(p1 - p2) / denom:.2f}"

    # =========================================================================
    # Formatting Helpers
    # =========================================================================

    def _calc_overall_header(self, df: pd.DataFrame, var: str) -> str:
        n_total = len(df)
        n_valid = int(df[var].count())
        pct     = (n_valid / n_total * 100) if n_total > 0 else 0.0
        mode    = self.config.total_mode
        if mode == "n":
            return str(n_total)
        if mode == "n_valid":
            return str(n_valid)
        return f"{n_valid} ({pct:.1f}%)"

    def _format_numeric_stats(self, data: pd.Series, metric: str) -> str:
        data = data.dropna()
        if len(data) == 0:
            return self.config.missing_value_symbol
        d = self.config.decimals
        if metric == "mean_sd":
            return f"{data.mean():.{d}f} ({data.std():.{d}f})"
        med = data.median()
        q25 = data.quantile(0.25)
        q75 = data.quantile(0.75)
        return f"{med:.{d}f} [{q25:.{d}f}–{q75:.{d}f}]"

    def _compute_stat(self, data: pd.Series, formula: str) -> str:
        """
        Evaluate a formula string (e.g. 'mean (± std)') against *data*.

        Supported tokens:
            mean, std, var, median
            pXX  → percentile XX  (e.g. p25, p75, p63)

        Word-boundary regex prevents 'std' from matching inside 'standard'.
        """
        data = data.dropna()
        if len(data) == 0:
            return self.config.missing_value_symbol

        d = self.config.decimals
        result = formula.strip()

        # Percentiles first (pXX pattern)
        for num in set(re.findall(r"p(\d+)", result)):
            val    = data.quantile(int(num) / 100)
            result = re.sub(rf"\bp{num}\b", f"{val:.{d}f}", result)

        # Keyword tokens — word boundaries prevent partial matches
        keywords = {
            "mean":   lambda s: s.mean(),
            "std":    lambda s: s.std(),
            "var":    lambda s: s.var(),
            "median": lambda s: s.median(),
        }
        for key, func in keywords.items():
            if re.search(rf"\b{key}\b", result):
                val    = func(data)
                result = re.sub(rf"\b{key}\b", f"{val:.{d}f}", result)

        return result

    def _format_p(self, p: float) -> str:
        if pd.isna(p):
            return ""
        if p < 0.001:
            return "<0.001"
        return f"{p:.{self.config.p_decimals}f}"

    def _indent(self, text: str) -> str:
        return (self.config.indent_char + " " * self.config.indent_width) + text

    def _normalize_rows(
        self, rows: List[List[Any]], target_len: int
    ) -> List[List[Any]]:
        return [
            (r + [""] * (target_len - len(r)))[:target_len]
            for r in rows
        ]

    @staticmethod
    def _flatten_multiindex_columns(df: pd.DataFrame) -> pd.DataFrame:
        flat = df.copy()
        if isinstance(flat.columns, pd.MultiIndex):
            flat.columns = [
                "\n".join(
                    str(c) for c in col
                    if c and str(c).strip() not in ("", " ")
                )
                for col in flat.columns.values
            ]
        return flat
