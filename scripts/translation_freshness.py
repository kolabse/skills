"""Track reviewed source revisions without claiming semantic translation quality."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from validate_localizations import FENCE, HEADING_TEXT, load_manifest, markdown_anchors, project_file

STATE_PATH = "docs/i18n/translation-status.json"
SHA = re.compile(r"^[0-9a-f]{64}$")
MAX_BYTES = 8 * 1024 * 1024


class FreshnessError(ValueError):
    pass


def read_text(path):
    if path.stat().st_size > MAX_BYTES:
        raise FreshnessError("localization input exceeds the size limit")
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sections(text):
    result, lines, counts = [], [], {}
    used = {"@preamble"}
    identifier, heading, fenced = "@preamble", "", False

    def flush():
        if lines:
            result.append({"id": identifier, "heading": heading, "sha256": sha("".join(lines))})

    for line in text.splitlines(keepends=True):
        if FENCE.match(line.rstrip("\n")):
            fenced = not fenced
        match = None if fenced else HEADING_TEXT.match(line.rstrip("\n"))
        if match:
            flush()
            lines = []
            heading = match.group(1)
            base = next(iter(markdown_anchors(line)), "section") or "section"
            occurrence = counts.get(base, 0)
            identifier = base if occurrence == 0 else f"{base}-{occurrence}"
            while identifier in used:
                occurrence += 1
                identifier = f"{base}-{occurrence}"
            counts[base] = occurrence + 1
            used.add(identifier)
        lines.append(line)
    flush()
    return result


def mappings(root):
    manifest = load_manifest(root)
    result, seen = [], set()
    for locale, config in sorted(manifest["locales"].items()):
        if not isinstance(config, dict) or not isinstance(config.get("documents"), list):
            raise FreshnessError("invalid document mappings")
        for item in config["documents"]:
            if not isinstance(item, dict) or set(item) != {"canonical", "translation"}:
                raise FreshnessError("invalid document mapping")
            canonical = project_file(root, item["canonical"], "canonical")
            translation = project_file(root, item["translation"], "translation")
            if item["translation"] in seen:
                raise FreshnessError("duplicate translated document mapping")
            seen.add(item["translation"])
            result.append({"locale": locale, **item,
                           "source_text": read_text(canonical), "translation_text": read_text(translation)})
    return result


def empty_state():
    return {"schema_version": 1, "snapshots": {}, "translations": []}


def validate_state(state, entries):
    if (not isinstance(state, dict) or set(state) != {"schema_version", "snapshots", "translations"}
            or type(state["schema_version"]) is not int or state["schema_version"] != 1
            or not isinstance(state["snapshots"], dict) or not isinstance(state["translations"], list)):
        raise FreshnessError("unsupported translation status contract")
    declared = {item["translation"]: item for item in entries}
    sources = {item["canonical"] for item in entries}
    for canonical, revisions in state["snapshots"].items():
        if canonical not in sources or not isinstance(revisions, dict):
            raise FreshnessError("snapshot is not a declared canonical document")
        for identity, snapshot in revisions.items():
            if (not SHA.fullmatch(identity) or not isinstance(snapshot, dict)
                    or set(snapshot) != {"sections"} or not isinstance(snapshot["sections"], list)):
                raise FreshnessError("invalid source snapshot")
            seen = set()
            for part in snapshot["sections"]:
                if (not isinstance(part, dict) or set(part) != {"id", "heading", "sha256"}
                        or not isinstance(part["id"], str) or not part["id"] or part["id"] in seen
                        or not isinstance(part["heading"], str) or not isinstance(part["sha256"], str)
                        or not SHA.fullmatch(part["sha256"])):
                    raise FreshnessError("invalid or duplicate source section")
                seen.add(part["id"])
    seen = set()
    for row in state["translations"]:
        if not isinstance(row, dict) or set(row) != {"locale", "canonical", "translation", "source_sha256", "translation_sha256", "review"}:
            raise FreshnessError("invalid translation revision record")
        path = row["translation"]
        if not isinstance(path, str) or path not in declared or path in seen:
            raise FreshnessError("duplicate or undeclared translation revision")
        seen.add(path)
        expected = declared[path]
        if row["locale"] != expected["locale"] or row["canonical"] != expected["canonical"]:
            raise FreshnessError("translation revision does not match the manifest")
        if (row["review"] not in ("baseline", "reviewed")
                or any(not isinstance(row[key], str) or not SHA.fullmatch(row[key]) for key in ("source_sha256", "translation_sha256"))):
            raise FreshnessError("invalid translation revision identities")
        snapshots = state["snapshots"].get(row["canonical"], {})
        if row["source_sha256"] not in snapshots:
            raise FreshnessError("translation revision has no source snapshot")
        if row["source_sha256"] == sha(expected["source_text"]):
            if snapshots[row["source_sha256"]]["sections"] != sections(expected["source_text"]):
                raise FreshnessError("source snapshot sections contradict its current identity")
    return state


def load_state(root, entries):
    path = root / STATE_PATH
    if not path.exists():
        return empty_state()
    path = project_file(root, STATE_PATH, "translation status")
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise FreshnessError("duplicate JSON key in translation status")
            result[key] = value
        return result
    return validate_state(json.loads(read_text(path), object_pairs_hook=unique_object), entries)


def snapshot(root):
    """Produce an initial proposal, never silently bless an existing stale record."""
    root = Path(root).resolve()
    if (root / STATE_PATH).exists():
        raise FreshnessError("initial snapshot already exists; review and record individual translations")
    state = empty_state()
    for item in mappings(root):
        add_record(state, item, "baseline")
    return state


def add_record(state, item, review):
    source_digest = sha(item["source_text"])
    state["snapshots"].setdefault(item["canonical"], {})[source_digest] = {"sections": sections(item["source_text"])}
    state["translations"] = [row for row in state["translations"] if row["translation"] != item["translation"]]
    state["translations"].append({key: item[key] for key in ("locale", "canonical", "translation")} | {
        "source_sha256": source_digest, "translation_sha256": sha(item["translation_text"]), "review": review})
    state["translations"].sort(key=lambda row: (row["locale"], row["canonical"]))


def record(root, locale, document, expected_source, expected_translation):
    root = Path(root).resolve()
    entries = mappings(root)
    selected = [item for item in entries if item["locale"] == locale and item["canonical"] == document]
    if len(selected) != 1:
        raise FreshnessError("review must select exactly one declared locale/document")
    item = selected[0]
    if sha(item["source_text"]) != expected_source or sha(item["translation_text"]) != expected_translation:
        raise FreshnessError("reviewed source or translation changed; inspect it again")
    state = load_state(root, entries)
    add_record(state, item, "reviewed")
    return state


def status(root):
    root = Path(root).resolve()
    entries = mappings(root)
    state = load_state(root, entries)
    recorded = {row["translation"]: row for row in state["translations"]}
    documents = []
    for item in entries:
        row = recorded.get(item["translation"])
        source_digest, translation_digest = sha(item["source_text"]), sha(item["translation_text"])
        reasons, changes = [], []
        if row is None:
            reasons.append("untracked")
        else:
            if row["source_sha256"] != source_digest:
                reasons.append("source-changed")
                before = {part["id"]: part for part in state["snapshots"][item["canonical"]][row["source_sha256"]]["sections"]}
                after = {part["id"]: part for part in sections(item["source_text"])}
                for identifier in sorted(before.keys() | after.keys()):
                    old, new = before.get(identifier), after.get(identifier)
                    if old != new:
                        changes.append({"id": identifier, "heading": (new or old)["heading"],
                                        "change": "added" if old is None else "removed" if new is None else "modified"})
            if row["translation_sha256"] != translation_digest:
                reasons.append("translation-changed")
        documents.append({key: item[key] for key in ("locale", "canonical", "translation")} | {
            "status": "needs-review" if reasons else "aligned", "reasons": reasons,
            "source_sha256": source_digest, "translation_sha256": translation_digest,
            "recorded_source_sha256": row["source_sha256"] if row else None,
            "review": row["review"] if row else "unknown", "changed_sections": changes})
    return {"schema_version": 1, "mutates": False, "aligned": all(not row["reasons"] for row in documents),
            "semantic_quality_verified": False, "documents": documents}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "snapshot", "record"))
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Fail status when a document needs review.")
    parser.add_argument("--locale")
    parser.add_argument("--document")
    parser.add_argument("--expected-source-sha256")
    parser.add_argument("--expected-translation-sha256")
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            result = status(args.project_root)
        elif args.command == "snapshot":
            result = snapshot(args.project_root)
        else:
            result = record(args.project_root, args.locale, args.document,
                            args.expected_source_sha256, args.expected_translation_sha256)
        if args.json or args.command != "status":
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        else:
            for row in result["documents"]:
                print(f"{row['locale']} {row['canonical']}: {row['status']} ({', '.join(row['reasons']) or row['review']})")
            print("Revision alignment is not a semantic-quality assessment.")
        return 1 if args.command == "status" and args.strict and not result["aligned"] else 0
    except (ValueError, OSError, RuntimeError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
