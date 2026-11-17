import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

FEATURES = ["recency", "frequency", "monetary"]
RANDOM_STATE = 42


def scale_features(rfm: pd.DataFrame) -> np.ndarray:
    log_values = np.log1p(rfm[FEATURES])
    return StandardScaler().fit_transform(log_values)


def evaluate_k(X: np.ndarray, k_min: int = 2, k_max: int = 8) -> pd.DataFrame:
    rows = []
    for k in range(k_min, k_max + 1):
        model = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE).fit(X)
        rows.append({
            "k": k,
            "inertia": model.inertia_,
            "silhouette": silhouette_score(X, model.labels_),
        })
    return pd.DataFrame(rows)


def fit_segments(rfm: pd.DataFrame, k: int) -> tuple[pd.DataFrame, KMeans]:
    X = scale_features(rfm)
    model = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE)
    labels = model.fit_predict(X)

    segmented = rfm.copy()
    segmented["cluster"] = labels
    return segmented, model


def name_segments(segmented: pd.DataFrame) -> dict[int, str]:
    median = segmented[FEATURES].median()
    profile = segmented.groupby("cluster")[FEATURES].mean()

    names = {}
    for cluster, row in profile.iterrows():
        recent = row["recency"] <= median["recency"]
        frequent = row["frequency"] >= median["frequency"]
        valuable = row["monetary"] >= median["monetary"]

        if recent and frequent and valuable:
            name = "Champions"
        elif recent and frequent:
            name = "Loyal Customers"
        elif recent:
            name = "Promising / New"
        elif valuable:
            name = "Big Spenders at Risk"
        elif frequent:
            name = "Lapsing Regulars"
        else:
            name = "Hibernating"
        names[cluster] = name

    counts = {}
    for cluster, name in names.items():
        counts[name] = counts.get(name, 0) + 1
        if counts[name] > 1:
            names[cluster] = f"{name} {counts[name]}"
    return names


def profile_table(segmented: pd.DataFrame, names: dict[int, str]) -> pd.DataFrame:
    grouped = segmented.groupby("cluster")
    table = grouped[FEATURES].mean().round(1)
    table.insert(0, "customers", grouped.size())
    table["revenue_share_%"] = (
        grouped["monetary"].sum() / segmented["monetary"].sum() * 100
    ).round(1)
    table.insert(0, "segment", table.index.map(names))
    return table.sort_values("revenue_share_%", ascending=False)
