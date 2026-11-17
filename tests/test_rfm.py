import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rfm import add_score_columns, build_rfm  # noqa: E402


def _make_clean():
    return pd.DataFrame({
        "customer_id": [1, 1, 2, 2],
        "invoice_id": [10, 11, 20, 21],
        "invoice_date": pd.to_datetime([
            "2025-01-01", "2025-01-10",
            "2025-01-05", "2025-01-20",
        ]),
        "quantity": [2, 3, 1, 1],
        "unit_price": [10.0, 10.0, 5.0, 5.0],
        "revenue": [20.0, 30.0, 5.0, 5.0],
    })


def test_rfm_values_by_hand():
    rfm = build_rfm(_make_clean()).set_index("customer_id")

    assert rfm.loc[1, "recency"] == 11
    assert rfm.loc[1, "frequency"] == 2
    assert rfm.loc[2, "frequency"] == 2
    assert rfm.loc[1, "monetary"] == 50.0
    assert rfm.loc[2, "monetary"] == 10.0
    assert rfm.loc[2, "recency"] == 1


def test_scores_best_customer_gets_five():
    rows = []
    for i in range(1, 21):
        rows.append({
            "customer_id": i,
            "recency": i,
            "frequency": i,
            "monetary": i * 100.0,
        })
    scored = add_score_columns(pd.DataFrame(rows)).set_index("customer_id")

    assert scored.loc[1, "R_score"] == 5
    assert scored.loc[20, "M_score"] == 5
    assert scored.loc[20, "R_score"] == 1
    for column in ["R_score", "F_score", "M_score"]:
        assert scored[column].between(1, 5).all()
    assert scored.loc[20, "RFM_code"] == "155"
