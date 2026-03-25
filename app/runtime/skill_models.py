from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class SkillSpec(BaseModel):
    """Markdown Skill 的运行时描述。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    body: str
    source_path: Path
