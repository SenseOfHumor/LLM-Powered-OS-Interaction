from typing import Any, Dict

from pydantic import BaseModel, Field


class Action(BaseModel):
    tool: str = Field(..., description="Name of the tool to call, e.g. 'run_shell'")
    args: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments for the tool, as a JSON object.",
    )
