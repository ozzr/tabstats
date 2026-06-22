import pandas as pd
from tabstat import tabstat

df = pd.DataFrame({'sex': ['M', 'F', 'M', 'F'], 'outcome': [0, 1, 0, 1], 'age': [30, 25, 40, 35]})
result = tabstat(df, 'sex | outcome', tablefmt='grid', show=False, title='Table 1', footnote='IQR note')
print('shape', result.shape)
print('columns:', list(result.columns))
print('row0:', result.iloc[0].tolist())
print('row1:', result.iloc[1].tolist())
print('row_last:', result.iloc[-1].tolist())
print(result)
