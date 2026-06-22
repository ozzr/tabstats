"""
tabstat_demo.py
---------------
Complete usage demo for the tabstat package.
Uses synthetic data resembling a pediatric clinical cohort.
"""
import numpy as np
import pandas as pd
from tabstat import tabstat, TabStatConfig, TabStatGenerator, TestOverrideConfig

# -----------------------------------------------------------------------------
# 1. Synthetic dataset
# -----------------------------------------------------------------------------
np.random.seed(572)
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
    "ldh":  np.random.lognormal(6.5, 0.5, N).round(0),
    "alt":  np.random.lognormal(3.8, 0.8, N).round(1),

    # Categorical
    "jaundice":   np.random.choice([0, 1], N, p=[0.65, 0.35]),
    "hemorrhage": np.random.choice([0, 1], N, p=[0.80, 0.20]),
    "grade":      np.random.choice(["Mild", "Moderate", "Severe"], N, p=[0.40, 0.35, 0.25]),

    # Grouping
    "site":    site,
    "outcome": outcome,
})

# ~8% missing in labs
for col in ["creatinine", "platelets", "ldh"]:
    mask = np.random.rand(N) < 0.08
    df.loc[mask, col] = np.nan


# -----------------------------------------------------------------------------
# DEMO A — Basic call
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("DEMO A — Basic table (grid format)")
print("=" * 70)

tabstat(
    df,
    "age_months + sex + creatinine + platelets + ldh | outcome",
    tablefmt="grid",
    column_labels={
        "age_months": "Age (months)",
        "creatinine": "Creatinine (mg/dL)",
        "outcome":    "Outcome",
        0:            "Survivor",
        1:            "Non-survivor",
    },
)


# -----------------------------------------------------------------------------
# DEMO B — Full features
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("DEMO B — Full features")
print("  SMD | missing sub-rows | binary collapse | section headers")
print("  custom continuous stats | hierarchical test overrides | Wilson CI")
print("=" * 70)

overrides = TestOverrideConfig(
    per_variable={"creatinine": "mannwhitneyu", "platelets": "mannwhitneyu"},
    per_group={"outcome": "never_parametric"},
    per_type={"categorical": "auto"},
    default="auto",
)

tabstat(
    df,
    "age_months + sex + weight_kg + creatinine + platelets + ldh + alt"
    " + jaundice + hemorrhage + grade | outcome",
    tablefmt              = "grid",
    title                 = "Table 1. Patient characteristics by outcome",
    footnote              = "IQR = interquartile range. * Winsorised at 99th percentile.",

    # Display
    display_smd           = True,
    display_missing       = True,
    collapse_binary       = True,

    # Sections
    sections={
        "Demographics": ["age_months", "sex", "weight_kg"],
        "Laboratory":   ["creatinine", "platelets", "ldh", "alt"],
        "Clinical":     ["jaundice", "hemorrhage", "grade"],
    },

    # Stats
    test_overrides        = overrides,
    correction            = "bonferroni",
    render_continuous={
        "creatinine": ["Median [IQR] = median [p25, p75]"],
        "platelets":  ["Median [IQR] = median [p25, p75]"],
        "__default__": [
            "Median [IQR] = median [p25, p75]",
            "Mean (SD)    = mean (± std)",
        ],
    },

    # Categorical formatting
    show_proportion_ci    = True,
    ci_level              = 0.95,

    # Footnote markers
    var_footnotes         = {"creatinine": "*"},

    # Labels
    column_labels={
        "age_months": "Age (months)",
        "sex":        "Sex",
        "weight_kg":  "Weight (kg)",
        "creatinine": "Creatinine (mg/dL)",
        "platelets":  "Platelets (×10³/µL)",
        "ldh":        "LDH (U/L)",
        "alt":        "ALT (U/L)",
        "jaundice":   "Jaundice",
        "hemorrhage": "Hemorrhage",
        "outcome":    "Outcome",
        0:            "Survivor",
        1:            "Non-survivor",
    },
)


