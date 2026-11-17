import json
from pathlib import Path

import pandas as pd

CONFIG_PATH = Path("config/assumptions.json")
PROFILE_PATH = Path("output/segment_profile.csv")
RESULTS_PATH = Path("output/business_case.csv")

WIN_BACK_SEGMENTS = ("Hibernating", "Lapsing Regulars", "Big Spenders at Risk")


def load_assumptions(path: Path = CONFIG_PATH) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"Could not find {path}. Create it with win_back_rate, "
            "offer_cost_per_customer and orders_per_year_if_returned."
        )
    settings = json.loads(path.read_text())
    settings.pop("_comment", None)
    return settings


def is_win_back(segment_name: str) -> bool:
    return any(segment_name.startswith(name) for name in WIN_BACK_SEGMENTS)


def default_order_value(profile: pd.DataFrame) -> float:
    return float(profile["monetary"].mean())


def calculate(profile: pd.DataFrame, settings: dict) -> pd.DataFrame:
    win_back_rate = float(settings["win_back_rate"])
    offer_cost = float(settings["offer_cost_per_customer"])
    orders_per_year = float(settings["orders_per_year_if_returned"])

    order_value = settings.get("average_order_value")
    if order_value in (None, ""):
        order_value = default_order_value(profile)
    order_value = float(order_value)

    rows = []
    for _, row in profile.iterrows():
        customers = int(row["customers"])
        targeted = is_win_back(str(row["segment"]))
        rate = win_back_rate if targeted else 0.0

        returned = customers * rate
        extra_revenue = returned * order_value * orders_per_year
        cost = customers * offer_cost if targeted else 0.0

        rows.append({
            "segment": row["segment"],
            "customers": customers,
            "assumed_win_back_rate": round(rate, 3),
            "assumed_returned_customers": round(returned, 1),
            "assumed_order_value": round(order_value, 2),
            "assumed_orders_per_year": orders_per_year,
            "assumption_based_extra_revenue": round(extra_revenue, 2),
            "offer_cost": round(cost, 2),
            "assumption_based_net_gain": round(extra_revenue - cost, 2),
        })

    result = pd.DataFrame(rows)
    result["figures_are"] = "assumption-based"
    return result.sort_values("assumption_based_net_gain", ascending=False)


def main() -> None:
    if not PROFILE_PATH.exists():
        raise FileNotFoundError(
            f"Could not find {PROFILE_PATH}. Run `python src/main.py` first."
        )

    profile = pd.read_csv(PROFILE_PATH)
    settings = load_assumptions()
    result = calculate(profile, settings)

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(RESULTS_PATH, index=False)

    total_gain = result["assumption_based_net_gain"].sum()
    print("BUSINESS CASE (all figures are ASSUMPTION-BASED, not measured from data)")
    print(f"  win-back rate   : {settings['win_back_rate']:.0%} of customers come back")
    print(f"  offer cost      : {settings['offer_cost_per_customer']:.2f} per customer")
    print(f"  orders per year : {settings['orders_per_year_if_returned']}")
    print()
    for _, row in result.iterrows():
        print(
            f"  {row['segment']:<22}"
            f" extra revenue {row['assumption_based_extra_revenue']:>12,.2f}"
            f"   net gain {row['assumption_based_net_gain']:>12,.2f}"
        )
    print(f"\n  Total assumed net gain: {total_gain:,.2f}")
    print("  Edit config/assumptions.json and run again to see how these move.")
    print(f"\nSaved to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
