import argparse
import os
from pathlib import Path

import httpx


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CSV = ROOT_DIR / "data" / "synthetic.csv"


def seed_synthetic(
    *,
    backend_url: str,
    csv_path: Path,
    token: str,
) -> dict:
    with csv_path.open("rb") as file:
        response = httpx.post(
            f"{backend_url.rstrip('/')}/ingest/csv",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (csv_path.name, file, "text/csv")},
            timeout=30.0,
        )
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed MoneyMind with data/synthetic.csv via POST /ingest/csv."
    )
    parser.add_argument(
        "--backend-url",
        default=os.getenv("BACKEND_URL", "http://127.0.0.1:8000"),
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--token", default=os.getenv("CLERK_JWT"))
    args = parser.parse_args()

    if not args.token:
        parser.error("pass --token or set CLERK_JWT")
    if not args.csv.exists():
        parser.error(f"CSV file does not exist: {args.csv}")

    result = seed_synthetic(
        backend_url=args.backend_url,
        csv_path=args.csv,
        token=args.token,
    )
    print(
        "Seeded synthetic data: "
        f"inserted={result.get('inserted')} "
        f"errors={len(result.get('errors', []))} "
        f"source={result.get('source')}"
    )


if __name__ == "__main__":
    main()
