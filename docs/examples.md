# Examples Gallery

Runnable examples covering every major feature. All use the same synthetic clinical dataset.

---

## Synthetic dataset

```python
import numpy as np
import pandas as pd

np.random.seed(42)
N = 160

outcome = np.random.choice([0, 1], size=N, p=[0.68, 0.32])
site    = np.random.choice(["Site A", "Site B"], size=N)

df = pd.DataFrame({
    # Demographics
    "age_months": np.random.randint(6, 180, N),
    "sex":        np.random.choice(["Male", "Female"], N),
    "weight_kg":  np.round(np.random.normal(18, 8, N).clip(5, 60), 1),

    # Labs
    "creatinine": np.where(
        outcome == 1,
        np.random.lognormal(0.8, 0.6, N),
        np.random.lognormal(0.2, 0.4, N),
    ).round(2),
    "platelets": np.where(
        outcome == 1,
        np.random.normal(60, 30, N).clip(5, 200),
        np.random.normal(180, 60, N).clip(50, 450),
    ).round(0),
    "ldh":       np.random.lognormal(6.5, 0.5, N).round(0),
    "alt":       np.random.lognormal(3.8, 0.8, N).round(1),

    # Categorical
    "jaundice":   np.random.choice([0, 1], N, p=[0.65, 0.35]),
    "hemorrhage": np.random.choice([0, 1], N, p=[0.80, 0.20]),
    "grade":      np.random.choice(["Mild", "Moderate", "Severe"], N, p=[0.4, 0.35, 0.25]),

    # Grouping
    "site":    site,
    "outcome": outcome,
})

# Introduce ~8% missing values in labs
for col in ["creatinine", "platelets", "ldh"]:
    mask = np.random.rand(N) < 0.08
    df.loc[mask, col] = np.nan
```

---

## Basic table

```python
from tabstat import tabstat

t = tabstat(df, "age_months + sex + creatinine + platelets | outcome")
```

Prints a formatted grid and returns a DataFrame. Both happen by default.

---

## Output formats

```python
# DataFrame only (no printing)
t = tabstat(df, "age_months + sex | outcome", tablefmt="df")

# Grid text
t = tabstat(df, "age_months + sex | outcome", tablefmt="grid")

# Markdown
t = tabstat(df, "age_months + sex | outcome", tablefmt="markdown")

# LaTeX
t = tabstat(df, "age_months + sex | outcome", tablefmt="latex")

# HTML string
html = tabstat(df, "age_months + sex | outcome", tablefmt="html")

# Suppress printing
t = tabstat(df, "age_months + sex | outcome", tablefmt="grid", show=False)
```

---

## Formula syntax

```python
# All columns except outcome
tabstat(df, "~ . | outcome")

# All columns, exclude specific ones
tabstat(df, "~ . - site - grade | outcome")

# No grouping (overall summary only)
tabstat(df, "age_months + sex + creatinine")

# Multi-level grouping
tabstat(df, "age_months + sex + creatinine | site + outcome")
```

---

## Column labels

```python
t = tabstat(
    df,
    "age_months + sex + creatinine + jaundice | outcome",
    column_labels={
        "age_months":  "Age (months)",
        "creatinine":  "Creatinine (mg/dL)",
        "jaundice":    "Jaundice, n (%)",
        "outcome":     "Outcome",
        0:             "Survivor",
        1:             "Non-survivor",
    },
)
```

Keys can be strings, integers, or booleans — they are matched against both the raw value and its `str()` equivalent.

---

## Meta-column titles (non-English tables)

```python
# Rename Characteristic/Total/P-value/Test/SMD — column_labels still
# handles variable names and group values separately.
t = tabstat(
    df,
    "age_months + sex | outcome",
    column_titles={
        "characteristic": "Característica",
        "p_value":        "Valor p",
        "test":           "Prueba",
    },
)
```

---

## Missing data

```python
# Show a Missing sub-row for every variable
t = tabstat(df, "~ . | outcome", display_missing=True)
```

---

## Section headers

Groups variables under labelled section dividers.

```python
t = tabstat(
    df,
    "age_months + sex + weight_kg + creatinine + platelets + alt + jaundice + hemorrhage | outcome",
    sections={
        "Demographics": ["age_months", "sex", "weight_kg"],
        "Laboratory":   ["creatinine", "platelets", "alt"],
        "Clinical":     ["jaundice", "hemorrhage"],
    },
)
```

