import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from churn import churn_summary  # noqa: E402


def test_churn_counts_customers_past_each_period():
    rfm = pd.DataFrame({"recency": [10, 100, 200, 400]})
    result = churn_summary(rfm).set_index("days")

    assert result.loc[90, "churned_customers"] == 3
    assert result.loc[90, "churn_pct"] == 75.0
    assert result.loc[180, "churned_customers"] == 2
    assert result.loc[180, "churn_pct"] == 50.0
    assert result.loc[365, "churned_customers"] == 1
    assert result.loc[365, "churn_pct"] == 25.0


def test_loader_renames_and_drops_cancellations(tmp_path):
    from load_online_retail import load_online_retail

    raw = pd.DataFrame({
        "Invoice": ["536365", "536366", "C536379"],
        "StockCode": ["A", "B", "C"],
        "Description": ["Mug", "Plate", "Broken"],
        "Quantity": [6, 6, -1],
        "InvoiceDate": ["2010-12-01 08:26", "2010-12-01 08:28", "2010-12-01 09:41"],
        "Price": [2.55, 3.39, 1.00],
        "Customer ID": [13085, 13086, 13086],
        "Country": ["UK", "UK", "UK"],
    })
    path = tmp_path / "retail.xlsx"
    raw.to_excel(path, index=False, sheet_name="Year 2010-2011")

    df = load_online_retail(path, sheet="Year 2010-2011")

    for name in ["customer_id", "invoice_id", "invoice_date", "quantity", "unit_price"]:
        assert name in df.columns
    assert len(df) == 2
    assert not df["invoice_id"].astype(str).str.startswith("C").any()
    assert pd.api.types.is_datetime64_any_dtype(df["invoice_date"])
