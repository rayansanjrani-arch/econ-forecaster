import pandas as pd
from config import CORE_CPI_SERIES, fred_csv_url

URL = fred_csv_url(CORE_CPI_SERIES)

df = pd.read_csv(URL, index_col=0, parse_dates=True)
df.columns = ["core_cpi_index"]
df["core_mom_pct"] = df["core_cpi_index"].pct_change() * 100

print(df.tail(8).round(3))
