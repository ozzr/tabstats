# API Reference

Complete reference for all public symbols in the `tabstat` package.

---

## `tabstat()` — convenience function

```python
from tabstat import tabstat

tabstat(
    df,
    formula,
    *,
    paired         = False,
    tablefmt       = "df",
    show           = True,
    column_labels  = None,
    title          = None,
    footnote       = None,
    **kwargs,          # any TabStatConfig field
) -> pd.DataFrame | str
```

Generate a publication-ready Table 1 in one call. Analysis runs exactly once; all
output formats derive from the same result object.

### Parameters

| Name | Type | Default | Description |
|---|---|---|---|
| `df` | `pd.DataFrame` | — | Source data. Each row is one subject. |
| `formula` | `str` | — | R-style formula (see below). |
| `paired` | `bool` | `False` | Use paired tests for all variables. See also `paired_vars`. |
| `tablefmt` | `str` | `"df"` | Output format: `"df"` · `"grid"` · `"markdown"` · `"latex"` · `"html"`. |
| `show` | `bool` | `True` | Print text output to stdout (text formats only). |
| `column_labels` | `dict` | `None` | Rename variables and/or group values. Keys can be strings, ints, or booleans. |
| `title` | `str` | `None` | Table title. For text: box above table. For `"df"`: prepended as a row when given. |
| `footnote` | `str` | `None` | Table footnote. For text: box below table. For `"df"`: appended as a row when given. |
| `**kwargs` | — | — | Any field of `TabStatConfig` (see configuration reference), including `column_titles` to rename the Characteristic/Total/P-value/Test/SMD headers. |

### Formula syntax

```
"var1 + var2 + var3 | group_col"     — explicit variable list, one grouping column
"var1 + var2 | group1 + group2"      — multi-level grouping
"~ . | group"                        — all columns except group
"~ . - id - date | group"            — all columns, exclude specific ones
"var1 + var2"                        — no grouping (overall summary only)
```

### Returns

- `pd.DataFrame` for `tablefmt="df"` (title/footnote prepended/appended as first-column rows if given)
- `str` for `tablefmt="html"`
- `pd.DataFrame` for text formats (printed if `show=True`; returned regardless)

### Example

```python
from tabstat import tabstat, TestOverrideConfig

t = tabstat(
    df,
    "age + sex + creatinine + jaundice | outcome",
    tablefmt        = "grid",
    title           = "Table 1. Patient characteristics",
    footnote        = "IQR = interquartile range.",
    display_smd     = True,
    display_missing = True,
    collapse_binary = True,
    correction      = "bonferroni",
    test_overrides  = TestOverrideConfig.preset("clinical_descriptive"),
    column_labels   = {
        "creatinine": "Creatinine (mg/dL)",
        "jaundice":   "Jaundice, n (%)",
        "outcome":    "Outcome",
        0:            "Survivor",
        1:            "Non-survivor",
    },
)
```

---

## `TabStatConfig`

```python
from tabstat import TabStatConfig
```

Dataclass holding all analysis and display options. All fields have sensible defaults
for clinical descriptive tables.

See [configuration.md](configuration.md) for the complete field reference.

---

## `TestOverrideConfig`

```python
from tabstat import TestOverrideConfig
```

Dataclass for hierarchical statistical test selection.

```python
@dataclass
class TestOverrideConfig:
    per_variable : Dict[str, str] = {}   # variable name → test token
    per_group    : Dict[str, str] = {}   # group column  → test token
    per_type     : Dict[str, str] = {}   # "numeric"/"categorical" → token
    default      : str            = "auto"
```

**Test tokens — numeric:**

| Token | Behaviour |
|---|---|
| `"auto"` | Automatic: normality test → t-test/Welch/Mann-Whitney U/ANOVA/Kruskal-Wallis |
| `"mannwhitneyu"` | Mann-Whitney U (2 groups) or Kruskal-Wallis (3+) |
| `"ttest"` | Student's t-test (2 groups) or one-way ANOVA (3+) |
| `"welch"` | Welch's t-test (2 groups) or one-way ANOVA (3+) |
| `"kruskal"` | Kruskal-Wallis (any number of groups) |
| `"anova"` | One-way ANOVA (any number of groups) |
| `"never_parametric"` | Always use non-parametric tests |
| `"always_parametric"` | Always use parametric tests |

