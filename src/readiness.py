import json
from pathlib import Path

from src import assistants, db, evaluate, judge, prompt_store
from src.config import get_settings
from src.llm_client import LLMClient


def main() -> None:
    settings = get_settings()
    LLMClient(settings)
    db.ensure_schema()
    prompt_store.initialize_store()

    file_cases = [
        json.loads(line)
        for line in Path("data/cases.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    database_case_count = db.fetch_one("SELECT count(*) AS count FROM evaluation_cases")
    prompt_count = db.fetch_one("SELECT count(*) AS count FROM prompts")
    if (
        not file_cases
        or database_case_count is None
        or prompt_count is None
        or database_case_count["count"] < 1
        or prompt_count["count"] < 1
    ):
        raise RuntimeError("seeded data is not ready")

    for assistant in prompt_store.ASSISTANTS:
        selected = prompt_store.get_prompt(assistant)
        historical = prompt_store.get_prompt_by_identity(selected["identity"])
        if not selected["text"] or historical["text"] != selected["text"]:
            raise RuntimeError("prompt identity does not resolve to its exact text")
    if not all((assistants, evaluate, judge)):
        raise RuntimeError("application modules did not load")
    print("application checks passed")


if __name__ == "__main__":
    main()
