import json
from pathlib import Path

from src import db
from src.config import get_settings
from src.llm_client import LLMClient
from src.prompt_store import get_prompt, get_prompt_by_identity


def test_client_constructs_without_provider_access():
    client = LLMClient(get_settings())
    assert client is not None


def test_seeded_store_is_reachable():
    db.ensure_schema()
    row = db.fetch_one("SELECT count(*) AS count FROM prompts")
    assert row is not None
    assert row["count"] >= 1


def test_seeded_prompt_resolves():
    prompt = get_prompt("protocol_summary")
    assert prompt["text"]
    assert prompt["identity"]
    assert get_prompt_by_identity(prompt["identity"])["text"] == prompt["text"]


def test_case_fixture_parses():
    rows = [json.loads(line) for line in Path("data/cases.jsonl").read_text().splitlines()]
    assert len(rows) >= 2
    assert all(rows)
