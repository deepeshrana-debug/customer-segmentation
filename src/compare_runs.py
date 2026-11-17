import json
from pathlib import Path

import pandas as pd

RUNS = [("synthetic", "output"), ("real (Online Retail II)", "output_real")]


def chosen_k(run_dir: Path) -> int | None:
    info = run_dir / "run_info.json"
    if not info.exists():
        return None
    return json.loads(info.read_text()).get("k")


def load_profile(run_dir: Path) -> pd.DataFrame | None:
    path = run_dir / "segment_profile.csv"
    if not path.exists():
        return None
    return pd.read_csv(path)


def describe_run(label: str, run_dir: Path) -> None:
    profile = load_profile(run_dir)
    if profile is None:
        print(f"\n{label}: not found (expected {run_dir}/segment_profile.csv)")
        return

    total = int(profile["customers"].sum())
    k = chosen_k(run_dir)

    print(f"\n{label}")
    print(f"  customers: {total:,}")
    print(f"  chosen k : {k if k is not None else 'unknown'}")

    profile = profile.copy()
    profile["customer_share_%"] = (profile["customers"] / total * 100).round(1)

    print(f"  {'segment':<22}{'customers':>10}{'cust %':>9}{'revenue %':>11}")
    for _, row in profile.iterrows():
        print(
            f"  {row['segment']:<22}{int(row['customers']):>10,}"
            f"{row['customer_share_%']:>9.1f}{row['revenue_share_%']:>11.1f}"
        )


def main() -> None:
    print("Synthetic data versus real data")
    for label, folder in RUNS:
        describe_run(label, Path(folder))
    print()


if __name__ == "__main__":
    main()
