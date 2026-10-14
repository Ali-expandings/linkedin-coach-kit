#!/usr/bin/env python3
"""Live check of tools/unipile-mcp.mjs against the real Unipile API with a real key.

Read-only by default. Prints summaries, not personal details.
    UNIPILE_API_KEY=... python tests/unipile_live_check.py
    UNIPILE_API_KEY=... python tests/unipile_live_check.py --noop-write
--noop-write re-saves the profile's CURRENT headline unchanged: it proves the write path
without changing anything visible on LinkedIn.
"""
import json
import os
import shutil
import subprocess
import sys

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(KIT, "tools", "unipile-mcp.mjs")
NODE = os.environ.get("KIT_NODE") or shutil.which("node") or os.path.join(KIT, "tools", "node", "node.exe")


def run(calls):
    p = subprocess.Popen([NODE, SERVER], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                         encoding="utf-8", bufsize=1)
    msgs = [{"jsonrpc": "2.0", "id": 0, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "live", "version": "1"}}}]
    for i, (name, args) in enumerate(calls, start=1):
        msgs.append({"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": name, "arguments": args}})
    out, _ = p.communicate("\n".join(json.dumps(m) for m in msgs) + "\n", timeout=600)
    res = {}
    for line in out.splitlines():
        m = json.loads(line)
        if m.get("id"):
            r = m["result"]
            text = r["content"][0]["text"]
            try:
                res[m["id"]] = (r.get("isError", False), json.loads(text))
            except json.JSONDecodeError:
                res[m["id"]] = (r.get("isError", False), text)
    return res


def main():
    if not (os.environ.get("UNIPILE_API_KEY") or os.path.exists(os.path.join(KIT, "tools", "unipile.json"))):
        sys.exit("Set UNIPILE_API_KEY (or run setup with a key) first.")
    noop_write = "--noop-write" in sys.argv

    r = run([("status", {})])
    err, st = r[1]
    print("status:", "ERROR " + str(st)[:300] if err else json.dumps(st, indent=1))
    if err or not st.get("linkedin_accounts"):
        sys.exit(1 if err else 0)

    r = run([("read_my_profile", {}),
             ("lookup_ids", {"type": "LOCATION", "keywords": "Cairo", "limit": 3}),
             ("search_jobs", {"keywords": "intern", "limit": 3})])
    err, prof = r[1]
    if err:
        sys.exit("read_my_profile ERROR " + str(prof)[:500])
    print("read_my_profile: headline %d chars, about %d chars, %d experience, %d education, %d skills, "
          "%d certifications, %d projects; first experience id present: %s" % (
              len(prof.get("headline") or ""), len(prof.get("about") or ""), len(prof.get("experience") or []),
              len(prof.get("education") or []), len(prof.get("skills") or []), len(prof.get("certifications") or []),
              len(prof.get("projects") or []), bool((prof.get("experience") or [{}])[0].get("id"))))
    err, ids = r[2]
    print("lookup_ids LOCATION Cairo:", "ERROR " + str(ids)[:300] if err else json.dumps(ids)[:300])
    err, jobs = r[3]
    print("search_jobs intern:", "ERROR " + str(jobs)[:300] if err else
          f"{len(jobs.get('data') or jobs.get('items') or [])} results, keys {list(jobs)[:5]}")

    headline = prof.get("headline") or ""
    calls = [("update_profile", {"changes": {"specifics": {"linkedin": {"headline": headline}}}})]
    if noop_write:
        calls.append(("update_profile", {"changes": {"specifics": {"linkedin": {"headline": headline}}}, "apply": True}))
        calls.append(("read_my_profile", {}))
    r = run(calls)
    err, dry = r[1]
    print("dry run:", "ERROR " + str(dry)[:300] if err else f"ok={dry.get('ok')} applied={dry.get('applied')}")
    if noop_write:
        err, w = r[2]
        print("no-op write (same headline):", "ERROR " + str(w)[:500] if err else f"applied={w.get('applied')} response={json.dumps(w.get('response'))[:200]}")
        err, after = r[3]
        print("headline unchanged after write:", (not err) and after.get("headline") == headline)


if __name__ == "__main__":
    main()
