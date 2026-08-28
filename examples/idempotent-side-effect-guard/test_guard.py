import json

import pytest

from guard import EffectReceiptStore, ReceiptStateError


def test_claim_then_commit_round_trip(tmp_path):
    store = EffectReceiptStore(tmp_path)
    key = store.key("send-email", {"recipient": "demo@example.com", "body": "hello"})
    assert store.claim(key, action="send-email")
    assert not store.claim(key, action="send-email")
    path = store.commit(key, action="send-email", evidence={"provider_id": "demo-1"})
    assert store.already_done(key)
    assert json.loads(path.read_text())["evidence"]["provider_id"] == "demo-1"


def test_claim_survives_restart_and_blocks_retry(tmp_path):
    first = EffectReceiptStore(tmp_path)
    key = first.key("publish", {"id": 7})
    assert first.claim(key, action="publish")
    restarted = EffectReceiptStore(tmp_path)
    assert not restarted.claim(key, action="publish")
    assert not restarted.already_done(key)


def test_unreadable_receipt_fails_closed(tmp_path):
    store = EffectReceiptStore(tmp_path)
    key = "broken"
    store.path_for(key).write_text("{not-json", encoding="utf-8")
    with pytest.raises(ReceiptStateError):
        store.already_done(key)
    with pytest.raises(ReceiptStateError):
        store.claim(key, action="send-email")


def test_key_is_order_independent(tmp_path):
    store = EffectReceiptStore(tmp_path)
    assert store.key("x", {"a": 1, "b": 2}) == store.key("x", {"b": 2, "a": 1})
