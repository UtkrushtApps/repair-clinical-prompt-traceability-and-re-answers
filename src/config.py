import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_base_url: str
    assistant_model: str
    judge_model: str
    database_url: str
    judge_samples_per_output: int


def get_settings() -> Settings:
    sample_count = int(os.getenv("JUDGE_SAMPLES_PER_OUTPUT", "3"))
    if sample_count < 1:
        raise ValueError("JUDGE_SAMPLES_PER_OUTPUT must be at least 1")
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        assistant_model=os.getenv("ASSISTANT_MODEL", "gpt-4o-mini"),
        judge_model=os.getenv("JUDGE_MODEL", "gpt-4o-mini"),
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql://clinical:clinical@localhost:54329/clinical_prompts",
        ),
        judge_samples_per_output=sample_count,
    )
