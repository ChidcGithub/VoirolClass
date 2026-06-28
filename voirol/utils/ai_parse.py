import json

from voirol.utils.logger import get_logger

logger = get_logger("utils.ai_parse")


def parse_ai_json_response(response: str) -> dict | None:
    try:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
        cleaned = cleaned.strip("`").strip()

        result = json.loads(cleaned)
        if not isinstance(result, dict):
            logger.warning(f"AI returned non-dict JSON: {result}")
            return None
        return result
    except json.JSONDecodeError:
        logger.warning(f"AI returned invalid JSON: {response}")
        return None