Variables not listed in any section are rendered without a divider. Only works with an explicit variable list (not `~ .`).

---

## Test overrides

```python
from tabstat import tabstat, TestOverrideConfig

# Named preset — non-parametric for all numeric
t = tabstat(df, "age_months + creatinine | outcome",
            test_overrides="conservative")

# Fine-grained override
overrides = TestOverrideConfig(
    per_variable={"creatinine": "mannwhitneyu"},
    per_group={"outcome": "never_parametric"},
    per_type={"categorical": "chi2"},
    default="auto",
)
t = tabstat(df, "age_months + sex + creatinine | outcome",
            test_overrides=overrides)
```

Available presets: `"clinical_descriptive"`, `"conservative"`, `"parametric"`.

Priority: `per_variable` > `per_group` > `per_type` > `default`.

---

## Custom continuous statistics

```python
t = tabstat(
    df,
    "age_months + creatinine + platelets + ldh | outcome",
    render_continuous={
        "creatinine": ["Median [IQR] = median [p25, p75]"],
        "__default__": [
            "Median [IQR] = median [p25, p75]",
            "Mean (SD)    = mean (± std)",
            "Range        = min – max",
            "N valid      = n",
        ],
    },
)
```

Supported tokens: `mean`, `std`, `var`, `median`, `min`, `max`, `n`, `p{N}` (e.g. `p25`, `p75`, `p05`).

Use `"__default__"` as the fallback key for a dict spec. Passing a plain list applies the spec to all numeric variables.

---

## Multiple testing correction

```python
# Bonferroni
t = tabstat(df, "~ . | outcome", correction="bonferroni")

# Benjamini-Hochberg FDR
t = tabstat(df, "~ . | outcome", correction="fdr_bh")
```

A note is automatically appended to the footnote when correction is applied.

---

## Binary variable collapse

```python
# One row per binary variable instead of header + two category rows
t = tabstat(
    df,
    "sex + jaundice + hemorrhage | outcome",
    collapse_binary=True,
    collapse_binary_level="last",   # "first" | "last" (natural sort)
)
```

---

## Categorical cell format

```python
# Global format
t = tabstat(df, "sex + grade | outcome", categorical_fmt="pct_only")

# Available values:
#   "n_pct"       → 12 (40.0%)        [default]
#   "pct_only"    → 40.0%
#   "n_only"      → 12
#   "n_total_pct" → 12/30 (40.0%)

# Per-variable override
t = tabstat(
    df,
    "sex + grade | outcome",
    render_config={"grade": "pct_only"},   # others use global default
)
```

---

## Wilson confidence intervals for proportions

```python
t = tabstat(
    df,
    "sex + jaundice + hemorrhage | outcome",
    show_proportion_ci=True,
    ci_level=0.95,
)
# Cells show: "12 (40.0%) [23.4%–58.9%]"
```

Incompatible with `split_count_pct=True`.

---

## Split n / % columns (SPSS style)

```python
t = tabstat(
    df,
    "sex + grade | outcome",
    split_count_pct=True,
)
# Each group gets two sub-columns: n | %
# Produces a 3-level MultiIndex in the returned DataFrame.
```

---

## Percentage denominator

```python
# % of each column's non-missing total (default)
t = tabstat(df, "grade | site + outcome", pct_denominator="group")

# % of grand total across all subjects
t = tabstat(df, "grade | site + outcome", pct_denominator="total")

# % within first-level group (multi-level grouping only)
t = tabstat(df, "grade | site + outcome", pct_denominator="parent_group")
```

---

## Total column

```python
# Show Total N
t = tabstat(df, "age_months + sex | outcome", total_mode="n")

# Show non-missing N
t = tabstat(df, "age_months + sex | outcome", total_mode="n_valid")

# Show non-missing N (%) — default
t = tabstat(df, "age_months + sex | outcome", total_mode="n_valid_percent")

# Move Total to first column
t = tabstat(df, "age_months + sex | outcome", overall_position="first")

# Hide Total column
t = tabstat(df, "age_months + sex | outcome", display_overall=False)
```

---

## SMD (Standardised Mean Difference)

```python
t = tabstat(
    df,
    "age_months + sex + creatinine | outcome",
    display_smd=True,   # meaningful with exactly 2 groups
)
```

---

## Layout presets

