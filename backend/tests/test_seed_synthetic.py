import pytest

from scripts import seed_synthetic


class _Response:
    def __init__(self):
        self.raised = False

    def raise_for_status(self):
        self.raised = True

    def json(self):
        return {"inserted": 330, "errors": [], "source": "csv_import_2026-05-24"}


def test_seed_synthetic_posts_csv_with_bearer_token(monkeypatch, tmp_path):
    csv_path = tmp_path / "synthetic.csv"
    csv_path.write_text("date,merchant,category,amount,currency\n", encoding="utf-8")
    seen = {}

    def fake_post(url, *, headers, files, timeout):
        seen["url"] = url
        seen["headers"] = headers
        seen["filename"] = files["file"][0]
        seen["content_type"] = files["file"][2]
        seen["timeout"] = timeout
        return _Response()

    monkeypatch.setattr(seed_synthetic.httpx, "post", fake_post)

    result = seed_synthetic.seed_synthetic(
        backend_url="http://api.test/",
        csv_path=csv_path,
        token="jwt",
    )

    assert result["inserted"] == 330
    assert seen == {
        "url": "http://api.test/ingest/csv",
        "headers": {"Authorization": "Bearer jwt"},
        "filename": "synthetic.csv",
        "content_type": "text/csv",
        "timeout": 30.0,
    }


def test_main_requires_token(monkeypatch, tmp_path):
    csv_path = tmp_path / "synthetic.csv"
    csv_path.write_text("date,merchant,category,amount,currency\n", encoding="utf-8")
    monkeypatch.delenv("CLERK_JWT", raising=False)
    monkeypatch.setattr(
        "sys.argv",
        ["seed_synthetic.py", "--csv", str(csv_path)],
    )

    with pytest.raises(SystemExit):
        seed_synthetic.main()
