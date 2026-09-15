from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from src.config import Settings, get_settings


@dataclass(frozen=True)
class Completion:
    text: str
    prompt_tokens: int
    completion_tokens: int


class LLMClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._client = OpenAI(
            api_key=self.settings.openai_api_key or "key-not-configured",
            base_url=self.settings.openai_base_url,
        )

    def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        response_format: dict[str, Any] | None = None,
        max_tokens: int | None = None,
    ) -> Completion:
        request: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format is not None:
            request["response_format"] = response_format
        if max_tokens is not None:
            request["max_tokens"] = max_tokens

        response = self._client.chat.completions.create(**request)
        if not response.choices:
            raise RuntimeError("model returned no completion choices")
        usage = response.usage
        return Completion(
            text=response.choices[0].message.content or "",
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )
