import argparse
from pathlib import Path

import numpy as np
import pandas as pd

RANDOM_SEED = 42

ARCHETYPES = {
    "loyal":          {"share": 0.20, "orders_per_year": 24, "items": 4, "price": 25},
    "big_spender":    {"share": 0.10, "orders_per_year": 8,  "items": 9, "price": 80},
    "bargain_hunter": {"share": 0.25, "orders_per_year": 12, "items": 2, "price": 8},
    "occasional":     {"share": 0.30, "orders_per_year": 2,  "items": 2, "price": 20},
    "dormant":        {"share": 0.15, "orders_per_year": 1,  "items": 1, "price": 15},
}


def generate(n_customers: int, start: str, end: str, seed: int = RANDOM_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    span_days = (end_ts - start_ts).days

    names = list(ARCHETYPES)
    shares = [ARCHETYPES[n]["share"] for n in names]
    years = span_days / 365

    rows = []
    invoice_no = 10_000
    for customer_id in range(1, n_customers + 1):
        archetype = rng.choice(names, p=shares)
        profile = ARCHETYPES[archetype]

        active_days = span_days * (0.25 if archetype == "dormant" else 1.0)
        n_orders = max(1, rng.poisson(profile["orders_per_year"] * years * (active_days / span_days)))

        offsets = rng.uniform(0, active_days, size=n_orders)
        for offset in offsets:
            invoice_no += 1
            invoice_date = start_ts + pd.Timedelta(days=float(offset))
            n_items = max(1, rng.poisson(profile["items"]))
            for _ in range(n_items):
                rows.append({
                    "customer_id": f"C{customer_id:05d}",
                    "invoice_id": f"INV{invoice_no}",
                    "invoice_date": invoice_date.date().isoformat(),
                    "quantity": int(rng.integers(1, 4)),
                    "unit_price": round(abs(rng.normal(profile["price"], profile["price"] * 0.2)) + 0.5, 2),
                })

    df = pd.DataFrame(rows)

    returns = df.sample(frac=0.01, random_state=seed).copy()
    returns["invoice_id"] = "R" + returns["invoice_id"]
    returns["quantity"] = -returns["quantity"]
    df = pd.concat([df, returns], ignore_index=True)
    df.loc[df.sample(frac=0.002, random_state=seed + 1).index, "customer_id"] = None

    return df.sort_values("invoice_date").reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic transaction data.")
    parser.add_argument("--customers", type=int, default=1000)
    parser.add_argument("--start", default="2025-01-01")
    parser.add_argument("--end", default="2026-10-31")
    parser.add_argument("--out", default="data/transactions.csv")
    args = parser.parse_args()

    df = generate(args.customers, args.start, args.end)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df):,} rows for {df['customer_id'].nunique():,} customers to {out_path}")


if __name__ == "__main__":
    main()
