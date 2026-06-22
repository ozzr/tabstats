# Configuration Reference

All fields of `TabStatConfig`, organised by category.  
Every field can be passed directly to `tabstat()` as a keyword argument.

```python
from tabstat import tabstat, TabStatConfig, TabStatGenerator

# Option A — keyword arguments
t = tabstat(df, formula, decimals=2, display_smd=True)

# Option B — config object (preferred when reusing across multiple tables)
cfg = TabStatConfig(decimals=2, display_smd=True)
gen = TabStatGenerator(cfg)
t   = gen.generate(df, formula)
```

---

## Numeric formatting

| Field | Type | Default | Description |
|---|---|---|---|
| `decimals` | `int` | `1` | Decimal places for statistics (means, medians, percentages). |
| `p_decimals` | `int` | `3` | Decimal places for p-values. Values < 0.001 are shown as `<0.001`. |

---

## Display toggles

| Field | Type | Default | Description |
|---|---|---|---|
| `display_overall` | `bool` | `True` | Show a Total column aggregating all subjects. |
| `overall_position` | `str` | `"last"` | Position of Total column: `"first"` or `"last"`. |
| `display_p_values` | `bool` | `True` | Show P-value column. |
| `display_test_name` | `bool` | `True` | Show Test column (e.g. "Mann-Whitney U"). |
| `display_smd` | `bool` | `False` | Show Standardised Mean Difference column. Only meaningful with exactly 2 groups; emits a warning otherwise. |
| `display_missing` | `bool` | `True` | Add a "Missing" sub-row per variable showing the count and percentage of missing values. |

---

## Total column mode

Controls how the Total column header value is computed.

| Field | Type | Default | Description |
|---|---|---|---|
| `total_mode` | `str` | `"n_valid_percent"` | See values below. |

| Value | Output example |
|---|---|
| `"n"` | Raw total N: `"120"` |
| `"n_valid"` | Non-missing N: `"114"` |
| `"n_valid_percent"` | Non-missing N and %: `"114 (95.0%)"` |

---

## Percentage denominator

Controls what denominator is used for categorical cell percentages.

| Field | Type | Default | Description |
|---|---|---|---|
| `pct_denominator` | `str` | `"group"` | See values below. |

| Value | Behaviour |
|---|---|
| `"group"` | % of the column's non-missing total (standard). |
| `"total"` | % of the grand total N across all subjects. |
| `"parent_group"` | For ≥2 grouping variables: % within the first-level group. Falls back to `"group"` for single grouping. |

---

## Categorical cell format

| Field | Type | Default | Description |
|---|---|---|---|
| `categorical_fmt` | `str` | `"n_pct"` | Global format for all categorical cells. |

| Value | Cell example |
|---|---|
| `"n_pct"` | `5 (25.0%)` |
| `"pct_only"` | `25.0%` |
| `"n_only"` | `5` |
| `"n_total_pct"` | `5/20 (25.0%)` |

Per-variable overrides: add the value to `render_config`:

```python
tabstat(df, formula, render_config={"grade": "pct_only"})
```

---

## Proportion confidence intervals

Wilson score CI appended to each categorical cell value.

| Field | Type | Default | Description |
|---|---|---|---|
| `show_proportion_ci` | `bool` | `False` | Append Wilson CI to categorical cells. Ignored when `split_count_pct=True`. |
| `ci_level` | `float` | `0.95` | Confidence level (e.g. `0.95` → 95% CI). |

When enabled, cells show: `5 (25.0%) [12.7%–43.5%]`

---

## Split count / percentage columns

| Field | Type | Default | Description |
|---|---|---|---|
| `split_count_pct` | `bool` | `False` | Split categorical n and % into separate sub-columns per group (SPSS-style). Produces a 3-level MultiIndex in the DataFrame output. |

---

## Binary variable collapsing

| Field | Type | Default | Description |
|---|---|---|---|
| `collapse_binary` | `bool` | `False` | Condense binary variables to a single row instead of header + two category rows. |
| `collapse_binary_level` | `str` | `"last"` | Which category to display: `"first"` or `"last"` (after natural sort). |

---

## Custom continuous statistics

| Field | Type | Default | Description |
|---|---|---|---|
| `render_config` | `dict` | `{}` | Override render type per variable. |
| `render_continuous` | `list` or `dict` | `[]` | Custom statistic templates for numeric variables. |

### `render_config` values

| Value | Behaviour |
|---|---|
| `"mean_sd"` | Force numeric rendering as Mean (SD) |
| `"median_iqr"` | Force numeric rendering as Median [IQR] |
| `"n_percent"` / `"n_pct"` | Force categorical rendering |
| `"pct_only"` · `"n_only"` · `"n_total_pct"` | Force categorical with specific format |

Special key `"default_numeric"` sets the fallback format for all numeric variables:

```python
render_config={"default_numeric": "mean_sd"}
```

### `render_continuous` templates

Each template string has the form: `"Label = formula"`

```python
render_continuous = [
    "Median [IQR] = median [p25, p75]",
    "Mean (SD)    = mean (± std)",
    "Range        = min – max",
    "N valid      = n",
]
```