**Test tokens — categorical:**

| Token | Behaviour |
|---|---|
| `"auto"` | Fisher Exact (2×2, expected cell < 5) else Chi-squared |
| `"chi2"` | Chi-squared always |
| `"fisher"` | Fisher Exact for 2×2; falls back to Chi-squared for larger tables |

### Named presets

```python
TestOverrideConfig.preset("clinical_descriptive")
# Numeric  → always non-parametric
# Categorical → auto (Fisher/Chi-squared by expected-cell rule)

TestOverrideConfig.preset("conservative")
# Everything → non-parametric

TestOverrideConfig.preset("parametric")
# Numeric → always parametric
```

### Usage

```python
# As a string shorthand (same as preset)
t = tabstat(df, formula, test_overrides="conservative")

# As an object
overrides = TestOverrideConfig(
    per_variable={"creatinine": "mannwhitneyu"},
    per_group={"site": "never_parametric"},
    per_type={"categorical": "chi2"},
    default="auto",
)
t = tabstat(df, formula, test_overrides=overrides)
```

---

## `TabStatGenerator`

```python
from tabstat import TabStatGenerator
from tabstat.config import TabStatConfig

gen = TabStatGenerator(config=TabStatConfig(...))
```

Lower-level class used when you need to re-use the same configuration for multiple
tables or need direct access to export methods.

### `generate()`

```python
gen.generate(
    df,
    formula,
    output_format  = "df",     # "df" | "grid" | "markdown" | "latex" | "html"
    column_labels  = None,
    paired         = False,
    title          = None,
    footnote       = None,
    show           = True,
) -> pd.DataFrame | str
```

Same semantics as `tabstat()`. Runs the full analysis pipeline once.

### Export methods

```python
# HTML — returns string, writes file if path given
html = gen.to_html(df_result, path="table1.html",
                   title="Table 1", footnote="...")

# Excel
gen.to_excel(df_result, path="table1.xlsx",
             title="Table 1", footnote="...")

# Excel, publication-style (three-line look; footnote kept outside the table)
gen.to_excel(df_result, path="table1.xlsx",
             title="Table 1", footnote="...",
             publication_style=True, bold_significant=True)

# Multi-sheet Excel workbook
gen.to_excel_workbook(
    [("Table 1", t1), ("Table 2", t2)],
    path="report.xlsx",
    publication_style=True,
)

# Word DOCX
gen.to_docx(df_result, path="table1.docx",
            title="Table 1", footnote="...")

# LaTeX string
latex = gen.to_latex(df_result)
```

---

## `export_tables_to_excel()`

```python
from tabstat import export_tables_to_excel

export_tables_to_excel(
    tables            = [("Table 1", t1), ("Table 2", t2)],
    output_path       = "report.xlsx",
    column_titles     = None,
    publication_style = False,
    **style_kwargs,
)
```

