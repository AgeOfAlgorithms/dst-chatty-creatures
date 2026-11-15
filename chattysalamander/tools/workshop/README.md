# Publishing to the Steam Workshop

- **Title:** Gilbert the Salamander (AI companion)
- **Description:** `description.txt` (Steam BBCode), pasted on the item's page. Before pasting, replace
  REPLACE_SLIME_ID: the Chatty Slime's item id, once it is up (or drop that link).
- **Preview:** `preview.png` (1024 x 1024; `python chattycore/workshop_preview.py chattysalamander` from the dst-mods root -
  it uses `hero.png`, a frame of the creature's own game art).
- **Screenshots:** `screenshots/*.jpg` (1920 x 1080, taken in the game by `tools/devtest/shots.lua` - see its header
  for how to rerun them). Suggested order: 1_talk, 2_relay, 4_fight, 5_tail, 3_follow, 6_fed, 7_sleep.
- **Tags:** Creature, Companion, Interface (DST's own), and "all_clients_require_mod".
- **Required item:** Proximity Comms (Text and Voice Chat), id 3819346216 - add it under "Add/Remove Required Items".

Upload with Klei's Don't Starve Mod Tools (Mod Uploader), from the folder `sh tools/install.sh` makes (only what the
game loads - never `tools/`). Upload hidden first, try it with a friend, then make it public.
