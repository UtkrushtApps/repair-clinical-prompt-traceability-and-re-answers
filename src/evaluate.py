import argparse
import json
import logging
from pathlib import Path
from statistics import fmean, pstdev
from typing import Any

from src import db
from src.assistants import run_assistant
from src.config import get_settings
from src.judge import DIMENSIONS, score_output
from src.llm_client import LLMClient

REPORT_PATH = Path("artifacts/evaluation-report.json")
MINIMUM_MEANINGFUL_DROP = 0.15
LOGGER = logging.getLogger(__name__)


def load_cases() -> list[dict[str, Any]]:
    return db.fetch_all(
        "SELECT id, assistant, slice_name, context FROM evaluation_cases ORDER BY id"
    )


def load_approved_baseline() -> dict[str, dict[str, Any]]:
    rows = db.fetch_all(
        """
        SELECT dimension, mean_score, score_spread, observation_count, release_name
        FROM approved_baseline ORDER BY dimension
        """
    )
    return {row["dimension"]: row for row in rows}


def summarize_dimensions(
    judgments: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    if not judgments:
        raise ValueError("cannot summarize an empty judgment set")
    result: dict[str, dict[str, Any]] = {}
    for dimension in DIMENSIONS:
        observations = [
            {
                "sample_id": item["sample_id"],
                "output_id": item["output_id"],
                "case_id": item["case_id"],
                "assistant": item["assistant"],
                "score": float(item["dimensions"][dimension]),
            }
            for item in judgments
        ]
        scores = [observation["score"] for observation in observations]
        result[dimension] = {
            "mean_score": fmean(scores),
            "score_spread": pstdev(scores) if len(scores) > 1 else 0.0,
            "minimum_score": min(scores),
            "maximum_score": max(scores),
            "observation_count": len(scores),
            "observations": observations,
        }
    return result


def release_decision(
    dimension_results: dict[str, dict[str, Any]],
    baseline: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Reject when any dimension falls meaningfully below its approved baseline.

    The approved baseline spread is the pre-declared variation allowance, with
    a small floor. The function is pure, making equivalent observations yield
    the same decision regardless of input ordering or run identity.
    """
    comparisons: dict[str, dict[str, Any]] = {}
    failed: list[str] = []
    for dimension in sorted(DIMENSIONS):
        if dimension not in dimension_results:
            raise ValueError(f"missing candidate dimension: {dimension}")
        if dimension not in baseline:
            raise ValueError(f"missing approved baseline dimension: {dimension}")
        candidate = float(dimension_results[dimension]["mean_score"])
        approved = float(baseline[dimension]["mean_score"])
        approved_spread = float(baseline[dimension]["score_spread"])
        allowed_drop = max(MINIMUM_MEANINGFUL_DROP, approved_spread)
        threshold = approved - allowed_drop
        passed = candidate >= threshold
        if not passed:
            failed.append(dimension)
        comparisons[dimension] = {
            "candidate_mean": candidate,
            "candidate_spread": float(
                dimension_results[dimension]["score_spread"]
            ),
            "approved_mean": approved,
            "approved_spread": approved_spread,
            "approved_observation_count": int(
                baseline[dimension]["observation_count"]
            ),
            "approved_release": baseline[dimension]["release_name"],
            "allowed_drop": allowed_drop,
            "minimum_acceptable_mean": threshold,
            "delta": candidate - approved,
            "passed": passed,
        }
    return {
        "approved": not failed,
        "reason": (
            "all scored dimensions meet the approved comparison"
            if not failed
            else "meaningful regression in: " + ", ".join(failed)
        ),
        "failed_dimensions": failed,
        "comparisons": comparisons,
    }


def run_evaluation(
    variant: str = "proposed",
    assistant_client: LLMClient | None = None,
    judge_client: LLMClient | None = None,
) -> dict[str, Any]:
    cases = load_cases()
    if not cases:
        raise RuntimeError("no evaluation cases are available")

    settings = get_settings()
    judgments: list[dict[str, Any]] = []
    output_ids: list[int] = []
    for case in cases:
        LOGGER.info("running %s for case %s", case["assistant"], case["id"])
        output = run_assistant(
            case["assistant"], case, variant=variant, client=assistant_client
        )
        output_ids.append(output["id"])
        for _ in range(settings.judge_samples_per_output):
            judgments.append(score_output(output, client=judge_client))

    dimensions = summarize_dimensions(judgments)
    baseline = load_approved_baseline()
    decision = release_decision(dimensions, baseline)
    overall = fmean(item["mean_score"] for item in dimensions.values())

    run_row = db.execute(
        """
        INSERT INTO evaluation_runs (variant, report, approved)
        VALUES (%s, '{}'::jsonb, %s)
        RETURNING id, created_at
        """,
        (variant, decision["approved"]),
    )
    if run_row is None:
        raise RuntimeError("failed to persist evaluation run")

    report = {
        "run_id": run_row["id"],
        "created_at": run_row["created_at"].isoformat(),
        "variant": variant,
        "case_count": len(cases),
        "judge_samples_per_output": settings.judge_samples_per_output,
        "output_ids": output_ids,
        "overall_score": overall,
        "dimensions": dimensions,
        "approved_baseline": baseline,
        "raw_judgments": judgments,
        "decision": decision,
    }
    db.execute(
        "UPDATE evaluation_runs SET report = %s::jsonb WHERE id = %s",
        (json.dumps(report), run_row["id"]),
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", default="proposed", choices=("approved", "proposed"))
    args = parser.parse_args()
    print(json.dumps(run_evaluation(args.variant), indent=2))


if __name__ == "__main__":
    main()
