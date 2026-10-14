#!/usr/bin/env python3
"""Test tools/unipile-mcp.mjs against a local mock of the Unipile API (stdlib only).

Checks the exact HTTP requests each tool sends, that dry runs send nothing, the safety
checks, picture encoding and error reporting. Run from the kit root:
    python tests/unipile_test.py
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(KIT, "tools", "unipile-mcp.mjs")
NODE = os.environ.get("KIT_NODE") or shutil.which("node") or os.path.join(KIT, "tools", "node", "node.exe")

RECORDED = []          # requests the mock received
FAIL_NEXT = {}         # path -> (status, body) to return once

PROFILE = {
    "object": "UserProfile", "id": "u1", "provider": "linkedin", "is_blocked": False, "type": "individual",
    "display_name": "Test User", "public_identifier": "test-user", "profile_url": "https://www.linkedin.com/in/test-user/",
    "description": "Student at Test University", "bio": "Old about text.", "location": "Cairo, Egypt",
    "specifics": {
        "is_open_to_work": False, "industry": "Education",
        "experience": [{"id": "exp-1", "job_title": "Intern", "company": "ACME", "started_on": {"month": 7, "year": 2025},
                        "description": "Did things.", "tracking_noise": "x"}],
        "education": [{"id": "edu-1", "school": "Test University", "degree": "BSc", "started_on": {"year": 2023}}],
        "skills": [{"name": "Excel", "endorsement_count": 2, "insights": ["noise"]}],
        "certifications": [], "projects": [], "languages": [], "volunteer_experience": [],
    },
}


class Mock(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _reply(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle(self, method):
        u = urlparse(self.path)
        length = int(self.headers.get("content-length") or 0)
        raw = self.rfile.read(length) if length else b""
        RECORDED.append({
            "method": method, "path": u.path, "query": {k: v[0] for k, v in parse_qs(u.query).items()},
            "api_key": self.headers.get("X-API-KEY"), "content_type": self.headers.get("content-type"),
            "body": json.loads(raw) if raw else None,
        })
        if u.path in FAIL_NEXT:
            status, body = FAIL_NEXT.pop(u.path)
            return self._reply(status, body)
        if method == "GET" and u.path == "/v2/accounts/":
            return self._reply(200, {"object": "AccountList", "has_more": False, "data": [
                {"id": "acc_li", "provider": "LINKEDIN", "name": "Test User", "status": "OK"},
                {"id": "acc_wa", "provider": "WHATSAPP", "name": "phone", "status": "OK"}]})
        if method == "GET" and u.path == "/v2/acc_li/users/me":
            return self._reply(200, PROFILE)
        if method == "GET" and u.path == "/v2/acc_li/linkedin/search/parameters":
            return self._reply(200, {"object": "ParameterList", "items": [{"id": "106155005", "title": "Egypt"}]})
        if method == "POST" and u.path == "/v2/acc_li/linkedin/search/jobs":
            return self._reply(200, {"data": [{"id": "job1", "title": "Intern"}], "total_count": 1})
        if method == "POST" and u.path == "/v2/auth/link":
            return self._reply(201, {"object": "HostedAuthLink", "link": "https://account.unipile.com/abc"})
        if method == "PATCH" and u.path == "/v2/acc_li/users/me":
            return self._reply(200, {"object": "UserProfileUpdated"})
        return self._reply(404, {"type": "errors/not_found", "detail": f"no mock for {method} {u.path}"})

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_PATCH(self):
        self._handle("PATCH")


class Client:
    def __init__(self, env):
        self.p = subprocess.Popen([NODE, SERVER], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, encoding="utf-8", env=env, bufsize=1)
        self.n = 0
        r = self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                    "clientInfo": {"name": "t", "version": "1"}})
        assert r["result"]["serverInfo"]["name"] == "unipile-linkedin", r
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        self.p.stdin.flush()

    def rpc(self, method, params):
        self.n += 1
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params}) + "\n")
        self.p.stdin.flush()
        deadline = time.time() + 30
        while time.time() < deadline:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError("server exited: " + self.p.stderr.read())
            msg = json.loads(line)
            if msg.get("id") == self.n:
                return msg
        raise TimeoutError(method)

    def call(self, name, args=None):
        r = self.rpc("tools/call", {"name": name, "arguments": args or {}})["result"]
        text = r["content"][0]["text"]
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = text
        return r.get("isError", False), data

    def close(self):
        self.p.stdin.close()
        self.p.wait(timeout=5)


PASSED = []


def check(name, cond, detail=""):
    if not cond:
        print(f"FAIL {name}  {detail}")
        sys.exit(1)
    PASSED.append(name)
    print(f"OK   {name}")


def main():
    httpd = HTTPServer(("127.0.0.1", 0), Mock)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}/v2"
    tmp = tempfile.mkdtemp()

    # --- not configured: clear message, no crash
    env = {k: v for k, v in os.environ.items() if not k.startswith("UNIPILE_")}
    env["UNIPILE_BASE_URL"] = base
    cfg_file = os.path.join(KIT, "tools", "unipile.json")
    had_cfg = os.path.exists(cfg_file)
    if had_cfg:
        os.rename(cfg_file, cfg_file + ".bak")
    try:
        c = Client(env)
        tools = c.rpc("tools/list", {})["result"]["tools"]
        names = sorted(t["name"] for t in tools)
        check("tools/list has exactly the 6 tools",
              names == ["connect_linkedin", "lookup_ids", "read_my_profile", "search_jobs", "status", "update_profile"], names)
        check("no messaging/invitation/post tools exist",
              not any(w in " ".join(names) for w in ("message", "invit", "connect_with", "post", "react")))
        err, out = c.call("status")
        check("unconfigured status returns a readable error", err and "not set up" in out, out)
        check("unconfigured status sent no request", RECORDED == [], RECORDED)
        c.close()
    finally:
        if had_cfg:
            os.rename(cfg_file + ".bak", cfg_file)

    # --- configured
    env["UNIPILE_API_KEY"] = "test-key-123"
    c = Client(env)

    err, out = c.call("status")
    check("status lists only LinkedIn accounts", not err and out["linkedin_accounts"] == [
        {"id": "acc_li", "name": "Test User", "status": "OK"}], out)
    check("status picks the single LinkedIn account as default", out["default_account_id"] == "acc_li", out)
    check("requests carry X-API-KEY", RECORDED[-1]["api_key"] == "test-key-123", RECORDED[-1])

    RECORDED.clear()
    err, out = c.call("read_my_profile")
    r = RECORDED[-1]
    check("read_my_profile: GET /v2/acc_li/users/me", r["method"] == "GET" and r["path"] == "/v2/acc_li/users/me", r)
    check("read_my_profile asks for all LinkedIn sections",
          r["query"] == {"with_sections": "linkedin_*", "variant": "linkedin_classic"}, r["query"])
    check("read_my_profile maps headline/about/experience ids",
          out["headline"] == "Student at Test University" and out["about"] == "Old about text."
          and out["experience"][0]["id"] == "exp-1" and "tracking_noise" not in out["experience"][0], out)

    RECORDED.clear()
    err, out = c.call("lookup_ids", {"type": "LOCATION", "keywords": "Egypt"})
    r = RECORDED[-1]
    check("lookup_ids: GET search/parameters with type, keywords, limit",
          r["path"] == "/v2/acc_li/linkedin/search/parameters"
          and r["query"] == {"type": "LOCATION", "keywords": "Egypt", "limit": "10"}, r)

    RECORDED.clear()
    err, out = c.call("search_jobs", {"keywords": "marketing intern", "location": ["106155005"], "date_posted": "PAST_WEEK",
                                      "filters": {"easy_apply": True}})
    r = RECORDED[-1]
    check("search_jobs: POST search/jobs with body", r["method"] == "POST" and r["path"] == "/v2/acc_li/linkedin/search/jobs"
          and r["body"] == {"keywords": "marketing intern", "easy_apply": True, "location": ["106155005"],
                            "date_posted": "PAST_WEEK"} and r["query"] == {"limit": "10"}, r)

    RECORDED.clear()
    err, out = c.call("connect_linkedin")
    r = RECORDED[-1]
    check("connect_linkedin: POST /v2/auth/link for linkedin", r["path"] == "/v2/auth/link"
          and r["body"]["providers"] == ["linkedin"] and r["body"]["redirect_uri"].startswith("https://")
          and r["body"]["expires_on"].endswith("Z") and out["link"] == "https://account.unipile.com/abc", (r, out))

    # --- update_profile: dry run sends nothing
    RECORDED.clear()
    changes = {"bio": "New about.", "specifics": {"linkedin": {
        "headline": "Marketing student | Content & social media",
        "experience": {"operation": "edit", "id": "exp-1", "description": "Ran the club's social media.\nGrew it."}}}}
    err, out = c.call("update_profile", {"changes": changes})
    check("dry run sends no request", RECORDED == [], RECORDED)
    check("dry run returns the exact PATCH", not err and out["dry_run"] and out["request"]["method"] == "PATCH"
          and out["request"]["body"]["bio"] == "New about.", out)
    check("notify_network defaults to false",
          out["request"]["body"]["specifics"]["linkedin"]["experience"]["notify_network"] is False, out)

    # --- safety checks
    bad = [
        ({"specifics": {"linkedin": {"headline": "x" * 221}}}, "221 characters"),
        ({"bio": "x" * 2601}, "2601 characters"),
        ({"first_name": "New"}, "cannot be changed"),
        ({"specifics": {"linkedin": {"experience": [{"operation": "create"}]}}}, "ONE object"),
        ({"specifics": {"linkedin": {"experience": {"operation": "edit", "description": "x"}}}}, "needs the entry's id"),
        ({"specifics": {"linkedin": {"experience": {"operation": "create", "job_title": {"name": "Intern"}}}}}, "needs company"),
        ({"specifics": {"linkedin": {"education": {"operation": "create", "school": "Cairo University",
                                                   "start_date": {"month": 9, "year": 2023}}}}}, '{"name": "..."}'),
        ({"specifics": {"linkedin": {"experience": {"operation": "create", "job_title": {"name": "I"},
                                                    "company": {"name": "C"}, "start_date": {"month": 13, "year": 2025}}}}},
         "month"),
        ({"specifics": {"linkedin": {"skills": ["Excel"]}}}, "skills must be a list"),
        ({"specifics": {"linkedin": {"open_to_work": {"job_title": []}}}}, "visibility is required"),
        ({"headline": "wrong place"}, "Unknown field"),
    ]
    for changes_bad, needle in bad:
        RECORDED.clear()
        err, out = c.call("update_profile", {"changes": changes_bad, "apply": True})
        check(f"rejects: {needle}", out.get("ok") is False and any(needle in p for p in out["problems"])
              and RECORDED == [], (out, RECORDED))

    # --- picture encoding + apply
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
    pic = os.path.join(tmp, "me.png")
    with open(pic, "wb") as f:
        f.write(png)
    RECORDED.clear()
    err, out = c.call("update_profile", {"changes": {"specifics": {"linkedin": {"headline": "Same headline"}}},
                                         "picture_path": pic, "apply": True})
    r = RECORDED[-1]
    check("apply sends PATCH /v2/acc_li/users/me as JSON", r["method"] == "PATCH" and r["path"] == "/v2/acc_li/users/me"
          and r["content_type"] == "application/json", r)
    check("picture is base64 with content type and filename",
          r["body"]["picture"] == {"content": base64.b64encode(png).decode(), "content_type": "image/png", "filename": "me.png"},
          r["body"].get("picture"))
    check("apply response is reported", not err and out["applied"] is True, out)
    err, out = c.call("update_profile", {"changes": {}, "picture_path": os.path.join(tmp, "me.gif")})
    check("rejects non-jpg/png pictures", out["ok"] is False and ".jpg or .png" in out["problems"][0], out)

    # --- API errors are readable
    FAIL_NEXT["/v2/acc_li/users/me"] = (422, {"type": "errors/invalid_parameters", "detail": "headline is invalid"})
    err, out = c.call("update_profile", {"changes": {"specifics": {"linkedin": {"headline": "Hi"}}}, "apply": True})
    check("API errors come back with status and detail", err and "HTTP 422" in out and "headline is invalid" in out, out)

    c.close()
    httpd.shutdown()
    print(f"\nALL {len(PASSED)} CHECKS PASSED")


if __name__ == "__main__":
    main()
