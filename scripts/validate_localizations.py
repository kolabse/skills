from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote


FENCE = re.compile(r"^```([^`]*)\s*$")
HEADING = re.compile(r"^(#{1,6})\s+\S")
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
HEADING_TEXT = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$")


class LocalizationError(RuntimeError):
    pass


def load_manifest(root: Path) -> dict[str, Any]:
    path = root / "docs" / "i18n" / "locales.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LocalizationError(f"invalid localization manifest: {error}") from error
    if not isinstance(value, dict):
        raise LocalizationError("localization manifest must be an object")
    if set(value) != {"schema_version", "canonical_locale", "locales"}:
        raise LocalizationError("localization manifest has an unsupported contract")
    if value["schema_version"] != 1 or value["canonical_locale"] != "en":
        raise LocalizationError("localization manifest version or canonical locale is invalid")
    if not isinstance(value["locales"], dict) or not value["locales"]:
        raise LocalizationError("localization manifest must declare at least one locale")
    return value


def project_file(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise LocalizationError(f"{label} must be a repository-relative POSIX path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise LocalizationError(f"{label} escapes the repository")
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise LocalizationError(f"{label} escapes the repository") from error
    if not path.is_file():
        raise LocalizationError(f"{label} is missing: {value}")
    return path


def markdown_structure(text: str) -> tuple[list[int], list[str]]:
    headings: list[int] = []
    shell_blocks: list[str] = []
    fence_language: str | None = None
    fence_lines: list[str] = []
    for line in text.splitlines():
        fence = FENCE.match(line)
        if fence:
            if fence_language is None:
                fence_language = fence.group(1).strip().lower()
                fence_lines = []
            else:
                if fence_language in {"shell", "bash", "powershell"}:
                    shell_blocks.append("\n".join(fence_lines))
                fence_language = None
                fence_lines = []
            continue
        if fence_language is not None:
            fence_lines.append(line)
            continue
        heading = HEADING.match(line)
        if heading:
            headings.append(len(heading.group(1)))
    if fence_language is not None:
        raise LocalizationError("unclosed Markdown code fence")
    return headings, shell_blocks


def markdown_anchors(text: str) -> set[str]:
    anchors: set[str] = set()
    occurrences: dict[str, int] = {}
    in_fence = False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        heading = HEADING_TEXT.match(line)
        if not heading:
            continue
        label = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", heading.group(1))
        label = re.sub(r"<[^>]+>", "", label)
        label = label.replace("`", "").replace("*", "").replace("_", "")
        slug = "".join(
            character
            for character in label.lower()
            if character.isalnum() or character in {" ", "-"}
        ).replace(" ", "-")
        suffix = occurrences.get(slug, 0)
        occurrences[slug] = suffix + 1
        anchors.add(slug if suffix == 0 else f"{slug}-{suffix}")
    return anchors


def validate_relative_links(root: Path, path: Path, text: str) -> None:
    local_anchors = markdown_anchors(text)
    for raw_target in LINK.findall(text):
        target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        if target.startswith("#"):
            anchor = unquote(target[1:])
            if anchor not in local_anchors:
                raise LocalizationError(f"broken Markdown anchor in {path}: {target}")
            continue
        path_part, separator, fragment = target.partition("#")
        relative_target = path_part.split("?", 1)[0]
        if not relative_target:
            continue
        resolved = (path.parent / relative_target).resolve()
        try:
            resolved.relative_to(root)
        except ValueError as error:
            raise LocalizationError(f"link escapes repository in {path}: {target}") from error
        if not resolved.exists():
            raise LocalizationError(f"broken relative link in {path}: {target}")
        if separator and resolved.is_file() and resolved.suffix.lower() == ".md":
            target_anchors = markdown_anchors(resolved.read_text(encoding="utf-8"))
            if unquote(fragment) not in target_anchors:
                raise LocalizationError(f"broken Markdown anchor in {path}: {target}")


def validate(root: Path) -> int:
    root = root.resolve()
    manifest = load_manifest(root)
    total = 0
    locale_names: list[str] = []
    for locale, config in sorted(manifest["locales"].items()):
        if not isinstance(locale, str) or not re.fullmatch(r"[a-z]{2}(?:-[A-Z]{2})?", locale):
            raise LocalizationError(f"invalid locale identifier: {locale}")
        if not isinstance(config, dict) or set(config) != {"name", "documents"}:
            raise LocalizationError(f"invalid locale configuration: {locale}")
        name = config["name"]
        documents = config["documents"]
        if not isinstance(name, str) or not name or not isinstance(documents, list):
            raise LocalizationError(f"invalid locale configuration: {locale}")
        locale_names.append(name)

    navigation_names = ["English", *locale_names]
    for locale, config in sorted(manifest["locales"].items()):
        documents = config["documents"]
        for index, entry in enumerate(documents):
            if not isinstance(entry, dict) or set(entry) != {"canonical", "translation"}:
                raise LocalizationError(f"invalid document mapping: {locale}[{index}]")
            canonical = project_file(root, entry["canonical"], "canonical document")
            translation = project_file(root, entry["translation"], "translated document")
            canonical_text = canonical.read_text(encoding="utf-8")
            translation_text = translation.read_text(encoding="utf-8")
            canonical_headings, canonical_shell = markdown_structure(canonical_text)
            translation_headings, translation_shell = markdown_structure(translation_text)
            if canonical_shell != translation_shell:
                raise LocalizationError(
                    f"shell code blocks differ: {canonical.relative_to(root)} and "
                    f"{translation.relative_to(root)}"
                )
            if canonical_headings != translation_headings:
                raise LocalizationError(
                    f"heading structure differs: {canonical.relative_to(root)} and "
                    f"{translation.relative_to(root)}"
                )
            canonical_navigation = "\n".join(canonical_text.splitlines()[:12])
            translation_navigation = "\n".join(translation_text.splitlines()[:12])
            for navigation_name in navigation_names:
                if navigation_name not in canonical_navigation:
                    raise LocalizationError(
                        f"canonical language navigation is missing {navigation_name}: {canonical}"
                    )
                if navigation_name not in translation_navigation:
                    raise LocalizationError(
                        f"translated language navigation is missing {navigation_name}: {translation}"
                    )
            validate_relative_links(root, canonical, canonical_text)
            validate_relative_links(root, translation, translation_text)
            total += 1
    if (root / "docs/i18n/translation-status.json").exists():
        from translation_freshness import status
        try:
            freshness = status(root)
        except (ValueError, OSError, RuntimeError) as error:
            raise LocalizationError(f"invalid translation freshness metadata: {error}") from error
        if not freshness["aligned"]:
            affected = sorted({row["locale"] for row in freshness["documents"] if row["status"] != "aligned"})
            raise LocalizationError(f"translation freshness needs review: {', '.join(affected)}")
    locale_ids = ", ".join(sorted(manifest["locales"]))
    print(
        f"Validated {total} translation(s) across "
        f"{len(locale_names)} locale(s): {locale_ids}."
    )
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate localized public documentation.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        validate(args.project_root.resolve())
    except LocalizationError as error:
        print(f"Localization validation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
