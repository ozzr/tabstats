# TabStat – Implementation Backlog & Session Resume Guide

Generated: 2026-04-12  
Status key: ✅ done | 🔄 in progress | ⬜ pending

---

## P0 – Bugs (must fix)

### ✅ P0-1: Fix p_col_idx → use col_layout.p_idx in multiple testing correction
**File:** `src/tabstat/generator.py` · `_run_analysis()`  
**Issue:** Lines 303–306 manually recompute the p-value column index instead of using
`col_layout.p_idx`. The manual calculation ignores `split_count_pct` on the Total column,
so with `split_count_pct=True` the correction writes to the wrong column.  
**Fix:**  
1. Move `col_layout = build_col_layout(...)` to right after `_compute_group_counts()`,
   before the per-variable for-loop (all required inputs are available there).  
2. In the correction block, replace the 4-line manual `p_col_idx` computation with
   `p_col_idx = col_layout.p_idx`.  
3. Remove the now-duplicate `col_layout = build_col_layout(...)` call at the end of
   `_run_analysis()` (line ~348).

---

### ✅ P0-2: HTML export does not render MultiIndex headers with colspan
**File:** `src/tabstat/exports.py` · `to_html_str()`  
**Issue:** `to_html_str()` calls `_flatten()` first, then renders a single `<tr>` header.
Multi-level group columns and `split_count_pct=True` produce `\n`-joined flat labels
instead of proper `<th colspan>` spanning cells.  
**Fix:** Add `_build_html_headers(df)` helper:
- If `df.columns` is a `pd.MultiIndex`, build one `<tr>` per level.
- In each level, detect runs of consecutive equal non-empty values and emit one
  `<th colspan="N">value</th>`.
- Empty values (padding) become `<th></th>`.
- Call this instead of the current single-row header in `to_html_str()`.
- Keep using `_flatten(df)` for the body rows only.

---

### ✅ P0-3: Silent variable failure hides errors from user
**File:** `src/tabstat/generator.py` · `_run_analysis()` line ~297  
**Issue:** `except Exception: logger.warning(...)` swallows per-variable failures silently.
User never sees them unless they configure logging.  
**Fix:**  
- Collect failed variable names in `failed_vars: List[str]`.  
- After the for-loop, if `failed_vars`: call `warnings.warn(...)` (UserWarning, stacklevel=3)
  with a message listing the variable names.

---

## P1 – High-impact features

### ✅ P1-1: SMD with >2 groups is silently meaningless
**File:** `src/tabstat/generator.py` · `generate()`  
**Issue:** `display_smd=True` always adds an SMD column, but SMD is only defined for
2-sample comparisons. With 3+ groups the column is always blank.  
**Fix:**  
- In `generate()`, after `_run_analysis` returns `groups`, add:
  `if self.config.display_smd and len(groups) > 2: warnings.warn(...)`.  
- Update `_build_columns()` to label the SMD column as `"SMD"` with a parenthetical note
  `"(2-group only)"` appended to the header when `len(groups) > 2`.

---

### ✅ P1-2: No variable section headers
**Files:** `src/tabstat/config.py`, `src/tabstat/generator.py`, `src/tabstat/rendering.py`,
`src/tabstat/exports.py`  
**Issue:** Long tables (~20+ vars) have no way to group variables under section labels
(e.g., "─── Demographics ───").  
**Fix:**  
- Add `sections: Optional[Dict[str, List[str]]] = None` to `TabStatConfig`.
  Key = section label, value = ordered list of variable names in that section.
  Variables not listed in any section are rendered ungrouped.  
- In `_run_analysis()`, before appending each variable's rows check if the variable is
  the first in its section and insert a `kind="section"` header row:
  `[f"─── {label} ───"] + [""] * (n_cols - 1)`.  
- In `render_text_table()`, detect section rows (first cell matches `^─+`) and render as
  a full-width `SCell` separator with the section label.  
- In `to_html_str()`, detect section rows and render as
  `<tr class="section-hdr"><td colspan="N"><strong>label</strong></td></tr>`.  
- In `to_excel_file()`, detect section rows and render as merged, bold, tinted row.

---

