# tabstats — Claude Code Task Brief

## Context

You are working on **tabstats** (`https://github.com/ozzr/tabstats`),
a Python package that generates publication-ready Table 1 for clinical
and epidemiological research.

Clone the repo and work from it:

```bash
git clone https://github.com/ozzr/tabstats.git
cd tabstats
```

The package source lives in `src/tabstat/`. It already has
`pyproject.toml`, `LICENSE` (GPL-3.0), `README.md`, and an `examples/`
folder. The core modules are: `__init__.py`, `config.py`,
`normality.py`, `resolver.py`, `generator.py`, `rendering.py`,
`exports.py`.

Commit **every logical unit of work** separately with a descriptive
message following Conventional Commits:
`feat:`, `fix:`, `test:`, `docs:`, `ci:`, `chore:`.

Push each commit immediately after creating it:

```bash
git add <files>
git commit -m "type: description"
git push origin main
```

---

## Task list — complete ALL of these in order

---

### TASK 1 — Fix: p-value truncation in separator headers (`fix:`)

**File:** `src/tabstat/rendering.py`, function `_make_label_separator()`

Currently the label is truncated with `s[:cw]` before centering, which
causes "P-value" to appear as "P-valu" when the column is narrow.

Fix: remove the truncation so the label is centered without slicing:

```python
# Before
parts.append(f" {s[:cw].center(cw)} ")

# After
parts.append(f" {s.center(cw)} ")
```

Commit: `fix: remove label truncation in separator causing P-valu bug`

---

### TASK 2 — Fix: p-value spanning for n>2 categories (`fix:`)

**File:** `src/tabstat/rendering.py` and `src/tabstat/generator.py`

Currently only the middle separator gets the p-value injected.
For variables with ≥ 3 categories, ALL inter-category separators must
be modified: the ones that are NOT the middle row should have their
p-value and test columns replaced with spaces (open/blank), and ONLY
the middle separator gets the actual value.

**In `generator.py`, `_get_pvalue_injections()`:**

Change the return type from `List[Tuple[int, str, str]]` to
`List[Tuple[int, str, str, bool]]` where the 4th element `is_middle`
is `True` only for the central separator.

```python
def _get_pvalue_injections(self, row_metas):
    injections = []
    for meta in row_metas:
        span = meta.get("pvalue_span")
        if span is None:
            continue
        p_str, test_str, cat_start_abs, n_cats = span
        if not p_str and not test_str:
            continue
        middle_k = cat_start_abs + (n_cats - 1) // 2
        for i in range(n_cats - 1):
            k = cat_start_abs + i
            is_middle = (k == middle_k)
            injections.append((k, p_str, test_str, is_middle))
    return injections
```

**In `rendering.py`, `render_text_table()`:**

Update the injection loop to accept 4-tuples and pass a blank string
for non-middle rows:

```python
for k, p_str, test_str, is_middle in pvalue_injections:
    sep_line_idx = header_sep_idx + 2 + k * 2
    if 0 <= sep_line_idx < len(lines):
        if is_middle:
            lines[sep_line_idx] = _inject_pvalue_into_separator(
                lines[sep_line_idx], col_layout, p_str, test_str
            )
        else:
            lines[sep_line_idx] = _inject_pvalue_into_separator(
                lines[sep_line_idx], col_layout, " ", " "
            )
```

**In `_inject_pvalue_into_separator()`**, update the inner `_replace`
helper so that when `text` is `" "` (single space), it replaces dashes
with spaces but does NOT write any label:

```python
def _replace(parts, idx, text):
    if idx is None or idx >= len(parts):
        return
    w = len(parts[idx])
    inner = w - 2
    if text.strip() == "":
        # blank: replace dashes with spaces (open cell)
        parts[idx] = " " * w
    else:
        display = str(text).strip()
        parts[idx] = f" {display.center(inner)} "
```

Commit: `fix: p-value spanning now opens all inter-category separators`

---

### TASK 3 — Feature: Tukey outlier detection and Hartigan Dip Test (`feat:`)

**File:** `src/tabstat/generator.py` and `src/tabstat/config.py`

Add two optional data-quality checks per numeric variable, displayed as
footnotes appended to the table string and the DataFrame:

1. **Tukey outlier test**: flag variable if any values fall outside
   `[Q1 - 3*IQR, Q3 + 3*IQR]` (far outliers, Tukey's fence).

2. **Hartigan's Dip Test**: flag variable if the distribution is
   significantly multimodal (`diptest` package; only run if installed).
   Wrap the import in a try/except so the package stays optional.

Add to `TabStatConfig`:

```python
check_outliers:    bool = False   # Tukey far-outlier detection
check_multimodal:  bool = False   # Hartigan Dip Test (requires diptest)
```

Add a method `_run_data_quality_checks(df, variables)` in
`TabStatGenerator` that returns a list of footnote strings like:
`"[*] Outliers detected in: CREAT, LDH"`
`"[†] Multimodal distribution detected in: AGE"`

Append these strings to the footnote in `generate()` when either flag
is True, separated by newlines.

Commit: `feat: add optional Tukey outlier and Hartigan dip test checks`

---

### TASK 4 — Feature: Bonferroni multiple testing correction (`feat:`)

**File:** `src/tabstat/config.py` and `src/tabstat/generator.py`

Add to `TabStatConfig`:

```python
correction:  str = "none"   # "none" | "bonferroni" | "fdr_bh"
```

`"fdr_bh"` is Benjamini-Hochberg FDR (use `scipy.stats.false_discovery_control`
available in scipy >= 1.11; fall back to `statsmodels` if not available,
or skip with a warning).

In `_run_analysis()`, after all p-values are computed, collect them,
apply the correction, and write the adjusted values back into the
row data before building the DataFrame.

When correction is active, add an automatic footnote:
`"P-values adjusted using Bonferroni correction."` or
`"P-values adjusted using Benjamini-Hochberg FDR."`.

Commit: `feat: add Bonferroni and BH-FDR multiple testing correction`

---

### TASK 5 — Tests (`test:`)

Create `tests/` with the following structure:

```
tests/
├── __init__.py
├── conftest.py
├── test_config.py
├── test_normality.py
├── test_resolver.py
├── test_generator.py
├── test_rendering.py
└── test_exports.py
```

#### `tests/conftest.py`

Create three shared fixtures:

```python
import pytest
import numpy as np
import pandas as pd

@pytest.fixture(scope="session")
def df_small():
    """N=30 — triggers Shapiro-Wilk branch (n < 50)."""
    np.random.seed(42)
    n = 30
    return pd.DataFrame({
        "age":     np.random.normal(8, 3, n).clip(1, 18),
        "creat":   np.random.lognormal(0.3, 0.5, n).round(2),
        "sex":     np.random.choice(["M", "F"], n),
        "grade":   np.random.choice([1, 2, 3, 4], n),
        "outcome": np.random.choice([0, 1], n, p=[0.7, 0.3]),
        "classif": np.random.choice(["Compatible", "Confirmed"], n),
    })

@pytest.fixture(scope="session")
def df_medium():
    """N=120 — triggers D'Agostino-Pearson branch (50 <= n < 5000)."""
    np.random.seed(42)
    n = 120
    df = pd.DataFrame({
        "age":     np.random.normal(8, 3, n).clip(1, 18),
        "creat":   np.random.lognormal(0.3, 0.5, n).round(2),
        "sex":     np.random.choice(["M", "F"], n),
        "grade":   np.random.choice([1, 2, 3, 4], n),
        "outcome": np.random.choice([0, 1], n, p=[0.7, 0.3]),
        "classif": np.random.choice(["Compatible", "Confirmed"], n),
    })
    # Introduce 10% missing in creat
    idx = np.random.choice(n, int(n * 0.1), replace=False)
    df.loc[idx, "creat"] = np.nan
    return df

@pytest.fixture(scope="session")
def df_large():
    """N=6000 — triggers moment-based branch (n >= 5000)."""
    np.random.seed(42)
    n = 6000
    return pd.DataFrame({
        "age":     np.random.normal(8, 3, n).clip(1, 18),
        "creat":   np.random.lognormal(0.3, 0.5, n).round(2),
        "sex":     np.random.choice(["M", "F"], n),
        "outcome": np.random.choice([0, 1], n),
    })
```

#### `tests/test_normality.py`

```python
from tabstat.normality import NormalitySelector

def test_small_n_uses_shapiro(df_small):
    sel = NormalitySelector()
    _, method = sel.test(df_small["age"])
    assert "Shapiro" in method

def test_medium_n_uses_dagostino(df_medium):
    sel = NormalitySelector()
    _, method = sel.test(df_medium["age"].dropna())
    assert "D'Agostino" in method

def test_large_n_uses_moment(df_large):
    sel = NormalitySelector()
    _, method = sel.test(df_large["age"])
    assert "Moment" in method

def test_all_normal_returns_bool(df_medium):
    sel = NormalitySelector()
    groups = [df_medium.loc[df_medium["outcome"]==g, "age"].dropna()
              for g in [0, 1]]
    result = sel.all_normal(groups)
    assert isinstance(result, bool)

def test_n_less_than_3_returns_false():
    import pandas as pd
    sel = NormalitySelector()
    is_normal, method = sel.test(pd.Series([1.0, 2.0]))
    assert is_normal is False
```

#### `tests/test_resolver.py`

```python
from tabstat.config import TestOverrideConfig
from tabstat.resolver import TestResolver

def test_per_variable_wins():
    ov = TestOverrideConfig(
        per_variable={"CREAT": "mannwhitneyu"},
        per_group={"outcome": "kruskal"},
        per_type={"numeric": "anova"},
        default="auto",
    )
    r = TestResolver(ov)
    assert r.resolve("CREAT", ["outcome"], "numeric") == "mannwhitneyu"

def test_per_group_wins_over_type():
    ov = TestOverrideConfig(
        per_group={"outcome": "kruskal"},
        per_type={"numeric": "anova"},
        default="auto",
    )
    r = TestResolver(ov)
    assert r.resolve("AGE", ["outcome"], "numeric") == "kruskal"

def test_per_type_wins_over_default():
    ov = TestOverrideConfig(per_type={"categorical": "fisher"}, default="auto")
    r = TestResolver(ov)
    assert r.resolve("SEX", ["outcome"], "categorical") == "fisher"

def test_default_fallback():
    ov = TestOverrideConfig(default="never_parametric")
    r = TestResolver(ov)
    assert r.resolve("AGE", ["outcome"], "numeric") == "never_parametric"

def test_preset_clinical_descriptive():
    ov = TestOverrideConfig.preset("clinical_descriptive")
    r = TestResolver(ov)
    assert r.resolve("AGE", ["outcome"], "numeric") == "never_parametric"
    assert r.resolve("SEX", ["outcome"], "categorical") == "auto"

def test_preset_conservative():
    ov = TestOverrideConfig.preset("conservative")
    r = TestResolver(ov)
    assert r.resolve("AGE", ["outcome"], "numeric") == "never_parametric"
    assert r.resolve("SEX", ["outcome"], "categorical") == "never_parametric"
```

#### `tests/test_generator.py`

```python
import pandas as pd
import numpy as np
import pytest
from tabstat import tabstat
from tabstat.generator import TabStatGenerator
from tabstat.config import TabStatConfig

def test_returns_dataframe(df_medium):
    t = tabstat(df_medium, "age + sex | outcome")
    assert isinstance(t, pd.DataFrame)

def test_title_as_first_row(df_medium):
    t = tabstat(df_medium, "age | outcome", title="Table 1")
    assert t.iloc[0, 0] == "Table 1"

def test_footnote_as_last_row(df_medium):
    t = tabstat(df_medium, "age | outcome", footnote="IQR note")
    assert t.iloc[-1, 0] == "IQR note"

def test_missing_row_present_when_enabled(df_medium):
    t = tabstat(df_medium, "creat | outcome", display_missing=True)
    flat = t.iloc[:, 0].tolist()
    assert any("Missing" in str(v) for v in flat)

def test_missing_row_absent_when_disabled(df_medium):
    t = tabstat(df_medium, "age | outcome", display_missing=False)
    flat = t.iloc[:, 0].tolist()
    assert not any("Missing" in str(v) for v in flat)

def test_smd_column_present(df_medium):
    t = tabstat(df_medium, "age | outcome", display_smd=True)
    cols = [str(c) for c in t.columns]
    assert any("SMD" in c for c in cols)

def test_no_futurewarning(df_medium):
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        tabstat(df_medium, "age + sex | classif + outcome")

def test_multi_group_produces_multiindex(df_medium):
    t = tabstat(df_medium, "age | classif + outcome")
    assert isinstance(t.columns, pd.MultiIndex)

def test_show_false_does_not_print(df_medium, capsys):
    tabstat(df_medium, "age | outcome", tablefmt="grid", show=False)
    captured = capsys.readouterr()
    assert captured.out == ""

def test_pct_denominator_total(df_medium):
    t_group = tabstat(df_medium, "sex | outcome", pct_denominator="group")
    t_total = tabstat(df_medium, "sex | outcome", pct_denominator="total")
    # With pct_denominator=total, percentages won't sum to 100 per column
    assert t_group is not None
    assert t_total is not None

def test_collapse_binary(df_medium):
    t = tabstat(df_medium, "sex | outcome", collapse_binary=True)
    labels = t.iloc[:, 0].tolist()
    # Should NOT have separate Male/Female rows
    assert not any(v in ["M", "F"] for v in labels if isinstance(v, str))

def test_formula_all_columns(df_medium):
    t = tabstat(df_medium, "~ . | outcome")
    assert isinstance(t, pd.DataFrame)
    assert len(t) > 1

def test_unknown_variable_warns(df_medium):
    with pytest.warns(None):  # no error, just warning via logging
        t = tabstat(df_medium, "nonexistent_col | outcome")
    assert isinstance(t, pd.DataFrame)
```

#### `tests/test_rendering.py`

```python
import pandas as pd
import numpy as np
from tabstat import tabstat

def test_pvalue_appears_in_separator(df_medium):
    """P-value for binary categorical should appear in a separator line."""
    result_str = ""
    import io, sys
    old = sys.stdout
    sys.stdout = buf = io.StringIO()
    tabstat(df_medium, "sex | outcome", tablefmt="grid", show=True)
    sys.stdout = old
    output = buf.getvalue()
    # The p-value column value should appear in a '+' line, not a '|' line
    separator_lines = [ln for ln in output.split("\n") if ln.startswith("+")]
    has_pval_in_sep = any(
        any(c.isdigit() for c in ln.split("+")[-2])  # p_idx segment
        for ln in separator_lines
    )
    assert has_pval_in_sep

def test_title_box_rendered(df_medium):
    import io, sys
    old = sys.stdout
    sys.stdout = buf = io.StringIO()
    tabstat(df_medium, "age | outcome",
            tablefmt="grid", title="My Title", show=True)
    sys.stdout = old
    output = buf.getvalue()
    assert "My Title" in output

def test_footnote_box_rendered(df_medium):
    import io, sys
    old = sys.stdout
    sys.stdout = buf = io.StringIO()
    tabstat(df_medium, "age | outcome",
            tablefmt="grid", footnote="My footnote", show=True)
    sys.stdout = old
    output = buf.getvalue()
    assert "My footnote" in output

def test_nested_header_contains_group_name(df_medium):
    import io, sys
    old = sys.stdout
    sys.stdout = buf = io.StringIO()
    tabstat(df_medium, "age | outcome", tablefmt="grid", show=True)
    sys.stdout = old
    output = buf.getvalue()
    assert "outcome" in output
```

#### `tests/test_exports.py`

```python
import os
import tempfile
import pandas as pd
from tabstat import tabstat
from tabstat.generator import TabStatGenerator
from tabstat.config import TabStatConfig

def test_html_returns_string(df_medium):
    html = tabstat(df_medium, "age | outcome", tablefmt="html")
    assert isinstance(html, str)
    assert "<table" in html.lower()

def test_html_contains_title(df_medium):
    html = tabstat(df_medium, "age | outcome",
                   tablefmt="html", title="Test Title")
    assert "Test Title" in html

def test_excel_creates_file(df_medium):
    gen = TabStatGenerator(TabStatConfig())
    result = gen.generate(df_medium, "age + sex | outcome")
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    try:
        gen.to_excel(result, path, title="Table 1")
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0
    finally:
        os.unlink(path)
```

#### `tests/test_config.py`

```python
import pytest
from tabstat.config import TabStatConfig, TestOverrideConfig

def test_default_config():
    cfg = TabStatConfig()
    assert cfg.decimals == 1
    assert cfg.pct_denominator == "group"
    assert cfg.display_missing is True
    assert cfg.display_smd is False

def test_preset_names():
    for name in ["clinical_descriptive", "conservative", "parametric"]:
        ov = TestOverrideConfig.preset(name)
        assert isinstance(ov, TestOverrideConfig)

def test_unknown_preset_raises():
    with pytest.raises(ValueError):
        TestOverrideConfig.preset("nonexistent_preset")

def test_pct_denominator_values():
    for v in ["group", "total", "parent_group"]:
        cfg = TabStatConfig(pct_denominator=v)
        assert cfg.pct_denominator == v
```

After writing all test files, run the tests to make sure they pass:

```bash
pip install -e ".[dev]"
pytest tests/ -v --tb=short
```

Fix any failures before committing.

Commit: `test: add full pytest suite covering normality, resolver, generator, rendering, exports`

---

### TASK 6 — GitHub Actions CI (`ci:`)

Create `.github/workflows/tests.yml`:

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run tests
        run: pytest tests/ -v --tb=short --cov=tabstat --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
        continue-on-error: true
```

Commit: `ci: add GitHub Actions test matrix for Python 3.10/3.11/3.12`

---

### TASK 7 — GitHub Actions docs deployment (`ci:`)

Create `.github/workflows/docs.yml`:

```yaml
name: Deploy Docs

on:
  push:
    branches: [main]

permissions:
  contents: write

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install docs dependencies
        run: pip install -e ".[docs]"
      - name: Deploy to GitHub Pages
        run: mkdocs gh-deploy --force
```

Commit: `ci: add mkdocs GitHub Pages deployment workflow`

---

### TASK 8 — MkDocs documentation site (`docs:`)

Create `docs/mkdocs.yml`:

```yaml
site_name: tabstats
site_description: Publication-ready Table 1 for clinical and epidemiological research
site_url: https://ozzr.github.io/tabstats
repo_url: https://github.com/ozzr/tabstats
repo_name: ozzr/tabstats

theme:
  name: material
  palette:
    scheme: default
    primary: teal
  features:
    - navigation.tabs
    - navigation.sections
    - content.code.copy

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          paths: [src]

nav:
  - Home: index.md
  - Quickstart: quickstart.md
  - User Guide:
      - Formula syntax: guide/formula.md
      - Statistical tests: guide/tests.md
      - Percentage denominators: guide/pct.md
      - Output formats: guide/formats.md
  - API Reference: api.md
  - Changelog: changelog.md
```

Create `docs/index.md` — project overview with a minimal working example.

Create `docs/quickstart.md` — step-by-step from install to first table,
with a grid-format example output block.

Create `docs/guide/formula.md` — formula syntax reference with all cases
(`~ .`, `var1 + var2 | group`, multi-group).

Create `docs/guide/tests.md` — how automatic test selection works,
the 4-level hierarchy, presets, and a decision table.

Create `docs/guide/pct.md` — pct_denominator options with example showing
different percentages for the same data.

Create `docs/guide/formats.md` — all output formats with examples.

Create `docs/api.md` — docstring-based API reference using mkdocstrings:

```markdown
# API Reference

## `tabstat()`

::: tabstat.tabstat

## `TabStatConfig`

::: tabstat.config.TabStatConfig

## `TestOverrideConfig`

::: tabstat.config.TestOverrideConfig

## `TabStatGenerator`

::: tabstat.generator.TabStatGenerator

## `NormalitySelector`

::: tabstat.normality.NormalitySelector

## `TestResolver`

::: tabstat.resolver.TestResolver
```

Create `docs/changelog.md`:

```markdown
# Changelog

## 1.1.0 (current)
- Single-pass analysis (`_run_analysis()`)
- SPSS-style p-value spanning for categorical variables
- Nested multi-level headers for multiple grouping variables
- `pct_denominator` option: `group` | `total` | `parent_group`
- `show` parameter to suppress stdout
- Title and footnote as rows in DataFrame output
- Tukey outlier detection (`check_outliers=True`)
- Hartigan Dip Test (`check_multimodal=True`)
- Multiple testing correction: Bonferroni and BH-FDR
- Full pytest suite

## 1.0.0
- Initial release
- Adaptive normality test selection by sample size
- 4-level hierarchical test override system
- SMD column, missing sub-rows, binary collapse
- Per-variable render specs
- HTML and Excel export
```

Commit: `docs: add mkdocs site with quickstart, guides, and API reference`

---

### TASK 9 — CITATION.cff (`chore:`)

Create `CITATION.cff` in the repo root:

```yaml
cff-version: 1.2.0
message: "If you use tabstats in your research, please cite it as below."
type: software
title: tabstats
version: 1.1.0
date-released: "2025-01-01"
authors:
  - family-names: "Rodríguez"
    given-names: "Osmany"
    affiliation: "Universidad de Sonora"
repository-code: "https://github.com/ozzr/tabstats"
license: GPL-3.0
abstract: >
  tabstats is a Python package for generating publication-ready Table 1
  for clinical and epidemiological research. It features automatic
  normality-test selection by sample size, a four-level hierarchical
  statistical test override system, SPSS-style p-value spanning,
  configurable percentage denominators, and nested multi-level column
  headers.
keywords:
  - table1
  - clinical research
  - epidemiology
  - descriptive statistics
  - python
  - pediatrics
```

Commit: `chore: add CITATION.cff for software citation`

---

### TASK 10 — README badges and polish (`docs:`)

Update `README.md` to add badges at the top:

```markdown
![Tests](https://github.com/ozzr/tabstats/actions/workflows/tests.yml/badge.svg)
[![Docs](https://img.shields.io/badge/docs-online-teal)](https://ozzr.github.io/tabstats)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
```

Also make sure README contains:
- Install instructions: `pip install tabstats`
- A minimal working example with output
- A comparison table vs `tableone` (Python)
- Link to docs site

Commit: `docs: update README with badges, install instructions, comparison table`

---

## Final verification

After all tasks:

```bash
# Run full test suite
pytest tests/ -v

# Verify the package installs cleanly
pip install -e .
python -c "from tabstat import tabstat; print('OK')"

# Build docs locally
mkdocs build --strict

# Verify git log looks clean
git log --oneline
```

The git log should show at least 10 commits, each corresponding to one task above.
