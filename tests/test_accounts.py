"""Tests for accounts: identity linking (merge-in-place), child profiles, consents.

The mutating methods (link_identity / add_child / delete_child / record_consents) are
``async`` (each holds a per-key asyncio.Lock across its read→mutate→write); read methods
stay sync. asyncio_mode=auto runs the ``async def`` tests directly.
"""

import asyncio
from datetime import date, timedelta

import pytest

from backend.accounts import AccountStore, age_days_from_birthdate, REQUIRED_CONSENTS
from backend.safety import age_band


def test_age_days_from_birthdate_and_boundary():
    born = date(2024, 1, 1)
    assert age_days_from_birthdate(born.isoformat(), today=born) == 0
    assert age_days_from_birthdate(born.isoformat(), today=born + timedelta(days=89)) == 89
    assert age_days_from_birthdate(born.isoformat(), today=born + timedelta(days=90)) == 90
    # newborn→infant flips at exactly 90 days
    assert age_band(age_days_from_birthdate(born.isoformat(), today=born + timedelta(days=89))) == "newborn"
    assert age_band(age_days_from_birthdate(born.isoformat(), today=born + timedelta(days=90))) == "infant"
    assert age_days_from_birthdate("2024-01-01", today=date(2023, 1, 1)) is None  # future
    assert age_days_from_birthdate("not-a-date") is None


async def test_link_identity_merge_in_place(tmp_path):
    store = AccountStore(str(tmp_path))
    # First sign-in links Kakao K123 to the caller's existing (anon) account in place.
    assert await store.link_identity("anon1", "kakao", "K123", "민지") == "anon1"
    assert store.is_authenticated("anon1")
    assert store.find_user_by_identity("kakao", "K123") == "anon1"
    # A later sign-in from a different anon session with the SAME identity resumes anon1.
    assert await store.link_identity("anon2", "kakao", "K123") == "anon1"
    assert not store.is_authenticated("anon2")


async def test_link_identity_concurrent_same_identity_no_split(tmp_path):
    """Two concurrent first-logins for the SAME identity yield exactly one index + link."""
    store = AccountStore(str(tmp_path))
    results = await asyncio.gather(
        store.link_identity("anonA", "kakao", "SAME", "A"),
        store.link_identity("anonB", "kakao", "SAME", "B"),
    )
    # Both resolve to the same winning account (identity-keyed lock serialises them).
    assert results[0] == results[1]
    winner = results[0]
    assert store.find_user_by_identity("kakao", "SAME") == winner
    # Exactly one identity file written.
    idfiles = list((tmp_path / "identities").glob("*.json"))
    assert len(idfiles) == 1


async def test_child_crud_and_isolation(tmp_path):
    store = AccountStore(str(tmp_path))
    child = await store.add_child("u1", "아기", "2024-06-01")
    assert child["id"] and child["name"] == "아기"
    assert [c["id"] for c in store.list_children("u1")] == [child["id"]]
    assert store.get_child("u1", child["id"])["birthdate"] == "2024-06-01"
    assert store.list_children("other") == []  # isolated
    assert await store.delete_child("u1", child["id"]) is True
    assert store.list_children("u1") == []


async def test_child_validation(tmp_path):
    store = AccountStore(str(tmp_path))
    with pytest.raises(ValueError):
        await store.add_child("u1", "", "2024-06-01")
    with pytest.raises(ValueError):
        await store.add_child("u1", "x", "not-a-date")
    with pytest.raises(ValueError):
        await store.add_child("u1", "bad\x00name", "2024-06-01")  # control char rejected


async def test_consents(tmp_path):
    store = AccountStore(str(tmp_path))
    assert store.has_required_consents("u1") is False
    await store.record_consents("u1", REQUIRED_CONSENTS, "1.0")
    assert store.has_required_consents("u1") is True
    await store.record_consents("u1", ["bogus"], "1.0")  # unknown kinds ignored
    assert "bogus" not in store.get_consents("u1")
