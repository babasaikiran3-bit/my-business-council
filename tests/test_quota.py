"""Tests for the per-user daily quota (the hard spend ceiling)."""

import json

from backend.quota import DailyQuota


async def test_quota_blocks_over_limit(tmp_path):
    q = DailyQuota(str(tmp_path), limit=3)
    for _ in range(3):
        assert await q.check_and_increment("u1") is True
    assert await q.check_and_increment("u1") is False  # 4th rejected
    # A rejected request does not consume further quota / corrupt the counter.
    assert await q.check_and_increment("u1") is False


async def test_quota_per_user_isolated(tmp_path):
    q = DailyQuota(str(tmp_path), limit=1)
    assert await q.check_and_increment("a") is True
    assert await q.check_and_increment("a") is False
    assert await q.check_and_increment("b") is True  # separate user unaffected


async def test_quota_resets_on_new_day(tmp_path):
    q = DailyQuota(str(tmp_path), limit=2)
    q.base.mkdir(parents=True, exist_ok=True)
    (q.base / "u1.json").write_text(json.dumps({"date": "2000-01-01", "count": 99}), encoding="utf-8")
    # Stale date is ignored — today starts fresh at 1.
    assert await q.check_and_increment("u1") is True
    data = json.loads((q.base / "u1.json").read_text(encoding="utf-8"))
    assert data["count"] == 1 and data["date"] != "2000-01-01"
