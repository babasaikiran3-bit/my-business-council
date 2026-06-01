"""Tests for the tenant-aware JSON storage backend (Phase 1a spine + WS-3 durability)."""

import asyncio
import json

import pytest

from backend.storage_backend import JsonStorageBackend, StorageCorruptionError


def test_tenant_isolation(tmp_path):
    """A user can never read another user's conversation by id (the core guarantee)."""
    store = JsonStorageBackend(str(tmp_path))
    a = store.create_conversation("anonA")
    b = store.create_conversation("anonB")

    assert store.get_conversation("anonA", b["id"]) is None      # A blocked from B
    assert store.get_conversation("anonB", b["id"]) is not None   # B can read own
    assert [c["id"] for c in store.list_conversations("anonA")] == [a["id"]]
    assert [c["id"] for c in store.list_conversations("anonB")] == [b["id"]]


async def test_append_messages_and_title(tmp_path):
    store = JsonStorageBackend(str(tmp_path))
    cid = store.create_conversation("u1")["id"]

    await store.append_user_message("u1", cid, "안녕하세요")
    await store.append_assistant_message(
        "u1", cid,
        {"evidence_brief": "", "sources": []}, [], [],
        {"model": "x", "response": "답변입니다", "sources": []},
    )
    await store.update_title("u1", cid, "수유 질문")

    conv = store.get_conversation("u1", cid)
    assert conv["title"] == "수유 질문"
    assert conv["messages"][0] == {"role": "user", "content": "안녕하세요"}
    assert conv["messages"][1]["role"] == "assistant"
    assert conv["messages"][1]["stage3"]["response"] == "답변입니다"
    assert store.list_conversations("u1")[0]["message_count"] == 2


def test_unsafe_ids_are_rejected(tmp_path):
    store = JsonStorageBackend(str(tmp_path))
    # Path-traversal conversation id is treated as "not found", never escapes the dir.
    assert store.get_conversation("u1", "../secret") is None
    # Path-traversal user id is rejected outright.
    with pytest.raises(ValueError):
        store.list_conversations("../../etc")


def test_list_empty_for_new_user(tmp_path):
    store = JsonStorageBackend(str(tmp_path))
    assert store.list_conversations("nobody") == []


# --- WS-3 durability ---------------------------------------------------------
async def test_concurrent_appends_lose_zero_messages(tmp_path):
    """100 concurrent appends to ONE conversation lose nothing — proves the asyncio.Lock
    (a flock-only design would race here under same-process async interleaving)."""
    store = JsonStorageBackend(str(tmp_path))
    cid = store.create_conversation("u1")["id"]
    await asyncio.gather(*[store.append_user_message("u1", cid, f"m{i}") for i in range(100)])
    conv = store.get_conversation("u1", cid)
    assert len(conv["messages"]) == 100
    assert {m["content"] for m in conv["messages"]} == {f"m{i}" for i in range(100)}


def test_corrupted_file_is_quarantined_and_skipped(tmp_path):
    store = JsonStorageBackend(str(tmp_path))
    good = store.create_conversation("u1")["id"]
    bad = store.create_conversation("u1")["id"]
    bad_path = tmp_path / "u1" / f"{bad}.json"
    bad_path.write_text("{ this is not valid json", encoding="utf-8")

    listed = [c["id"] for c in store.list_conversations("u1")]
    assert listed == [good]  # one bad file never 500s the listing
    assert (tmp_path / "u1" / f"{bad}.json.corrupted").exists()


def test_get_corrupted_conversation_raises(tmp_path):
    store = JsonStorageBackend(str(tmp_path))
    cid = store.create_conversation("u1")["id"]
    (tmp_path / "u1" / f"{cid}.json").write_text("not json", encoding="utf-8")
    with pytest.raises(StorageCorruptionError):
        store.get_conversation("u1", cid)


async def test_partial_save_shape_reloads_without_empty_panels(tmp_path):
    """A mid-pipeline partial persists stage0+stage1 (real) with empty later stages,
    marked short_circuit, and reloads intact (frontend keys on short_circuit/length)."""
    store = JsonStorageBackend(str(tmp_path))
    cid = store.create_conversation("u1")["id"]
    stage0 = {"evidence_brief": "근거", "sources": [{"url": "https://who.int/x", "title": "WHO"}]}
    stage1 = [{"model": "m1", "response": "부분 답변", "sources": []}]
    await store.append_assistant_message(
        "u1", cid, stage0, stage1, [], {"model": "incomplete", "response": "중단됨", "sources": []},
        short_circuit=True,
    )
    msg = store.get_conversation("u1", cid)["messages"][-1]
    assert msg["short_circuit"] is True
    assert msg["stage0"]["evidence_brief"] == "근거"
    assert len(msg["stage1"]) == 1
    assert msg["stage2"] == []  # empty later stage — frontend skips its panel


async def test_unicode_roundtrips_through_atomic_write(tmp_path):
    store = JsonStorageBackend(str(tmp_path))
    cid = store.create_conversation("u1")["id"]
    await store.update_title("u1", cid, "신생아 발열 응급 🚑")
    raw = json.loads((tmp_path / "u1" / f"{cid}.json").read_text(encoding="utf-8"))
    assert raw["title"] == "신생아 발열 응급 🚑"


async def test_delete_conversation(tmp_path):
    store = JsonStorageBackend(str(tmp_path))
    cid = store.create_conversation("u1")["id"]
    assert await store.delete_conversation("u1", cid) is True
    assert store.get_conversation("u1", cid) is None
    assert await store.delete_conversation("u1", cid) is False  # already gone
