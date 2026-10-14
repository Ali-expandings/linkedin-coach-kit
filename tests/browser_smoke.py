#!/usr/bin/env python3
"""Start the kit's browser MCP server exactly as opencode.json defines it, open a real page
through it, and check the page loaded. Proves the browser tool can drive Chrome/Edge here.

Usage (from the kit root):  python tests/browser_smoke.py
"""
import json
import subprocess
import sys
import time


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


def main():
    cfg = json.load(open("opencode.json", encoding="utf-8"))["mcp"]["chrome"]
    # Headless for CI only; the real coach runs headed so the user can watch.
    cmd = cfg["command"] + ["--headless"]
    proc = subprocess.Popen(cmd, cwd=cfg.get("cwd", "."), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1)
    deadline = time.time() + 180
    rpc(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
               "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                          "clientInfo": {"name": "smoke", "version": "1"}}})
    if not read_until(proc, 1, deadline):
        proc.kill(); sys.exit("FAIL no initialize response")
    rpc(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    rpc(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
               "params": {"name": "browser_navigate", "arguments": {"url": "https://example.com"}}})
    resp = read_until(proc, 2, deadline)
    rpc(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
               "params": {"name": "browser_close", "arguments": {}}})
    read_until(proc, 3, time.time() + 30)
    proc.kill()
    text = json.dumps(resp or {})
    if resp and "Example Domain" in text and not resp.get("result", {}).get("isError"):
        print("OK  browser tool opened https://example.com (page title: Example Domain)")
        sys.exit(0)
    print("FAIL browser tool did not load the page:", text[:800])
    sys.exit(1)


if __name__ == "__main__":
    main()
