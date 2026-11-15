#!/bin/sh
# Copies the mod (only what the game loads) into DST's mods folder as "chattyslime" (local development), named
# "... (local dev)" in the game's mod list. Run from the repo root: sh tools/install.sh
GAME="/c/Program Files (x86)/Steam/steamapps/common/Don't Starve Together"
DST="${DST:-$GAME}"
DEST="$DST/mods/chattyslime"
rm -rf "$DEST"
mkdir -p "$DEST"
cp modinfo.lua modmain.lua modicon.tex modicon.xml "$DEST/"
sed -i 's/^name = "\(.*\)"$/name = "\1 (local dev)"/' "$DEST/modinfo.lua"
cp -r scripts anim sound "$DEST/"
diff -r scripts "$DEST/scripts" >/dev/null && echo "installed: $DEST"
