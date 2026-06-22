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
    groups = [df_medium.loc[df_medium["outcome"] == g, "age"].dropna()
              for g in [0, 1]]
    result = sel.all_normal(groups)
    assert isinstance(result, bool)


def test_n_less_than_3_returns_false():
    import pandas as pd
    sel = NormalitySelector()
    is_normal, method = sel.test(pd.Series([1.0, 2.0]))
    assert is_normal is False
