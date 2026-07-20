"""Discover and load local SKILL.md files only when requested."""

from dataclasses import dataclass
from pathlib import Path


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

    @staticmethod
    def _frontmatter(text: str, key: str) -> str | None:
        for line in text.splitlines():
            prefix = f"{key}:"
            if line.startswith(prefix):
                return line.removeprefix(prefix).strip().strip('"')
        return None
