import pandas as pd

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPILFESL"

df = pd.read_csv(URL, index_col=0, parse_dates=True)
df.columns = ["core_cpi_index"]
df["core_mom_pct"] = df["core_cpi_index"].pct_change() * 100

print(df.tail(8).round(3))