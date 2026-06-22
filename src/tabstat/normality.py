"""
tabstat/normality.py
────────────────────
Automatic normality test selection based on sample size.

Selection strategy
──────────────────
n < 3          → Not testable → assumed non-normal
3 ≤ n < 50     → Shapiro-Wilk       (highest power in small samples)
50 ≤ n < 5000  → D'Agostino-Pearson (scipy.stats.normaltest)
n ≥ 5000       → Moment-based       |skew| < skew_thresh & |kurt| < kurt_thresh
                 (formal tests almost always reject H₀ at large n for
                  clinically trivial deviations; moment criteria are more
                  meaningful in practice)
"""
from __future__ import annotations

import logging
from typing import Iterable, Tuple

import numpy as np
import pandas as pd
from scipy.stats import kurtosis, normaltest, shapiro, skew

logger = logging.getLogger(__name__)


class NormalitySelector:
    """
    Selects and runs the most appropriate normality test for a given Series.

    Parameters
    ----------
    alpha : float
        Significance level for formal tests (Shapiro-Wilk, D'Agostino).
    skew_threshold : float
        Absolute skewness threshold for the large-n moment criterion.
    kurt_threshold : float
        Absolute excess kurtosis threshold for the large-n moment criterion.
    """

    def __init__(
        self,
        alpha: float = 0.05,
        skew_threshold: float = 2.0,
        kurt_threshold: float = 7.0,
    ) -> None:
        self.alpha = alpha
        self.skew_threshold = skew_threshold
        self.kurt_threshold = kurt_threshold

    # ─────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────

    def test(self, data: pd.Series) -> Tuple[bool, str]:
        """
        Test normality of *data*.

        Returns
        -------
        is_normal : bool
        method_description : str   (for audit/logging purposes)
        """
        data = data.dropna()
        n = len(data)

        if n < 3:
            return False, "n<3 → non-normal assumed"

        if n < 50:
            _, p = shapiro(data)
            is_normal = p >= self.alpha
            logger.debug(
                "Shapiro-Wilk: n=%d  p=%.4f  normal=%s", n, p, is_normal
            )
            return is_normal, f"Shapiro-Wilk (p={p:.3f})"

        if n < 5_000:
            _, p = normaltest(data)
            is_normal = p >= self.alpha
            logger.debug(
                "D'Agostino-Pearson: n=%d  p=%.4f  normal=%s", n, p, is_normal
            )
            return is_normal, f"D'Agostino-Pearson (p={p:.3f})"

        # Large n — moment-based criterion
        s = float(abs(skew(data)))
        k = float(abs(kurtosis(data)))  # excess kurtosis
        is_normal = s < self.skew_threshold and k < self.kurt_threshold
        logger.debug(
            "Moment-based: n=%d  |skew|=%.3f  |kurt|=%.3f  normal=%s",
            n, s, k, is_normal,
        )
        return is_normal, f"Moment-based (|skew|={s:.2f}, |kurt|={k:.2f})"

    def all_normal(self, groups: Iterable[pd.Series]) -> bool:
        """Return True only if **all** group Series pass the normality test."""
        return all(self.test(g)[0] for g in groups)
