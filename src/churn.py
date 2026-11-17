import pandas as pd

CHURN_PERIODS = [90, 180, 365]


def churn_summary(rfm: pd.DataFrame) -> pd.DataFrame:
    total = len(rfm)
    rows = []
    for days in CHURN_PERIODS:
        churned = int((rfm["recency"] > days).sum())
        rows.append({
            "days": days,
            "churned_customers": churned,
            "churn_pct": round(churned / total * 100, 1) if total else 0.0,
        })
    return pd.DataFrame(rows)
