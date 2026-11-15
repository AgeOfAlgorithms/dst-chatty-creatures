"""Stages a chatty creature mod for the Steam Workshop: only what the game loads, in <mod>/dist/<mod>, with the
mod.manifest DST's own Mod Uploader would add (without it DST loads none of a Workshop mod's scripts - see
proxcomms/tools/publish.py). Checks that the core is in sync and that the modinfo is not a local dev copy's.

    python chattycore/stage.py chattyslime        (from dst-mods/)

Then publish the folder with the steam-workshop-publish skill's workshop.py (the item ids: <mod>/tools/workshop/README.md).
"""
import os
import re
import shutil
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["modinfo.lua", "modmain.lua", "modicon.tex", "modicon.xml"]
DIRS = ["scripts", "anim", "sound"]


def sdbm(s):
    h = 0
    for c in s:
        h = (ord(c) + (h << 6) + (h << 16) - h) & 0xFFFFFFFF
    return h


def manifest(folder):
    """DST's mod.manifest: "MNFS", version 1, the file count, each file's sdbm hash (lower-case path with "/")"""
    paths = sorted(os.path.relpath(os.path.join(r, f), folder).replace("\\", "/").lower()
                   for r, _, fs in os.walk(folder) for f in fs if f.lower() != "mod.manifest")
    return b"MNFS" + struct.pack("<II", 1, len(paths)) + b"".join(struct.pack("<I", sdbm(p)) for p in paths)


def stage(mod):
    src = os.path.join(ROOT, mod)
    out = os.path.join(src, "dist", mod)
    if subprocess.run([sys.executable, os.path.join(ROOT, "chattycore", "sync.py"), "--check"]).returncode != 0:
        raise SystemExit("the core's copies differ from chattycore/core.lua: run python chattycore/sync.py")
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    for f in FILES:
        shutil.copy2(os.path.join(src, f), os.path.join(out, f))
    for d in DIRS:
        shutil.copytree(os.path.join(src, d), os.path.join(out, d),
                        ignore=shutil.ignore_patterns("*.fsbcache", "__pycache__"))
    info = open(os.path.join(out, "modinfo.lua"), encoding="utf-8").read()
    if "(local dev)" in info:
        raise SystemExit("the staged modinfo.lua is a local dev copy's")
    version = re.search(r'^version = "([^"]+)"', info, re.M).group(1)
    open(os.path.join(out, "mod.manifest"), "wb").write(manifest(out))
    n = sum(len(fs) for _, _, fs in os.walk(out))
    size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(out) for f in fs)
    print(f"staged {n} files, {size // 1024} KB, in {out} (version {version})")
    return out, version


if __name__ == "__main__":
    for m in sys.argv[1:] or ["chattyslime", "chattysalamander"]:
        stage(m)
