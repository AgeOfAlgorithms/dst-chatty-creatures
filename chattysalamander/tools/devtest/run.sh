#!/bin/sh
# One automated in-game run (dev only): installs this mod, then runs Proximity Comms' dev harness (its repo next to
# this one, PROXCOMMS) with this folder's salamander scene and its fake language model; that turns the mods on in DST's
# mods/modsettings.lua for the run (proxcomms, proxcomms_devtest and chattysalamander) and puts it back after. Queue it through
# the teardown-mods broker: python <teardown-mods>/tools/turn.py run --what "chattysalamander: devtest" --minutes 8 -- sh ...
# Run from the repo root (Git Bash): KOETAMA=<a koetama build> sh tools/devtest/run.sh <scratch dir>
OUT="${1:?a scratch folder}"
PROXCOMMS="${PROXCOMMS:-$(cd .. && pwd)/proxcomms}"
HERE="$(pwd)"
sh tools/install.sh
cd "$PROXCOMMS" && ENABLE_MODS=chattysalamander SCENE=salamander SCENE_DIR="$HERE/tools/devtest" FAKE_LLM=1 sh tools/devtest/run.sh "$OUT"
