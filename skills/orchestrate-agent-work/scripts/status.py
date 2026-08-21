#!/usr/bin/env python3
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
required = [root / "SKILL.md", root / "agents" / "openai.yaml", root / "collection-metadata.json"]
missing = [str(path.relative_to(root)) for path in required if not path.is_file()]
print(json.dumps({"skill": "orchestrate-agent-work", "configured": not missing, "missing": missing}, sort_keys=True))
raise SystemExit(1 if missing else 0)
