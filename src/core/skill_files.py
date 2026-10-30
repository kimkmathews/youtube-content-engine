"""Reads skills/<name>/SKILL.md files: one folder = one output format.

Frontmatter carries everything the pipeline needs (output file, strategy, rubric);
the body is the writing instructions. Adding a format never needs a Python change.
"""

import os
import re
from dataclasses import dataclass, field

import yaml

from config.settings import Config

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
STRATEGIES = ("reduce", "per_chunk")


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    output_file: str
    # reduce: one call over every chunk's digest (coherent single pieces).
    # per_chunk: one call per transcript chunk, stitched in order (depth-first formats).
    strategy: str
    body: str
    rubric: list[str] = field(default_factory=list)


def read_skill_frontmatter(skill_dir: str) -> dict | None:
    """Parse the YAML frontmatter (name, description, ...) of a skill directory."""
    skill_md = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(skill_md):
        return None
    with open(skill_md, "r", encoding="utf-8") as f:
        content = f.read()
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return None
    return yaml.safe_load(match.group(1))


def read_skill_body(skill_dir: str) -> str:
    """Full SKILL.md content with the YAML frontmatter block stripped."""
    skill_md = os.path.join(skill_dir, "SKILL.md")
    with open(skill_md, "r", encoding="utf-8") as f:
        content = f.read()
    return _FRONTMATTER_RE.sub("", content, count=1).strip()


def load_skills(skills_dir: str = Config.SKILLS_DIR) -> dict[str, Skill]:
    skills = {}
    for entry in sorted(os.listdir(skills_dir)):
        skill_dir = os.path.join(skills_dir, entry)
        meta = read_skill_frontmatter(skill_dir) if os.path.isdir(skill_dir) else None
        if not meta:
            continue
        strategy = meta.get("strategy", "reduce")
        if strategy not in STRATEGIES:
            raise ValueError(f"{entry}: strategy must be one of {STRATEGIES}, got {strategy!r}")
        skills[meta["name"]] = Skill(
            name=meta["name"],
            description=meta["description"],
            output_file=meta.get("output_file", f"{meta['name']}.md"),
            strategy=strategy,
            body=read_skill_body(skill_dir),
            rubric=list(meta.get("rubric") or []),
        )
    return skills
