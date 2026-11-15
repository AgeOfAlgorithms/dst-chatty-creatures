# Chatty creatures for Don't Starve Together

AI companions you talk to, in the chat or out loud. They answer in character, follow you, fight beside you, dance,
eat and sleep, and decide for themselves when a conversation is about them. They are
[Proximity Comms](https://github.com/AgeOfAlgorithms/dst-proximity-comms) agents, played by the language model of an
admin's [Koetama](https://github.com/AgeOfAlgorithms/koetama). Without it they still live: they wander, obey plain
commands said with their name, and make their own noises.

| folder | what | Workshop |
|---|---|---|
| `chattyslime/` | **Gummy the Slime**: a small, cheerful slime | [3834526151](https://steamcommunity.com/sharedfiles/filedetails/?id=3834526151) |
| `chattysalamander/` | **Gilbert the Salamander**: a giant river salamander with an axolotl's face, bigger than you | [3834525969](https://steamcommunity.com/sharedfiles/filedetails/?id=3834525969) |
| `chattycore/` | their shared mind (the judge, fight or flee, events, messages), copied into each mod by `sync.py`; their voices (`makesound.py`, `fmodbank.py`) | |
| `tools/blender/` | the DST look for the salamander's 3D renders | |

Both mods need Proximity Comms ([3819346216](https://steamcommunity.com/sharedfiles/filedetails/?id=3819346216)).
Each mod's own scripts hold who its creature is (`scripts/<mod>/agent.lua`: persona, names, noises), its prefab,
brain and stategraph; `tools/` has the art and animation pipeline (`tools/gen`, `tools/anim/rig.py`), the offline
tests and the in-game test (`tools/devtest/run.sh`, through Proximity Comms' dev harness). `chattycore/PROJECT.md`
has the commands.

Art: drawings made with Qwen-Image-Edit (locally, in ComfyUI), cut into parts and rigged by code; the salamander's
parts rendered from a 3D model in Blender. The animations are baked by `tools/anim/rig.py` into DST's anim format.

MIT License (`LICENSE`).
