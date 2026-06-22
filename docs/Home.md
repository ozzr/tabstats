# tabstat

**Publication-ready Table 1 for clinical and epidemiological research.**

`tabstat` automates the standard descriptive statistics table found in most
clinical papers — the one that characterises your cohort and tests for group
differences. It handles variable detection, test selection, formatting, and
export in a single function call.

This wiki is generated from the [`docs/`](https://github.com/ozzr/tabstats/tree/main/docs)
folder on every push to `main` — edit the source files there, not here.

## Pages

- [API Reference](API-reference) — every public function and class, with signatures and examples
- [Configuration Reference](Configuration) — every `TabStatConfig` field, organised by category
- [Examples Gallery](Examples) — runnable examples covering every major feature

## Quick start

```python
import pandas as pd
from tabstat import tabstat

t = tabstat(df, "age + sex + creatinine | outcome")
```

See the [project README](https://github.com/ozzr/tabstats#readme) for
installation and a feature overview.
