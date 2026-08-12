from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPOSITORY_ROOT / "skills"


def frontmatter(skill_file: Path) -> dict[str, str]:
    text = skill_file.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if not match:
        raise ValueError("missing YAML frontmatter")
    values: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            raise ValueError(f"invalid frontmatter line: {line}")
        values[key.strip()] = value.strip().strip('"')
    return values


def validate() -> list[str]:
    errors: list[str] = []
    names: set[str] = set()
    skill_files = sorted(SKILLS_ROOT.glob("*/SKILL.md"))
    if not skill_files:
        return ["no skills found under skills/"]

    for skill_file in skill_files:
        folder_name = skill_file.parent.name
        try:
            metadata = frontmatter(skill_file)
        except ValueError as error:
            errors.append(f"{skill_file}: {error}")
            continue
        name = metadata.get("name", "")
        description = metadata.get("description", "")
        if name != folder_name:
            errors.append(f"{skill_file}: name '{name}' does not match folder '{folder_name}'")
        if not description:
            errors.append(f"{skill_file}: description is required")
        if name in names:
            errors.append(f"{skill_file}: duplicate skill name '{name}'")
        names.add(name)

        openai_yaml = skill_file.parent / "agents/openai.yaml"
        if openai_yaml.is_file():
            yaml_text = openai_yaml.read_text(encoding="utf-8")
            if f"${name}" not in yaml_text:
                errors.append(f"{openai_yaml}: default prompt must mention ${name}")

        forbidden_config = skill_file.parent / ".agents/operate-yandex-cloud/project.yaml"
        if forbidden_config.exists():
            errors.append(f"{forbidden_config}: project configuration is bundled in the skill")

        for python_file in skill_file.parent.glob("scripts/*.py"):
            try:
                ast.parse(
                    python_file.read_text(encoding="utf-8"),
                    filename=str(python_file),
                )
            except SyntaxError as error:
                errors.append(f"{python_file}: {error}")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    count = len(list(SKILLS_ROOT.glob("*/SKILL.md")))
    print(f"Validated {count} skill(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
