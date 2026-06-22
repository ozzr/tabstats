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
