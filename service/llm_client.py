import os
import json
from functools import lru_cache
from pathlib import Path
from typing import List, Dict, Any

import requests


@lru_cache(maxsize=1)
def _load_prompt_sections() -> Dict[str, str]:
    """
    Load and split patterns/welcome_prompt.md into sections based on headings:

    ## CHAT
    ... text ...

    ## ACTION
    ... text ...

    Returns a dict like: {"CHAT": "...", "ACTION": "..."}.
    """
    # service/llm_client.py -> project root -> patterns/welcome_prompt.md
    root = Path(__file__).resolve().parent.parent
    prompt_path = root / "patterns" / "welcome_prompt.md"

    if not prompt_path.exists():
        # Fallback minimal prompts if file is missing
        return {
            "CHAT": (
                "You are a helpful offline terminal assistant. "
                "Answer succinctly and safely."
            ),
            "ACTION": (
                "You are a terminal control agent. Respond ONLY with JSON using "
                'schema: {"plan": string, "actions": [{"tool": "...", "args": {...}}]}.\n'
                "Valid tools:\n{{TOOLS}}\n"
                "No extra text outside JSON."
            ),
        }

    text = prompt_path.read_text(encoding="utf-8")

    sections: Dict[str, str] = {}
    current_key: str | None = None
    buffer: list[str] = []

    def _flush():
        nonlocal current_key, buffer
        if current_key is not None:
            sections[current_key] = "".join(buffer).strip()
        buffer = []

    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("## "):
            # New section
            heading = stripped[3:].strip().upper()
            if heading in ("CHAT", "ACTION"):
                _flush()
                current_key = heading
                continue
        if current_key is not None:
            buffer.append(line)

    _flush()

    # Basic safety defaults if missing
    if "CHAT" not in sections:
        sections["CHAT"] = (
            "You are a helpful offline terminal assistant. "
            "Answer succinctly and safely."
        )
    if "ACTION" not in sections:
        sections["ACTION"] = (
            "You are a terminal control agent. Respond ONLY with JSON using "
            'schema: {"plan": string, "actions": [{"tool": "...", "args": {...}}]}.\n'
            "Valid tools:\n{{TOOLS}}\n"
            "No extra text outside JSON."
        )

    return sections


class LLMClient:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = 60,
    ) -> None:
        self.base_url = base_url or os.getenv(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        )
        self.model = model or os.getenv("TERMINAL_AGENT_MODEL", "llama3.2")
        self.timeout = timeout

    def _post_chat(self, messages: List[Dict[str, str]]) -> str:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        resp = requests.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        content = data.get("message", {}).get("content", "")
        return content

    def chat(
        self, user_query: str, mode: str = "chat", tools_summary: str | None = None
    ) -> str:
        """
        mode = 'chat' | 'action'
        If mode == 'action', we instruct model to output ONLY JSON.
        """
        sections = _load_prompt_sections()

        if mode == "action":
            system_prompt = sections["ACTION"]
            if tools_summary:
                system_prompt = system_prompt.replace("{{TOOLS}}", tools_summary)
            else:
                system_prompt = system_prompt.replace("{{TOOLS}}", "")
        else:
            system_prompt = sections["CHAT"]

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
        ]

        return self._post_chat(messages)
