import uuid

from src import db
from src.prompt_store import get_prompt, restore_prompt, update_prompt, update_shared


def _variant():
    return "grading-" + uuid.uuid4().hex


def _insert_variant(variant, assistant, text):
    db.execute(
        "INSERT INTO prompts (assistant, variant, full_text) VALUES (%s, %s, %s)",
        (assistant, variant, text),
    )


def test_edits_have_distinct_resolvable_identities():
    variant = _variant()
    first_text = "First exact clinical writing instruction."
    second_text = "Second exact clinical writing instruction."
    _insert_variant(variant, "protocol_summary", first_text)
    first = get_prompt("protocol_summary", variant)
    update_prompt("protocol_summary", variant, second_text)
    second = get_prompt("protocol_summary", variant)
    assert first["identity"]
    assert second["identity"]
    assert first["identity"] != second["identity"]
    restored = restore_prompt("protocol_summary", first["identity"])
    assert restored["identity"] == first["identity"]
    assert restored["text"] == first_text
    assert get_prompt("protocol_summary")["text"] == first_text


def test_shared_change_updates_both_and_preserves_prior_text():
    before = {
        name: get_prompt(name)
        for name in ("protocol_summary", "safety_narrative")
    }
    marker = "Shared grading clause " + uuid.uuid4().hex
    update_shared(marker)
    after = {
        name: get_prompt(name)
        for name in ("protocol_summary", "safety_narrative")
    }
    for name in before:
        assert before[name]["identity"] != after[name]["identity"]
        assert marker in after[name]["text"]
        restored = restore_prompt(name, before[name]["identity"])
        assert restored["text"] == before[name]["text"]