# -----------------------------------------------------------------------------
# DEMO C — Preset shorthand + markdown format
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("DEMO C — Preset shorthand  (test_overrides='conservative')")
print("=" * 70)

tabstat(
    df,
    "creatinine + platelets + ldh | outcome",
    tablefmt       = "markdown",
    test_overrides = "conservative",
)


# -----------------------------------------------------------------------------
# DEMO D — Multi-level grouping
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("DEMO D — Multi-level grouping  (site + outcome)")
print("=" * 70)

tabstat(
    df,
    "age_months + sex + creatinine | site + outcome",
    tablefmt        = "grid",
    pct_denominator = "parent_group",
    column_labels={
        "age_months": "Age (months)",
        "creatinine": "Creatinine (mg/dL)",
        "outcome":    "Outcome",
        0:            "Survivor",
        1:            "Non-survivor",
    },
)


# -----------------------------------------------------------------------------
# DEMO E — Normality transparency + NaN as category
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("DEMO E — Normality method transparency + NaN as explicit category")
print("=" * 70)

df_nan = df.copy()
df_nan.loc[np.random.rand(N) < 0.10, "grade"] = np.nan

tabstat(
    df_nan,
    "age_months + creatinine + grade | outcome",
    tablefmt                 = "grid",
    show_normality_method    = True,
    include_nan_as_category  = True,
    nan_category_label       = "Unknown",
    display_missing          = False,   # incompatible with include_nan_as_category
    column_labels={"outcome": "Outcome", 0: "Survivor", 1: "Non-survivor"},
)


# -----------------------------------------------------------------------------
# DEMO F — Exports (HTML, Excel, DOCX, LaTeX)
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("DEMO F — Exports")
print("=" * 70)

gen = TabStatGenerator(
    TabStatConfig(
        display_missing = True,
        collapse_binary = True,
        test_overrides  = TestOverrideConfig.preset("clinical_descriptive"),
        sections={
            "Demographics": ["age_months", "sex", "weight_kg"],
            "Laboratory":   ["creatinine", "platelets", "ldh"],
            "Clinical":     ["jaundice", "hemorrhage"],
        },
    )
)

result_df = gen.generate(
    df,
    "age_months + sex + weight_kg + creatinine + platelets + ldh + jaundice + hemorrhage | outcome",
    output_format = "df",
    column_labels={
        "age_months": "Age (months)",
        "weight_kg":  "Weight (kg)",
        "creatinine": "Creatinine (mg/dL)",
        "platelets":  "Platelets (×10³/µL)",
        "ldh":        "LDH (U/L)",
        "outcome":    "Outcome",
        0:            "Survivor",
        1:            "Non-survivor",
    },
)

TITLE    = "Table 1. Patient characteristics"
FOOTNOTE = "IQR = interquartile range."

# HTML
html_path = "tabstat_output.html"
gen.to_html(result_df, path=html_path, title=TITLE, footnote=FOOTNOTE)
print(f"  HTML  → {html_path}")

# Excel
try:
    excel_path = "tabstat_output.xlsx"
    gen.to_excel(result_df, path=excel_path, title=TITLE, footnote=FOOTNOTE)
    print(f"  Excel → {excel_path}")
except ImportError as e:
    print(f"  Excel skipped: {e}")

# DOCX
try:
    docx_path = "tabstat_output.docx"
    gen.to_docx(result_df, path=docx_path, title=TITLE, footnote=FOOTNOTE)
    print(f"  DOCX  → {docx_path}")
except ImportError as e:
    print(f"  DOCX  skipped: {e}")

# LaTeX
latex_str = gen.to_latex(result_df)
print("\n  LaTeX preview (first 300 chars):")
print("  " + latex_str[:300].replace("\n", "\n  "))

print("\nDemo complete.")
