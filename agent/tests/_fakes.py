"""Hermetic-testing helpers for agent tool tests.

Test-internal (note the leading underscore in the module name). If anything
in here becomes useful to production code, MOVE it rather than re-export.

Consolidates four patterns that appeared across tickets #11-#14 (#14a).
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import contextmanager
from typing import Any

from mongomock_motor import AsyncMongoMockClient


def make_mongomock_collection(
    db_name: str = "moneymind",
    collection_name: str = "transactions",
):
    """Return an empty mongomock-motor collection.

    Established in #11 for query_transactions; reused by #12 + #14. Use this
    for tools whose Mongo operators are supported by mongomock-motor
    (find, insert_one, count_documents, regular aggregation stages). Tools
    that need `$vectorSearch` or `$dateTrunc` should use FakeCollection
    instead.
    """
    client = AsyncMongoMockClient()
    return client[db_name][collection_name]


class FakeCollection:
    """Hand-rolled fake that replays canned docs and tripwires on writes.

    Established in #13 for recall_memory (mongomock-motor doesn't implement
    `$vectorSearch`). Records every `.aggregate(pipeline)` call so tests
    can assert on pipeline shape, and applies the $vectorSearch limit +
    filter + $match score floor in Python so result-mapping logic is testable.

    Mutating methods (insert_one/many, update_one/many, delete_one/many,
    replace_one, find_one_and_update, find_one_and_delete, bulk_write) all
    raise AssertionError — any tool that should be read-only will fail
    loudly if a future refactor introduces a write path.
    """

    def __init__(self, docs: list[dict] | None = None):
        self._docs = list(docs or [])
        self.pipelines: list[list[dict]] = []
        self.writes: list[str] = []

    def aggregate(self, pipeline: list[dict]):
        self.pipelines.append(pipeline)
        # Apply $match score floor in Python so the score filter is testable.
        score_floor = 0.0
        for stage in pipeline:
            if "$match" in stage and "score" in stage["$match"]:
                score_floor = stage["$match"]["score"].get("$gte", 0.0)
        # Apply $vectorSearch limit + user_id/type filter on the canned set.
        vs = pipeline[0].get("$vectorSearch", {})
        limit = vs.get("limit", len(self._docs))
        vf = vs.get("filter", {})
        out = []
        for d in self._docs:
            if "user_id" in vf and d.get("user_id") != vf["user_id"]["$eq"]:
                continue
            if "type" in vf and d.get("type") != vf["type"]["$eq"]:
                continue
            if d.get("score", 0.0) < score_floor:
                continue
            out.append(d)
        out.sort(key=lambda d: d.get("score", 0.0), reverse=True)
        out = out[:limit]

        async def _aiter() -> AsyncIterator[dict]:
            for d in out:
                yield d

        return _aiter()

    def _trip(self, method: str):
        self.writes.append(method)
        raise AssertionError(
            f"FakeCollection.{method} called — this tool must not write to the collection"
        )

    # Mutating methods: tripwires.
    def insert_one(self, *a, **kw):
        return self._trip("insert_one")

    def insert_many(self, *a, **kw):
        return self._trip("insert_many")

    def update_one(self, *a, **kw):
        return self._trip("update_one")

    def update_many(self, *a, **kw):
        return self._trip("update_many")

    def delete_one(self, *a, **kw):
        return self._trip("delete_one")

    def delete_many(self, *a, **kw):
        return self._trip("delete_many")

    def replace_one(self, *a, **kw):
        return self._trip("replace_one")

    def find_one_and_update(self, *a, **kw):
        return self._trip("find_one_and_update")

    def find_one_and_delete(self, *a, **kw):
        return self._trip("find_one_and_delete")

    def bulk_write(self, *a, **kw):
        return self._trip("bulk_write")


def make_fake_embedder(dim: int = 1024) -> Callable[[str], Awaitable[list[float]]]:
    """Async embedder that returns a deterministic vector of `dim` floats.

    Established in #13 (recall_memory) + #14 (write_memory). Contract:
    non-zero (slot 0 encodes `len(text)`), right dimension, deterministic
    per input. Tests can assert `embedding[0] == float(len(summary))` to
    prove the embedding came from the embedder path, not a leak.
    """

    async def _embed(text: str) -> list[float]:
        vec = [0.0] * dim
        vec[0] = float(len(text))
        return vec

    return _embed


@contextmanager
def get_database_tripwire(monkeypatch: Any, module: Any):
    """Make `module.get_database` explode so any fallback to the global
    Mongo handle fails loudly.

    Established in #14 for write_memory. Tools that take `collection=None`
    must be given an explicit collection in tests. If a future refactor
    silently reaches for `get_database()` instead, this raises and the
    test fails loud.

    Usage:
        with get_database_tripwire(monkeypatch, agent.tools.write_memory):
            await write_memory(params, collection=injected_coll, ...)
    """

    def _explode():
        raise AssertionError(
            f"{module.__name__} must use the injected `collection` kwarg, "
            f"not get_database()"
        )

    monkeypatch.setattr(module, "get_database", _explode)
    try:
        yield
    finally:
        # monkeypatch handles teardown; the try/finally is just for clarity
        # if the body raises.
        pass
