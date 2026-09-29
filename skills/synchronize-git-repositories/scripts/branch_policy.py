#!/usr/bin/env python3
"""Private, confirmed naming preferences for callers using this skill.

This is a decision aid, not an authority or proof that all instructions were read.
All documents use schema_version: 1; unknown fields and duplicate keys fail closed.

Choice: {schema_version, honor_project_policy: bool, fallback: application |
collection | external-skill | user-global}. External/global choices additionally
require provider: {identity, template_source: absolute JSON file path}. A provider
file contains {schema_version, identity, revision, templates}. Templates contain
feature, bugfix, release, hotfix strings with exactly one {slug} substitution.

Context: {schema_version, agent: codex | claude-code, task_kind, slug,
application_rule, binding_rule?, project_rule?, explicit_user_rule?,
urgent_production_fix?: bool, collection_metadata?: {version, source}}.
Each rule is {source, priority: nonnegative integer (smaller means higher),
evidence, templates, allows_user_choice?: bool}; application_rule requires the
boolean. binding_rule represents the highest mandatory instruction, including
mandatory project constraints even when project preferences are disabled. A
stronger application default may delegate to that constraint through explicit
allows_user_choice. Other stronger non-delegating instructions make that context
inconsistent. Optional project_rule defaults apply where permitted unless a
confirmed preference disables them. A mandatory rule is never overridden by
preferences. Explicit choices obey priority and any higher rule's delegation.
Set application_rule explicitly to null when no application naming rule exists;
never fabricate an application template or priority. Other declared rules and
confirmed preferences can then resolve the name. Without them, resolution blocks.
A fallback selected without an application rule has priority: null because it
does not derive a ranking from an external application instruction.

configure without --confirm returns a plan and digest without writing. Review
the concrete plan; only --confirm --expected-digest DIGEST adopts it. --yes is
not a naming-consent option. resolve --output saves a decision at a caller-chosen
private path. check recomputes it immediately before first publication; it never
creates, publishes, renames or deletes branches. status is always read-only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

AGENTS = ("codex", "claude-code")
KINDS = ("feature", "bugfix", "release", "hotfix")
FALLBACKS = ("application", "collection", "external-skill", "user-global")
LIMIT = 128 * 1024
COLLECTION = {"schema_version": 1, "identity": "kolabse/skills", "revision": "1",
              "templates": {kind: kind + "/{slug}" for kind in KINDS}}


class PolicyError(ValueError):
    """Policy is unresolved, unsupported, malformed or stale."""


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def _safe_path(path):
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise PolicyError(f"Symbolic links/junctions are unsupported: {part}")
    return path


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PolicyError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _read(path):
    path = _safe_path(path)
    try:
        with path.open("rb") as stream:
            raw = stream.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise PolicyError(f"JSON exceeds {LIMIT} bytes: {path}")
        return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_pairs,
                          parse_constant=lambda value: _fail(f"Invalid JSON constant: {value}"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PolicyError(f"Cannot read JSON {path}: {error}") from error


def _fail(message):
    raise PolicyError(message)


def _object(value, required, optional=()):
    if not isinstance(value, dict):
        raise PolicyError("Expected a JSON object")
    missing, extra = set(required) - value.keys(), value.keys() - set(required) - set(optional)
    if missing or extra:
        raise PolicyError(f"Invalid fields; missing={sorted(missing)}, unknown={sorted(extra)}")
    if "schema_version" in value and (type(value["schema_version"]) is not int or value["schema_version"] != 1):
        raise PolicyError("Unsupported schema_version")


def _text(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > 2048:
        raise PolicyError(f"{field} must be a nonempty string of at most 2048 characters")
    return value


def _boolean(value, field):
    if type(value) is not bool:
        raise PolicyError(f"{field} must be boolean")


def _branch(name):
    if (not isinstance(name, str) or not name or len(name.encode("utf-8")) > 1024
            or name in ("@", "HEAD") or name.startswith("-") or name.endswith(".")
            or ".." in name or "@{" in name or re.search(r"[\x00-\x20\x7f~^:?*\[\\]", name)
            or any(not part or part.startswith(".") or part.endswith(".lock") for part in name.split("/"))):
        raise PolicyError(f"Invalid Git branch name: {name!r}")
    return name


def _templates(value):
    _object(value, KINDS)
    for template in value.values():
        _text(template, "template")
        if template.count("{slug}") != 1 or "{" in template.replace("{slug}", "") or "}" in template.replace("{slug}", ""):
            raise PolicyError("Each template requires exactly one {slug} placeholder")
        _branch(template.replace("{slug}", "example"))


def _snapshot(value):
    _object(value, ("schema_version", "identity", "revision", "templates"))
    _text(value["identity"], "identity")
    _text(value["revision"], "revision")
    _templates(value["templates"])


def _choice(value):
    _object(value, ("schema_version", "honor_project_policy", "fallback"), ("provider",))
    _boolean(value["honor_project_policy"], "honor_project_policy")
    if value["fallback"] not in FALLBACKS:
        raise PolicyError("Unsupported fallback source")
    external = value["fallback"] in ("external-skill", "user-global")
    if external != ("provider" in value):
        raise PolicyError("Only external-skill/user-global require provider identity and template_source")
    if external:
        _object(value["provider"], ("identity", "template_source"))
        _text(value["provider"]["identity"], "provider.identity")
        source = _text(value["provider"]["template_source"], "provider.template_source")
        if not Path(source).is_absolute():
            raise PolicyError("Provider template_source must be an absolute path")


def _provider(choice):
    if choice["fallback"] == "application":
        return None
    if choice["fallback"] == "collection":
        return json.loads(json.dumps(COLLECTION))
    provider = choice["provider"]
    snapshot = _read(provider["template_source"])
    _snapshot(snapshot)
    if snapshot["identity"] != provider["identity"]:
        raise PolicyError("Provider identity does not match the explicit selection")
    return snapshot


def _config_path(agent, config_root=None):
    if agent not in AGENTS:
        raise PolicyError(f"Unsupported agent: {agent}")
    if config_root is None:
        if os.name == "nt":
            base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData/Roaming")))
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
        config_root = base / "kolabse/branch-policy"
    return _safe_path(Path(config_root) / (agent + ".json"))


def _load(agent, config_root):
    path = _config_path(agent, config_root)
    if not path.exists():
        return None
    value = _read(path)
    _object(value, ("schema_version", "agent", "scope", "choice", "accepted_snapshot"))
    if value["agent"] != agent or value["scope"] != "skill-workflows":
        raise PolicyError("Configuration agent/scope mismatch")
    _choice(value["choice"])
    snapshot = value["accepted_snapshot"]
    if value["choice"]["fallback"] == "application":
        if snapshot is not None:
            raise PolicyError("Application defaults must be supplied by current context")
    else:
        _snapshot(snapshot)
        identity = "kolabse/skills" if value["choice"]["fallback"] == "collection" else value["choice"]["provider"]["identity"]
        if snapshot["identity"] != identity:
            raise PolicyError("Accepted snapshot identity mismatch")
    return value


def status(agent, config_root=None):
    """Read private preference and current provider without creating any files."""
    preference = _load(agent, config_root)
    result = {"schema_version": 1, "agent": agent, "scope": "skill-workflows",
              "state": "configured" if preference else "unconfigured",
              "config_path": str(_config_path(agent, config_root)),
              "config_digest": digest(preference), "preference": preference,
              "recommended": {"honor_project_policy": True, "fallback": "application"},
              "choices": [
                  {"fallback": "application", "description": "Preserve the actual application default from context", "example": "Requires detected application rule"},
                  {"fallback": "collection", "description": "kolabse/skills revision " + COLLECTION["revision"], "example": "bugfix/{slug}", "templates": COLLECTION["templates"]},
                  {"fallback": "external-skill", "description": "Explicit identified collection or standalone skill JSON templates", "example": "Requires readable template source"},
                  {"fallback": "user-global", "description": "Explicit user policy JSON for this application", "example": "Requires readable template source"}],
              "project_policy": "Independent honor_project_policy boolean; mandatory instructions always apply"}
    if preference:
        result["provider_snapshot"] = preference["accepted_snapshot"]
        try:
            result["current_provider"] = _provider(preference["choice"])
            if result["current_provider"] != preference["accepted_snapshot"]:
                result.update(state="confirmation-pending", warning="Provider changed; accepted snapshot remains effective until explicit confirmation")
        except PolicyError as error:
            result.update(state="provider-unavailable", warning=str(error), current_provider=None)
    return result


def _write(path, value):
    path = _safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _safe_path(path)
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=str(path.parent))
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        _safe_path(path)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def configure(agent, choice_file, config_root=None, expected_digest=None, confirm=False):
    """Plan, or explicitly confirm precisely the displayed choice/provider state."""
    choice = _read(choice_file)
    _choice(choice)
    previous = _load(agent, config_root)
    snapshot = _provider(choice)
    proposed = {"schema_version": 1, "agent": agent, "scope": "skill-workflows",
                "choice": choice, "accepted_snapshot": snapshot}
    plan = {"schema_version": 1, "state": "confirmation-required", "scope": "skill-workflows",
            "config_path": str(_config_path(agent, config_root)), "previous": previous,
            "proposed": proposed}
    plan["plan_digest"] = digest(plan)
    if not confirm:
        return plan
    if not expected_digest or expected_digest != plan["plan_digest"]:
        raise PolicyError("Confirmation requires the exact current plan_digest; review the new plan")
    _write(_config_path(agent, config_root), proposed)
    return status(agent, config_root)


def _rule(rule, application=False):
    _object(rule, ("source", "priority", "evidence", "templates"), ("allows_user_choice",))
    _text(rule["source"], "rule.source")
    _text(rule["evidence"], "rule.evidence")
    if type(rule["priority"]) is not int or rule["priority"] < 0:
        raise PolicyError("Rule priority must be a nonnegative integer; smaller means higher")
    _templates(rule["templates"])
    if application or "allows_user_choice" in rule:
        _boolean(rule.get("allows_user_choice"), "allows_user_choice")


def _context(value):
    _object(value, ("schema_version", "agent", "task_kind", "slug", "application_rule"),
            ("binding_rule", "project_rule", "explicit_user_rule", "urgent_production_fix", "collection_metadata"))
    if value["agent"] not in AGENTS or value["task_kind"] not in KINDS:
        raise PolicyError("Unknown agent or task_kind")
    _text(value["slug"], "slug")
    _branch(value["slug"])
    if "urgent_production_fix" in value:
        _boolean(value["urgent_production_fix"], "urgent_production_fix")
    if value["task_kind"] == "hotfix" and value.get("urgent_production_fix") is not True:
        raise PolicyError("hotfix requires an explicit urgent production fix request")
    for key in ("application_rule", "binding_rule", "project_rule", "explicit_user_rule"):
        if key in value:
            if key == "application_rule" and value[key] is None:
                continue
            _rule(value[key], application=key == "application_rule")
    if "collection_metadata" in value:
        _object(value["collection_metadata"], ("version", "source"))
        for key, item in value["collection_metadata"].items():
            _text(item, "collection_metadata." + key)
    binding = value.get("binding_rule")
    if binding:
        for key in ("application_rule", "project_rule", "explicit_user_rule"):
            other = value.get(key)
            if other and other["priority"] <= binding["priority"]:
                if other["priority"] == binding["priority"] or not other.get("allows_user_choice", False):
                    raise PolicyError("binding_rule conflicts with a stronger non-delegating or equal-priority instruction")


def _provenance():
    helper = Path(__file__).resolve()
    skill = helper.parents[1] / "SKILL.md"
    try:
        return {"helper_path": str(helper), "helper_sha256": hashlib.sha256(helper.read_bytes()).hexdigest(),
                "skill_path": str(skill), "skill_sha256": hashlib.sha256(skill.read_bytes()).hexdigest()}
    except OSError as error:
        raise PolicyError(f"Skill artifact is unavailable: {error}") from error


def resolve(context_file, config_root=None):
    """Resolve declared context; it is caller testimony, not independently verified authority."""
    context = _read(context_file)
    _context(context)
    current = status(context["agent"], config_root)
    if current["state"] == "provider-unavailable":
        raise PolicyError("Selected provider unavailable; cannot silently choose another policy: " + current["warning"])
    preference = current["preference"]
    app = context["application_rule"]
    binding, project, explicit = (context.get(key) for key in ("binding_rule", "project_rule", "explicit_user_rule"))
    render = lambda rule: _branch(rule["templates"][context["task_kind"]].replace("{slug}", context["slug"]))
    selected = binding or app
    explanation = ["Evaluated caller-supplied declared context; this does not prove instruction completeness."]
    if app is None:
        explanation.append("No application naming rule was declared; no application template or priority is inferred.")
    if binding:
        explanation.append("Highest mandatory binding rule takes precedence over preferences.")
        if explicit and render(explicit) != render(binding):
            raise PolicyError("Explicit user choice conflicts with the binding instruction")
    else:
        if project and app and project["priority"] == app["priority"] and render(project) != render(app):
            raise PolicyError("Ambiguous equal-priority application and project rules")
        # Existing project instructions use the application's express delegation;
        # no persistent preference is inferred from an unattended installation.
        honor_project = preference is None or preference["choice"]["honor_project_policy"]
        if project and ((app is None and honor_project) or
                        (app is not None and (project["priority"] < app["priority"] or
                         (app["allows_user_choice"] and honor_project)))):
            selected = project
        permitted = selected is None or selected.get("allows_user_choice", False)
        if explicit:
            if selected is not None and render(explicit) != render(selected):
                if explicit["priority"] == selected["priority"]:
                    raise PolicyError("Ambiguous equal-priority explicit user and applicable rules")
                if explicit["priority"] > selected["priority"] and not permitted:
                    raise PolicyError("Higher-priority rule does not permit this explicit user choice")
            selected = explicit
            explanation.append("Explicit user choice applies by priority or express permission from the applicable instruction.")
        elif permitted and preference:
            choice = preference["choice"]
            if project and choice["honor_project_policy"]:
                selected = project
                explanation.append("Confirmed preference honors the applicable repository policy.")
            elif selected is app and choice["fallback"] != "application":
                snapshot = preference["accepted_snapshot"]
                selected = {"source": snapshot["identity"] + " (confirmed " + choice["fallback"] + ")",
                            "priority": app["priority"] + 1 if app else None, "templates": snapshot["templates"],
                            "evidence": "Explicit confirmed private preference, revision " + snapshot["revision"]}
                explanation.append("Application permits the confirmed fallback preference." if app else
                                   "Confirmed fallback applies without an application naming constraint; its priority is not inferred.")
        elif preference and not permitted:
            explanation.append("Saved preference cannot override the applicable instruction's restriction on user choice.")
    if selected is None:
        raise PolicyError("No applicable naming rule: application default is absent; supply an actual project/user rule or explicitly confirm a concrete fallback")
    branch = render(selected)
    candidates = [("kolabse/skills collection default", render(COLLECTION))]
    if app:
        candidates.append((app["source"], render(app)))
    if project:
        candidates.append((project["source"], render(project)))
    for source, alternative in candidates:
        if alternative != branch:
            explanation.append(f"Selected {branch} from {selected['source']}; unused default {source} proposes {alternative}.")
    if current.get("warning"):
        explanation.append(current["warning"])
    return {"schema_version": 1, "scope": "skill-workflows", "agent": context["agent"],
            "task_kind": context["task_kind"], "slug": context["slug"],
            "branch": branch, "source": selected["source"], "priority": selected["priority"],
            "evidence": selected["evidence"], "explanation": explanation,
            "context_digest": digest(context), "config_digest": current["config_digest"],
            "provider_digest": digest(current.get("current_provider")),
            "provenance": _provenance(), "collection_metadata": context.get("collection_metadata")}


def check(context_file, decision_file, branch, config_root=None):
    """Require exact current name, context, preference, provider and actual artifacts."""
    saved = _read(decision_file)
    current = resolve(context_file, config_root)
    if saved != current:
        raise PolicyError("Stale or mismatched decision: context, policy, provider or skill artifact changed; resolve again")
    if _branch(branch) != current["branch"]:
        raise PolicyError("Final branch name does not match the effective policy decision")
    return {"schema_version": 1, "state": "verified", "branch": branch,
            "decision_digest": digest(current), "scope": "skill-workflows"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "configure", "resolve", "check"):
        command = commands.add_parser(name)
        command.add_argument("--config-root", type=Path)
        if name in ("status", "configure"):
            command.add_argument("--agent", choices=AGENTS, required=True)
        if name == "configure":
            command.add_argument("--choice-file", type=Path, required=True)
            command.add_argument("--expected-digest")
            command.add_argument("--confirm", action="store_true")
        if name in ("resolve", "check"):
            command.add_argument("--context", type=Path, required=True)
        if name == "resolve":
            command.add_argument("--output", type=Path)
        if name == "check":
            command.add_argument("--decision", type=Path, required=True)
            command.add_argument("--branch", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            result = status(args.agent, args.config_root)
        elif args.command == "configure":
            result = configure(args.agent, args.choice_file, args.config_root, args.expected_digest, args.confirm)
        elif args.command == "resolve":
            result = resolve(args.context, args.config_root)
            if args.output:
                protected = [args.context, _config_path(result["agent"], args.config_root)]
                preference = _load(result["agent"], args.config_root)
                if preference and "provider" in preference["choice"]:
                    protected.append(preference["choice"]["provider"]["template_source"])
                output_key = os.path.normcase(str(_safe_path(args.output)))
                if output_key in {os.path.normcase(str(_safe_path(path))) for path in protected}:
                    raise PolicyError("Decision output must not overwrite context, preference or selected provider")
                _write(args.output, result)
        else:
            result = check(args.context, args.decision, args.branch, args.config_root)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except (PolicyError, OSError) as error:
        print(json.dumps({"state": "blocked", "error": str(error)}, ensure_ascii=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
