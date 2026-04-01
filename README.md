# tabstats

Genera tablas descriptivas listas para publicación (Tabla 1) en investigación clínica y epidemiológica.

## Instalación

Requiere Python 3.9+.

Usa pip:

```bash
python -m pip install .
# o para instalar desde PyPI:
# pip install tabstat
```

Dependencias automáticas:
- pandas>=1.5
- numpy>=1.23
- scipy>=1.9
- tabulate>=0.9

Instalación de pruebas/desarrollo:

```bash
python -m pip install -e .[dev]
```

## Uso

```python
import pandas as pd
from tabstat import tabstat, TestOverrideConfig

df = pd.DataFrame({
    'age': [25, 40, 60, 35, 50],
    'sex': [0, 1, 1, 0, 0],
    'outcome': [1, 0, 1, 0, 1],
    'creat': [88, 102, 130, 90, 110],
})

result = tabstat(
    df,
    "~ . | outcome",
    tablefmt="grid",
    display_smd=True,
    test_overrides=TestOverrideConfig.preset("clinical_descriptive"),
)
print(result)
```

## Construcción de paquete

```bash
python -m build
python setup.py sdist bdist_wheel
```

## Paquete

El código fuente está en `src/tabstat`.
