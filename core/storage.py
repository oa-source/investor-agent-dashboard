import pandas as pd
import os


CSV_FILE = "investor_data.csv"


def save_data(rows):

    if not rows:
        return

    df = pd.DataFrame(rows)

    if os.path.exists(CSV_FILE):

        old_df = pd.read_csv(CSV_FILE)

        df = pd.concat([old_df, df])

    df.drop_duplicates(inplace=True)

    df.to_csv(CSV_FILE, index=False)

    print("\nDATA SAVED.")