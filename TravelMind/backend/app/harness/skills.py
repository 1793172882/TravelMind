"""Discover and load local SKILL.md files only when requested."""

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field


@dataclass(frozen=True, slots=True)
class SkillMetadata:
    """Small startup-time index entry for a skill."""

    name: str
    description: str
    path: Path


class SkillLoader:
    """Index skill metadata and defer full file reads."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def discover(self) -> list[SkillMetadata]:
        """Return metadata from immediate child SKILL.md files."""
        found: list[SkillMetadata] = []
        for path in sorted(self.root.glob("*/SKILL.md")):
            text = path.read_text(encoding="utf-8")
            found.append(
                SkillMetadata(
                    name=self._frontmatter(text, "name") or path.parent.name,
                    description=self._frontmatter(text, "description") or "",
                    path=path,
                )
            )
        return found

    def load(self, metadata: SkillMetadata) -> str:
        """Load full instructions only after a skill is selected."""
        return metadata.path.read_text(encoding="utf-8")

    def load_by_name(self, name: str) -> str:
        """Load one indexed skill by its exact name."""
        for metadata in self.discover():
            if metadata.name == name:
                return self.load(metadata)
        raise KeyError(f"未知 Skill：{name}")

    def catalog(self) -> str:
        """Return only names and descriptions for the dynamic prompt."""
        return "\n".join(
            f"- {skill.name}: {skill.description}" for skill in self.discover()
        ) or "- 暂无可用 Skill"

    @staticmethod
    def _frontmatter(text: str, key: str) -> str | None:
        for line in text.splitlines():
            prefix = f"{key}:"
            if line.startswith(prefix):
                return line.removeprefix(prefix).strip().strip('"')
        return None


class LoadSkillArgs(BaseModel):
    name: str = Field(min_length=1, max_length=100)
