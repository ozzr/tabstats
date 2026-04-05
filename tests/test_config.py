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
