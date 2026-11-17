import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rfm import clean_transactions  # noqa: E402


def test_clean_keeps_only_the_valid_row():
    raw = pd.DataFrame({
        "customer_id": [1001, 1002, 1003, 1004],
        "invoice_id": [1, 2, 3, 4],
        "invoice_date": ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04"],
        "quantity": [2, -1, 1, 1],
        "unit_price": [10.0, 5.0, 0.0, 7.5],
    })
    raw.loc[3, "customer_id"] = None

    clean = clean_transactions(raw)

    assert len(clean) == 1
    assert clean.iloc[0]["customer_id"] == 1001
    assert clean.iloc[0]["revenue"] == 20.0
