import json

import requests

from voirol.ai.engine import AIEngine
from voirol.utils.logger import get_logger

logger = get_logger("ai.openai")


class OpenAIEngine(AIEngine):
    def __init__(self, api_url: str, api_key: str, model: str):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def chat(self, messages: list[dict], temperature: float, timeout: int) -> str | None:
        try:
            resp = requests.post(
                f"{self.api_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": 256,
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return content.strip()
        except requests.Timeout:
            logger.warning("AI request timed out")
            return None
        except requests.RequestException as e:
            logger.warning(f"AI request failed: {e}")
            return None
        except (KeyError, json.JSONDecodeError, IndexError) as e:
            logger.warning(f"AI response parse failed: {e}")
            return None
