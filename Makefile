.PHONY: seed

seed:
	cd backend && uv run python scripts/seed_synthetic.py
