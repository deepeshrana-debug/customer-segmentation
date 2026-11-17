from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

MOST_ORDERS = 10
REGULAR_ORDERS = 3
LEAST_ORDERS = 1
LAST_MONTH_DAYS = 30
FREQUENT_TOP_PERCENT = 20
BIG_SPENDER_TOP_PERCENT = 10

REQUIRED_COLUMNS = [
    "customer_id",
    "invoice_id",
    "invoice_date",
    "quantity",
    "unit_price",
]

COLUMN_ALIASES = {
    "customer_id": [
        "customer id", "customerid", "customer", "customerno", "customer no",
        "customer number", "client id", "user id", "buyer id", "id",
    ],
    "invoice_id": [
        "invoice id", "invoiceid", "invoice", "invoice no", "invoice number",
        "order id", "order no", "order number", "order", "bill no",
    ],
    "invoice_date": [
        "invoice date", "invoicedate", "date", "order date", "orderdate",
        "purchase date", "transaction date", "datetime",
    ],
    "quantity": ["quantity", "qty", "units", "amount", "count", "items"],
    "unit_price": [
        "unit price", "unitprice", "price", "price each", "unit cost", "cost",
        "rate",
    ],
}

COLUMN_PLAIN_NAMES = {
    "customer_id": "customer ID",
    "invoice_id": "invoice or order number",
    "invoice_date": "date of the purchase",
    "quantity": "quantity (how many were bought)",
    "unit_price": "price of one item",
}

SEGMENT_NAMES = ["Best buyers", "Good buyers", "Buyers at risk", "Inactive buyers"]

TYPED_KEYS = ["total", "most", "regular", "least", "frequent", "last_month", "big_spenders"]

FIELDS = [
    ("total", "Total buyers", "How many people bought from you in total?"),
    ("most", "Most buyers", f"How many placed {MOST_ORDERS} or more orders?"),
    ("regular", "Regular buyers", f"How many placed {REGULAR_ORDERS} to {MOST_ORDERS - 1} orders?"),
    ("least", "Least buyers", "How many placed only 1 order?"),
    ("frequent", "Frequent buyers", f"How many are in your busiest {FREQUENT_TOP_PERCENT}% of buyers?"),
    ("last_month", "Bought last month", "How many people bought last month?"),
    ("big_spenders", "Big spenders", f"How many are in your top {BIG_SPENDER_TOP_PERCENT}% by spend?"),
]

NAME_ALIASES = {
    "total buyers": "total",
    "total": "total",
    "most buyers": "most",
    "most": "most",
    "regular buyers": "regular",
    "regular": "regular",
    "least buyers": "least",
    "least": "least",
    "frequent buyers": "frequent",
    "frequent": "frequent",
    "bought last month": "last_month",
    "last month": "last_month",
    "big spenders": "big_spenders",
    "did not buy last month": "not_last_month",
    "total revenue": "revenue",
}

DOCUMENT_KINDS = {
    ".txt": "text",
    ".text": "text",
    ".md": "text",
    ".csv": "text",
    ".docx": "word",
    ".pdf": "pdf",
}


def document_kind(filename: str) -> str | None:
    name = str(filename or "").lower().strip()
    for ending, kind in DOCUMENT_KINDS.items():
        if name.endswith(ending):
            return kind
    return None


def _text_from_word(file_bytes: bytes) -> str:
    import io as _io

    import docx

    document = docx.Document(_io.BytesIO(file_bytes))
    lines = [paragraph.text for paragraph in document.paragraphs]

    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            cells = [cell for cell in cells if cell]
            if len(cells) >= 2:
                lines.append(f"{cells[0]}: {' '.join(cells[1:])}")
            elif cells:
                lines.append(cells[0])

    return "\n".join(lines)