A `Layout` controls which columns appear and how rows are assembled.
Pass a preset name or a `Layout` instance to `layout=`.

```python
from tabstat import tabstat, Layout

# "standard" — default behavior: metric sub-row for continuous,
#              n valid shown in Total column header
t = tabstat(df, "age_months + sex + creatinine | outcome", layout="standard")

# "no_cases" — dedicated N valid column; continuous stat on one inline row
t = tabstat(df, "age_months + sex + creatinine | outcome", layout="no_cases")

# "compact" — like standard but without the Test column
t = tabstat(df, "age_months + sex + creatinine | outcome", layout="compact")

# "full" — adds n_valid and SMD columns
t = tabstat(df, "age_months + sex + creatinine | outcome",
            layout="full", display_smd=True)
```

### Fluent builder

Start from any preset and strip or add columns:

```python
# no_cases without Test column
layout = Layout.from_preset("no_cases").without_column("test")
t = tabstat(df, "age_months + sex + creatinine | outcome", layout=layout)

# standard with SMD
layout = Layout.from_preset("standard").with_column("smd")
t = tabstat(df, "age_months + sex + creatinine | outcome",
            layout=layout, display_smd=True)

# chain multiple builder calls
layout = (
    Layout.from_preset("full")
    .without_column("test", "smd")
    .with_column("n_valid", after="char")
)
```

### Custom layout from scratch

Define exactly what each row looks like using the token vocabulary:

```python
layout = Layout(
    columns     = ["char", "n_valid", "group", "total", "p"],
    continuous  = [
        # one row: label + n_valid + group stats + total + p-value
        ["char", "n_valid", "group", "total", "p"],
    ],
    categorical = [
        # header row
        ["char",  "n_valid", "_",     "_",     "p"],
        # one row per category
        ["cat",   "_",       "group", "total", "_"],
    ],
)
t = tabstat(df, "age_months + sex + creatinine | outcome", layout=layout)
```

**Token vocabulary:** `_` · `char` · `n_valid` · `group` · `total` · `p` · `test` · `smd` · `metric` (repeats per metric spec) · `cat` (repeats per category) · `missing`

---

## Footnote markers

```python
t = tabstat(
    df,
    "age_months + creatinine + platelets | outcome",
    var_footnotes={"creatinine": "*", "platelets": "†"},
    footnote="* Winsorised at 99th percentile.\n† Log-transformed for testing.",
)
```

---

## Per-variable paired tests

```python
t = tabstat(
    df,
    "creatinine + platelets + sex | outcome",
    paired_vars=["creatinine", "platelets"],  # paired regardless of global `paired`
)
```

---

## Normality method transparency

```python
t = tabstat(
    df,
    "age_months + creatinine + ldh | outcome",
    show_normality_method=True,
)
# Appends footnote lines such as "age_months: D'Agostino-Pearson (p=0.03)"
```

---

## NaN as explicit category

```python
# Introduce some NaN in grade
import numpy as np
df_nan = df.copy()
df_nan.loc[np.random.rand(len(df_nan)) < 0.1, "grade"] = np.nan

t = tabstat(
    df_nan,
    "grade | outcome",
    include_nan_as_category=True,
    nan_category_label="Unknown",
)
```

Incompatible with `display_missing=True` — the Missing row shows 0 and a warning is emitted.

---

## Data quality checks

```python
# Tukey far-outlier detection (1.5 × IQR from fences)
t = tabstat(df, "creatinine + ldh | outcome", check_outliers=True)

# Hartigan Dip Test for multimodality (requires diptest package)
t = tabstat(df, "creatinine + ldh | outcome", check_multimodal=True)
```

Both append notes to the table footnote listing flagged variables.

---

## Multi-level grouping

```python
t = tabstat(
    df,
    "age_months + sex + creatinine | site + outcome",
    tablefmt="grid",
)
# Header row 1: Site A | Site B
# Header row 2: Survivor | Non-survivor | Survivor | Non-survivor
```

With `pct_denominator="parent_group"`, percentages are computed within each first-level group (site).

---

## TabStatGenerator — reuse config

