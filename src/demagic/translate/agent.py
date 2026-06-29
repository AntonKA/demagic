"""Pydantic AI translation agent (optional `[api]` headless mode only).

The deterministic, agent-driven path does not import this module - it uses
`demagic.translate.context` instead, which has no LLM-SDK dependency.
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models import Model

from demagic.translate.context import SYSTEM_PROMPT


class TranslationResult(BaseModel):
    python_code: str = Field(description="Complete Python module body with run()")
    assumptions: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    flags: list[str] = Field(default_factory=list,
                             description="Behaviors needing human review")


def build_agent(model: Model | str) -> "Agent[None, TranslationResult]":
    agent: Agent[None, TranslationResult] = Agent(  # ty: ignore[invalid-assignment]
        model, output_type=TranslationResult, system_prompt=SYSTEM_PROMPT)
    return agent
