import json
import logging
import re
from typing import Any

from google import genai
from google.genai import types

from .. import config

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


class GeminiClient:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=config.GOOGLE_API_KEY)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> dict | list:
        """Call Gemini 2.5 Pro and parse a JSON response.

        Handles responses wrapped in ```json … ``` fences.
        Retries up to 3 times on empty or invalid JSON.
        """
        for attempt in range(1, 4):
            try:
                raw = self._call(system_prompt, user_prompt, temperature)
                return self._parse_json(raw)
            except (ValueError, json.JSONDecodeError) as exc:
                logger.warning(
                    "generate_json attempt %d/%d failed: %s", attempt, 3, exc
                )
                if attempt == 3:
                    raise RuntimeError(
                        f"Gemini returned invalid JSON after 3 attempts: {exc}"
                    ) from exc
        # unreachable — satisfies type checker
        raise RuntimeError("Unexpected exit from retry loop")

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> str:
        """Call Gemini 2.5 Pro and return the raw text response."""
        return self._call(system_prompt, user_prompt, temperature)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call(self, system_prompt: str, user_prompt: str, temperature: float) -> str:
        response = self._client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
            ),
        )
        text = (response.text or "").strip()
        if not text:
            raise ValueError("Gemini returned an empty response")
        return text

    @staticmethod
    def _parse_json(text: str) -> Any:
        # Strip ```json … ``` fences if present
        match = _FENCE_RE.search(text)
        if match:
            text = match.group(1).strip()
        return json.loads(text)


# Singleton
gemini_client = GeminiClient()
