import json

from src.evaluate import run_evaluation
from src.llm_client import Completion


class AssistantDouble:
    def complete(self, messages, model, temperature, **kwargs):
        prompt = messages[0]["content"]
        proposed = "typical for the study" in prompt or "likely clinical" in prompt
        text = "proposed polished draft" if proposed else "approved cautious draft"
        return Completion(text=text, prompt_tokens=10, completion_tokens=5)


class JudgeDouble:
    def __init__(self):
        self.index = 0

    def complete(self, messages, model, temperature, **kwargs):
        proposed = "proposed polished draft" in messages[1]["content"]
        offset = (-0.1, 0.0, 0.1)[self.index % 3]
        self.index += 1
        if proposed:
            scores = {
                "factuality": 3.0 + offset,
                "coverage": 4.8 + offset,
                "usability": 4.7 + offset,
            }
        else:
            scores = {
                "factuality": 4.6 + offset,
                "coverage": 3.2 + offset,
                "usability": 3.4 + offset,
            }
        return Completion(text=json.dumps(scores), prompt_tokens=8, completion_tokens=4)


def _approved(report):
    return report["decision"]["approved"]


def test_proposed_release_names_dimension_and_is_rejected():
    report = run_evaluation(
        variant="proposed",
        assistant_client=AssistantDouble(),
        judge_client=JudgeDouble(),
    )
    encoded = json.dumps(report).lower()
    assert _approved(report) is False
    assert "factuality" in encoded
    assert "coverage" in encoded
    assert "usability" in encoded
    assert "spread" in encoded or "variance" in encoded or "standard_deviation" in encoded or "confidence" in encoded


def test_unchanged_repeated_run_has_same_verdict():
    first = run_evaluation(
        variant="proposed",
        assistant_client=AssistantDouble(),
        judge_client=JudgeDouble(),
    )
    second = run_evaluation(
        variant="proposed",
        assistant_client=AssistantDouble(),
        judge_client=JudgeDouble(),
    )
    assert _approved(first) == _approved(second)
