#!/usr/bin/env python3
"""Validate the request bodies tools/unipile-mcp.mjs builds against Unipile's own published
OpenAPI schema for "Update a User Profile" (downloaded at test time).

Two checks per body:
  1. jsonschema validation against the official request schema;
  2. a strict walk that every key we send exists in that schema (API schemas often allow unknown
     keys, so a misspelt field would otherwise pass validation and be silently ignored live).

Needs: pip install jsonschema    Run from the kit root: python tests/unipile_schema_test.py
"""
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

import jsonschema

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(KIT, "tools", "unipile-mcp.mjs")
NODE = os.environ.get("KIT_NODE") or shutil.which("node") or os.path.join(KIT, "tools", "node", "node.exe")
SPEC_URL = "https://developer.unipile.com/v2.0/reference/updateuserprofile.md"
OP_PATH = "/v2/{account_id}/users/{user_id}"


def load_spec():
    req = urllib.request.Request(SPEC_URL, headers={"User-Agent": "linkedin-coach-kit-tests"})
    text = urllib.request.urlopen(req, timeout=60).read().decode("utf-8")
    return json.loads(re.search(r"```json\s*(\{.*\})\s*```", text, re.S).group(1))


def resolver(spec):
    def r(node):
        while isinstance(node, dict) and "$ref" in node:
            cur = spec
            for part in node["$ref"].lstrip("#/").split("/"):
                cur = cur[part.replace("~1", "/").replace("~0", "~")]
            node = cur
        return node
    return r


def known_keys_problems(value, schema, r, where="body"):
    """Every object key in value must be declared somewhere in schema (any branch)."""
    schema = r(schema)
    problems = []
    if isinstance(value, dict):
        branches = [schema]
        for comb in ("allOf", "anyOf", "oneOf"):
            branches += [r(s) for s in schema.get(comb, [])]
        # flatten nested combinators once more
        flat = []
        for b in branches:
            flat.append(b)
            for comb in ("allOf", "anyOf", "oneOf"):
                flat += [r(s) for s in b.get(comb, [])]
        props = {}
        for b in flat:
            props.update(b.get("properties", {}))
        for k, v in value.items():
            if k not in props:
                problems.append(f"{where}.{k} is not a field in Unipile's schema")
            else:
                problems += known_keys_problems(v, props[k], r, f"{where}.{k}")
    elif isinstance(value, list):
        items = schema.get("items")
        if items is None:
            for comb in ("allOf", "anyOf", "oneOf"):
                for s in schema.get(comb, []):
                    items = items or r(s).get("items")
        for i, v in enumerate(value):
            if items is not None:
                problems += known_keys_problems(v, items, r, f"{where}[{i}]")
    return problems


def dry_run_bodies(cases, picture):
    env = {k: v for k, v in os.environ.items() if not k.startswith("UNIPILE_")}
    p = subprocess.Popen([NODE, SERVER], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                         encoding="utf-8", env=env, bufsize=1)
    msgs = [{"jsonrpc": "2.0", "id": 0, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "s", "version": "1"}}}]
    for i, (_, args) in enumerate(cases, start=1):
        a = dict(args)
        if a.pop("_with_picture", False):
            a["picture_path"] = picture
        msgs.append({"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": "update_profile", "arguments": a}})
    out, _ = p.communicate("\n".join(json.dumps(m) for m in msgs) + "\n", timeout=60)
    results = {}
    for line in out.splitlines():
        m = json.loads(line)
        if m.get("id"):
            results[m["id"]] = json.loads(m["result"]["content"][0]["text"])
    return results


