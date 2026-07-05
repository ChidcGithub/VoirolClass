import copy
import json
from dataclasses import dataclass, field
from typing import Any, Callable

from voirol.utils.logger import get_logger

logger = get_logger("agent.skill_registry")


@dataclass
class Skill:
    name: str
    description: str
    parameters: dict
    handler: Callable
    resolve_element: bool = False


@dataclass
class SkillRegistry:
    _skills: dict[str, Skill] = field(default_factory=dict)

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill
        logger.info(f"Registered skill: {skill.name}")

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def get_all(self) -> list[Skill]:
        return list(self._skills.values())

    def get_schema_text(self) -> str:
        lines = []
        for skill in self._skills.values():
            lines.append(f"### {skill.name}")
            lines.append(skill.description)
            lines.append("Parameters:")
            lines.append(json.dumps(skill.parameters, indent=2, ensure_ascii=False))
            lines.append("")
        return "\n".join(lines).strip()

    def execute(self, name: str, params: dict, elements: list | None = None) -> Any:
        skill = self.get(name)
        if skill is None:
            logger.error(f"Skill not found: {name}")
            raise KeyError(f"Skill not found: {name}")

        resolved = copy.deepcopy(params)

        if skill.resolve_element and elements is not None and "element_id" in resolved:
            element_id = resolved.pop("element_id")
            for el in elements:
                if el.element_id == element_id:
                    resolved["x"] = el.cx
                    resolved["y"] = el.cy
                    break
            else:
                logger.warning(f"Element not found for id: {element_id}, providing fallback values")
                resolved.setdefault("x", 0)
                resolved.setdefault("y", 0)

        logger.debug(f"Executing skill: {name} with params: {resolved}")
        return skill.handler(resolved)
