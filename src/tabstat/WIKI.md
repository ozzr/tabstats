# tabstat — Developer Wiki

## Architecture

```
tabstat/
├── __init__.py       Public API: tabstat() convenience function
├── config.py         TabStatConfig, TestOverrideConfig dataclasses
├── normality.py      NormalitySelector — adaptive normality testing
├── resolver.py       TestResolver — 4-level hierarchical test override
├── generator.py      TabStatGenerator — core analysis engine
├── rendering.py      render_text_table — text/grid rendering, p-value spanning
└── exports.py        to_html_str, to_excel_file
```

---

## Data flow

```
tabstat()
  └─ TabStatGenerator.generate()
       └─ _run_analysis()              ← analysis runs ONCE
            ├─ _parse_formula()
            ├─ _validate_dataframe()
            ├─ _get_groups()
            ├─ _compute_group_counts()
            ├─ for each variable:
            │    ├─ _get_render_type()
            │    ├─ _summarize_numeric()   → (rows, metas)
            │    └─ _summarize_categorical() → (rows, metas)
            └─ _build_columns()
       
       Then branches by output_format:
       ├─ 'df'   → _attach_title_footnote(result_df)
       ├─ 'html' → exports.to_html_str()
       └─ text   → _get_pvalue_injections(metas)
                   → rendering.render_text_table()
                   → _attach_title_footnote(result_df)
```

---

## Row metadata (`RowMeta` dicts)

Every row produced by `_summarize_*` comes with a parallel metadata dict:

```python
{
    "kind":         "var_header" | "stat" | "category" | "missing",
    "var":          str,                    # variable name
    "pvalue_span":  None | (p_str, test_str, cat_offset, n_cats),
}
```

`cat_offset` starts as a **relative** offset (rows from this header to first
category row in the local list, always 1).  `_run_analysis()` converts it to
an **absolute** index in the full flat DataFrame before passing to
`_get_pvalue_injections()`.

---

## P-value spanning for categoricals

The SPSS-style spanning is implemented in two parts:

### 1. Generator (`generator.py`)

`_summarize_categorical()` sets `pvalue_span` on the `var_header` meta:

```python
span = (p_str, test_name, cat_offset=1, n_cats=len(categories))
```

Category rows have **empty** p-value/test cells.

`_get_pvalue_injections(row_metas)` converts spans to:

```python
[(k, p_str, test_str), ...]
# k = cat_start_abs + (n_cats - 1) // 2
# separator AFTER row k gets the injection
```

### 2. Renderer (`rendering.py`)

`render_text_table()` calls tabulate with blank headers, finds the `===`
separator, then injects p-values **before** building the nested header:

```python
sep_line_idx = header_sep_idx + 2 + k * 2
lines[sep_line_idx] = _inject_pvalue_into_separator(lines[sep_line_idx], ...)
```

`_inject_pvalue_into_separator()` splits the separator on `+`, replaces
the dash segments at `p_idx` and `test_idx` with centered text:

```
Before: +-------+-------+-------+
After:  +-------+-------+ 0.023 + Chi-Squared +
```

---

## Column layout (`ColLayout`)

`build_col_layout()` mirrors `_build_columns()` exactly.  Both must be
updated together if the column ordering changes.

```
col index → role
─────────────────────────────────────────────────────
0           Characteristic (always)
1           Total (if display_overall and position='first')
1..N        Group columns (one per unique group key)
N+1         Total (if display_overall and position='last')
N+2         P-value (if display_p_values)
N+3         Test    (if display_test_name)
N+4         SMD     (if display_smd)
```

`ColLayout` stores these as named integer attributes (`p_idx`, `test_idx`,
`smd_idx`, etc.) and is shared between `generator.py` and `rendering.py`.

---

## Normality selection (`normality.py`)

| n | Method |
|---|---|
| < 3 | Non-normal assumed |
| 3–49 | Shapiro-Wilk (highest power small n) |
| 50–4999 | D'Agostino-Pearson (scipy `normaltest`) |
| ≥ 5000 | Moment-based: `|skew| < 2` and `|kurt| < 7` |

Configure thresholds:

```python
from tabstat.normality import NormalitySelector
sel = NormalitySelector(alpha=0.05, skew_threshold=2.0, kurt_threshold=7.0)
```

---

## Test resolver (`resolver.py`)

4-level hierarchy, first match wins:

```
per_variable → per_group → per_type → default
```

Valid tokens:

- **Numeric:** `auto` | `mannwhitneyu` | `ttest` | `welch` | `kruskal` | `anova` | `never_parametric` | `always_parametric`
- **Categorical:** `auto` | `chi2` | `fisher`

---

## Percentage denominator (`pct_denominator`)

Implemented in `_get_cat_denom()` in `generator.py`.

For `parent_group`, `_summarize_categorical()` pre-computes `parent_counts`
by summing non-missing values of the variable across all rows sharing the
same first-level group key:

```python
parent_mask = df[group_cols[0]] == parent_key
parent_counts[g] = int(df.loc[parent_mask, var].count())
```

The overall column always uses total non-missing N regardless of mode.

---

## Export formats (`exports.py`)

### HTML

`to_html_str(df, title, footnote)` produces a self-contained HTML document
with inline CSS — compatible with Word paste-in.

### Excel

`to_excel_file(df, path, title)` requires `openpyxl`.  Features:
- Title row (row 1, bold, merged)
- Header rows (dark background, white text)
- Alternating row fill
- Auto-fitted column widths (max 42 chars)
- Frozen top rows

---

## Extending tabstat

### Adding a new test token

1. Add the token to `TestOverrideConfig` docstring in `config.py`
2. Add a branch in `_calculate_pvalue_numeric()` or `_calculate_pvalue_categorical()` in `generator.py`
3. Update `README.md`

### Adding a new render stat

The `render_continuous` system parses `"Label = formula"` strings.
To add a new keyword (e.g. `range`), extend the `keywords` dict in
`_compute_stat()`:

```python
keywords = {
    "mean":   lambda d: d.mean(),
    "std":    lambda d: d.std(),
    "var":    lambda d: d.var(),
    "median": lambda d: d.median(),
    "range":  lambda d: d.max() - d.min(),   # new
}
```

### Adding a new output format

1. Add a branch in `generate()` in `generator.py`
2. Expose via `tabstat()` in `__init__.py`

---

## Design decisions

| Decision | Rationale |
|---|---|
| Analysis runs once | Avoids duplicated computation in the old wrapper |
| `df.attrs` NOT used for title/footnote | Fragile (lost on copy/filter); rows in df are explicit |
| P-value in separator, not cell | Matches SPSS/Word table conventions for readability |
| `NormalitySelector` as separate class | Testable independently, swappable |
| `TestResolver` as separate class | Clean separation of resolution logic from stats logic |
| `ColLayout` shared between generator and renderer | Guarantees column index consistency |
| `FutureWarning` fix: `observed=True` | pandas ≥ 2.0 default; explicit is always better |