CASES = [
    ("About + headline", {"changes": {"bio": "First paragraph.\n\nSecond paragraph.",
                                      "specifics": {"linkedin": {"headline": "Marketing student | Social media"}}}}),
    ("add skills", {"changes": {"specifics": {"linkedin": {"skills": [{"name": "Microsoft Excel"}, {"name": "Canva"}]}}}}),
    ("location", {"changes": {"location": "106155005"}}),
    ("create experience with a link", {"changes": {"specifics": {"linkedin": {"experience": {
        "operation": "create", "job_title": {"name": "Social Media Volunteer"}, "company": {"name": "Student Union"},
        "start_date": {"month": 10, "year": 2024}, "end_date": {"month": 6, "year": 2025},
        "description": "Ran the Instagram account.\nGrew followers from 300 to 1,200.", "workplace_type": "HYBRID",
        "location": {"name": "Cairo, Egypt"},
        "media": {"type": "link", "url": "https://example.com/portfolio", "title": "Campaign samples"}}}}}}),
    ("edit experience", {"changes": {"specifics": {"linkedin": {"experience": {
        "operation": "edit", "id": "2549284031", "description": "Updated description."}}}}}),
    ("delete experience", {"changes": {"specifics": {"linkedin": {"experience": {"operation": "delete", "id": "2549284031"}}}}}),
    ("create education", {"changes": {"specifics": {"linkedin": {"education": {
        "operation": "create", "school": {"name": "Cairo University"}, "degree": {"name": "Bachelor's degree"},
        "field_of_study": {"name": "Political Science"}, "start_date": {"month": 9, "year": 2023},
        "end_date": {"month": 6, "year": 2027}, "activities": "Model UN, debate club"}}}}}),
    ("edit education", {"changes": {"specifics": {"linkedin": {"education": {
        "operation": "edit", "id": "123", "grade": "Very good"}}}}}),
    ("open to work", {"changes": {"specifics": {"linkedin": {"open_to_work": {
        "job_title": [{"title": "Marketing Intern", "id": "2410"}],
        "workplace": [{"type": "HYBRID", "location": ["106155005"]}],
        "employment_type": ["INTERNSHIP"], "start_date": "IMMEDIATELY", "visibility": "RECRUITERS_ONLY"}}}}}),
    ("custom link", {"changes": {"specifics": {"linkedin": {"custom_link": {
        "type": "PORTFOLIO", "url": "https://example.com", "display_on": "PROFILE_ONLY"}}}}}),
    ("profile photo", {"changes": {}, "_with_picture": True}),
]


def main():
    spec = load_spec()
    r = resolver(spec)
    body_schema = r(spec["paths"][OP_PATH]["patch"]["requestBody"]["content"]["application/json"]["schema"])
    root = dict(spec)
    root["$ref"] = "#/paths/" + OP_PATH.replace("~", "~0").replace("/", "~1") + \
                   "/patch/requestBody/content/application~1json/schema"
    validator = jsonschema.Draft202012Validator(root)

    # The strict key walk must catch a misspelling, or it proves nothing.
    assert known_keys_problems({"specifics": {"linkedin": {"headlin": "x"}}}, body_schema, r), \
        "key walk failed to flag a misspelt field"

    tmp = tempfile.mkdtemp()
    pic = os.path.join(tmp, "photo.png")
    with open(pic, "wb") as f:
        f.write(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="))

    results = dry_run_bodies(CASES, pic)
    failed = 0
    for i, (name, _) in enumerate(CASES, start=1):
        res = results[i]
        if not res.get("ok"):
            print(f"FAIL {name}: server rejected it: {res.get('problems')}")
            failed += 1
            continue
        body = res["request"]["body"]
        errors = sorted(validator.iter_errors(body), key=lambda e: e.path)
        unknown = known_keys_problems(body, body_schema, r)
        if errors or unknown:
            failed += 1
            print(f"FAIL {name}")
            for e in errors[:5]:
                print(f"     schema: {list(e.path)}: {e.message[:200]}")
            for u in unknown:
                print(f"     key: {u}")
        else:
            print(f"OK   {name}")
    if failed:
        sys.exit(1)
    print(f"\nALL {len(CASES)} BODIES MATCH UNIPILE'S PUBLISHED SCHEMA")


if __name__ == "__main__":
    main()
