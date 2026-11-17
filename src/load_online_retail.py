from pathlib import Path

import pandas as pd

SHEET_2010_2011 = "Year 2010-2011"

COLUMN_MAP = {
    "Invoice": "invoice_id",
    "StockCode": "product_code",
    "Description": "description",
    "Quantity": "quantity",
    "InvoiceDate": "invoice_date",
    "Price": "unit_price",
    "Customer ID": "customer_id",
    "Country": "country",
}

REQUIRED = ["customer_id", "invoice_id", "invoice_date", "quantity", "unit_price"]


def load_online_retail(path: str | Path, sheet: str | None = SHEET_2010_2011) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Could not find the Excel file: {path}\n"
            "Download it from https://archive.ics.uci.edu/dataset/502/online+retail+ii "
            "and save it there."
        )

    raw = pd.read_excel(path, sheet_name=sheet if sheet is not None else 0)

    raw = raw.rename(columns={"CustomerID": "Customer ID"})

    missing = [name for name in COLUMN_MAP if name not in raw.columns]
    if missing:
        raise ValueError(
            "The Excel file is missing these columns: " + ", ".join(missing)
        )

    df = raw.rename(columns=COLUMN_MAP)

    extra = [c for c in df.columns if c not in REQUIRED]
    df = df[REQUIRED + extra]

    invoice_text = df["invoice_id"].astype(str)
    is_cancellation = invoice_text.str.startswith("C")
    df = df[~is_cancellation]

    df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")

    return df.reset_index(drop=True)


def describe(path: str | Path, sheet: str | None = SHEET_2010_2011) -> None:
    df = load_online_retail(path, sheet)
    print(f"Rows read: {len(df):,}")
    print(f"Date range: {df['invoice_date'].min()} to {df['invoice_date'].max()}")
    print(f"Customers: {df['customer_id'].nunique():,}")


if __name__ == "__main__":
    describe("data/online_retail_II.xlsx")
