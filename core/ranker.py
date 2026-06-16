import pandas as pd


df = pd.read_csv(
    "lp_funds_filtered.csv"
)


def to_float(value):

    try:
        return float(value)
    except:
        return 0


df["irr_score"] = df["irr_max"].apply(to_float)

df["tvpi_score"] = df["tvpi_max"].apply(to_float)

df["dpi_score"] = df["dpi_max"].apply(to_float)

df["score"] = (
    df["irr_score"] * 40 +
    df["tvpi_score"] * 30 +
    df["dpi_score"] * 30
)


ranked = df.sort_values(
    by="score",
    ascending=False
)


top = ranked.head(100)


top.to_csv(
    "top_funds.csv",
    index=False
)


print("\nTOP FUNDS\n")

print(
    top[
        [
            "fund_name",
            "manager_name",
            "sub_strategy",
            "vintage_year",
            "irr_max",
            "tvpi_max",
            "dpi_max",
            "score"
        ]
    ]
)

print("\nSaved top_funds.csv")