Convenience wrapper — writes multiple `tabstat` DataFrames into one Excel workbook,
one sheet per table.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `tables` | `List[Tuple[str, pd.DataFrame]]` | — | `(sheet_name, df)` pairs |
| `output_path` | `str` | `"./report.xlsx"` | Output path |
| `column_titles` | `dict` | `None` | Pass the same `column_titles` used to build each table, so the P-value/Test columns are located correctly for spanning/merging. |
| `publication_style` | `bool` | `False` | Apply the three-line look — see [`apply_publication_style()`](#apply_publication_style). |
| `**style_kwargs` | — | — | Forwarded to `apply_publication_style()` (e.g. `bold_significant=True`). |

---

## `to_html_str()`

```python
from tabstat.exports import to_html_str

html = to_html_str(
    df,
    title    = "Table 1. Characteristics of the study population",
    footnote = None,
) -> str
```

Convert a `tabstat` DataFrame to a self-contained, styled HTML document.
MultiIndex columns are rendered with `<th colspan>` spanning headers.
Section-header rows are rendered as `<tr class="section-hdr">` spanning all columns.

---

## `to_excel_file()`

```python
from tabstat.exports import to_excel_file

to_excel_file(
    df_or_tables,                    # DataFrame or List[Tuple[str, DataFrame]]
    path,
    title                = "Table 1",
    footnote             = None,
    characteristic_label = "Characteristic",
    total_label          = "Total",
    p_value_label        = "P-value",
    test_label           = "Test",
    smd_label            = "SMD",
    publication_style    = False,
    **style_kwargs,
) -> None
```

Export to a styled Excel workbook (requires `openpyxl`).

Features: title row, multi-level header rows with merged cells, alternating-row fill,
auto-fitted column widths (capped at 42 chars), frozen header rows, p-value cells
merged across category rows, section-header rows merged and tinted. The footnote
(if given) is written as an italic, borderless row separated from the table body
by a blank spacer row — outside the table, not its last row.

The `*_label` parameters tell the exporter what text to look for when locating the
Total/P-value/Test/SMD columns for merging — pass the same strings you used in
`column_titles` if you renamed them.

Set `publication_style=True` to additionally apply the three-line academic look —
see `apply_publication_style()` below for the extra keyword args.

---

## `apply_publication_style()` {#apply_publication_style}

```python
from tabstat.exports import apply_publication_style

apply_publication_style(
    wb_or_path,                       # openpyxl.Workbook or path to .xlsx
    out_path             = None,      # save copy here if wb_or_path is a path
    font_name            = "Arial",
    font_size            = 10,
    title_size           = 12,
    col1_width           = None,      # None = keep to_excel_file's auto width
    other_width          = None,
    bold_significant     = False,     # bold the P-value cell when p < 0.05
    characteristic_label = "Characteristic",
    total_label          = "Total",
    p_value_label        = "P-value",
    test_label           = "Test",
    smd_label            = "SMD",
) -> None
```

Applies a three-line (academic-journal) look to a workbook already produced by
`to_excel_file()`: white background, no gridlines, bold variable labels,
thick/thin rules at the header and table foot. Works on every sheet.

Column positions (group spanner, P-value, Test) are located by header **text**,
not by a fixed index, so it keeps working regardless of `split_count_pct`, group
count, or whether `display_test_name`/`display_smd` are enabled — pass the
`*_label` arguments if you renamed those columns via `column_titles`.

The footnote row (italic, written by `to_excel_file`) is detected and left
untouched: the closing thick rule is drawn under the last *data* row, not under
the footnote, so it reads as outside/below the table.

Can be called directly on a path:

```python
apply_publication_style("table1.xlsx", bold_significant=True)
```

or, more efficiently, via `to_excel_file(..., publication_style=True)` /
`gen.to_excel(..., publication_style=True)`, which applies it to the in-memory
workbook before a single save.

---

## `to_docx_file()`

```python
from tabstat.exports import to_docx_file

to_docx_file(
    df_or_tables,          # DataFrame or List[Tuple[str, DataFrame]]
    path,
    title    = None,
    footnote = None,
) -> None
```

Export to a Word document (requires `python-docx`).

Features: dark header row with white bold text, multi-level column headers with
merged cells per level, section-header rows merged and tinted, alternating data-row
shading, bold title paragraph, italic footnote paragraph.

---

## `NormalitySelector`

```python
from tabstat.normality import NormalitySelector

sel = NormalitySelector(alpha=0.05, skew_threshold=2.0, kurt_threshold=7.0)
is_normal, description = sel.test(series)
```

Automatically selects the most appropriate normality test based on sample size:

| n | Test |
|---|---|
| n < 3 | Assumed non-normal |
| 3 ≤ n < 50 | Shapiro-Wilk |
| 50 ≤ n < 5000 | D'Agostino-Pearson |
| n ≥ 5000 | Moment-based (\|skew\| < 2 and \|excess kurtosis\| < 7) |

### Methods

```python
# Test one series
is_normal: bool
description: str   # e.g. "Shapiro-Wilk (p=0.23)"
is_normal, description = sel.test(series)

# Test multiple groups — True only if ALL pass
all_ok = sel.all_normal([group1_series, group2_series])
```

---

## `TestResolver`

```python
from tabstat.resolver import TestResolver
from tabstat.config import TestOverrideConfig

resolver = TestResolver(TestOverrideConfig(...))
token = resolver.resolve(var_name, group_cols, var_type)
```

Resolves the test token for a variable by walking the four-level priority hierarchy
(per_variable → per_group → per_type → default). Used internally by `TabStatGenerator`.

```python
token = resolver.resolve(
    var        = "creatinine",
    group_cols = ["outcome"],
    var_type   = "numeric",        # "numeric" or "categorical"
)
# → "auto"  (or whatever the highest-priority override specifies)
```
