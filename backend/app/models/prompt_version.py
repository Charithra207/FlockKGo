from dataclasses import dataclass


@dataclass(frozen=True)
class PromptVersion:
    trip_id: str
    prompt_version: str
