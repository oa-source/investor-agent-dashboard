import requests
import pandas as pd
import time


API_URL = "https://api.lp-data.com/funds"


TARGET_SUBSTRATEGIES = [
    "buyout",
    "growth_equity",
    "venture_capital"
]


def clean(value):

    if value is None:
        return ""

    return str(value).strip()


all_rows = []

skip = 0

limit = 100


while True:

    print(f"\nFetching batch starting at {skip}...")

    params = {
        "skip": skip,
        "limit": limit
    }

    try:

        response = requests.get(
            API_URL,
            params=params,
            timeout=30
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code != 200:

            print("Request failed")
            break

        data = response.json()

        funds = data.get("items", [])

        if not funds:

            print("\nNo more funds found.")
            break

        filtered_count = 0

        for fund in funds:

            sub_strategy = clean(
                fund.get("sub_strategy")
            ).lower()

            if sub_strategy not in TARGET_SUBSTRATEGIES:
                continue

            row = {

                "fund_id": clean(
                    fund.get("fund_id")
                ),

                "fund_name": clean(
                    fund.get("name")
                ),

                "manager_name": clean(
                    fund.get("manager_name")
                ),

                "strategy": clean(
                    fund.get("strategy")
                ),

                "sub_strategy": sub_strategy,

                "geography": clean(
                    fund.get("geography")
                ),

                "vintage_year": clean(
                    fund.get("vintage_year")
                ),

                "lp_count": clean(
                    fund.get("lp_count")
                ),

                "irr_min": clean(
                    fund.get("irr_min")
                ),

                "irr_max": clean(
                    fund.get("irr_max")
                ),

                "tvpi_min": clean(
                    fund.get("tvpi_min")
                ),

                "tvpi_max": clean(
                    fund.get("tvpi_max")
                ),

                "dpi_min": clean(
                    fund.get("dpi_min")
                ),

                "dpi_max": clean(
                    fund.get("dpi_max")
                ),

                "gross_asset_value_usd": clean(
                    fund.get("gross_asset_value_usd")
                ),

                "final_close_size_usd": clean(
                    fund.get("final_close_size_usd")
                ),

                "latest_as_of_date": clean(
                    fund.get("latest_as_of_date")
                )
            }

            all_rows.append(row)

            filtered_count += 1

        print(
            f"Saved {filtered_count} matching funds"
        )

        has_more = data.get("has_more", False)

        if not has_more:

            print("\nReached end of dataset.")
            break

        skip += limit

        time.sleep(1)

    except Exception as e:

        print("\nERROR:")
        print(e)
        break


df = pd.DataFrame(all_rows)

filename = "lp_funds_filtered.csv"

df.to_csv(
    filename,
    index=False
)

print("\nDONE")
print(f"Total rows saved: {len(df)}")
print(f"Saved to: {filename}")