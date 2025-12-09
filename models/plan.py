from typing import List

from pydantic import BaseModel, Field

from .action import Action


class Plan(BaseModel):
    plan: str = Field(
        default="No high-level plan provided.",
        description="Natural language explanation of what the agent will do.",
    )
    actions: List[Action] = Field(
        default_factory=list,
        description="Ordered list of tool calls to perform.",
    )