```python
from tabstat import TabStatGenerator, TabStatConfig, TestOverrideConfig

cfg = TabStatConfig(
    display_missing  = True,
    collapse_binary  = True,
    test_overrides   = TestOverrideConfig.preset("clinical_descriptive"),
    sections={
        "Demographics": ["age_months", "sex", "weight_kg"],
        "Laboratory":   ["creatinine", "platelets", "alt"],
    },
)
gen = TabStatGenerator(cfg)

t1 = gen.generate(df_cohort_a, "age_months + sex + creatinine | outcome",
                  title="Table 1. Cohort A")
t2 = gen.generate(df_cohort_b, "age_months + sex + creatinine | outcome",
                  title="Table 1. Cohort B")
```

---

## Exports

### HTML

```python
from tabstat import TabStatGenerator, TabStatConfig

gen = TabStatGenerator(TabStatConfig(display_missing=True, collapse_binary=True))
df_result = gen.generate(df, "age_months + sex + creatinine | outcome", output_format="df")

html = gen.to_html(
    df_result,
    path     = "table1.html",
    title    = "Table 1. Cohort characteristics",
    footnote = "IQR = interquartile range.",
)
```

### Excel

```python
gen.to_excel(
    df_result,
    path     = "table1.xlsx",
    title    = "Table 1. Cohort characteristics",
    footnote = "IQR = interquartile range.",
)

# Multiple tables in one workbook
from tabstat import export_tables_to_excel

export_tables_to_excel(
    [("Table 1", t1), ("Table 2", t2)],
    output_path="report.xlsx",
)
```

### Excel — publication style (three-line look)

`publication_style=True` applies a white-background, no-gridlines, bold-variable-label
look with thick/thin rules at the header and table foot. The footnote is kept
*outside* the table — separated by a blank row, italic — and the closing rule is
drawn under the last data row, not under the footnote.

```python
gen.to_excel(
    df_result,
    path              = "table1.xlsx",
    title             = "Table 1. Cohort characteristics",
    footnote          = "IQR = interquartile range.",
    publication_style = True,
    bold_significant  = True,   # bold the P-value cell when p < 0.05
)

# Or apply it to an already-exported file / in-memory workbook directly:
from tabstat.exports import apply_publication_style
apply_publication_style("table1.xlsx", bold_significant=True)
```

Works regardless of `split_count_pct`, group count, or whether
`display_test_name`/`display_smd` are enabled — columns are located by header
text, not by a fixed position.

### Word (DOCX)

```python
gen.to_docx(
    df_result,
    path     = "table1.docx",
    title    = "Table 1. Cohort characteristics",
    footnote = "IQR = interquartile range.",
)
```

### LaTeX

```python
latex_str = gen.to_latex(df_result)
print(latex_str)
```

---

## Full featured example

```python
from tabstat import tabstat, TestOverrideConfig

t = tabstat(
    df,
    "age_months + sex + weight_kg + creatinine + platelets + ldh + alt + jaundice + hemorrhage + grade | outcome",
    tablefmt              = "grid",
    title                 = "Table 1. Patient characteristics by outcome",
    footnote              = "IQR = interquartile range. * Winsorised at 99th percentile.",

    # Formatting
    decimals              = 1,
    p_decimals            = 3,

    # Display
    display_smd           = True,
    display_missing       = True,
    collapse_binary       = True,
    display_test_name     = True,

    # Sections
    sections={
        "Demographics":  ["age_months", "sex", "weight_kg"],
        "Laboratory":    ["creatinine", "platelets", "ldh", "alt"],
        "Clinical":      ["jaundice", "hemorrhage", "grade"],
    },

    # Statistics
    test_overrides        = TestOverrideConfig.preset("clinical_descriptive"),
    correction            = "bonferroni",
    render_continuous={
        "creatinine": ["Median [IQR] = median [p25, p75]"],
        "__default__": [
            "Median [IQR] = median [p25, p75]",
            "Mean (SD)    = mean (± std)",
        ],
    },

    # Categorical
    categorical_fmt       = "n_pct",
    show_proportion_ci    = True,

    # Footnote markers
    var_footnotes         = {"creatinine": "*"},

    # Labels
    column_labels={
        "age_months":  "Age (months)",
        "weight_kg":   "Weight (kg)",
        "creatinine":  "Creatinine (mg/dL)*",
        "platelets":   "Platelets (×10³/µL)",
        "ldh":         "LDH (U/L)",
        "alt":         "ALT (U/L)",
        "jaundice":    "Jaundice",
        "hemorrhage":  "Hemorrhage",
        "outcome":     "Outcome",
        0:             "Survivor",
        1:             "Non-survivor",
    },
)
```
