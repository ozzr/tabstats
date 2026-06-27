"""
tabstat/layouts.py
──────────────────
Layout system for table column structure.

A Layout defines which columns appear and in what order, plus how each
row type (header, metric sub-row, category row) is assembled from tokens.

Token vocabulary
----------------
_        empty cell
char     variable name / label
n_valid  N valid (%) for this variable — for a dedicated column or inline
group    statistic per group — expands to N actual columns
total    overall statistic or N valid for the total column
p        p-value
test     statistical test name
smd      standardised mean difference
metric   metric label (continuous sub-row, indented; repeats per metric)
cat      category label (indented; repeats per category)
missing  missing-data row (emitted only when missings > 0; repeats once)

Usage
-----
>>> layout = Layout.from_preset("no_cases")
>>> layout = Layout.from_preset("standard").without_column("test")
>>> gen.generate(df, formula, layout=layout)
"""
from __future__ import annotations

from copy import deepcopy
from typing import Dict, List, Optional

VALID_COLUMNS = ["char", "n_valid", "group", "total", "p", "test", "smd"]
LOCKED_COLUMNS = frozenset({"char", "group", "total"})

_REPEAT: Dict[str, str] = {
    "cat":     "category",
    "metric":  "metric",
    "missing": "missing",
}


class RowTemplate:
    """
    One output row per variable.

    ``tokens[i]`` maps to the i-th active column in the parent Layout.
    The *repeat_type* property controls whether the row is emitted once or
    repeated (once per metric spec, once per category, or once if missings > 0).
    """

    __slots__ = ("tokens",)

    def __init__(self, tokens: List[str]) -> None:
        self.tokens = list(tokens)

    @property
    def repeat_type(self) -> Optional[str]:
        for tok, rtype in _REPEAT.items():
            if tok in self.tokens:
                return rtype
        return None

    def token_at(self, col_idx: int) -> str:
        return self.tokens[col_idx] if col_idx < len(self.tokens) else "_"

    def __repr__(self) -> str:  # pragma: no cover
        return f"RowTemplate({self.tokens})"


