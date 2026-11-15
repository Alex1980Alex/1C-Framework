"""Raw ChatAnthropic validation inputs used by framework callers."""

from typing import TypedDict


class AnthropicModelKwargs(TypedDict, total=False):
    """Preserve SDK aliases and optional-key omission before Pydantic validation."""

    model: str
    model_name: str
    temperature: float
    max_tokens: int
    api_key: str | None
    base_url: str