### ✅ P1-3: No Word/DOCX export
**File:** `src/tabstat/exports.py`, `src/tabstat/generator.py`  
**Issue:** Clinical researchers require Word format. HTML pasted into Word loses styling.  
**Fix:**  
- Add `to_docx_file(df_or_tables, path, title, footnote)` in `exports.py`.
  Wrap import in try/ImportError like openpyxl.  
- For MultiIndex columns: build merged cells for repeated header values per level.  
- Header row: bold, dark background, white text (via XML shading).  
- Alternating row shading.  
- Add `to_docx(self, df, path, title, footnote)` convenience method on `TabStatGenerator`.

---

## P2 – Medium-impact features

### ✅ P2-1: No confidence intervals for proportions
**Files:** `src/tabstat/config.py`, `src/tabstat/generator.py`  
**Issue:** Many journals require Wilson CI alongside n(%).  
**Fix:**  
- Add `show_proportion_ci: bool = False` and `ci_level: float = 0.95` to `TabStatConfig`.  
- Add `_wilson_ci(self, k, n, level) → Optional[Tuple[float,float]]` method in generator.  
- Add `_format_cat_cell(self, n_gc, denom, var)` helper that respects `categorical_fmt`
  and appends `[lo%–hi%]` when `show_proportion_ci=True` and `split_count_pct=False`.  
- Apply in `_summarize_categorical` for every group cell and the binary-collapse row.  
- Wilson formula:  
  `z = norm.ppf(1 - (1-level)/2)`  
  `center = (k + z²/2) / (n + z²)`  
  `hw = z · √(k(n−k)/n + z²/4) / (n + z²)`

---

### ✅ P2-2: No per-variable footnote markers
**Files:** `src/tabstat/config.py`, `src/tabstat/generator.py`  
**Issue:** Cannot attach `*`, `†` markers to specific variables referencing footnote text.  
**Fix:**  
- Add `var_footnotes: Dict[str, str] = {}` to `TabStatConfig`. Maps var name → symbol.  
- In `_summarize_numeric` and `_summarize_categorical`, if `var in cfg.var_footnotes`,
  append the marker to the variable label: `f"{label}{cfg.var_footnotes[var]}"`.

---

### ✅ P2-3: No render_categorical format customization
**Files:** `src/tabstat/config.py`, `src/tabstat/generator.py`  
**Issue:** Cannot show only %, `n/total (%)`, or `n` alone for categorical cells.  
**Fix:**  
- Add `categorical_fmt: str = "n_pct"` to `TabStatConfig`.
  Values: `"n_pct"` (default), `"pct_only"`, `"n_only"`, `"n_total_pct"`.  
- Extend `render_config` to accept these values per variable.  
- Update `_get_render_type()` to recognise `"pct_only"/"n_only"/"n_total_pct"` as
  categorical format hints (not type overrides; separate concern).  
- Use `_format_cat_cell()` helper (see P2-1) everywhere a categorical cell is built.

---

## P3 – Nice-to-have

### ✅ P3-1: Paired tests are all-or-nothing
**Files:** `src/tabstat/config.py`, `src/tabstat/generator.py`  
**Issue:** `paired=True` in `generate()` applies to all variables.  
**Fix:**  
- Add `paired_vars: List[str] = []` to `TabStatConfig`.  
- In `_run_analysis()`, when calling `_summarize_numeric` / `_summarize_categorical`,
  pass `paired=paired or var in cfg.paired_vars`.

---

### ✅ P3-2: Normality test result is hidden
**Files:** `src/tabstat/config.py`, `src/tabstat/generator.py`  
**Issue:** `NormalitySelector.test()` returns `(is_normal, description)` but the description
is discarded; reviewers often ask which test was used.  
**Fix:**  
- Add `show_normality_method: bool = False` to `TabStatConfig`.  
- In `_summarize_numeric()`, if the flag is set, call `normality_selector.test(gs)` on each
  group series (after group_series is built) and store descriptions in
  `meta["normality_info"] = (var, [desc1, desc2, ...])` for the stat meta.  
- In `generate()`, after `_run_analysis`, collect all `normality_info` metas and append
  `"Normality: VAR: desc1; desc2 | ..."` to the footnote.

---