**Supported tokens:** `mean`, `std`, `var`, `median`, `min`, `max`, `n`, `p{N}` (e.g. `p25`, `p05`).

Per-variable specs (use `"__default__"` as fallback):

```python
render_continuous = {
    "creatinine":  ["Median [IQR] = median [p25, p75]"],
    "__default__": ["Median [IQR] = median [p25, p75]", "Mean (SD) = mean (± std)"],
}
```

---

## Render type override

Force a variable to be treated as numeric or categorical:

```python
# Integer column with many values → force to numeric
render_config={"score": "median_iqr"}

# Numeric column with few unique values → already auto-detected as categorical
# (integer columns with ≤5 unique values are automatically treated as categorical)
```

---

## Multiple testing correction

| Field | Type | Default | Description |
|---|---|---|---|
| `correction` | `str` | `"none"` | Correction method applied to all p-values. |

| Value | Method |
|---|---|
| `"none"` | No correction |
| `"bonferroni"` | Bonferroni (multiply each p by number of tests, cap at 1) |
| `"fdr_bh"` | Benjamini-Hochberg FDR (requires `scipy >= 1.11` or `statsmodels`) |

When correction is applied, a note is automatically appended to the table footnote.

---

## Per-variable footnote markers

| Field | Type | Default | Description |
|---|---|---|---|
| `var_footnotes` | `dict` | `{}` | Maps variable name → marker symbol appended to the variable's label row. |

```python
tabstat(
    df, formula,
    var_footnotes={"creatinine": "*", "platelets": "†"},
    footnote="* Winsorised at 99th percentile.\n† Log-transformed for analysis.",
)
```

---

## Per-variable paired tests

| Field | Type | Default | Description |
|---|---|---|---|
| `paired_vars` | `list[str]` | `[]` | Variable names that always use paired tests regardless of the global `paired` argument. |

---

## Normality method transparency

| Field | Type | Default | Description |
|---|---|---|---|
| `show_normality_method` | `bool` | `False` | Append a footnote describing which normality test was used for each numeric variable. |

---

## NaN as explicit category

| Field | Type | Default | Description |
|---|---|---|---|
| `include_nan_as_category` | `bool` | `False` | Treat NaN as an explicit category (labelled by `nan_category_label`) included in proportions and statistical tests. |
| `nan_category_label` | `str` | `"Unknown"` | Label to use for the NaN category. |

Note: when both `include_nan_as_category=True` and `display_missing=True`, the Missing sub-row will show 0. A warning is emitted.

---

## Section headers

| Field | Type | Default | Description |
|---|---|---|---|
| `sections` | `dict` or `None` | `None` | Group variables under labelled section headers. |

```python
sections = {
    "Demographics":  ["age", "sex", "weight"],
    "Vital signs":   ["sbp", "dbp", "heart_rate"],
    "Laboratory":    ["creatinine", "platelets", "alt", "bilirubin"],
}
```

Only applies when variables are explicitly listed in the formula (not `~ .`).
Variables not listed in any section are rendered ungrouped.

---

## Data quality checks

| Field | Type | Default | Description |
|---|---|---|---|
| `check_outliers` | `bool` | `False` | Tukey far-outlier detection (1.5 × IQR from fences). Variables with outliers are listed in the footnote. |
| `check_multimodal` | `bool` | `False` | Hartigan Dip Test for multimodality (requires `diptest` package). Variables with p < 0.05 are noted. |

---

## Statistical test overrides

| Field | Type | Default | Description |
|---|---|---|---|
| `test_overrides` | `TestOverrideConfig` | `TestOverrideConfig()` | Hierarchical test selection overrides. Can also be a preset string. |

```python
# Preset string shorthand
tabstat(df, formula, test_overrides="clinical_descriptive")

# Full object
from tabstat import TestOverrideConfig
tabstat(df, formula,
        test_overrides=TestOverrideConfig(
            per_variable={"creatinine": "mannwhitneyu"},
            default="auto",
        ))
```

---

## Symbols and indentation

| Field | Type | Default | Description |
|---|---|---|---|
| `missing_value_symbol` | `str` | `"NA"` | Displayed when a group has zero valid values. |
| `indent_char` | `str` | `"⠀"` | Character used for indentation (Braille blank — visually safe). |
| `indent_width` | `int` | `3` | Number of indent characters before category labels. |

---

## Meta-column title overrides

Rename the fixed structural column headers — not variable labels (use
`column_labels` passed to `tabstat()` for those).

| Field | Type | Default | Description |
|---|---|---|---|
| `column_titles` | `dict` | `{}` | Maps a header key to its display text. Unset keys keep the English default. |

Recognised keys: `characteristic`, `total`, `p_value`, `test`, `smd`.

```python
tabstat(
    df, formula,
    column_titles={
        "characteristic": "Característica",
        "total":          "Total",
        "p_value":        "Valor p",
        "test":           "Prueba",
        "smd":            "DME",
    },
)
```

When exporting to Excel with `publication_style=True` (or calling
`apply_publication_style()` directly), pass the same label strings as
`p_value_label`/`test_label`/etc. — they're how the styling pass locates those
columns. `export_tables_to_excel()` and `gen.to_excel()` / `gen.to_excel_workbook()`
do this automatically when given the same `column_titles`.
