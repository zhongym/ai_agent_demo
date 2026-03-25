from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.runtime.skill_models import SkillSpec

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


class SkillRegistryError(RuntimeError):
    pass


class SkillRegistry:
    """负责加载、校验并索引 Markdown Skills。"""

    def __init__(self, skills: dict[str, SkillSpec]) -> None:
        self.skills = skills

    @classmethod
    def from_directory(cls, skills_dir: str | Path) -> "SkillRegistry":
        resolved_dir = Path(skills_dir).resolve()
        if not resolved_dir.exists():
            raise SkillRegistryError(f"Skill 目录不存在: {resolved_dir}")
        return cls(cls._load_skills(resolved_dir))

    def list(self) -> list[SkillSpec]:
        return [self.skills[name] for name in sorted(self.skills)]

    def get(self, name: str) -> SkillSpec:
        try:
            return self.skills[name]
        except KeyError as exc:
            raise SkillRegistryError(f"找不到 Skill: {name}") from exc

    @staticmethod
    def _split_frontmatter(text: str) -> tuple[dict[str, object], str]:
        match = FRONTMATTER_RE.match(text.strip())
        if not match:
            raise SkillRegistryError("Skill 文件缺少 YAML front matter")

        frontmatter_text, body = match.groups()
        data = yaml.safe_load(frontmatter_text) or {}
        return data, body.strip()

    @classmethod
    def _load_skills(cls, skills_dir: Path) -> dict[str, SkillSpec]:
        skills: dict[str, SkillSpec] = {}
        for path in sorted(skills_dir.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            frontmatter, body = cls._split_frontmatter(text)
            extra_keys = sorted(set(frontmatter) - {"name", "description"})
            if extra_keys:
                joined = ", ".join(extra_keys)
                raise SkillRegistryError(f"Skill {path.name} 只允许 name 和 description，检测到多余字段: {joined}")

            if not body:
                raise SkillRegistryError(f"Skill {path.name} 正文不能为空")

            try:
                skill = SkillSpec.model_validate(
                    {
                        "name": frontmatter.get("name"),
                        "description": frontmatter.get("description"),
                        "body": body,
                        "source_path": path,
                    }
                )
            except ValidationError as exc:
                raise SkillRegistryError(f"Skill {path.name} 格式不合法: {exc}") from exc

            if skill.name in skills:
                raise SkillRegistryError(f"检测到重复的 Skill 名称: {skill.name}")
            skills[skill.name] = skill
        return skills
