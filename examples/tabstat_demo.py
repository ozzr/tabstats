"""
tabstat_demo.py
───────────────
Complete usage demo for the tabstat package.
Uses synthetic data resembling a RMSF pediatric cohort.
"""
import numpy as np
import pandas as pd
from tabstat import tabstat, TabStatConfig, TabStatGenerator, TestOverrideConfig

# ─────────────────────────────────────────────────────────────────────────────
# 1. Synthetic RMSF-like dataset
# ─────────────────────────────────────────────────────────────────────────────
np.random.seed(572)   # same seed as the real pipeline
N = 140

outcome = np.random.choice([0, 1], size=N, p=[0.70, 0.30])

df = pd.DataFrame({
    # Demographics
    "edad_meses": np.random.randint(6, 180, N),
    "sexo":       np.random.choice(["Masculino", "Femenino"], N),

    # Labs (different distributions per outcome)
    "CREAT": np.where(
        outcome == 1,
        np.random.lognormal(0.8, 0.6, N),
        np.random.lognormal(0.2, 0.4, N),
    ).round(2),
    "PLT": np.where(
        outcome == 1,
        np.random.normal(60, 30, N).clip(5, 200),
        np.random.normal(180, 60, N).clip(50, 450),
    ).round(0),
    "LDH": np.random.lognormal(6.5, 0.5, N).round(0),
    "GPT": np.random.lognormal(3.8, 0.8, N).round(1),
    "NEUTROS": np.random.lognormal(8.5, 0.7, N).round(0),

    # Categorical
    "ictericia":  np.random.choice([0, 1], N, p=[0.65, 0.35]),
    "hemorragia": np.random.choice([0, 1], N, p=[0.80, 0.20]),

    # Outcome
    "outcome": outcome,
})

# Introduce some missing values
for col in ["CREAT", "PLT", "LDH"]:
    mask = np.random.rand(N) < 0.08
    df.loc[mask, col] = np.nan

# ─────────────────────────────────────────────────────────────────────────────
# 2. Demo A — Basic call
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "═" * 70)
print("DEMO A — Basic table (grid format)")
print("═" * 70)

t = tabstat(
    df,
    "edad_meses + sexo + CREAT + PLT + LDH | outcome",
    tablefmt  = "grid",
    column_labels = {
        "edad_meses": "Age (months)",
        "outcome":    "Fatal outcome",
        0:            "Survivor",
        1:            "Fatal",
    },
)

# ─────────────────────────────────────────────────────────────────────────────
# 3. Demo B — Full features
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "═" * 70)
print("DEMO B — Full features")
print("  ✓ SMD column")
print("  ✓ Missing sub-rows")
print("  ✓ Binary collapse")
print("  ✓ Per-variable render specs")
print("  ✓ Hierarchical test overrides")
print("  ✓ clinical_descriptive preset (non-parametric for numeric)")
print("═" * 70)

overrides = TestOverrideConfig(
    # Specific variables: always Mann-Whitney (very skewed in RMSF)
    per_variable={"CREAT": "mannwhitneyu", "PLT": "mannwhitneyu"},
    # Grouped by 'outcome': conservative (non-parametric) for all numerics
    per_group={"outcome": "never_parametric"},
    # Categorical: auto (Fisher/Chi² by expected-cell rule)
    per_type={"categorical": "auto"},
    default="auto",
)

t_full = tabstat(
    df,
    "edad_meses + sexo + CREAT + PLT + LDH + GPT + NEUTROS + ictericia + hemorragia | outcome",
    tablefmt         = "grid",
    display_smd      = True,
    display_missing  = True,
    collapse_binary  = True,
    collapse_binary_level = "last",
    test_overrides   = overrides,
    render_continuous = {
        # CREAT and PLT → median [IQR] only
        "CREAT":      ["Median [IQR] = median [p25, p75]"],
        "PLT":        ["Median [IQR] = median [p25, p75]"],
        # All other numeric vars → both stats
        "__default__": [
            "Median [IQR] = median [p25, p75]",
            "Mean (SD)    = mean (± std)",
        ],
    },
    column_labels = {
        "edad_meses": "Age (months)",
        "sexo":       "Sex",
        "ictericia":  "Jaundice",
        "hemorragia": "Hemorrhage",
        "outcome":    "Outcome",
        0:            "Survivor",
        1:            "Fatal",
    },
)

# ─────────────────────────────────────────────────────────────────────────────
# 4. Demo C — Export to HTML and Excel
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "═" * 70)
print("DEMO C — Exports")
print("═" * 70)

gen = TabStatGenerator(
    TabStatConfig(
        display_smd     = True,
        display_missing = True,
        collapse_binary = True,
        test_overrides  = TestOverrideConfig.preset("clinical_descriptive"),
    )
)

result_df = gen.generate(
    df,
    "edad_meses + sexo + CREAT + PLT + hemorragia | outcome",
    output_format="df",
)

# HTML
html_path = "tabstat_output.html"
gen.to_html(result_df, path=html_path)
print(f"  HTML  → {html_path}")

# Excel
try:
    excel_path = "tabstat_output.xlsx"
    gen.to_excel(result_df, path=excel_path, title="Table 1. RMSF Cohort Characteristics")
    print(f"  Excel → {excel_path}")
except ImportError as e:
    print(f"  Excel skipped: {e}")

# LaTeX
latex_str = gen.to_latex(result_df)
print("\n  LaTeX preview (first 400 chars):")
print("  " + latex_str[:400].replace("\n", "\n  "))

print("\n✓ Demo complete.")

# ─────────────────────────────────────────────────────────────────────────────
# 5. Demo D — Preset shorthand via string
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "═" * 70)
print("DEMO D — Preset shorthand  (test_overrides='conservative')")
print("═" * 70)

t_conservative = tabstat(
    df,
    "CREAT + PLT + LDH | outcome",
    tablefmt       = "markdown",
    test_overrides = "conservative",   # string shorthand
)
