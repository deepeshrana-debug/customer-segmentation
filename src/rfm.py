import pandas as pd


def clean_transactions(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df = df.dropna(subset=["customer_id"])
    df = df[df["quantity"] > 0]
    df = df[df["unit_price"] > 0]
    df["invoice_date"] = pd.to_datetime(df["invoice_date"])
    df["revenue"] = df["quantity"] * df["unit_price"]
    return df.reset_index(drop=True)


def build_rfm(clean: pd.DataFrame, snapshot_date: pd.Timestamp | None = None) -> pd.DataFrame:
    if snapshot_date is None:
        snapshot_date = clean["invoice_date"].max() + pd.Timedelta(days=1)

    rfm = clean.groupby("customer_id").agg(
        last_purchase=("invoice_date", "max"),
        frequency=("invoice_id", "nunique"),
        monetary=("revenue", "sum"),
    )
    rfm["recency"] = (snapshot_date - rfm["last_purchase"]).dt.days
    rfm["monetary"] = rfm["monetary"].round(2)

    return rfm[["recency", "frequency", "monetary"]].reset_index()


def add_score_columns(rfm: pd.DataFrame) -> pd.DataFrame:
    scored = rfm.copy()

    def quintiles(series: pd.Series, higher_is_better: bool) -> pd.Series:
        labels = [1, 2, 3, 4, 5] if higher_is_better else [5, 4, 3, 2, 1]
        scores = pd.qcut(series.rank(method="first"), 5, labels=labels, duplicates="drop")
        return scores.astype(int)

    scored["R_score"] = quintiles(scored["recency"], higher_is_better=False)
    scored["F_score"] = quintiles(scored["frequency"], higher_is_better=True)
    scored["M_score"] = quintiles(scored["monetary"], higher_is_better=True)

    scored["RFM_code"] = (
        scored["R_score"].astype(str)
        + scored["F_score"].astype(str)
        + scored["M_score"].astype(str)
    )
    return scored
