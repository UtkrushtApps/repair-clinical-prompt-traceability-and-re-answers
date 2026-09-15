from src.config import get_settings
from src.llm_client import LLMClient


def main() -> None:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    result = LLMClient(settings).complete(
        messages=[{"role": "user", "content": "Reply OK."}],
        model=settings.assistant_model,
        temperature=0,
        max_tokens=3,
    )
    if not result.text:
        raise RuntimeError("model ping returned no text")
    print("model ping passed")


if __name__ == "__main__":
    main()
