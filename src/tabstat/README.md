# tabstat

**Publication-ready Table 1 for clinical and epidemiological research.**

`tabstat` generates descriptive summary tables (Table 1) from a pandas DataFrame.  It handles automatic statistical test selection, hierarchical test overrides, SPSS-style p-value spanning, nested multi-level headers, and exports to grid text, HTML, Excel, and LaTeX — with a single function call.

---

## Installation

```bash
# Copy the tabstat/ folder into your project, then:
pip install scipy tabulate openpyxl
```

---

## Quickstart

```python
from tabstat import tabstat, TestOverrideConfig

t = tabstat(
    df,
    "CREAT + GENDER + AGEGRP | CASECLASSIF + FATAL",
    tablefmt       = "grid",
    display_missing = True,
    title    = "Table 1. Cohort characteristics",
    footnote = "IQR = interquartile range.",
)
```

The returned `t` is a standard `pd.DataFrame` — the title and footnote appear as the first and last rows in the Characteristic column.

---

## Formula syntax

| Formula | Meaning |
|---|---|
| `"age + sex \| outcome"` | Specific variables, one grouping column |
| `"~ . \| outcome"` | All columns except `outcome` |
| `"~ ."` | All columns, no stratification |
| `"var1 + var2 \| grp1 + grp2"` | Multi-level grouping (nested headers) |

---

## Parameters

### `tabstat(df, formula, *, ...)`

| Parameter | Default | Description |
|---|---|---|
| `paired` | `False` | Paired tests (McNemar, Wilcoxon, paired-t) |
| `tablefmt` | `'df'` | `'df'` \| `'grid'` \| `'markdown'` \| `'latex'` \| `'html'` |
| `show` | `True` | Print text output to stdout |
| `column_labels` | `None` | Rename variables or group values |
| `title` | `None` | Table title |
| `footnote` | `None` | Table footnote |

Any field of `TabStatConfig` can be passed as a keyword argument:

| Field | Default | Description |
|---|---|---|
| `decimals` | `1` | Decimal places for statistics |
| `p_decimals` | `3` | Decimal places for p-values |
| `display_overall` | `True` | Show Total column |
| `overall_position` | `'last'` | `'first'` or `'last'` |
| `display_p_values` | `True` | Show P-value column |
| `display_test_name` | `True` | Show Test column |
| `display_smd` | `False` | Show Standardized Mean Difference column |
| `display_missing` | `True` | Show Missing sub-row per variable |
| `total_mode` | `'n_valid_percent'` | `'n'` \| `'n_valid'` \| `'n_valid_percent'` |
| `pct_denominator` | `'group'` | `'group'` \| `'total'` \| `'parent_group'` |
| `collapse_binary` | `False` | Single row for dichotomous variables |
| `render_config` | `{}` | Force render type per variable |
| `render_continuous` | `[]` | Custom statistics specs |
| `test_overrides` | `auto` | `TestOverrideConfig` instance or preset string |

---

## Statistical tests

### Automatic selection

**Numeric:**
- `n < 3` → non-parametric assumed
- `3 ≤ n < 50` → Shapiro-Wilk normality test
- `50 ≤ n < 5000` → D'Agostino-Pearson normality test
- `n ≥ 5000` → moment-based criterion (|skew| < 2, |kurt| < 7)

If normal: Student's t-test / Welch's t-test (Levene decides) / ANOVA  
If not normal: Mann-Whitney U / Kruskal-Wallis

**Categorical:** Chi-squared; Fisher exact if any expected cell < 5.

### Hierarchical overrides

```python
from tabstat import TestOverrideConfig

overrides = TestOverrideConfig(
    per_variable = {"CREAT": "mannwhitneyu"},   # level 1 (highest)
    per_group    = {"outcome": "never_parametric"},  # level 2
    per_type     = {"categorical": "fisher"},    # level 3
    default      = "auto",                       # level 4 (fallback)
)

t = tabstat(df, formula, test_overrides=overrides)
```

**Presets:**

```python
test_overrides = "clinical_descriptive"  # non-parametric + auto categorical
test_overrides = "conservative"          # non-parametric for everything
test_overrides = "parametric"            # always parametric for numeric
```

---

## Percentage denominator (`pct_denominator`)

Controls the denominator for percentage calculations in categorical variables:

| Value | Denominator |
|---|---|
| `'group'` | Non-missing N in each column group (standard) |
| `'total'` | Grand total N across all groups |
| `'parent_group'` | For ≥2 grouping variables, N in the first-level group |

**Example** — for `"CASECLASSIF + FATAL"`:
- `'group'` → % of Compatible/No, Compatible/Yes, Confirmed/No, Confirmed/Yes separately
- `'parent_group'` → % within all Compatible or all Confirmed (SPSS "Layer %" equivalent)

---

## Custom statistics rendering

```python
tabstat(df, formula,
    render_continuous = {
        "CREAT": ["Median [IQR] = median [p25, p75]"],
        "__default__": [
            "Median [IQR] = median [p25, p75]",
            "Mean (SD)    = mean (± std)",
            "P63          = p63",
        ],
    }
)
```

**Supported tokens:** `mean`, `std`, `var`, `median`, `pXX` (any percentile).

---

## Output formats

### Text grid (default when `tablefmt='grid'`)

Nested headers span multi-level groups automatically.  P-values for
categorical variables span across category rows (SPSS style).

### DataFrame (`tablefmt='df'`)

Returns a `pd.DataFrame`.  Title and footnote appear as actual rows
in the Characteristic column (first and last rows respectively).

### HTML

```python
html = tabstat(df, formula, tablefmt="html", title="Table 1")
# or via generator:
gen = TabStatGenerator(config)
gen.to_html(result_df, path="table1.html", title="Table 1", footnote="...")
```

### Excel

```python
gen = TabStatGenerator(config)
result = gen.generate(df, formula, title="Table 1", footnote="IQR = interquartile range.")
gen.to_excel(result, path="table1.xlsx", title="Table 1", footnote="IQR = interquartile range.")
```

```python
# Export multiple Table 1 outputs into one workbook.
gen = TabStatGenerator(config)
t1 = gen.generate(df, "age + sex | outcome", title="Table 1")
t2 = gen.generate(df, "creat | outcome", title="Table 2")
gen.to_excel_workbook([
    ("AgeSex", t1),
    ("Creatinine", t2),
], path="table1_workbook.xlsx")
```

---

## Advanced usage

```python
from tabstat import TabStatGenerator, TabStatConfig, TestOverrideConfig

config = TabStatConfig(
    decimals        = 2,
    display_smd     = True,
    display_missing = True,
    pct_denominator = "parent_group",
    test_overrides  = TestOverrideConfig.preset("clinical_descriptive"),
)

gen    = TabStatGenerator(config)
result = gen.generate(
    df, "CREAT + PLT + LDH | outcome",
    output_format = "grid",
    title    = "Table 1.",
    footnote = "IQR = interquartile range.",
)
```
