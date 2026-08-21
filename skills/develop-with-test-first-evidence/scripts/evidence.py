#!/usr/bin/env python3
"""Validate or digest test-first evidence without writing files."""
import argparse, hashlib, json, re
from pathlib import Path

TOP={"schema_version","behavior","subject","red","green","evidence_digest"}; RUN={"command","exit_code","summary"}
RED=RUN|{"failure_class","intended_behavior_failure_reason"}; SHA=re.compile(r"^sha256:[0-9a-f]{64}$"); COMMIT=re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")

def digest(data):
    payload={k:v for k,v in data.items() if k!="evidence_digest"}
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    return "sha256:"+hashlib.sha256(raw).hexdigest()

def fields(value, expected, path, errors):
    if not isinstance(value,dict): errors.append(f"{path} must be an object"); return False
    for key in sorted(expected-set(value)): errors.append(f"missing {path}.{key}")
    for key in sorted(set(value)-expected): errors.append(f"unexpected {path}.{key}")
    return set(value)==expected

def run(value,path,expected,allowed,errors):
    if not fields(value,allowed,path,errors): return
    argv=value["command"]
    if not isinstance(argv,list) or not argv or any(not isinstance(x,str) or not x for x in argv): errors.append(f"{path}.command must be a non-empty argv string array")
    code=value["exit_code"]
    if type(code) is not int: errors.append(f"{path}.exit_code must be an integer")
    elif expected==0 and code!=0: errors.append(f"{path}.exit_code must be zero")
    elif expected!=0 and code==0: errors.append(f"{path}.exit_code must be nonzero")
    if not isinstance(value["summary"],str) or not value["summary"].strip(): errors.append(f"{path}.summary must be non-empty")

def validate(data):
    errors=[]
    if not fields(data,TOP,"evidence",errors): return errors
    if type(data["schema_version"]) is not int or data["schema_version"]!=1: errors.append("schema_version must be exactly 1")
    if not isinstance(data["behavior"],str) or not data["behavior"].strip(): errors.append("behavior must be non-empty")
    subject=data["subject"]
    if fields(subject,{"kind","identity"},"subject",errors):
        kind,identity=subject["kind"],subject["identity"]
        if kind not in {"commit","worktree"}: errors.append("subject.kind must be commit or worktree")
        elif not isinstance(identity,str): errors.append("subject.identity must be a string")
        elif kind=="commit" and not COMMIT.fullmatch(identity): errors.append("commit identity must be a lowercase 40- or 64-character object id")
        elif kind=="worktree" and not SHA.fullmatch(identity): errors.append("worktree identity must be sha256:<64 lowercase hex characters>")
    red=data["red"]; run(red,"red",1,RED,errors)
    if isinstance(red,dict):
        if red.get("failure_class")!="intended_behavior": errors.append("red.failure_class must be intended_behavior; environment, setup, syntax, and unrelated failures are invalid")
        if not isinstance(red.get("intended_behavior_failure_reason"),str) or not red.get("intended_behavior_failure_reason","").strip(): errors.append("red.intended_behavior_failure_reason must explicitly connect the failure to the intended behavior")
    green=data["green"]
    if fields(green,{"focused","broader"},"green",errors):
        run(green["focused"],"green.focused",0,RUN,errors); run(green["broader"],"green.broader",0,RUN,errors)
    bound=data["evidence_digest"]
    if not isinstance(bound,str) or not SHA.fullmatch(bound): errors.append("evidence_digest must be sha256:<64 lowercase hex characters>")
    elif bound!=digest(data): errors.append("evidence_digest does not match the canonical evidence payload")
    return errors

def main():
    parser=argparse.ArgumentParser(description=__doc__); subs=parser.add_subparsers(dest="command",required=True)
    for name in ("validate","digest"): subs.add_parser(name).add_argument("--input",required=True)
    args=parser.parse_args(); data=json.loads(Path(args.input).read_text(encoding="utf-8"))
    if args.command=="digest": print(digest(data)); return
    errors=validate(data); print(json.dumps({"valid":not errors,"errors":errors},sort_keys=True)); raise SystemExit(1 if errors else 0)
if __name__=="__main__": main()
