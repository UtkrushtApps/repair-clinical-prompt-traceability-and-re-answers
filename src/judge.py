import json
from pathlib import Path
from typing import Any

from src import db
from src.config import get_settings
from src.llm_client import LLMClient

DIMENSIONS = ("factuality", "coverage", "usability")
JUDGE_PROMPT_PATH = Path("prompts/judge.txt")


def _parse_scores(text: str) -> tuple[dict[str, Any], dict[str, float]]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"judge returned invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("judge response must be a JSON object")

    scores: dict[str, float] = {}
    for dimension in DIMENSIONS:
        try:
            score = float(parsed[dimension]["score"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"judge response lacks a valid {dimension} score") from exc
        if not 1.0 <= score <= 5.0:
            raise ValueError(f"{dimension} score must be between 1 and 5")
        scores[dimension] = score
    return parsed, scores


def score_output(
    output_record: dict[str, Any],
    client: LLMClient | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    llm = client or LLMClient(settings)
    completion = llm.complete(
        messages=[
            {
                "role": "system",
                "content": JUDGE_PROMPT_PATH.read_text(encoding="utf-8"),
            },
            {
                "role": "user",
                "content": (
                    "CASE FACTS:\n"
                    + output_record["case"]["context"]
                    + "\n\nASSISTANT OUTPUT:\n"
                    + output_record["output"]
                ),
            },
        ],
        model=settings.judge_model,
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    parsed, scores = _parse_scores(completion.text)
    overall = sum(scores.values()) / len(scores)
    row = db.execute(
        """
        INSERT INTO judge_samples (
            output_id, raw_response, overall_score, dimension_scores
        ) VALUES (%s, %s::jsonb, %s, %s::jsonb)
        RETURNING id
        """,
        (
            output_record["id"],
            json.dumps(parsed),
            overall,
            json.dumps(scores),
        ),
    )
    if row is None:
        raise RuntimeError("failed to persist judge sample")
    return {
        "sample_id": row["id"],
        "output_id": output_record["id"],
        "case_id": output_record["case_id"],
        "assistant": output_record["assistant"],
        "overall_score": overall,
        "dimensions": scores,
        "raw": parsed,
    }
