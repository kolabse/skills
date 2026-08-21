#!/usr/bin/env python3
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]; required=[root/"SKILL.md",root/"agents"/"openai.yaml",root/"collection-metadata.json"]; missing=[str(p.relative_to(root)) for p in required if not p.is_file()]
print(json.dumps({"skill":"diagnose-software-defects","configured":not missing,"missing":missing},sort_keys=True)); raise SystemExit(1 if missing else 0)
