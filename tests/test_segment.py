import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from segment import name_segments, scale_features  # noqa: E402


def _make_rfm():
    return pd.DataFrame({
        "customer_id": [1, 2, 3, 4],
        "recency": [1, 30, 90, 300],
        "frequency": [20, 9, 3, 1],
        "monetary": [5000.0, 900.0, 200.0, 50.0],
    })


def test_scaled_shape_and_mean():
    X = scale_features(_make_rfm())

    assert X.shape[0] == 4
    for column in range(X.shape[1]):
        assert abs(X[:, column].mean()) < 1e-9


def test_names_are_unique():
    rfm = _make_rfm()
    rfm["cluster"] = [0, 0, 1, 1]
    names = name_segments(rfm)

    assert len(names) == 2
    assert len(set(names.values())) == len(names)
