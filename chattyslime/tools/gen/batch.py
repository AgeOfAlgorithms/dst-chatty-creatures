"""Many images from tools/gen/qwen.py: a JSON list of jobs {out, prompt, refs: [...], size: [w, h] | null, seed}, run
one after another; a job whose out exists is skipped (so a list can grow and be run again).

    python tools/gen/batch.py jobs.json
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qwen  # noqa: E402

jobs = json.load(open(sys.argv[1], encoding="utf-8"))
for j in jobs:
    if os.path.exists(j["out"]):
        continue
    try:
        out, seed, dt = qwen.generate(j["prompt"], j.get("refs", []), j["out"],
                                      tuple(j["size"]) if j.get("size") else None, j.get("seed"))
        print("ok", os.path.basename(out), f"{dt:.0f}s", flush=True)
    except Exception as e:  # noqa: BLE001
        print("FAIL", j["out"], str(e)[:300], flush=True)
print("done", flush=True)
