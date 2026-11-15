"""The chatty creatures' core (chattycore/core.lua) into each mod as scripts/<mod>/core.lua - DST mods share one require
namespace, so each mod carries its own copy (never another mod's). Run after editing core.lua:

    python chattycore/sync.py          # copy
    python chattycore/sync.py --check  # exit 1 if a mod's copy differs (the mods' tests run this)
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODS = ["chattyslime", "chattysalamander"]


def main():
    src = (ROOT / "chattycore" / "core.lua").read_bytes()
    check = "--check" in sys.argv
    bad = []
    for mod in MODS:
        dst = ROOT / mod / "scripts" / mod / "core.lua"
        if check:
            if not dst.exists() or dst.read_bytes() != src:
                bad.append(str(dst))
        elif not dst.exists() or dst.read_bytes() != src:
            dst.write_bytes(src)
            print("updated", dst)
    if bad:
        print("out of date (run python chattycore/sync.py):", *bad, sep="\n  ")
        sys.exit(1)


if __name__ == "__main__":
    main()
