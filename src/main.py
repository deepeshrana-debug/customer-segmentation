import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from churn import churn_summary
from load_online_retail import load_online_retail
from rfm import add_score_columns, build_rfm, clean_transactions
from segment import (
    FEATURES,
    evaluate_k,
    fit_segments,
    name_segments,
    profile_table,
    scale_features,
)


def plot_elbow(k_scores: pd.DataFrame, chosen_k: int, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(k_scores["k"], k_scores["inertia"], marker="o", color="#2A6F97")
    ax.axvline(chosen_k, color="#C8553D", linestyle="--", label=f"chosen k = {chosen_k}")
    ax.set_xlabel("Number of segments (k)")
    ax.set_ylabel("Inertia (within-cluster spread)")
    ax.set_title("Elbow method")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_scatter(segmented: pd.DataFrame, names: dict[int, str], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5.5))
    for cluster in sorted(segmented["cluster"].unique()):
        subset = segmented[segmented["cluster"] == cluster]
        ax.scatter(subset["recency"], subset["monetary"], s=18, alpha=0.7, label=names[cluster])
    ax.set_xlabel("Recency (days since last purchase)")
    ax.set_ylabel("Monetary (total spend)")
    ax.set_title("Customer segments: recency vs spend")
    ax.legend(title="Segment", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_sizes(profile: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(profile["segment"], profile["customers"], color="#2A6F97")
    ax.set_xlabel("Customers")
    ax.set_title("Segment sizes")
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def load_raw(source: str, data_path: str) -> pd.DataFrame:
    if source == "retail2":
        return load_online_retail(data_path)
    return pd.read_csv(data_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RFM customer segmentation.")
    parser.add_argument(
        "--source",
        choices=["synthetic", "retail2"],
        default="synthetic",
        help="synthetic = data/transactions.csv, retail2 = the UCI Online Retail II Excel file",
    )
    parser.add_argument("--data", default=None, help="input file (a sensible default is picked for you)")
    parser.add_argument("--out", default=None, help="folder for the results")
    parser.add_argument("--k", type=int, default=None, help="number of segments (auto if omitted)")
    args = parser.parse_args()

    if args.source == "retail2":
        data_path = args.data or "data/online_retail_II.xlsx"
        default_out = "output_real"
    else:
        data_path = args.data or "data/transactions.csv"
        default_out = "output"
    out_dir = Path(args.out or default_out)
    out_dir.mkdir(parents=True, exist_ok=True)

    raw = load_raw(args.source, data_path)
    clean = clean_transactions(raw)
    print(f"Source: {args.source} ({data_path})")
    print(f"Loaded {len(raw):,} rows, {len(clean):,} usable after cleaning")

    rfm = build_rfm(clean)
    print(f"Built RFM for {len(rfm):,} customers")

    X = scale_features(rfm)
    k_scores = evaluate_k(X)
    k_scores.to_csv(out_dir / "k_selection.csv", index=False)

    if args.k is None:
        k = int(k_scores.loc[k_scores["silhouette"].idxmax(), "k"])
        print(f"Automatically selected k = {k} (best silhouette score)")
    else:
        k = args.k
        print(f"Using k = {k} from command line")

    segmented, _ = fit_segments(rfm, k)
    names = name_segments(segmented)
    segmented["segment"] = segmented["cluster"].map(names)

    profile = profile_table(segmented, names)
    segmented.sort_values("monetary", ascending=False).to_csv(out_dir / "segments.csv", index=False)
    profile.to_csv(out_dir / "segment_profile.csv")

    plot_elbow(k_scores, k, out_dir / "elbow_plot.png")
    plot_scatter(segmented, names, out_dir / "segments_plot.png")
    plot_sizes(profile, out_dir / "segment_sizes.png")

    print("\nSegment profile:")
    print(profile.to_string())

    scored = add_score_columns(rfm)
    scored.merge(
        segmented[["customer_id", "cluster", "segment"]], on="customer_id", how="left"
    ).to_csv(out_dir / "rfm_scores.csv", index=False)

    churn = churn_summary(rfm)
    churn.to_csv(out_dir / "churn_summary.csv", index=False)
    print("\nCustomers who have not bought in the last N days:")
    for _, row in churn.iterrows():
        print(
            f"  {int(row['days']):>3} days: {int(row['churned_customers']):>6,} customers "
            f"({row['churn_pct']:.1f}%)"
        )

    (out_dir / "run_info.json").write_text(
        json.dumps({"source": args.source, "data": data_path, "k": k}, indent=2)
    )

    print(f"\nResults saved to {out_dir.resolve()}")


if __name__ == "__main__":
    main()
