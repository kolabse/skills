from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPOSITORY_ROOT / "skills"
NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ALLOWED_PLATFORMS = {"linux", "macos", "windows"}
ALLOWED_STATUSES = {"experimental", "stable", "deprecated"}
ALLOWED_PROVENANCE = {"original", "migrated", "vendored"}
PLUGIN_NAME = "kolabse-skills"
PLUGIN_VERSION_PATTERN = re.compile(
    r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?$"
)


def validate_plugin_manifest(repository_root: Path) -> list[str]:
    manifest_path = repository_root / ".codex-plugin/plugin.json"
    if not manifest_path.is_file():
        return [f"{manifest_path}: required plugin manifest is missing"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        return [f"{manifest_path}: invalid JSON: {error}"]
    if not isinstance(manifest, dict):
        return [f"{manifest_path}: manifest root must be an object"]

    errors: list[str] = []
    if manifest.get("name") != PLUGIN_NAME:
        errors.append(f"{manifest_path}: name must be '{PLUGIN_NAME}'")
    version = manifest.get("version")
    if not isinstance(version, str) or not PLUGIN_VERSION_PATTERN.fullmatch(version):
        errors.append(f"{manifest_path}: version must use semantic versioning")
    if not isinstance(manifest.get("description"), str) or not manifest["description"]:
        errors.append(f"{manifest_path}: description is required")
    if manifest.get("skills") != "./skills/":
        errors.append(f"{manifest_path}: skills must be './skills/'")
    if manifest.get("license") != "Apache-2.0":
        errors.append(f"{manifest_path}: license must be 'Apache-2.0'")
    author = manifest.get("author")
    if not isinstance(author, dict) or not author.get("name"):
        errors.append(f"{manifest_path}: author.name is required")
    interface = manifest.get("interface")
    required_interface = {
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
    }
    if not isinstance(interface, dict):
        errors.append(f"{manifest_path}: interface must be an object")
    else:
        for field in sorted(required_interface):
            if not isinstance(interface.get(field), str) or not interface[field]:
                errors.append(f"{manifest_path}: interface.{field} is required")
    return errors


def validate_trigger_evals(
    repository_root: Path,
    entry: dict[str, object],
    location: str,
) -> list[str]:
    errors: list[str] = []
    name = entry.get("name")
    relative_path = entry.get("trigger_evals")
    if not isinstance(relative_path, str) or not relative_path:
        return [f"{location}.trigger_evals is required"]
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        return [f"{location}.trigger_evals must stay inside the repository"]
    eval_path = repository_root / path
    if not eval_path.is_file():
        return [f"{eval_path}: trigger eval file is missing"]
    try:
        data = json.loads(eval_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        return [f"{eval_path}: invalid JSON: {error}"]
    if not isinstance(data, dict):
        return [f"{eval_path}: eval root must be an object"]
    if data.get("skill") != name:
        errors.append(f"{eval_path}: skill must be '{name}'")

    seen_prompts: set[str] = set()
    for branch in ("positive", "negative"):
        cases = data.get(branch)
        if not isinstance(cases, list) or len(cases) < 3:
            errors.append(f"{eval_path}: {branch} must contain at least 3 cases")
            continue
        for index, case in enumerate(cases):
            case_location = f"{eval_path}: {branch}[{index}]"
            if not isinstance(case, dict):
                errors.append(f"{case_location} must be an object")
                continue
            prompt = case.get("prompt")
            reason = case.get("reason")
            if not isinstance(prompt, str) or not prompt.strip():
                errors.append(f"{case_location}.prompt is required")
            elif prompt in seen_prompts:
                errors.append(f"{case_location}.prompt is duplicated")
            else:
                seen_prompts.add(prompt)
            if not isinstance(reason, str) or not reason.strip():
                errors.append(f"{case_location}.reason is required")
    return errors


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


def validate(repository_root: Path = REPOSITORY_ROOT) -> list[str]:
    errors = validate_plugin_manifest(repository_root)
    names: set[str] = set()
    skills_root = repository_root / "skills"
    readme = repository_root / "README.md"
    readme_text = readme.read_text(encoding="utf-8") if readme.is_file() else ""
    skill_files = sorted(skills_root.glob("*/SKILL.md"))
    if not skill_files:
        return [*errors, "no skills found under skills/"]

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
        if not NAME_PATTERN.fullmatch(name) or len(name) > 63:
            errors.append(
                f"{skill_file}: name must be lowercase hyphen-case "
                "and at most 63 characters"
            )
        if not description:
            errors.append(f"{skill_file}: description is required")
        unexpected_metadata = set(metadata) - {"name", "description"}
        if unexpected_metadata:
            errors.append(
                f"{skill_file}: unsupported frontmatter fields: "
                f"{sorted(unexpected_metadata)}"
            )
        if name in names:
            errors.append(f"{skill_file}: duplicate skill name '{name}'")
        names.add(name)

        line_count = len(skill_file.read_text(encoding="utf-8").splitlines())
        if line_count > 500:
            errors.append(f"{skill_file}: exceeds the 500-line skill limit")
        if f"### `{name}`" not in readme_text:
            errors.append(f"{readme}: missing catalog heading for '{name}'")

        openai_yaml = skill_file.parent / "agents/openai.yaml"
        if openai_yaml.is_file():
            yaml_text = openai_yaml.read_text(encoding="utf-8")
            if f"${name}" not in yaml_text:
                errors.append(f"{openai_yaml}: default prompt must mention ${name}")

        forbidden_config = skill_file.parent / ".agents"
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

    catalog_path = repository_root / "skill-catalog.json"
    if not catalog_path.is_file():
        errors.append(f"{catalog_path}: required catalog is missing")
        return errors
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        errors.append(f"{catalog_path}: invalid JSON: {error}")
        return errors
    if not isinstance(catalog, dict):
        errors.append(f"{catalog_path}: catalog root must be an object")
        return errors
    if catalog.get("schema_version") != 1:
        errors.append(f"{catalog_path}: schema_version must be 1")
    if not isinstance(catalog.get("license"), str) or not catalog["license"]:
        errors.append(f"{catalog_path}: repository license is required")
    if not (repository_root / "LICENSE").is_file():
        errors.append(f"{repository_root / 'LICENSE'}: required license file is missing")
    entries = catalog.get("skills")
    if not isinstance(entries, list):
        errors.append(f"{catalog_path}: skills must be a list")
        return errors

    catalog_names: set[str] = set()
    catalog_paths: set[str] = set()
    for index, entry in enumerate(entries):
        location = f"{catalog_path}: skills[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{location} must be an object")
            continue
        name = entry.get("name")
        path = entry.get("path")
        if not isinstance(name, str) or not name:
            errors.append(f"{location}.name is required")
            continue
        expected_path = f"skills/{name}"
        if path != expected_path:
            errors.append(f"{location}.path must be '{expected_path}'")
        if name in catalog_names:
            errors.append(f"{location}: duplicate catalog name '{name}'")
        catalog_names.add(name)
        if isinstance(path, str):
            if path in catalog_paths:
                errors.append(f"{location}: duplicate catalog path '{path}'")
            catalog_paths.add(path)
        if entry.get("status") not in ALLOWED_STATUSES:
            errors.append(f"{location}.status must be one of {sorted(ALLOWED_STATUSES)}")
        maintainers = entry.get("maintainers")
        if not isinstance(maintainers, list) or not maintainers or not all(
            isinstance(value, str) and value for value in maintainers
        ):
            errors.append(f"{location}.maintainers must be a non-empty string list")
        platforms = entry.get("platforms")
        if not isinstance(platforms, list) or not platforms:
            errors.append(f"{location}.platforms must be a non-empty list")
        elif not all(isinstance(value, str) for value in platforms):
            errors.append(f"{location}.platforms must contain only strings")
        elif set(platforms) - ALLOWED_PLATFORMS:
            errors.append(f"{location}.platforms contains unsupported values")
        if not isinstance(entry.get("license"), str) or not entry["license"]:
            errors.append(f"{location}.license is required")
        errors.extend(validate_trigger_evals(repository_root, entry, location))
        provenance = entry.get("provenance")
        if not isinstance(provenance, dict):
            errors.append(f"{location}.provenance must be an object")
        else:
            kind = provenance.get("kind")
            if kind not in ALLOWED_PROVENANCE:
                errors.append(
                    f"{location}.provenance.kind must be one of "
                    f"{sorted(ALLOWED_PROVENANCE)}"
                )
            if not provenance.get("source"):
                errors.append(f"{location}.provenance.source is required")
            if not provenance.get("canonical_repository"):
                errors.append(f"{location}.provenance.canonical_repository is required")
            if kind == "vendored" and not provenance.get("source_revision"):
                errors.append(
                    f"{location}.provenance.source_revision is required "
                    "for vendored skills"
                )

    for missing in sorted(names - catalog_names):
        errors.append(f"{catalog_path}: skill '{missing}' is missing from the catalog")
    for unknown in sorted(catalog_names - names):
        errors.append(f"{catalog_path}: catalog references unknown skill '{unknown}'")
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
