"""Tests for the tenant-aware JSON storage backend (Phase 1a spine)."""

import pytest

from backend.storage_backend import JsonStorageBackend


def test_tenant_isolation(tmp_path):
    """A user can never read another user's conversation by id (the core guarantee)."""
    store = JsonStorageBackend(str(tmp_path))
    a = store.create_conversation("anonA")
    b = store.create_conversation("anonB")

    assert store.get_conversation("anonA", b["id"]) is None      # A blocked from B
    assert store.get_conversation("anonB", b["id"]) is not None   # B can read own
    assert [c["id"] for c in store.list_conversations("anonA")] == [a["id"]]
    assert [c["id"] for c in store.list_conversations("anonB")] == [b["id"]]


def test_append_messages_and_title(tmp_path):
    store = JsonStorageBackend(str(tmp_path))
    cid = store.create_conversation("u1")["id"]

    store.append_user_message("u1", cid, "안녕하세요")
    store.append_assistant_message(
        "u1", cid,
        {"evidence_brief": "", "sources": []}, [], [],
        {"model": "x", "response": "답변입니다", "sources": []},
    )
    store.update_title("u1", cid, "수유 질문")

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
