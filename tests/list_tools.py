#!/usr/bin/env python3
"""Start the kit's MCP servers exactly as opencode.json defines them, list their tools,
and exit non-zero if a server fails to start or an expected tool is missing.

Usage:  python tests/list_tools.py [--schema TOOL ...]
Reads ./opencode.json from the kit folder (run from the kit root).
"""
import json
import os
import subprocess
import sys
import threading
import time

EXPECTED = {
    "linkedin": {"get_my_profile", "get_person_profile", "search_jobs", "get_job_details", "close_session"},
    "chrome": {"browser_navigate", "browser_snapshot", "browser_click", "browser_type",
               "browser_press_key", "browser_select_option", "browser_file_upload"},
}


def rpc(proc, msg):
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()


def read_until(proc, want_id, deadline):
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            return None
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("id") == want_id:
            return msg
    return None


def list_server(name, cfg, show_schema):
    cmd = cfg["command"]
    env = dict(os.environ, **cfg.get("environment", {}))
    cwd = cfg.get("cwd") or "."
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1)
    deadline = time.time() + 600  # first start may download Python packages and a browser
    rpc(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
               "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                          "clientInfo": {"name": "kit-test", "version": "1"}}})
    if read_until(proc, 1, deadline) is None:
        proc.kill()
        return None, f"{name}: no initialize response"
    rpc(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    rpc(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    resp = read_until(proc, 2, deadline)
    proc.kill()
    if resp is None:
        return None, f"{name}: no tools/list response"
    tools = resp.get("result", {}).get("tools", [])
    for t in tools:
        if t["name"] in show_schema:
            print(f"--- schema {name}.{t['name']}:\n{json.dumps(t.get('inputSchema'), indent=1)[:1500]}")
    return {t["name"] for t in tools}, None


def main():
    show_schema = set(sys.argv[sys.argv.index("--schema") + 1:]) if "--schema" in sys.argv else set()
    cfg = json.load(open("opencode.json", encoding="utf-8"))
    failed = False
    for name, server in cfg["mcp"].items():
        names, err = list_server(name, server, show_schema)
        if err:
            print(f"FAIL {err}")
            failed = True
            continue
        missing = EXPECTED.get(name, set()) - names
        print(f"{'OK  ' if not missing else 'FAIL'} {name}: {len(names)} tools" + (f", missing {sorted(missing)}" if missing else ""))
        print("     " + ", ".join(sorted(names)))
        failed |= bool(missing)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
