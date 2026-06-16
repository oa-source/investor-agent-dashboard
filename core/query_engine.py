import pandas as pd


df = pd.read_csv(
    "lp_funds_filtered.csv"
)


def to_float(value):

    try:
        return float(value)
    except:
        return 0


def search_funds():

    print("\nINVESTOR INTELLIGENCE SEARCH\n")

    strategy = input(
        "Sub-strategy (buyout / growth_equity / venture_capital): "
    ).strip().lower()

    geography = input(
        "Geography (optional): "
    ).strip().lower()

    min_tvpi = input(
        "Minimum TVPI (optional): "
    ).strip()

    min_irr = input(
        "Minimum IRR (optional): "
    ).strip()

    min_vintage = input(
        "Minimum vintage year (optional): "
    ).strip()

    filtered = df.copy()

    if strategy:

        filtered = filtered[
            filtered["sub_strategy"]
            .astype(str)
            .str.lower()
            == strategy
        ]

    if geography:

        filtered = filtered[
            filtered["geography"]
            .astype(str)
            .str.lower()
            .str.contains(geography)
        ]

    if min_tvpi:

        filtered = filtered[
            filtered["tvpi_max"]
            .apply(to_float)
            >= float(min_tvpi)
        ]

    if min_irr:

        filtered = filtered[
            filtered["irr_max"]
            .apply(to_float)
            >= float(min_irr)
        ]

    if min_vintage:

        filtered = filtered[
            filtered["vintage_year"]
            .apply(to_float)
            >= float(min_vintage)
        ]

    filtered["score"] = (
        filtered["irr_max"].apply(to_float) * 40 +
        filtered["tvpi_max"].apply(to_float) * 30 +
        filtered["dpi_max"].apply(to_float) * 30
    )

    filtered = filtered.sort_values(
        by="score",
        ascending=False
    )

    results = filtered.head(25)

    print("\nTOP MATCHES:\n")

    if len(results) == 0:

        print("No matching funds found.")
        return

    columns = [
        "fund_name",
        "manager_name",
        "sub_strategy",
        "geography",
        "vintage_year",
        "irr_max",
        "tvpi_max",
        "dpi_max",
        "score"
    ]

    print(results[columns])

    results.to_csv(
        "query_results.csv",
        index=False
    )

    print("\nSaved query_results.csv")


search_funds()