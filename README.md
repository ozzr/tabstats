# tabstat

**Publication-ready Table 1 for clinical and epidemiological research.**

`tabstat` automates the standard descriptive statistics table found in most clinical papers — the one that characterises your cohort and tests for group differences. It handles variable detection, test selection, formatting, and export in a single function call.

📖 Full reference, configuration, and examples: [project wiki](https://github.com/ozzr/tabstats/wiki) (generated from [`docs/`](docs/)).

---

## Features

| Feature | Detail |
|---|---|
| Formula syntax | `"var1 + var2 \| group"` · `"~ . \| group"` · `"~ . - VAR1"` |
| Auto test selection | Shapiro-Wilk / D'Agostino / moment-based normality → t-test, Welch, Mann-Whitney U, ANOVA, Kruskal-Wallis, Fisher, Chi-squared, McNemar |
| Multi-level grouping | `"age + sex \| site + outcome"` — nested group headers |
| Output formats | DataFrame · grid text · markdown · LaTeX · HTML · Excel · Word (DOCX) |
| Custom continuous stats | `"Median [IQR] = median [p25, p75]"` template DSL |
| Multiple testing correction | Bonferroni · Benjamini-Hochberg FDR |
| Section headers | Group variables under labelled sections |
| SMD | Standardised Mean Difference (2-group) |
| Wilson CI | 95% (or custom level) confidence intervals for proportions |
| Categorical format | `n_pct` · `pct_only` · `n_only` · `n_total_pct` — global or per-variable |
| Binary collapse | Single row for dichotomous variables |
| Per-variable overrides | Paired tests, test type, render format, footnote markers |
| Data quality | Tukey outlier detection · Hartigan Dip Test for multimodality |
| Missing data | `display_missing=True` adds a Missing sub-row per variable |
| Meta-column titles | Rename Characteristic/Total/P-value/Test/SMD headers (e.g. for non-English tables) |
| Publication-style Excel | `publication_style=True` — three-line academic look, footnote kept outside the table |

---

## Installation

Requires Python 3.9+.

```bash
pip install tabstat
```

Or from source:

```bash
git clone https://github.com/ozzr/tabstats
cd tabstats
pip install -e .
```

Optional extras:

```bash
pip install openpyxl      # Excel export
pip install python-docx   # Word (.docx) export
pip install diptest        # Hartigan Dip Test for multimodality
```

---

## Quick start

```python
import pandas as pd
from tabstat import tabstat

# Any DataFrame — each row is one subject
t = tabstat(df, "age + sex + creatinine | outcome")
```

This prints a formatted grid table and returns a DataFrame. That's it.

### Selecting variables

```python
# Explicit list
tabstat(df, "age + sex + creatinine | outcome")

# All columns except the group variable
tabstat(df, "~ . | outcome")

# All columns, exclude specific ones
tabstat(df, "~ . - patient_id - date | outcome")

# No grouping (overall summary only)
tabstat(df, "age + sex + creatinine")
```

### Output formats

```python
# Default: returns DataFrame, no printing
t = tabstat(df, "age + sex | outcome", tablefmt="df")

# Grid text (prints + returns DataFrame)
t = tabstat(df, "age + sex | outcome", tablefmt="grid")

# Markdown
t = tabstat(df, "age + sex | outcome", tablefmt="markdown")

# LaTeX
t = tabstat(df, "age + sex | outcome", tablefmt="latex")

# HTML string
html = tabstat(df, "age + sex | outcome", tablefmt="html")

# Suppress printing (text formats only)
t = tabstat(df, "age + sex | outcome", tablefmt="grid", show=False)
```

---

## Examples

### Multi-level grouping

```python
# Two grouping variables → nested headers
t = tabstat(df, "age + sex + creatinine | site + outcome")
```

### Custom column labels

```python
t = tabstat(
    df,
    "age_months + sex + creatinine | outcome",
    column_labels={
        "age_months":  "Age (months)",
        "creatinine":  "Creatinine (mg/dL)",
        "outcome":     "Outcome",
        0:             "Survivor",
        1:             "Non-survivor",
    },
)
```

### Custom meta-column titles

`column_labels` renames *variables* and group values. To rename the fixed
structural columns (Characteristic, Total, P-value, Test, SMD) — e.g. for a
table in Spanish — use `column_titles` instead:

```python
t = tabstat(
    df,
    "age + sex | outcome",
    column_titles={
        "characteristic": "Característica",
        "total":          "Total",
        "p_value":        "Valor p",
        "test":           "Prueba",
        "smd":            "DME",
    },
)
```

### Test overrides

```python
from tabstat import tabstat, TestOverrideConfig

# Named preset — non-parametric for all numeric
t = tabstat(df, "age + creatinine | outcome",
            test_overrides="conservative")

# Fine-grained override
overrides = TestOverrideConfig(
    per_variable={"creatinine": "mannwhitneyu"},
    per_group={"outcome": "never_parametric"},
    per_type={"categorical": "auto"},
    default="auto",
)
t = tabstat(df, "age + sex + creatinine | outcome",
            test_overrides=overrides)
```

Available presets: `"clinical_descriptive"`, `"conservative"`, `"parametric"`.

### Custom continuous statistics

```python
t = tabstat(
    df,
    "age + creatinine + platelets | outcome",
    render_continuous={
        "creatinine": ["Median [IQR] = median [p25, p75]"],
        "__default__": [
            "Median [IQR] = median [p25, p75]",
            "Mean (SD)    = mean (± std)",
        ],
    },
)
```

Supported tokens: `mean`, `std`, `var`, `median`, `min`, `max`, `n`, `p{N}` (e.g. `p25`, `p75`).

### Multiple testing correction

```python
# Bonferroni
t = tabstat(df, "~ . | outcome", correction="bonferroni")

# Benjamini-Hochberg FDR
t = tabstat(df, "~ . | outcome", correction="fdr_bh")
```

### Wilson confidence intervals for proportions

```python
t = tabstat(
    df,
    "sex + jaundice + hemorrhage | outcome",
    show_proportion_ci=True,
    ci_level=0.95,
)
# Cells show: "12 (40.0%) [23.4%–58.9%]"
```

### Section headers

```python
t = tabstat(
    df,
    "age + sex + weight + creatinine + platelets + alt | outcome",
    sections={
        "Demographics":    ["age", "sex", "weight"],
        "Laboratory":      ["creatinine", "platelets", "alt"],
    },
)
```

### Footnote markers

```python
t = tabstat(
    df,
    "age + creatinine + platelets | outcome",
    var_footnotes={"creatinine": "*", "platelets": "†"},
    footnote="* Winsorised at 99th percentile. † log-transformed for testing.",
)
```

### Categorical format

```python
# Show only percentages
t = tabstat(df, "sex + grade | outcome", categorical_fmt="pct_only")

# n/total (%)
t = tabstat(df, "sex + grade | outcome", categorical_fmt="n_total_pct")

# Per-variable override via render_config
t = tabstat(
    df,
    "sex + grade | outcome",
    render_config={"grade": "pct_only"},   # others use global default
)
```

### Binary variable collapse

```python
# Single row per binary variable instead of header + 2 category rows
t = tabstat(df, "sex + jaundice + hemorrhage | outcome",
            collapse_binary=True)
```

### Missing data

```python
t = tabstat(df, "~ . | outcome",
            display_missing=True)  # adds "Missing" sub-row for each variable
```

### NaN as explicit category

```python
# Treat NaN as "Unknown" category included in chi-square test
t = tabstat(df, "grade | outcome",
            include_nan_as_category=True,
            nan_category_label="Unknown")
```

### Normality method transparency

```python
# Append which normality test was used for each numeric variable
t = tabstat(df, "age + creatinine | outcome",
            show_normality_method=True)
```

### Per-variable paired tests

```python
# Apply paired tests to specific variables only
t = tabstat(df, "before + after + sex | group",
            paired_vars=["before", "after"])
```

### SMD (Standardised Mean Difference)

```python
t = tabstat(df, "age + sex + creatinine | outcome",
            display_smd=True)   # only meaningful with exactly 2 groups
```

---

## Exports

### HTML

```python
from tabstat import TabStatGenerator, TabStatConfig

gen = TabStatGenerator(TabStatConfig(display_missing=True))
df_result = gen.generate(df, "age + sex + creatinine | outcome",
                         output_format="df")

# Returns HTML string (also writes file if path given)
html = gen.to_html(df_result, path="table1.html",
                   title="Table 1. Cohort characteristics")
```

### Excel

```python
gen.to_excel(df_result, path="table1.xlsx",
             title="Table 1",
             footnote="IQR = interquartile range.")

# Multiple tables in one workbook
from tabstat import export_tables_to_excel

export_tables_to_excel(
    [("Table 1", t1), ("Table 2", t2)],
    output_path="report.xlsx",
)
```

#### Publication-style Excel (three-line / academic look)

Set `publication_style=True` to apply a white-background, no-gridlines,
bold-variable-label, thick/thin-rule look on top of the base export. The
footnote is kept *outside* the table — separated by a blank row, italic, with
the closing rule drawn under the last data row instead of under the footnote.

```python
gen.to_excel(df_result, path="table1.xlsx",
             title="Table 1. Cohort characteristics",
             footnote="IQR = interquartile range.",
             publication_style=True,
             bold_significant=True)   # bold the P-value cell when p < 0.05

# Multi-sheet workbook — pass the same column_titles used to build each table
# so the P-value/Test columns are still located correctly for merging.
export_tables_to_excel(
    [("Table 1", t1), ("Table 2", t2)],
    output_path="report.xlsx",
    column_titles={"p_value": "Valor p"},
    publication_style=True,
)
```

Column positions (group spanner, P-value, Test) are located by header text,
so this keeps working regardless of `split_count_pct`, group count, or
whether `display_test_name`/`display_smd` are enabled.

### Word (DOCX)

```python
gen.to_docx(df_result, path="table1.docx",
            title="Table 1. Cohort characteristics",
            footnote="IQR = interquartile range.")
```

---

## Configuration reference

All options can be passed directly to `tabstat()` as keyword arguments, or bundled in a `TabStatConfig` object.

```python
from tabstat import TabStatConfig, TabStatGenerator

cfg = TabStatConfig(
    # Formatting
    decimals             = 1,       # decimal places for statistics
    p_decimals           = 3,       # decimal places for p-values

    # Columns
    display_overall      = True,    # show Total column
    overall_position     = "last",  # "first" | "last"
    display_p_values     = True,
    display_test_name    = True,
    display_smd          = False,
    display_missing      = True,

    # Total column mode
    total_mode           = "n_valid_percent",  # "n" | "n_valid" | "n_valid_percent"

    # Percentage denominator
    pct_denominator      = "group",  # "group" | "total" | "parent_group"

    # Categorical format
    categorical_fmt      = "n_pct",  # "n_pct" | "pct_only" | "n_only" | "n_total_pct"

    # Confidence intervals
    show_proportion_ci   = False,
    ci_level             = 0.95,

    # Split n and % into separate columns (SPSS style)
    split_count_pct      = False,

    # Binary variables
    collapse_binary       = False,
    collapse_binary_level = "last",  # "first" | "last"

    # Multiple testing correction
    correction           = "none",   # "none" | "bonferroni" | "fdr_bh"

    # Per-variable overrides
    render_config        = {},       # e.g. {"age": "mean_sd", "grade": "pct_only"}
    render_continuous    = [],       # List[str] or Dict[str, List[str]]
    var_footnotes        = {},       # {"var": "symbol"}
    paired_vars          = [],       # variable names always using paired tests

    # NaN handling
    include_nan_as_category = False,
    nan_category_label      = "Unknown",

    # Section headers
    sections             = None,    # {"Section label": ["var1", "var2"]}

    # Meta-column title overrides (not variable labels — use column_labels for those)
    column_titles        = {},      # {"characteristic": "...", "total": "...",
                                     #  "p_value": "...", "test": "...", "smd": "..."}

    # Normality transparency
    show_normality_method = False,

    # Data quality checks
    check_outliers       = False,
    check_multimodal     = False,

    # Statistical test overrides
    test_overrides       = TestOverrideConfig(),
)

gen = TabStatGenerator(cfg)
```

---

## Test override hierarchy

Priority (highest → lowest):

| Level | Key | Example |
|---|---|---|
| 1. per_variable | variable name | `{"creatinine": "mannwhitneyu"}` |
| 2. per_group | grouping column | `{"outcome": "never_parametric"}` |
| 3. per_type | `"numeric"` / `"categorical"` | `{"numeric": "auto"}` |
| 4. default | — | `"auto"` |

Valid test tokens:

| Type | Tokens |
|---|---|
| Numeric | `auto` · `mannwhitneyu` · `ttest` · `welch` · `kruskal` · `anova` · `never_parametric` · `always_parametric` |
| Categorical | `auto` · `chi2` · `fisher` |

---

## Package layout

```
tabstat/
  __init__.py      tabstat() convenience function, export_tables_to_excel()
  config.py        TabStatConfig, TestOverrideConfig
  generator.py     TabStatGenerator — core analysis pipeline
  normality.py     NormalitySelector — automatic normality test selection
  resolver.py      TestResolver — hierarchical test override resolution
  rendering.py     Canvas-based text table renderer
  exports.py       to_html_str(), to_excel_file(), to_docx_file(),
                   apply_publication_style()
```

---

## Running tests

```bash
pip install pytest
pytest tests/ -v
```

---

## License

MIT. See [LICENSE](LICENSE).
