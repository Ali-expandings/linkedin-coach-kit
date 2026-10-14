#!/usr/bin/env python3
"""Mac/Linux test helper: write opencode.json from the template exactly as setup.ps1 step 7
does on Windows, using this machine's uvx, node and the kit's absolute path."""
import json, os, shutil, sys

kit = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
uvx = shutil.which("uvx")
node = shutil.which("node")
if not uvx or not node:
    sys.exit("uvx and node must be on PATH")
cfg = open(os.path.join(kit, "opencode.template.json"), encoding="utf-8").read()
for k, v in {"__UVX__": uvx, "__NODE__": node, "__KIT__": kit,
             "__BROWSER__": "chrome", "__PYTHON__": "3.13"}.items():
    cfg = cfg.replace(k, v)
json.loads(cfg)  # must be valid JSON
open(os.path.join(kit, "opencode.json"), "w", encoding="utf-8").write(cfg)
print("wrote opencode.json with", uvx, node)
