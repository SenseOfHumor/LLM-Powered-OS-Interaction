import json
from typing import Any, Dict, Optional

from pydantic import ValidationError

from service.llm_client import LLMClient
from models import Plan


def _extract_json(raw: str) -> Optional[Dict[str, Any]]:
    """
    Try to parse the model response as JSON. If it fails, try to strip
    possible ```json ... ``` or ``` ... ``` fences. Return dict or None.
    """
    raw = raw.strip()
    if not raw:
        return None

    # First attempt: direct JSON
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Second attempt: strip markdown fences
    if "```" in raw:
        # Find the first code fence
        start_idx = raw.find("```")
        if start_idx != -1:
            # Skip past the opening fence and optional language name
            start_line_end = raw.find("\n", start_idx)
            if start_line_end == -1:
                return None

            # Find the closing fence
            end_idx = raw.find("```", start_line_end)
            if end_idx != -1:
                # Extract content between fences
                json_content = raw[start_line_end + 1 : end_idx].strip()
                try:
                    return json.loads(json_content)
                except json.JSONDecodeError:
                    pass

        # Fallback: try line-by-line approach
        lines = raw.splitlines()
        inner: list[str] = []
        in_fence = False
        for line in lines:
            if line.strip().startswith("```"):
                if not in_fence:
                    in_fence = True
                else:
                    break  # Found closing fence
                continue
            if in_fence:
                inner.append(line)

        joined = "\n".join(inner).strip()
        if joined:
            try:
                return json.loads(joined)
            except json.JSONDecodeError:
                pass

    return None


def get_action_plan(
    llm: LLMClient,
    user_query: str,
    tools: str,
) -> Optional[Plan]:
    """
    Ask the LLM for a JSON action plan and parse it into a Plan model.

    Returns:
        Plan instance or None if parsing / validation failed.
    """
    raw = llm.chat(user_query=user_query, mode="action", tools_summary=tools)

    data = _extract_json(raw)
    if data is None:
        return None

    try:
        plan = Plan.model_validate(data)
    except ValidationError:
        return None

    return plan