### ✅ P3-3: render_continuous DSL missing common tokens; no validation
**File:** `src/tabstat/generator.py` · `_compute_stat()`  
**Issue:** `_compute_stat()` supports `mean`, `std`, `var`, `median`, `p{N}` but not
`min`, `max`, `n`. Users writing custom specs get silent wrong output.  
**Fix:**  
- Add `min`, `max`, `n` to the token substitution loop in `_compute_stat()`.  
- At spec parse time (inside the `if specs:` branch), if the formula part still contains
  word-like tokens after substitution, log a `logger.warning` listing unrecognised tokens.

---

### ✅ P3-4: No include_nan_as_category option
**Files:** `src/tabstat/config.py`, `src/tabstat/generator.py`  
**Issue:** NaN is always excluded from categorical counts; cannot model "Unknown" as
an explicit category in proportions and chi-square tests.  
**Fix:**  
- Add `include_nan_as_category: bool = False` and `nan_category_label: str = "Unknown"`
  to `TabStatConfig`.  
- In `_summarize_categorical()`, if enabled: `df[var].fillna(cfg.nan_category_label)`
  before building `series`; set denominator to `len(df)` (not `.count()`).  
- Note: incompatible with `display_missing=True` (the missing row would show 0).
  Add a `logger.warning` when both are active.

---

### ✅ P3-5: column_labels with non-string / tuple group values is undocumented and fragile
**Files:** `src/tabstat/generator.py`, `src/tabstat/__init__.py`  
**Issue:** With multi-level groups, group values are tuples or booleans; `column_labels`
remaps each element through `str(v)`, so `{True: 'Fatal'}` silently does nothing.  
**Fix:**  
- In the group-remapping loop in `generate()`, try the raw value key before falling back
  to `str(v)`: `column_labels.get(v, column_labels.get(str(v), str(v)))`.  
- Document tuple-level remapping in the `tabstat()` docstring with an example.

---

## Dead code / audit

### ✅ DC-1: Unused `val_ov` variable in three locations
**File:** `src/tabstat/generator.py`  
- `_summarize_categorical()` binary collapse block: `val_ov = f"..."` (the value is never
  read; `_append_total(n=, pct=)` is called directly instead).  
- `_summarize_categorical()` standard multi-row block: same issue.  
- `_make_missing_row()`: `val_ov = f"..."` is computed and never read.  
**Fix:** Remove the three `val_ov = ...` assignment lines.

### ✅ DC-2: Redundant type annotation on `group_series` in `_summarize_numeric`
**File:** `src/tabstat/generator.py`  
- Inside the `else:` branch (line ~720): `group_series: List[pd.Series] = []` repeats
  the annotation already present in the `if specs:` branch.  
**Fix:** Change to `group_series = []` (remove type annotation on the second occurrence).

---

## Test coverage checklist (after all fixes)

Run `python -m pytest tests/ -v` — all should be green.  
New behaviours to add tests for:
- `p_col_idx` fix: `correction="bonferroni"` with `split_count_pct=True` → correct column
- HTML headers: MultiIndex produces `<th colspan>` in output
- `var_footnotes` marker appears in characteristic label
- `categorical_fmt="pct_only"` cells show only `%`
- `show_proportion_ci=True` cells contain `[lo%–hi%]`
- `sections` inserts section header row
- DOCX file is created without error

---

## Session resume guide

If starting a new session, follow these steps:

1. `python -m pytest tests/ -v` — verify baseline is green.
2. `git log --oneline` — see which commits exist; each task above gets its own commit.
3. Find the first item still marked `⬜` above and implement it.
4. Key file map:
   - Feature flags / config → `src/tabstat/config.py`
   - Analysis pipeline → `src/tabstat/generator.py`
   - Text table renderer → `src/tabstat/rendering.py`
   - HTML / Excel / DOCX → `src/tabstat/exports.py`
   - Public API → `src/tabstat/__init__.py`
5. After implementing, mark the item `✅`, run tests, then commit with the task label
   as the commit subject (e.g., `fix: P0-1 use col_layout.p_idx for correction`).
6. Config fields go in `TabStatConfig` with a comment block for the section.
   Generator logic goes in the relevant `_summarize_*` method or `generate()`.
7. Imports to remember:
   - `warnings` (stdlib) for `warnings.warn(...)` calls
   - `Optional` from `typing` (add to config.py imports)
   - `scipy.stats.norm` for Wilson CI
   - `python-docx` for DOCX (optional, wrap in try/ImportError)
