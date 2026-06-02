from bson import ObjectId

from scripts.dedupe_transactions import duplicate_ids_to_delete, duplicate_pipeline


def test_duplicate_pipeline_scopes_to_user_and_exact_raw_row():
    pipeline = duplicate_pipeline("user_123")

    assert pipeline[0] == {"$match": {"user_id": "user_123"}}
    group_id = pipeline[2]["$group"]["_id"]
    assert group_id["raw"] == "$raw"
    assert group_id["date"] == "$date"
    assert pipeline[3] == {"$match": {"count": {"$gt": 1}}}


def test_duplicate_ids_to_delete_keeps_oldest_id():
    oldest = ObjectId()
    duplicate = ObjectId()
    newest = ObjectId()

    assert duplicate_ids_to_delete([{"ids": [oldest, duplicate, newest]}]) == [
        duplicate,
        newest,
    ]