class Layout:
    """
    Defines how continuous and categorical variables are laid out.

    Parameters
    ----------
    columns     : ordered list of active logical column IDs
    continuous  : list of row templates for continuous variables
    categorical : list of row templates for categorical variables
    name        : optional preset name (informational only)

    Fluent builder
    --------------
    >>> layout = Layout.from_preset("no_cases").without_column("test")
    >>> gen.generate(df, formula, layout=layout)

    Custom from scratch
    -------------------
    >>> from tabstat import Layout
    >>> layout = (
    ...     Layout(
    ...         columns     = ["char", "n_valid", "group", "total", "p"],
    ...         continuous  = [["char", "n_valid", "group", "total", "p"]],
    ...         categorical = [
    ...             ["char", "n_valid", "_",     "_",     "p"],
    ...             ["cat",  "_",       "group", "total", "_"],
    ...         ],
    ...     )
    ... )
    """

    def __init__(
        self,
        columns:     List[str],
        continuous:  List[List[str]],
        categorical: List[List[str]],
        name:        Optional[str] = None,
    ) -> None:
        self._columns     = list(columns)
        self._continuous  = [RowTemplate(r) for r in continuous]
        self._categorical = [RowTemplate(r) for r in categorical]
        self._name        = name

    # ── Read-only properties ──────────────────────────────────────────────────

    @property
    def columns(self) -> List[str]:
        return list(self._columns)

    @property
    def continuous(self) -> List[RowTemplate]:
        return list(self._continuous)

    @property
    def categorical(self) -> List[RowTemplate]:
        return list(self._categorical)

    @property
    def name(self) -> Optional[str]:
        return self._name

    def col_idx(self, col_id: str) -> Optional[int]:
        """Return the index of *col_id* in the active columns list, or None."""
        try:
            return self._columns.index(col_id)
        except ValueError:
            return None

    def has_column(self, col_id: str) -> bool:
        return col_id in self._columns

    # ── Fluent builder ────────────────────────────────────────────────────────

    def without_column(self, *col_ids: str) -> "Layout":
        """
        Return a new Layout with the specified columns removed.

        Locked columns (char, group, total) are silently ignored.
        """
        remove    = set(col_ids) - LOCKED_COLUMNS
        drop_idxs = {i for i, c in enumerate(self._columns) if c in remove}
        new_cols  = [c for c in self._columns if c not in remove]

        def _strip(rows: List[RowTemplate]) -> List[List[str]]:
            return [
                [tok for i, tok in enumerate(r.tokens) if i not in drop_idxs]
                for r in rows
            ]

        return Layout(new_cols, _strip(self._continuous), _strip(self._categorical))

    def with_column(self, col_id: str, after: Optional[str] = None) -> "Layout":
        """
        Return a new Layout with *col_id* added (all row templates get a blank
        token for that column).  Uses canonical column order when *after* is not
        specified.
        """
        if col_id in self._columns:
            return self
        if col_id not in VALID_COLUMNS:
            raise ValueError(
                f"Unknown column {col_id!r}. Valid: {VALID_COLUMNS}"
            )

        if after and after in self._columns:
            ins = self._columns.index(after) + 1
        else:
            canon = VALID_COLUMNS.index(col_id)
            ins   = len(self._columns)
            for i, c in enumerate(self._columns):
                if VALID_COLUMNS.index(c) > canon:
                    ins = i
                    break

        new_cols = self._columns[:ins] + [col_id] + self._columns[ins:]

        def _expand(rows: List[RowTemplate]) -> List[List[str]]:
            return [[*r.tokens[:ins], "_", *r.tokens[ins:]] for r in rows]

        return Layout(new_cols, _expand(self._continuous), _expand(self._categorical))

    def continuous_rows(self, *rows: List[str]) -> "Layout":
        """Return a new Layout with continuous row templates replaced."""
        return Layout(
            self._columns,
            list(rows),
            [r.tokens for r in self._categorical],
        )

    def categorical_rows(self, *rows: List[str]) -> "Layout":
        """Return a new Layout with categorical row templates replaced."""
        return Layout(
            self._columns,
            [r.tokens for r in self._continuous],
            list(rows),
        )

    # ── Preset factory ────────────────────────────────────────────────────────

    @classmethod
    def from_preset(cls, name: str) -> "Layout":
        """
        Load a named layout preset.

        Presets
        -------
        "standard"  Default.  Continuous: header row + metric sub-row(s).
                    Categorical: header row + per-category rows.
        "no_cases"  Dedicated N valid column; continuous stats on a single
                    inline row (no sub-row).  One metric only.
        "compact"   Like standard but without the Test column.
        "full"      All columns: n_valid, groups, total, p, test, smd.
        """
        if name not in _PRESETS:
            raise ValueError(
                f"Unknown layout preset {name!r}. "
                f"Available: {list(_PRESETS)}"
            )
        return deepcopy(_PRESETS[name])

    @classmethod
    def available_presets(cls) -> List[str]:
        """Return the list of built-in preset names."""
        return list(_PRESETS.keys())

    def __repr__(self) -> str:  # pragma: no cover
        n = f"'{self._name}'" if self._name else "custom"
        return (
            f"Layout({n}, columns={self._columns}, "
            f"continuous={len(self._continuous)} rows, "
            f"categorical={len(self._categorical)} rows)"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Built-in preset definitions
# ─────────────────────────────────────────────────────────────────────────────
#
# Token position maps to the column at the same index in `columns`.
# "group" column expands to N actual data columns (one per group).
# "total" column may expand to 2 when split_count_pct=True.
#
# For continuous header rows without "metric" token: the template sets up the
# variable label row.  "n_valid" in the total column position shows the
# per-variable N valid string there (token resolved by generator).
#
# For categorical, the header row template should include "p"/"test" tokens
# if you want pvalue_span injection (grid mode) / direct fill (df mode).

def _make(name: str, cols: List[str],
          cont:  List[List[str]],
          cat:   List[List[str]]) -> Layout:
    return Layout(cols, cont, cat, name=name)


_PRESETS: Dict[str, Layout] = {

    # ── standard ─────────────────────────────────────────────────────────────
    # Reproduces the existing default TabStat layout exactly.
    # Continuous: header row (n valid in total col) + metric sub-row(s).
    # Categorical: header row (n valid + p + test) + per-category rows.
    "standard": _make(
        "standard",
        cols=["char", "group", "total", "p", "test"],
        cont=[
            ["char",   "_",     "n_valid", "_",    "_"   ],  # header row
            ["metric", "group", "total",   "p",    "test"],  # sub-row per metric
        ],
        cat=[
            ["char",   "_",     "n_valid", "p",    "test"],  # header row
            ["cat",    "group", "total",   "_",    "_"   ],  # per category
        ],
    ),

    # ── no_cases ─────────────────────────────────────────────────────────────
    # Dedicated "N valid" column between Characteristic and groups.
    # Continuous: single inline row (stat + n_valid on the same line).
    # Categorical: header shows n_valid + p + test; categories show stats.
    "no_cases": _make(
        "no_cases",
        cols=["char", "n_valid", "group", "total", "p", "test"],
        cont=[
            ["char",  "n_valid", "group", "total", "p",    "test"],  # inline row
        ],
        cat=[
            ["char",  "n_valid", "_",     "_",     "p",    "test"],  # header
            ["cat",   "_",       "group", "total", "_",    "_"   ],  # per category
        ],
    ),

    # ── compact ──────────────────────────────────────────────────────────────
    # Like standard but without the Test name column.
    "compact": _make(
        "compact",
        cols=["char", "group", "total", "p"],
        cont=[
            ["char",   "_",     "n_valid", "_"],
            ["metric", "group", "total",   "p"],
        ],
        cat=[
            ["char",   "_",     "n_valid", "p"],
            ["cat",    "group", "total",   "_"],
        ],
    ),

    # ── full ─────────────────────────────────────────────────────────────────
    # All columns: dedicated n_valid, groups, total, p, test, smd.
    "full": _make(
        "full",
        cols=["char", "n_valid", "group", "total", "p", "test", "smd"],
        cont=[
            ["char",   "n_valid", "_",     "_",     "_", "_",    "_"  ],
            ["metric", "_",       "group", "total", "p", "test", "smd"],
        ],
        cat=[
            ["char",   "n_valid", "_",     "_",     "p", "test", "_"  ],
            ["cat",    "_",       "group", "total", "_", "_",    "smd"],
        ],
    ),
}