def _text_from_pdf(file_bytes: bytes) -> str:
    import io as _io

    from pypdf import PdfReader

    reader = PdfReader(_io.BytesIO(file_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def read_document(filename: str, file_bytes: bytes) -> dict:
    kind = document_kind(filename)
    if kind is None:
        return {
            "error": "Please upload a Word file (.docx), a PDF, or a plain text file.",
            "text": "", "values": {}, "unknown_lines": [],
            "missing": list(TYPED_KEYS),
        }

    if not file_bytes.strip():
        return {
            "error": "This document is empty. Please check the file and try again.",
            "text": "", "values": {}, "unknown_lines": [],
            "missing": list(TYPED_KEYS),
        }

    try:
        if kind == "word":
            text = _text_from_word(file_bytes)
        elif kind == "pdf":
            text = _text_from_pdf(file_bytes)
        else:
            text = file_bytes.decode("utf-8", errors="replace")
    except Exception:
        return {
            "error": "This document could not be read. Please try another file.",
            "text": "", "values": {}, "unknown_lines": [],
            "missing": list(TYPED_KEYS),
        }

    if not text.strip():
        return {
            "error": "We could not find any text in this document. "
                     "If it is a scan or a photo, please type the numbers instead.",
            "text": "", "values": {}, "unknown_lines": [],
            "missing": list(TYPED_KEYS),
        }

    values, unknown_lines = parse_list(text)

    for key, _label, _hint in FIELDS:
        if key in values:
            continue
        found = _find_number_near(text, key)
        if found is not None:
            values[key] = found

    missing = [key for key in TYPED_KEYS if key not in values]

    if not values:
        return {
            "error": "We could not find any of the buyer numbers in this document. "
                     "Please type them instead.",
            "text": text, "values": {}, "unknown_lines": unknown_lines,
            "missing": missing,
        }

    return {
        "error": None,
        "text": text,
        "values": values,
        "unknown_lines": unknown_lines,
        "missing": missing,
    }


def _find_number_near(text: str, key: str) -> int | None:
    names = [name for name, target in NAME_ALIASES.items() if target == key]
    names.sort(key=len, reverse=True)

    lowered = " ".join(text.lower().split())

    for name in names:
        start = lowered.find(name)
        if start == -1:
            continue
        rest = lowered[start + len(name): start + len(name) + 60]
        for token in rest.replace(":", " ").split():
            cleaned = token.replace(",", "").strip(".")
            if cleaned.isdigit() and len(cleaned) <= 9:
                return int(cleaned)
    return None


THREE_GROUPS = ["most", "regular", "least"]


def parse_list(text: str) -> tuple[dict, list[str]]:
    values: dict[str, int] = {}
    unknown: list[str] = []

    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if ":" not in line:
            unknown.append(raw_line)
            continue

        name, _, number_text = line.partition(":")

        cleaned_name = " ".join(name.strip().lower().split())
        key = NAME_ALIASES.get(cleaned_name)

        number_text = number_text.strip()
        if not number_text.isdigit():
            unknown.append(raw_line)
            continue

        if key is None:
            unknown.append(raw_line)
            continue

        values[key] = int(number_text)

    return values, unknown


def percentages(values: dict) -> dict:
    total = values.get("total") or 0
    if total <= 0:
        return {}

    result = {}
    for key, _label, _hint in FIELDS:
        if key == "total":
            continue
        number = values.get(key)
        if number is None:
            continue
        result[key] = round(number * 100.0 / total, 1)
    return result


def check_numbers(values: dict) -> list[str]:
    warnings = []
    total = values.get("total") or 0

    for key in ("most", "least", "last_month"):
        number = values.get(key) or 0
        if total and number > total:
            warnings.append("Total buyers looks too small. Please check the numbers.")
            break

    most = values.get("most")
    regular = values.get("regular")
    least = values.get("least")
    if total and None not in (most, regular, least):
        if (most + regular + least) != total:
            warnings.append(
                "Most, Regular and Least buyers add up to "
                f"{_comma(most + regular + least)}, not {_comma(total)}. "
                "Some buyers may be missing from those three groups."
            )

    return warnings


def _comma(number: int) -> str:
    return f"{int(number):,}"


def sentences(values: dict) -> list[str]:
    total = values.get("total") or 0
    most = values.get("most")
    regular = values.get("regular")
    least = values.get("least")
    last_month = values.get("last_month")
    pcts = percentages(values)

    out = []

    if total and most is not None:
        share = pcts.get("most")
        share_text = f", or {share:g}% of them" if share is not None else ""
        out.append(
            f"Out of {_comma(total)} buyers, {_comma(most)} buy often{share_text}."
        )

    if last_month is not None:
        out.append(
            f"{_comma(last_month)} "
            + ("buyer bought" if last_month == 1 else "buyers bought")
            + " last month."
        )

    if least is not None and regular is not None and most is not None:
        if least > regular and least > most:
            out.append(
                "Most of your buyers placed only one order, "
                "so a second-purchase offer could help."
            )
        elif most > regular and most > least:
            out.append(
                "Most of your buyers order often already, "
                "so look after them to keep them coming back."
            )
        elif regular > most and regular > least:
            out.append(
                "Most of your buyers order a few times, "
                "so a gentle nudge could turn them into regulars."
            )
        else:
            out.append(
                "Your three order groups are about the same size, "
                "so try a different offer for each one."
            )

    return out


def _clean_name(name: str) -> str:
    return "".join(str(name).lower().split()).replace("_", "").replace("-", "")


def find_columns(headers: list[str]) -> tuple[dict, list[str]]:
    by_clean = {_clean_name(header): header for header in headers}
    mapping, missing = {}, []

    for column in REQUIRED_COLUMNS:
        found = by_clean.get(_clean_name(column))
        if found is None:
            for alias in COLUMN_ALIASES.get(column, []):
                if _clean_name(alias) in by_clean:
                    found = by_clean[_clean_name(alias)]
                    break
        if found is None:
            missing.append(column)
        else:
            mapping[column] = found

    return mapping, missing


def missing_column_message(column: str) -> str:
    return f"The file needs a column for the {COLUMN_PLAIN_NAMES.get(column, column)}."


def read_upload(file_bytes: bytes) -> dict:
    report = {
        "rows_read": 0,
        "rows_used": 0,
        "rows_removed": 0,
        "no_customer_id": 0,
        "returns": 0,
        "bad_price": 0,
        "bad_date": 0,
    }

    if not file_bytes.strip():
        return {"error": "This file has no rows. Please check the file and try again."}

    try:
        raw = pd.read_csv(pd.io.common.BytesIO(file_bytes), dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError:
        return {"error": "This file has no rows. Please check the file and try again."}
    except Exception:
        return {"error": "This file could not be read. Please check it is a CSV file and try again."}

    report["rows_read"] = int(len(raw))
    if len(raw) == 0:
        return {"error": "This file has no rows. Please check the file and try again."}

    mapping, missing = find_columns(list(raw.columns))
    if missing:
        return {
            "error": missing_column_message(missing[0]),
            "missing_columns": missing,
            "report": report,
        }

    data = pd.DataFrame({
        "customer_id": raw[mapping["customer_id"]].astype(str).str.strip(),
        "invoice_id": raw[mapping["invoice_id"]].astype(str).str.strip(),
        "invoice_date": raw[mapping["invoice_date"]],
        "quantity": pd.to_numeric(raw[mapping["quantity"]], errors="coerce"),
        "unit_price": pd.to_numeric(raw[mapping["unit_price"]], errors="coerce"),
    })

    no_id = data["customer_id"].isin(["", "nan", "none", "null"])
    returns = (~no_id) & (pd.to_numeric(data["quantity"], errors="coerce").lt(1) | data["quantity"].isna())
    bad_price = (
        (~no_id) & (~returns)
        & (data["unit_price"].isna() | (data["unit_price"] <= 0))
    )
    parsed_date = pd.to_datetime(data["invoice_date"], errors="coerce", format="mixed")
    bad_date = (~no_id) & (~returns) & (~bad_price) & parsed_date.isna()

    report["no_customer_id"] = int(no_id.sum())
    report["returns"] = int(returns.sum())
    report["bad_price"] = int(bad_price.sum())
    report["bad_date"] = int(bad_date.sum())

    keep = ~(no_id | returns | bad_price | bad_date)
    clean = pd.DataFrame({
        "customer_id": data["customer_id"][keep],
        "invoice_id": data["invoice_id"][keep],
        "invoice_date": parsed_date[keep],
        "quantity": data["quantity"][keep],
        "unit_price": data["unit_price"][keep],
    })
    clean["revenue"] = clean["quantity"] * clean["unit_price"]

    report["rows_used"] = int(len(clean))
    report["rows_removed"] = report["rows_read"] - report["rows_used"]

    if len(clean) == 0:
        return {
            "error": "No valid rows were found after cleaning.",
            "report": report,
        }

    return {"error": None, "clean": clean, "report": report}


def _orders_per_customer(clean: pd.DataFrame) -> pd.Series:
    return clean.groupby("customer_id")["invoice_id"].nunique()


def count_total_buyers(clean: pd.DataFrame) -> int:
    return int(clean["customer_id"].nunique())


def count_most_buyers(orders: pd.Series) -> int:
    return int((orders >= MOST_ORDERS).sum())


def count_regular_buyers(orders: pd.Series) -> int:
    return int(((orders >= REGULAR_ORDERS) & (orders < MOST_ORDERS)).sum())


def count_least_buyers(orders: pd.Series) -> int:
    return int((orders == LEAST_ORDERS).sum())


def count_frequent_buyers(orders: pd.Series) -> int:
    if len(orders) == 0:
        return 0
    how_many = int(round(len(orders) * FREQUENT_TOP_PERCENT / 100.0))
    return max(1, min(how_many, int(len(orders))))


def count_bought_last_month(clean: pd.DataFrame) -> int:
    latest = clean["invoice_date"].max()
    cutoff = latest - pd.Timedelta(days=LAST_MONTH_DAYS)
    recent = clean[clean["invoice_date"] > cutoff]
    return int(recent["customer_id"].nunique())


def count_big_spenders(spend: pd.Series) -> int:
    if len(spend) == 0:
        return 0
    how_many = int(round(len(spend) * BIG_SPENDER_TOP_PERCENT / 100.0))
    return max(1, min(how_many, int(len(spend))))


def total_revenue(clean: pd.DataFrame) -> float:
    return float(round((clean["quantity"] * clean["unit_price"]).sum(), 2))


def file_numbers(clean: pd.DataFrame) -> dict:
    orders = _orders_per_customer(clean)
    spend = clean.groupby("customer_id")["revenue"].sum()
    total = count_total_buyers(clean)
    last_month = count_bought_last_month(clean)

    return {
        "total": total,
        "most": count_most_buyers(orders),
        "regular": count_regular_buyers(orders),
        "least": count_least_buyers(orders),
        "frequent": count_frequent_buyers(orders),
        "last_month": last_month,
        "not_last_month": total - last_month,
        "big_spenders": count_big_spenders(spend),
        "revenue": total_revenue(clean),
    }


def build_rfm(clean: pd.DataFrame) -> pd.DataFrame:
    snapshot = clean["invoice_date"].max() + pd.Timedelta(days=1)
    rfm = clean.groupby("customer_id").agg(
        last_purchase=("invoice_date", "max"),
        frequency=("invoice_id", "nunique"),
        monetary=("revenue", "sum"),
    )
    rfm["recency"] = (snapshot - rfm["last_purchase"]).dt.days
    return rfm[["recency", "frequency", "monetary"]].reset_index()


def _segment_names(segmented: pd.DataFrame) -> dict[int, str]:
    if segmented["cluster"].nunique() <= 1:
        return {int(segmented["cluster"].iloc[0]): SEGMENT_NAMES[0]}

    profile = segmented.groupby("cluster").mean(numeric_only=True)

    def scale(series: pd.Series) -> pd.Series:
        low, high = series.min(), series.max()
        if high == low:
            return pd.Series(0.5, index=series.index)
        return (series - low) / (high - low)

    score = (
        (1 - scale(profile["recency"]))
        + scale(profile["frequency"])
        + scale(profile["monetary"])
    )
    ranked = list(score.sort_values(ascending=False).index)

    names = {}
    for position, cluster in enumerate(ranked):
        which = min(position, len(SEGMENT_NAMES) - 1)
        names[int(cluster)] = SEGMENT_NAMES[which]
    return names


def run_segmentation(clean: pd.DataFrame) -> dict:
    rfm = build_rfm(clean)
    if len(rfm) < 4:
        return {
            "available": False,
            "message": "There are too few buyers in this file to make segments. "
            "The other numbers above are still correct.",
        }

    features = ["recency", "frequency", "monetary"]
    values = np.log1p(rfm[features])
    scaled = StandardScaler().fit_transform(values)

    k = min(len(SEGMENT_NAMES), len(rfm))
    labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(scaled)

    segmented = rfm.copy()
    segmented["cluster"] = labels
    names = _segment_names(segmented)

    money = segmented["monetary"].sum()
    segments = []
    for cluster, group in segmented.groupby("cluster"):
        segments.append({
            "segment": names[int(cluster)],
            "customers": int(len(group)),
            "recency": round(float(group["recency"].mean()), 1),
            "frequency": round(float(group["frequency"].mean()), 1),
            "monetary": round(float(group["monetary"].mean()), 2),
            "revenue_share": round(float(group["monetary"].sum() / money * 100), 1) if money else 0.0,
        })
    segments.sort(key=lambda item: item["customers"], reverse=True)

    return {"available": True, "segments": segments, "message": ""}


def file_sentences(numbers: dict) -> list[str]:
    out = []
    total = numbers.get("total") or 0
    most = numbers.get("most")
    last_month = numbers.get("last_month")
    pcts = percentages(numbers)

    if total and most is not None:
        share = pcts.get("most")
        share_text = f", or {share:g}% of them" if share is not None else ""
        out.append(f"Out of {_comma(total)} buyers, {_comma(most)} buy often{share_text}.")

    if last_month is not None:
        if last_month <= max(1, int(total * 0.02)):
            out.append(f"Only {_comma(last_month)} "
                       + ("buyer bought" if last_month == 1 else "buyers bought")
                       + " last month.")
        else:
            out.append(f"{_comma(last_month)} "
                       + ("buyer bought" if last_month == 1 else "buyers bought")
                       + " last month.")

    least, regular = numbers.get("least"), numbers.get("regular")
    if None not in (least, regular, most):
        if least >= regular and least >= most:
            out.append("Most of your buyers placed only one order, "
                       "so a second-purchase offer could help.")
        elif most >= regular and most >= least:
            out.append("Most of your buyers order often already, "
                       "so look after them to keep them coming back.")
        else:
            out.append("Most of your buyers order a few times, "
                       "so a gentle nudge could turn them into regulars.")

    return out
