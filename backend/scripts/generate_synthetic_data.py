import csv
import random
from datetime import date, timedelta
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
FULL_PATH = DATA_DIR / "synthetic.csv"
TINY_PATH = DATA_DIR / "synthetic-tiny.csv"

random.seed(482)


def money(amount: float) -> str:
    return f"{amount:.2f}"


def add_row(rows: list[dict], day: date, merchant: str, category: str, amount: float) -> None:
    rows.append(
        {
            "date": day.isoformat(),
            "merchant": merchant,
            "category": category,
            "amount": money(amount),
            "currency": "USD",
        }
    )


def daterange(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def is_stress_event(day: date) -> bool:
    feb_exam_week = date(2026, 2, 9) <= day <= date(2026, 2, 15)
    may_work_week = date(2026, 5, 18) <= day <= date(2026, 5, 24)
    return feb_exam_week or may_work_week


def generate_rows() -> list[dict]:
    rows: list[dict] = []
    start = date(2025, 12, 1)
    end = date(2026, 5, 24)

    for day in daterange(start, end):
        if day.day in {1, 15}:
            add_row(rows, day, "Direct Deposit", "income.salary", 2400.00)
            add_row(rows, day, "Emergency Fund Transfer", "savings.emergency_fund", -115.00)

        if day.day == 1:
            add_row(rows, day, "Maple Leaf Apartments", "housing.rent", -1725.00)

        if day.day == 3:
            add_row(rows, day, "Netflix", "subscriptions.streaming", -17.99)
        if day.day == 8:
            add_row(rows, day, "Spotify", "subscriptions.streaming", -11.99)
        if day.day == 12:
            add_row(rows, day, "Notion", "subscriptions.software", -10.00)
        if day.day == 20:
            add_row(rows, day, "GoodLife Fitness", "health.gym", -34.99)

        if day.weekday() in {0, 2, 4}:
            coffee_amount = random.uniform(5.25, 8.75)
            add_row(rows, day, random.choice(["Starbucks", "Balzac's Coffee", "Tim Hortons"]), "food.coffee", -coffee_amount)

        if day.weekday() < 5:
            add_row(rows, day, "TTC", "transport.transit", -3.35)

        if day.weekday() == 2:
            grocery_amount = random.uniform(58.0, 92.0)
            add_row(rows, day, random.choice(["Loblaws", "FreshCo", "No Frills"]), "food.groceries", -grocery_amount)

        if day.weekday() == 4:
            base_delivery = random.uniform(24.0, 38.0)
            if is_stress_event(day):
                base_delivery *= 3.0
            add_row(rows, day, random.choice(["DoorDash", "Uber Eats"]), "food.delivery", -base_delivery)

        if is_stress_event(day) and day.weekday() in {1, 3, 5}:
            add_row(rows, day, "DoorDash", "food.delivery", -random.uniform(32.0, 49.0))

        if day.day in {2, 16} and day.weekday() in {4, 5, 6}:
            add_row(rows, day, "Uber", "transport.rideshare", -random.uniform(18.0, 35.0))
            add_row(rows, day, random.choice(["Cineplex", "The Rec Room", "Bar Raval"]), "entertainment", -random.uniform(22.0, 64.0))

        if day.day in {6, 22}:
            add_row(rows, day, "Amazon", "shopping.amazon", -random.uniform(18.0, 75.0))

    return sorted(rows, key=lambda row: (row["date"], row["merchant"], row["amount"]))


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["date", "merchant", "category", "amount", "currency"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows = generate_rows()
    write_csv(FULL_PATH, rows)
    write_csv(TINY_PATH, rows[:30])
    print(f"Wrote {len(rows)} rows to {FULL_PATH}")
    print(f"Wrote 30 rows to {TINY_PATH}")


if __name__ == "__main__":
    main()
