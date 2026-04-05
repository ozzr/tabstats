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
