#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path

plan = json.loads(Path(__file__).with_name("plan.json").read_text())
for step in plan:
    subprocess.run(["tool", "call", step["tool"], json.dumps(step["arguments"])], check=True)
