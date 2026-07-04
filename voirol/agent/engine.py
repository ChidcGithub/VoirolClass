from voirol.agent.screen import ScreenAnalyzer, ScreenElement
from voirol.agent.skill_registry import SkillRegistry
from voirol.agent.prompt import build_system_prompt
from voirol.ai.openai_engine import OpenAIEngine
from voirol.utils.logger import get_logger
from voirol.utils.ai_parse import parse_ai_json_response
import pyautogui

logger = get_logger("agent.engine")

_engine_instance: "AgentEngine | None" = None


def set_current_engine(engine: "AgentEngine") -> None:
    global _engine_instance
    _engine_instance = engine


def get_current_engine() -> "AgentEngine | None":
    return _engine_instance


class AgentEngine:
    def __init__(
        self,
        screen_analyzer: ScreenAnalyzer,
        skill_registry: SkillRegistry,
        llm_engine: OpenAIEngine | None,
        max_steps: int = 30,
        system_prompt: str = "",
        temperature: float = 0.1,
        timeout: int = 15,
    ):
        self._screen = screen_analyzer
        self._registry = skill_registry
        self._llm = llm_engine
        self._max_steps = max_steps
        self._system_prompt = system_prompt
        self._temperature = temperature
        self._timeout = timeout

    @property
    def is_ready(self) -> bool:
        return self._llm is not None

    def _get_exclude_regions(self) -> list[tuple[int, int, int, int]]:
        sw, sh = pyautogui.size()
        return [(sw // 4, sh - 120, sw // 2, 120)]

    def execute(self, instruction: str) -> str:
        history: list[dict] = []
        self._screen._exclude_regions = self._get_exclude_regions()
        prev_skill = None
        prev_params_hash = None
        repeat_count = 0

        for step in range(1, self._max_steps + 1):
            logger.info(f"Step {step}/{self._max_steps}: capturing screen")

            screenshot = self._screen.capture()
            elements = self._screen.analyze(screenshot)
            observation = self._screen.format_observation(elements)
            schema = self._registry.get_schema_text()

            if repeat_count >= 3:
                warning = f"[LOOP_WARNING] 已连续{repeat_count}次执行同一操作({prev_skill})，界面无变化。不要继续此操作，换其他方式推进。"
                history.append({
                    "skill": "system",
                    "params": {},
                    "reasoning": warning,
                    "observation": "",
                    "result": warning,
                })
                repeat_count = 0

            prompt_text = self._system_prompt or build_system_prompt(
                instruction=instruction,
                observation=observation,
                skill_schema=schema,
                history=history,
                screen_size=pyautogui.size(),
            )

            logger.info(f"Step {step}: calling LLM")

            decision = None
            for attempt in range(3):
                raw = self._llm.chat(
                    messages=[{"role": "user", "content": prompt_text}],
                    temperature=self._temperature,
                    timeout=self._timeout,
                ) if self._llm else None

                if raw is None:
                    logger.warning(f"Step {step}: LLM returned None (attempt {attempt + 1}/3)")
                    continue

                parsed = parse_ai_json_response(raw)
                if parsed is None:
                    logger.warning(f"Step {step}: LLM returned invalid JSON (attempt {attempt + 1}/3)")
                    continue

                if "skill" not in parsed or "params" not in parsed:
                    logger.warning(
                        f"Step {step}: LLM response missing skill/params keys: {parsed}"
                    )
                    continue

                decision = parsed
                break

            if decision is None:
                return "LLM failed to produce a valid decision after 3 attempts"

            skill_name = decision["skill"]
            params = decision["params"]
            reasoning = decision.get("reasoning", "")

            logger.info(f"Step {step}: skill={skill_name}, reasoning={reasoning}")

            if skill_name == "done":
                result = params.get("result", "")
                logger.info(f"Task completed: {result}")
                return result

            try:
                result = self._registry.execute(skill_name, params, elements)
            except KeyError as e:
                logger.warning(f"Step {step}: {e}")
                result = f"Error: {e}"

            current_hash = f"{skill_name}:{sorted((k, str(v)) for k, v in params.items())}"
            if skill_name == prev_skill and current_hash == prev_params_hash:
                repeat_count += 1
            else:
                repeat_count = 0
            prev_skill = skill_name
            prev_params_hash = current_hash

            history.append({
                "skill": skill_name,
                "params": params,
                "reasoning": reasoning,
                "observation": observation,
                "result": str(result),
            })

        return "已达最大步数限制，任务未完成"
