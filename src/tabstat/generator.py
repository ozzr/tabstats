"""
tabstat/generator.py
────────────────────
Core Table 1 generator.  Analysis runs ONCE in _run_analysis(); all output
formats (df, grid, html, …) branch from that single result.

Row metadata
────────────
Every row produced by _summarize_* comes paired with a RowMeta dict:
  kind        : 'var_header' | 'stat' | 'category' | 'missing'
  var         : variable name
  pvalue_span : (p_str, test_str, cat_offset, n_cats) | None
                cat_offset is *relative* (rows from this header to first cat).
                _run_analysis() converts it to an absolute index used by
                _get_pvalue_injections() → rendering.py.

P-value display for categoricals
─────────────────────────────────
For categorical variables with ≥2 categories, the p-value is NOT placed
inside a data cell.  Instead it is injected into the separator line between
the middle two category rows by render_text_table() in rendering.py.
This produces the SPSS-style spanning appearance.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from scipy.stats import (
    binom,
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

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# McNemar (no statsmodels dependency)
# ─────────────────────────────────────────────────────────────────────────────

def _mcnemar_exact(ct: pd.DataFrame) -> float:
    b, c = int(ct.iloc[0, 1]), int(ct.iloc[1, 0])
    n = b + c
    if n == 0:
        return np.nan
    return float(min(2 * binom.cdf(min(b, c), n, 0.5), 1.0))


# ─────────────────────────────────────────────────────────────────────────────
# Generator
# ─────────────────────────────────────────────────────────────────────────────

class TabStatGenerator:
    """
    Generates publication-ready Table 1 for descriptive clinical studies.

    Usage
    -----
    >>> gen = TabStatGenerator()
    >>> df_out = gen.generate(df, "age + sex + creat | outcome",
    ...                       output_format="grid", title="Table 1")
    """

    def __init__(self, config: Optional[TabStatConfig] = None) -> None:
        self.config = config or TabStatConfig()
        self.normality_selector = NormalitySelector()
        self.test_resolver = TestResolver(self.config.test_overrides)

    # =========================================================================
    # Public API
    # =========================================================================

    def generate(
        self,
        df: pd.DataFrame,
        formula: str,
        output_format: str = "df",   # 'df'|'grid'|'markdown'|'latex'|'html'
        column_labels: Optional[Dict[str, str]] = None,
        paired: bool = False,
        title: Optional[str] = None,
        footnote: Optional[str] = None,
        show: bool = True,
    ) -> Union[pd.DataFrame, str]:
        """
        Run analysis once and return result in the requested format.

        Parameters
        ----------
        df            : source DataFrame
        formula       : "var1+var2 | group"  /  "~ . | group"  /  "~ ."
        output_format : 'df' | 'grid' | 'markdown' | 'latex' | 'html'
        column_labels : rename variables or group values
        paired        : use paired tests
        title         : optional title (box above for text; row in df)
        footnote      : optional footnote (box below for text; row in df)
        show          : if True (default), print text formats to stdout

        Returns
        -------
        pd.DataFrame  for 'df' (always contains title/footnote rows if provided)
        str           for 'html'
        pd.DataFrame  for text formats (printed if show=True; df also returned)
        """
        from .rendering import build_col_layout, render_text_table

        # ── Single analysis run ───────────────────────────────────────────
        (result_df, row_metas, col_layout,
         group_cols, groups, group_counts) = self._run_analysis(
            df, formula, column_labels, paired
        )

        # ── DataFrame output ──────────────────────────────────────────────
        if output_format == "df":
            return self._attach_title_footnote(result_df, title, footnote)

        # ── HTML output ───────────────────────────────────────────────────
        if output_format == "html":
            from .exports import to_html_str
            return to_html_str(result_df,
                               title=title or "Table 1",
                               footnote=footnote)

        # ── Text output (grid / markdown / latex / …) ─────────────────────
        flat_df = self._flatten_multiindex_columns(result_df)
        pvalue_injections = self._get_pvalue_injections(row_metas)

        # Remap group names/values for the renderer when column_labels given
        if column_labels:
            render_groups = [
                tuple(column_labels.get(str(v), str(v)) for v in g)
                if isinstance(g, tuple)
                else column_labels.get(str(g), str(g))
                for g in groups
            ]
            render_counts = {rg: group_counts[og]
                             for rg, og in zip(render_groups, groups)}
            render_group_cols = [column_labels.get(gc, gc) for gc in group_cols]
        else:
            render_groups     = groups
            render_counts     = group_counts
            render_group_cols = group_cols

        text = render_text_table(
            flat_df           = flat_df,
            col_layout        = col_layout,
            group_cols        = render_group_cols,
            groups            = render_groups,
            group_counts      = render_counts,
            n_total           = len(df),
            tablefmt          = output_format,
            title             = title,
            footnote          = footnote,
            pvalue_injections = pvalue_injections,
        )

        if show:
            print(text)

        return self._attach_title_footnote(result_df, title, footnote)

    # ── Export helpers ────────────────────────────────────────────────────

    def to_html(self, df: pd.DataFrame, path: Optional[str] = None,
                title: str = "Table 1",
                footnote: Optional[str] = None) -> str:
        from .exports import to_html_str
        html = to_html_str(df, title=title, footnote=footnote)
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(html)
            logger.info("HTML written to %s", path)
        return html

    def to_excel(self, df: pd.DataFrame, path: str,
                 title: str = "Table 1") -> None:
        from .exports import to_excel_file
        to_excel_file(df, path, title)
        logger.info("Excel written to %s", path)

    def to_latex(self, df: pd.DataFrame) -> str:
        flat = self._flatten_multiindex_columns(df)
        return tabulate(flat, headers="keys", tablefmt="latex", showindex=False)

    # =========================================================================
    # Core analysis (runs exactly once)
    # =========================================================================

    def _run_analysis(
        self,
        df: pd.DataFrame,
        formula: str,
        column_labels: Optional[Dict[str, str]],
        paired: bool,
    ) -> Tuple:
        """
        Execute the full statistical pipeline.

        Returns
        -------
        (result_df, row_metas, col_layout, group_cols, groups, group_counts)
        """
        from .rendering import build_col_layout

        variables, group_cols = self._parse_formula(df, formula)
        self._validate_dataframe(df, variables, group_cols)

        groups       = self._get_groups(df, group_cols)
        group_counts = self._compute_group_counts(df, group_cols, groups)

        all_rows:  List[List[Any]] = []
        all_metas: List[Dict]      = []

        for var in variables:
            try:
                vtype = self._get_render_type(df, var)
                if vtype == "numeric":
                    var_rows, var_metas = self._summarize_numeric(
                        df, var, group_cols, groups, paired=paired
                    )
                else:
                    var_rows, var_metas = self._summarize_categorical(
                        df, var, group_cols, groups, paired=paired
                    )

                # Remap variable label
                if column_labels and var_rows:
                    key = var_rows[0][0]
                    var_rows[0][0] = column_labels.get(key, key)

                # Convert relative cat_offset → absolute cat_start_abs
                base = len(all_rows)
                for local_i, meta in enumerate(var_metas):
                    span = meta.get("pvalue_span")
                    if span is not None:
                        p_str, test_str, cat_offset, n_cats = span
                        meta["pvalue_span"] = (
                            p_str, test_str,
                            base + local_i + cat_offset,  # absolute
                            n_cats,
                        )

                all_rows.extend(var_rows)
                all_metas.extend(var_metas)

            except Exception as exc:
                logger.warning("Failed to summarize '%s': %s", var, exc)

        # Build DataFrame
        columns   = self._build_columns(df, group_cols, groups, group_counts)
        n_cols    = len(columns)
        norm_rows = self._normalize_rows(all_rows, n_cols)
        result_df = pd.DataFrame(norm_rows, columns=columns)

        # Remap column labels
        if column_labels:
            if isinstance(result_df.columns, pd.MultiIndex):
                result_df.columns = pd.MultiIndex.from_tuples([
                    tuple(column_labels.get(str(c), c) for c in col)
                    for col in result_df.columns
                ])
            else:
                result_df.rename(columns=column_labels, inplace=True)

        col_layout = build_col_layout(
            group_cols        = group_cols,
            groups            = groups,
            display_overall   = self.config.display_overall,
            overall_position  = self.config.overall_position,
            display_p_values  = self.config.display_p_values,
            display_test_name = self.config.display_test_name,
            display_smd       = self.config.display_smd,
        )

        return result_df, all_metas, col_layout, group_cols, groups, group_counts

    def _get_pvalue_injections(
        self, row_metas: List[Dict]
    ) -> List[Tuple[int, str, str]]:
        """
        Convert RowMeta pvalue_span entries into (row_k, p_str, test_str) tuples.
        row_k is the flat_df row index AFTER which the separator gets the p-value.
        """
        injections = []
        for meta in row_metas:
            span = meta.get("pvalue_span")
            if span is None:
                continue
            p_str, test_str, cat_start_abs, n_cats = span
            if not p_str and not test_str:
                continue
            # Inject into the separator after the middle category row
            for i in range(n_cats - 1):          # separadores entre categorías
                k = cat_start_abs + i
                is_middle = (i == (n_cats - 1) // 2 - (1 if n_cats % 2 == 0 else 0))
                # más simple: is_middle = (k == cat_start_abs + (n_cats - 1) // 2)
                injections.append((k, p_str, test_str, k == cat_start_abs + (n_cats - 1) // 2))
        return injections

    def _attach_title_footnote(
        self,
        df: pd.DataFrame,
        title: Optional[str],
        footnote: Optional[str],
    ) -> pd.DataFrame:
        """
        Prepend title row and/or append footnote row to the DataFrame.
        Both appear in the first column; all other columns are empty.
        """
        if not title and not footnote:
            return df

        n_cols  = len(df.columns)
        empty   = [""] * n_cols
        parts   = []

        if title:
            r       = empty.copy()
            r[0]    = title
            parts.append(pd.DataFrame([r], columns=df.columns))

        parts.append(df)

        if footnote:
            r       = empty.copy()
            r[0]    = footnote
            parts.append(pd.DataFrame([r], columns=df.columns))

        return pd.concat(parts, ignore_index=True)

    # =========================================================================
    # Formula parsing & validation
    # =========================================================================

    def _parse_formula(self, df, formula):
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

        missing_v = set(variables)  - set(valid_vars)
        missing_g = set(group_cols) - set(valid_groups)
        if missing_v: logger.warning("Variables not in DataFrame: %s", missing_v)
        if missing_g: logger.warning("Group cols not in DataFrame: %s", missing_g)

        return valid_vars, valid_groups

    def _validate_dataframe(self, df, variables, group_cols):
        if df.columns.duplicated().any():
            dupes = df.columns[df.columns.duplicated()].tolist()
            raise ValueError(f"Duplicate columns: {dupes}")
        for g in group_cols:
            if df[g].nunique(dropna=True) < 2:
                logger.warning("Group '%s' has <2 unique values; tests skipped.", g)
        for v in variables:
            if df[v].isna().all():
                logger.warning("Variable '%s' is entirely NaN.", v)

    # =========================================================================
    # Render-type detection
    # =========================================================================

    def _get_render_type(self, df, var, max_cardinality=5):
        cfg = self.config.render_config
        if var in cfg:
            if cfg[var] in ("mean_sd", "median_iqr"):
                return "numeric"
            if cfg[var] == "n_percent":
                return "categorical"
        series = df[var]
        if pd.api.types.is_numeric_dtype(series):
            if (pd.api.types.is_integer_dtype(series)
                    and series.nunique() <= max_cardinality):
                return "categorical"
            return "numeric"
        return "categorical"

    # =========================================================================
    # Group structure helpers
    # =========================================================================

    def _get_groups(self, df, group_cols):
        if not group_cols:
            return []
        if len(group_cols) == 1:
            unique = df[group_cols[0]].dropna().unique()
            try:    return sorted(unique)
            except: return sorted(str(v) for v in unique)
        else:
            df_clean = df.dropna(subset=group_cols)
            grp = df_clean.groupby(group_cols, observed=True)
            try:    return sorted(grp.groups.keys())
            except: return sorted(grp.groups.keys(),
                                  key=lambda x: tuple(str(v) for v in x))

    def _compute_group_counts(self, df, group_cols, groups):
        if not group_cols:
            return {}
        return {g: int(self._get_group_mask(df, group_cols, g).sum())
                for g in groups}

    def _get_group_mask(self, df, group_cols, g_tuple):
        mask = pd.Series(True, index=df.index)
        for i, col in enumerate(group_cols):
            val = g_tuple if len(group_cols) == 1 else g_tuple[i]
            mask &= df[col] == val
        return mask

    # =========================================================================
    # Render-spec resolution
    # =========================================================================

    def _get_render_specs(self, var):
        rc = self.config.render_continuous
        if isinstance(rc, dict):
            return rc.get(var, rc.get("__default__", []))
        return rc if isinstance(rc, list) else []

    # =========================================================================
    # Percentage denominator
    # =========================================================================

    def _get_cat_denom(
        self,
        df: pd.DataFrame,
        var: str,
        group_cols: List[str],
        g_tuple: Any,
        parent_counts: Dict[Any, int],
    ) -> int:
        """
        Return the denominator for the percentage of a categorical cell.

        parent_counts : {g_tuple → n_valid_for_parent_group}
                        Pre-computed in _summarize_categorical when
                        pct_denominator == 'parent_group'.
        """
        mode = self.config.pct_denominator
        if mode == "total":
            return int(df[var].count())
        if mode == "parent_group" and len(group_cols) > 1:
            return parent_counts.get(g_tuple, 1)
        # 'group' (default)
        mask = self._get_group_mask(df, group_cols, g_tuple)
        return int(df.loc[mask, var].count())

    # =========================================================================
    # Numeric summarization
    # =========================================================================

    def _summarize_numeric(
        self,
        df: pd.DataFrame,
        var: str,
        group_cols: List[str],
        groups: List[Any],
        paired: bool = False,
    ) -> Tuple[List[List[Any]], List[Dict]]:
        """Returns (rows, metas)."""
        cfg           = self.config
        rows: List    = []
        metas: List   = []
        resolved_test = self.test_resolver.resolve(var, group_cols, "numeric")
        specs         = self._get_render_specs(var)
        overall_hdr   = self._calc_overall_header(df, var)

        # var_header row
        row_main = self._make_header_row(var, overall_hdr, group_cols, groups)
        rows.append(row_main)
        metas.append({"kind": "var_header", "var": var, "pvalue_span": None})

        if specs:
            for idx, spec in enumerate(specs):
                if " = " not in spec:
                    logger.warning("Invalid render spec: %s", spec)
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
                    row_s.append(self._compute_stat(subset, formula)
                                 if len(subset) > 0 else cfg.missing_value_symbol)

                if cfg.display_overall and cfg.overall_position == "last":
                    row_s.append(val_overall)

                if group_cols and cfg.display_p_values:
                    if idx == 0:
                        p, test = self._calculate_pvalue_numeric(
                            group_series, resolved_test, paired)
                        row_s.append(self._format_p(p))
                        if cfg.display_test_name:
                            row_s.append(test)
                    else:
                        row_s.append("")
                        if cfg.display_test_name:
                            row_s.append("")

                if group_cols and cfg.display_smd:
                    if idx == 0 and len(groups) == 2:
                        row_s.append(self._compute_smd_numeric(
                            group_series[0], group_series[1]))
                    else:
                        row_s.append("")

                rows.append(row_s)
                metas.append({"kind": "stat", "var": var, "pvalue_span": None})
        else:
            metric = cfg.render_config.get(
                var, cfg.render_config.get("default_numeric", "median_iqr"))
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
                row_s.append(self._format_numeric_stats(subset, metric)
                             if len(subset) > 0 else cfg.missing_value_symbol)

            if cfg.display_overall and cfg.overall_position == "last":
                row_s.append(val_overall)

            if group_cols and cfg.display_p_values:
                p, test = self._calculate_pvalue_numeric(
                    group_series, resolved_test, paired)
                row_s.append(self._format_p(p))
                if cfg.display_test_name:
                    row_s.append(test)

            if group_cols and cfg.display_smd:
                row_s.append(self._compute_smd_numeric(
                    group_series[0], group_series[1])
                    if len(groups) == 2 else "")

            rows.append(row_s)
            metas.append({"kind": "stat", "var": var, "pvalue_span": None})

        if cfg.display_missing:
            miss = self._make_missing_row(df, var, group_cols, groups)
            if miss is not None:
                rows.append(miss)
                metas.append({"kind": "missing", "var": var, "pvalue_span": None})

        return rows, metas

    # =========================================================================
    # Categorical summarization
    # =========================================================================

    def _summarize_categorical(
        self,
        df: pd.DataFrame,
        var: str,
        group_cols: List[str],
        groups: List[Any],
        paired: bool = False,
    ) -> Tuple[List[List[Any]], List[Dict]]:
        """Returns (rows, metas)."""
        cfg          = self.config
        rows: List   = []
        metas: List  = []

        categories    = sorted(df[var].dropna().unique())
        is_binary     = len(categories) == 2
        overall_hdr   = self._calc_overall_header(df, var)
        resolved_test = self.test_resolver.resolve(var, group_cols, "categorical")

        # ── P-value ───────────────────────────────────────────────────────
        p_value, test_name = np.nan, ""
        if group_cols:
            p_value, test_name = self._calculate_pvalue_categorical(
                df, var, group_cols, resolved_test, paired)
        p_str = self._format_p(p_value) if group_cols else ""

        # ── SMD (binary, 2-group only) ─────────────────────────────────────
        smd_str = ""
        if group_cols and cfg.display_smd and is_binary and len(groups) == 2:
            ref_cat = categories[-1]
            s1 = df.loc[self._get_group_mask(df, group_cols, groups[0]), var].dropna()
            s2 = df.loc[self._get_group_mask(df, group_cols, groups[1]), var].dropna()
            p1 = (s1 == ref_cat).sum() / len(s1) if len(s1) > 0 else 0.0
            p2 = (s2 == ref_cat).sum() / len(s2) if len(s2) > 0 else 0.0
            smd_str = self._compute_smd_binary(p1, p2)

        # ── Pre-compute parent group counts for pct_denominator='parent_group' ──
        parent_counts: Dict[Any, int] = {}
        if cfg.pct_denominator == "parent_group" and len(group_cols) > 1:
            parent_col = group_cols[0]
            for g in groups:
                parent_key  = g[0] if isinstance(g, tuple) else g
                parent_mask = df[parent_col] == parent_key
                parent_counts[g] = int(df.loc[parent_mask, var].count())

        n_valid_total = int(df[var].count())

        # ── Binary collapse → single row, p-value directly in cell ───────
        if is_binary and cfg.collapse_binary:
            cat   = (categories[-1] if cfg.collapse_binary_level == "last"
                     else categories[0])
            label = f"{var}, {cat}"
            row   = [label]

            n_cat  = int((df[var] == cat).sum())
            pct_ov = (n_cat / n_valid_total * 100) if n_valid_total > 0 else 0.0
            val_ov = f"{n_cat} ({pct_ov:.{cfg.decimals}f}%)"

            if cfg.display_overall and cfg.overall_position == "first":
                row.append(val_ov)
            for g_tuple in groups:
                mask  = self._get_group_mask(df, group_cols, g_tuple)
                sub   = df.loc[mask, var]
                denom = self._get_cat_denom(df, var, group_cols, g_tuple, parent_counts)
                n_gc  = int((sub == cat).sum())
                pct   = (n_gc / denom * 100) if denom > 0 else 0.0
                row.append(f"{n_gc} ({pct:.{cfg.decimals}f}%)")
            if cfg.display_overall and cfg.overall_position == "last":
                row.append(val_ov)
            if group_cols and cfg.display_p_values:
                row.append(p_str)
                if cfg.display_test_name:
                    row.append(test_name)
            if group_cols and cfg.display_smd:
                row.append(smd_str)

            rows.append(row)
            metas.append({"kind": "var_header", "var": var, "pvalue_span": None})

            if cfg.display_missing:
                miss = self._make_missing_row(df, var, group_cols, groups)
                if miss is not None:
                    rows.append(miss)
                    metas.append({"kind": "missing", "var": var, "pvalue_span": None})

            return rows, metas

        # ── Standard multi-row (header + one row per category) ───────────
        row_main = self._make_header_row(var, overall_hdr, group_cols, groups)
        # SMD on the var_header (last column if display_smd)
        if group_cols and cfg.display_smd and smd_str:
            row_main[-1] = smd_str
        rows.append(row_main)

        # pvalue_span: (p_str, test_str, cat_offset=1, n_cats)
        # cat_offset=1 → categories start 1 row below this header in local list
        span = None
        if group_cols and cfg.display_p_values and len(categories) >= 1:
            span = (p_str, test_name, 1, len(categories))
        metas.append({"kind": "var_header", "var": var, "pvalue_span": span})

        for cat in categories:
            row_cat = [self._indent(str(cat))]

            n_cat_tot = int((df[var] == cat).sum())
            pct_tot   = (n_cat_tot / n_valid_total * 100) if n_valid_total > 0 else 0.0
            val_ov    = f"{n_cat_tot} ({pct_tot:.{cfg.decimals}f}%)"

            if cfg.display_overall and cfg.overall_position == "first":
                row_cat.append(val_ov)

            for g_tuple in groups:
                mask  = self._get_group_mask(df, group_cols, g_tuple)
                sub   = df.loc[mask, var]
                denom = self._get_cat_denom(df, var, group_cols, g_tuple, parent_counts)
                n_gc  = int((sub == cat).sum())
                pct   = (n_gc / denom * 100) if denom > 0 else 0.0
                row_cat.append(f"{n_gc} ({pct:.{cfg.decimals}f}%)")

            if cfg.display_overall and cfg.overall_position == "last":
                row_cat.append(val_ov)

            # P-value and test: ALWAYS EMPTY in category rows
            # (they will be injected into the separator line by render_text_table)
            if group_cols and cfg.display_p_values:
                row_cat.append("")
                if cfg.display_test_name:
                    row_cat.append("")

            # SMD already in var_header
            if group_cols and cfg.display_smd:
                row_cat.append("")

            rows.append(row_cat)
            metas.append({"kind": "category", "var": var, "pvalue_span": None})

        if cfg.display_missing:
            miss = self._make_missing_row(df, var, group_cols, groups)
            if miss is not None:
                rows.append(miss)
                metas.append({"kind": "missing", "var": var, "pvalue_span": None})

        return rows, metas

    # =========================================================================
    # Row builders
    # =========================================================================

    def _make_header_row(self, label, overall_hdr, group_cols, groups):
        cfg = self.config
        row = [label]
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

    def _make_missing_row(self, df, var, group_cols, groups):
        cfg     = self.config
        n_miss  = int(df[var].isna().sum())
        if n_miss == 0:
            return None
        n_total = len(df)
        pct_ov  = (n_miss / n_total * 100) if n_total > 0 else 0.0
        val_ov  = f"{n_miss} ({pct_ov:.{cfg.decimals}f}%)"

        row = [self._indent("Missing")]
        if cfg.display_overall and cfg.overall_position == "first":
            row.append(val_ov)
        for g_tuple in groups:
            mask     = self._get_group_mask(df, group_cols, g_tuple)
            sub      = df.loc[mask, var]
            n_miss_g = int(sub.isna().sum())
            pct_g    = (n_miss_g / len(sub) * 100) if len(sub) > 0 else 0.0
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
    # Column index construction
    # =========================================================================

    def _build_columns(self, df, group_cols, groups, group_counts):
        cfg = self.config
        if not group_cols:
            cols = ["Characteristic"]
            if cfg.display_overall:
                cols.append(f"Total (n={len(df)})")
            return pd.Index(cols)

        final_cols = []
        if len(group_cols) == 1:
            grp_name = group_cols[0]
            final_cols.append(("Characteristic", ""))
            if cfg.display_overall and cfg.overall_position == "first":
                final_cols.append(("Total", f"(n={len(df)})"))
            for g in groups:
                n = group_counts.get(g, "?")
                final_cols.append((grp_name, f"{g} (n={n})"))
            if cfg.display_overall and cfg.overall_position == "last":
                final_cols.append(("Total", f"(n={len(df)})"))
            if cfg.display_p_values:
                final_cols.append(("P-value", ""))
                if cfg.display_test_name:
                    final_cols.append(("Test", ""))
            if cfg.display_smd:
                final_cols.append(("SMD", ""))
        else:
            pad = ("",) * len(group_cols)
            final_cols.append(("Characteristic",) + pad)
            if cfg.display_overall and cfg.overall_position == "first":
                final_cols.append(("Total",) + pad)
            for g in groups:
                n = group_counts.get(g, "?")
                final_cols.append(g + (f"(n={n})",))
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
    # Statistical tests
    # =========================================================================

    def _calculate_pvalue_numeric(self, groups_data, resolved_test, paired=False):
        valid = [g.dropna() for g in groups_data if len(g.dropna()) > 1]
        if len(valid) < 2:
            return np.nan, "N/A"

        if resolved_test == "mannwhitneyu":
            if len(valid) == 2:
                _, p = mannwhitneyu(*valid, alternative="two-sided")
                return p, "Mann-Whitney U"
            _, p = kruskal(*valid); return p, "Kruskal-Wallis"
        if resolved_test in ("ttest", "student"):
            if len(valid) == 2:
                _, p = ttest_ind(*valid, equal_var=True)
                return p, "Student's t-test"
            _, p = f_oneway(*valid); return p, "ANOVA"
        if resolved_test == "welch":
            if len(valid) == 2:
                _, p = ttest_ind(*valid, equal_var=False)
                return p, "Welch's t-test"
            _, p = f_oneway(*valid); return p, "ANOVA"
        if resolved_test == "kruskal":
            _, p = kruskal(*valid); return p, "Kruskal-Wallis"
        if resolved_test == "anova":
            _, p = f_oneway(*valid); return p, "ANOVA"

        is_normal = (False if resolved_test == "never_parametric"
                     else True if resolved_test == "always_parametric"
                     else self.normality_selector.all_normal(valid))

        if paired and len(valid) == 2:
            if is_normal:
                _, p = ttest_rel(valid[0], valid[1]); return p, "Paired t-test"
            _, p = wilcoxon(valid[0], valid[1]); return p, "Wilcoxon Signed-Rank"
        if len(valid) == 2:
            if is_normal:
                lev_p  = levene(*valid)[1]
                eq_var = lev_p >= 0.05
                _, p   = ttest_ind(valid[0], valid[1], equal_var=eq_var)
                return p, ("Student's t-test" if eq_var else "Welch's t-test")
            _, p = mannwhitneyu(*valid, alternative="two-sided")
            return p, "Mann-Whitney U"
        if is_normal:
            _, p = f_oneway(*valid); return p, "ANOVA"
        _, p = kruskal(*valid); return p, "Kruskal-Wallis"

    def _calculate_pvalue_categorical(self, df, var, group_cols, resolved_test, paired=False):
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
            return np.nan, "McNemar (N/A for >2×2)"

        if resolved_test == "chi2":
            _, p, _, _ = chi2_contingency(ct); return p, "Chi-Squared"
        if resolved_test == "fisher":
            if ct.shape == (2, 2):
                _, p = fisher_exact(ct); return p, "Fisher Exact"
            _, p, _, _ = chi2_contingency(ct)
            return p, "Chi-Squared (Fisher N/A >2×2)"

        # auto: expected-cell rule
        if ct.shape == (2, 2):
            _, p_chi, _, expected = chi2_contingency(ct)
            if expected.min() < 5 or (expected < 1).any():
                _, p = fisher_exact(ct); return p, "Fisher Exact"
            return p_chi, "Chi-Squared"
        _, p, _, _ = chi2_contingency(ct); return p, "Chi-Squared"

    # =========================================================================
    # SMD
    # =========================================================================

    def _compute_smd_numeric(self, g1, g2):
        g1, g2 = g1.dropna(), g2.dropna()
        if len(g1) < 2 or len(g2) < 2:
            return ""
        pooled_sd = np.sqrt((g1.var(ddof=1) + g2.var(ddof=1)) / 2.0)
        return "" if pooled_sd == 0 else f"{abs(g1.mean()-g2.mean())/pooled_sd:.2f}"

    def _compute_smd_binary(self, p1, p2):
        p_avg = (p1 + p2) / 2.0
        denom = np.sqrt(p_avg * (1.0 - p_avg)) if 0.0 < p_avg < 1.0 else 0.0
        return "" if denom == 0 else f"{abs(p1-p2)/denom:.2f}"

    # =========================================================================
    # Formatting helpers
    # =========================================================================

    def _calc_overall_header(self, df, var):
        n_total = len(df)
        n_valid = int(df[var].count())
        pct     = (n_valid / n_total * 100) if n_total > 0 else 0.0
        mode    = self.config.total_mode
        if mode == "n":          return str(n_total)
        if mode == "n_valid":    return str(n_valid)
        return f"{n_valid} ({pct:.1f}%)"

    def _format_numeric_stats(self, data, metric):
        data = data.dropna()
        if len(data) == 0:
            return self.config.missing_value_symbol
        d = self.config.decimals
        if metric == "mean_sd":
            return f"{data.mean():.{d}f} ({data.std():.{d}f})"
        med = data.median()
        return f"{med:.{d}f} [{data.quantile(.25):.{d}f}–{data.quantile(.75):.{d}f}]"

    def _compute_stat(self, data, formula):
        data = data.dropna()
        if len(data) == 0:
            return self.config.missing_value_symbol
        d      = self.config.decimals
        result = formula.strip()
        for num in set(re.findall(r"p(\d+)", result)):
            val    = data.quantile(int(num) / 100)
            result = re.sub(rf"\bp{num}\b", f"{val:.{d}f}", result)
        for key, func in [("mean", lambda s: s.mean()),
                          ("std",  lambda s: s.std()),
                          ("var",  lambda s: s.var()),
                          ("median", lambda s: s.median())]:
            if re.search(rf"\b{key}\b", result):
                result = re.sub(rf"\b{key}\b", f"{func(data):.{d}f}", result)
        return result

    def _format_p(self, p):
        if pd.isna(p):   return ""
        if p < 0.001:    return "<0.001"
        return f"{p:.{self.config.p_decimals}f}"

    def _indent(self, text):
        return (self.config.indent_char + " " * self.config.indent_width) + text

    def _normalize_rows(self, rows, target_len):
        return [(r + [""] * (target_len - len(r)))[:target_len] for r in rows]

    @staticmethod
    def _flatten_multiindex_columns(df):
        out = df.copy()
        if isinstance(out.columns, pd.MultiIndex):
            out.columns = [
                "\n".join(str(c) for c in col
                          if c and str(c).strip() not in ("", " "))
                for col in out.columns.values
            ]
        return out
