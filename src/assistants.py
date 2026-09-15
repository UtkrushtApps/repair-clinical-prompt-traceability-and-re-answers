import json
from typing import Any

from src import db
from src.config import get_settings
from src.llm_client import LLMClient
from src.prompt_store import ASSISTANTS, get_prompt


def run_assistant(
    assistant: str,
    case: dict[str, Any],
    variant: str = "proposed",
    client: LLMClient | None = None,
) -> dict[str, Any]:
    if assistant not in ASSISTANTS:
        raise ValueError(f"unknown assistant: {assistant}")
    if case.get("assistant") and case["assistant"] != assistant:
        raise ValueError("case assistant does not match requested assistant")

    selected = get_prompt(assistant, variant)
    settings = get_settings()
    llm = client or LLMClient(settings)
    completion = llm.complete(
        messages=[
            {"role": "system", "content": selected["text"]},
            {"role": "user", "content": case["context"]},
        ],
        model=settings.assistant_model,
        temperature=0.2,
    )
    if not completion.text.strip():
        raise RuntimeError(f"{assistant} returned an empty response")

    row = db.execute(
        """
        INSERT INTO outputs (
            case_id, assistant, prompt_variant, prompt_identity, output_text,
            prompt_tokens, completion_tokens
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id, created_at
        """,
        (
            case["id"],
            assistant,
            variant,
            selected["identity"],
            completion.text,
            completion.prompt_tokens,
            completion.completion_tokens,
        ),
    )
    if row is None:
        raise RuntimeError("failed to persist assistant output")
    return {
        "id": row["id"],
        "created_at": row["created_at"].isoformat(),
        "assistant": assistant,
        "case_id": case["id"],
        "prompt_variant": variant,
        "prompt_identity": selected["identity"],
        "output": completion.text,
        "usage": {
            "prompt_tokens": completion.prompt_tokens,
            "completion_tokens": completion.completion_tokens,
        },
        "case": json.loads(json.dumps(case)),
    }
