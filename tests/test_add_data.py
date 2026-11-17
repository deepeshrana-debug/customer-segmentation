import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd  # noqa: E402

from summary import (  # noqa: E402
    BIG_SPENDER_TOP_PERCENT,
    MOST_ORDERS,
    REGULAR_ORDERS,
    build_rfm,
    count_big_spenders,
    count_bought_last_month,
    count_frequent_buyers,
    count_least_buyers,
    count_most_buyers,
    count_regular_buyers,
    count_total_buyers,
    file_numbers,
    find_columns,
    parse_list,
    percentages,
    read_upload,
    run_segmentation,
    total_revenue,
)

SAMPLE_CSV = """customer_id,invoice_id,invoice_date,quantity,unit_price
C1,I1,2024-03-09,1,10
C1,I2,2024-03-09,1,10
C1,I3,2024-03-08,1,10
C1,I4,2024-03-08,1,10
C1,I5,2024-03-07,1,10
C1,I6,2024-03-07,1,10
C1,I7,2024-03-06,1,10
C1,I8,2024-03-06,1,10
C1,I9,2024-03-05,1,10
C1,I10,2024-03-05,1,10
C1,I11,2024-03-04,1,10
C1,I12,2024-03-04,1,10
C2,I13,2024-01-02,2,5
C3,I14,2024-03-01,1,20
C3,I15,2024-02-20,1,20
C3,I16,2024-02-15,1,20
C4,I17,2023-12-01,1,7
C4,I18,2023-12-01,1,7
C4,I19,2023-12-01,1,7
C4,I20,2023-12-01,1,7
C4,I21,2023-12-01,1,7
C4,I22,2023-12-01,1,7
C4,I23,2023-12-01,1,7
C4,I24,2023-12-01,1,7
C4,I25,2023-12-01,1,7
C4,I26,2023-12-01,1,7
, I27,2024-03-01,1,10
C1,I28,2024-03-01,-1,10
C1,I29,2024-03-01,1,0
C1,I30,not-a-date,1,10
"""


def sample_frame() -> pd.DataFrame:
    result = read_upload(SAMPLE_CSV.encode("utf-8"))
    assert result["error"] is None
    return result["clean"]


def test_column_names_are_matched_loosely():
    headers = ["Customer ID", "Invoice", "InvoiceDate", "Qty", "Price"]
    mapping, missing = find_columns(headers)

    assert missing == []
    assert mapping["customer_id"] == "Customer ID"
    assert mapping["invoice_id"] == "Invoice"
    assert mapping["invoice_date"] == "InvoiceDate"
    assert mapping["unit_price"] == "Price"


def test_missing_column_is_named():
    result = read_upload(b"invoice_id,invoice_date,quantity,unit_price\nI1,2024-01-01,1,5\n")
    assert result["error"] == "The file needs a column for the customer ID."


def test_empty_file_is_reported():
    empty_csv = b"customer_id,invoice_id,invoice_date,quantity,unit_price\n"
    result = read_upload(empty_csv)
    assert result["error"] == "This file has no rows. Please check the file and try again."


def test_cleaning_counts_every_reason():
    report = read_upload(SAMPLE_CSV.encode("utf-8"))["report"]

    assert report["rows_read"] == 30
    assert report["no_customer_id"] == 1
    assert report["returns"] == 1
    assert report["bad_price"] == 1
    assert report["bad_date"] == 1
    assert report["rows_used"] == 26
    assert report["rows_removed"] == 4
    assert report["rows_read"] - report["rows_removed"] == report["rows_used"]


def test_no_valid_rows_after_cleaning():
    text = "customer_id,invoice_id,invoice_date,quantity,unit_price\n, I1,2024-01-01,1,5\n"
    result = read_upload(text.encode("utf-8"))
    assert result["error"] == "No valid rows were found after cleaning."


def test_a_broken_file_does_not_crash():
    result = read_upload(b"\xff\xfe\x00\x00broken")
    assert result["error"] is not None


def test_each_count():
    clean = sample_frame()
    orders = clean.groupby("customer_id")["invoice_id"].nunique()
    spend = clean.groupby("customer_id")["revenue"].sum()

    assert count_total_buyers(clean) == 4
    assert count_most_buyers(orders) == 2
    assert count_regular_buyers(orders) == 1
    assert count_least_buyers(orders) == 1
    assert count_frequent_buyers(orders) == 1
    assert count_big_spenders(spend) == 1


def test_bought_last_month_uses_the_files_own_latest_date():
    assert count_bought_last_month(sample_frame()) == 2


def test_total_revenue():
    assert total_revenue(sample_frame()) == 260.0


def test_thresholds_come_from_the_settings():
    orders = pd.Series([1, 5, 9, 10, 12])
    assert MOST_ORDERS == 10
    assert REGULAR_ORDERS == 3
    assert count_most_buyers(orders) == 2
    assert count_regular_buyers(orders) == 2


def test_file_numbers_are_one_dict():
    numbers = file_numbers(sample_frame())
    assert numbers["total"] == 4
    assert numbers["not_last_month"] == 2
    assert numbers["revenue"] == 260.0


def test_percentages_of_file_numbers():
    numbers = file_numbers(sample_frame())
    shares = percentages(numbers)
    assert shares["most"] == 50.0
    assert shares["least"] == 25.0


def test_segments_use_the_four_plain_names():
    result = run_segmentation(sample_frame())
    assert result["available"] is True
    assert len(result["segments"]) == 4
    for row in result["segments"]:
        assert row["segment"] in [
            "Best buyers", "Good buyers", "Buyers at risk", "Inactive buyers",
        ]
    assert sum(row["customers"] for row in result["segments"]) == 4


def test_rfm_has_one_row_per_buyer():
    rfm = build_rfm(sample_frame())
    assert len(rfm) == 4
    assert list(rfm.columns) == ["customer_id", "recency", "frequency", "monetary"]


def test_too_few_buyers_for_segments():
    text = "customer_id,invoice_id,invoice_date,quantity,unit_price\n"
    text += "".join(f"C{i},I{i},2024-01-0{i},1,5\n" for i in (1, 2, 3))
    result = read_upload(text.encode("utf-8"))
    segmented = run_segmentation(result["clean"])
    assert segmented["available"] is False
    assert segmented["message"]


def test_typed_percentage():
    assert percentages({"total": 1000, "most": 233})["most"] == 23.3


def test_parse_list_matches_names_loosely():
    text = "  MOST BUYERS : 233\n  regular buyers  :  433\nbought last month: 24"
    values, unknown = parse_list(text)
    assert values == {"most": 233, "regular": 433, "last_month": 24}
    assert unknown == []


def test_parse_list_reports_unknown_lines():
    values, unknown = parse_list("Most buyers: 233\nhello there\nLeast buyers: many")
    assert values == {"most": 233}
    assert unknown == ["hello there", "Least buyers: many"]


if __name__ == "__main__":
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                passed += 1
                print(f"PASS {name}")
            except AssertionError as exc:
                failed += 1
                print(f"FAIL {name}: {exc}")
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
