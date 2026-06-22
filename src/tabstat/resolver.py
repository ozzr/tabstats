"""
tabstat/resolver.py
───────────────────
Hierarchical resolution of which statistical test to use.

Priority (highest → lowest):
  1. per_variable  — exact variable name
  2. per_group     — any matching grouping column name (first match wins)
  3. per_type      — variable type ('numeric' | 'categorical')
  4. default       — global fallback
"""
from __future__ import annotations

import logging
from typing import List

from .config import TestOverrideConfig

logger = logging.getLogger(__name__)


class TestResolver:
    """
    Resolves the statistical test token for a given variable context.

    Parameters
    ----------
    overrides : TestOverrideConfig
        The override specification (see config.py).
    """

    def __init__(self, overrides: TestOverrideConfig) -> None:
        self.ov = overrides

    def resolve(self, var: str, group_cols: List[str], var_type: str) -> str:
        """
        Return the test token that should be used.

        Parameters
        ----------
        var       : variable name
        group_cols: list of grouping column names in the formula
        var_type  : 'numeric' | 'categorical'

        Returns
        -------
        str — one of the valid test tokens defined in TestOverrideConfig.
        """
        # Level 1 — per variable (highest priority)
        if var in self.ov.per_variable:
            token = self.ov.per_variable[var]
            logger.debug("[Resolver] %s → per_variable → %s", var, token)
            return token

        # Level 2 — per grouping column (first match wins)
        for g in group_cols:
            if g in self.ov.per_group:
                token = self.ov.per_group[g]
                logger.debug(
                    "[Resolver] %s → per_group[%s] → %s", var, g, token
                )
                return token

        # Level 3 — per variable type
        if var_type in self.ov.per_type:
            token = self.ov.per_type[var_type]
            logger.debug(
                "[Resolver] %s → per_type[%s] → %s", var, var_type, token
            )
            return token

        # Level 4 — global default
        logger.debug("[Resolver] %s → default → %s", var, self.ov.default)
        return self.ov.default
