# Chatty creatures' core

The mind of the Chatty Slime and the Chatty Salamander (DST), shared: Mochi the Corgi's features (Teardown,
`teardown-mods/mochi`) ported (the user, 2026-11-05: "plan the port", then "yes"). Each mod keeps only who its creature
is (`scripts/<mod>/agent.lua`: persona, names, noises, the brain's numbers) and loads its own copy of this core.

| path | what |
|---|---|
| `core.lua` | the core (source of truth): `require("<mod>/core")(F)` -> the agent module for flavour F |
| `sync.py` | copies `core.lua` into each mod as `scripts/<mod>/core.lua` (`--check`: exit 1 when a copy differs) |
| `test_core.lua` | offline tests through a mod's `agent.lua` (mocked DST, mocked Proximity Comms API 2) |

| `makesound.py` | the creatures' voices: MOSS-SoundEffect jobs from a mod's `tools/sound/voice.json`, review, bank build |
| `fmodbank.py` | writes an FMOD Designer 4.44 project (.fdp) and builds it with the Mod Tools' `fmod_designercl.exe` |

Why a copy in each mod: DST mods share one `require` namespace - a shared `chattycore/...` path would load whichever
mod's copy came first, possibly an older one.

## Commands

```bash
python chattycore/sync.py                                    # after editing core.lua (from dst-mods/)
cd chattyslime && luajit -joff tools/test_chattyslime.lua    # 93 checks, the core through the slime
cd chattysalamander && luajit -joff tools/test_chattysalamander.lua
cd chattyslime && KOETAMA=<koetama build> sh tools/devtest/run.sh <scratch>   # in game (Proximity Comms' devtest)
```

## Voices (2026-11-05: the user asked for the creatures' own sounds)

Each mod has its own bank, `sound/<mod>.fev` + `.fsb`, loaded in modmain (`Asset("SOUNDPACKAGE")`, `Asset("SOUND")`);
the stategraphs play `"<mod>/<group>/<event>"` (slime: `chattyslime/slime/...`, salamander:
`chattysalamander/salamander/...`). An event with several takes plays one at random, never the same twice running.

```bash
python chattycore/makesound.py jobs chattyslime                   # voice.json -> audio-gen/chatty_raw/<mod>/jobs.json
MOSS=/c/Users/seann/miniconda3/envs/audiogen-moss/python.exe
(cd ../audio-gen && $MOSS gen_moss.py chatty_raw/chattyslime/jobs.json --skip-existing)  # ~27 s a take; fills the GPU
$MOSS chattycore/makesound.py review chattyslime                  # auto-picks missing events; review.html to listen
$MOSS chattycore/makesound.py build chattyslime                   # picks.json -> tools/sound/wav/ -> sound/
```

- Takes: mono, trimmed at -40 dB, peak -1 dBFS; the event's `volume_db` and the stategraph's volume set the level.
- Events are 3D, Linear rolloff, 3 to 30, oneshot: what 4728 of DST's own 6030 events use (read from
  `data/sound/*.fev` by matching the fields of a test build, 2026-11-05).
- In game (devtest, 2026-11-05): every event of both banks plays with no FMOD error (a missing one logs
  `FMOD Error: Can't play event '...'`; the scenes play each event once, then a missing one, to show that). Picks are
  automatic (length and noisiness) until the user has listened: `audio-gen/chatty_raw/<mod>/review.html`.
- To change a sound: edit its prompt or add takes in `voice.json`, remove its entry from `picks.json`, rerun the
  steps (`--skip-existing` renders only new takes; a changed prompt needs its old takes deleted first).

## The user's rules (2026-11-05)

- **Fight or flee:** "flee automatically but let the AI decide whether to fight or flee". With its AI on and fit
  (health >= 30 %), a danger (something attacking it, its leader or a player near it) is an urgent event and its AI
  calls `attack` or `run_away` (or neither - an answer without a call is a choice too). No answer within 6 s: it acts
  on its own for 30 s. On its own (no AI, badly hurt, or that): it fights what attacks it or its leader; badly hurt it
  flees; the slime (`F.fearful`) also keeps away from monsters.
- **Attacks: host only** ("for now"). Every player a call answers must be the host (a client-hosted server's host -
  the client entry with `performance`; a dedicated server: its admins); other creatures' lines in the same turn don't
  count (seen in game: a second slime's chatter in the host's turn blocked the host's order). Fighting a danger it was
  told of is its own choice, whoever asked; one it already fights is not asked about.
- **Owner, not host** (2026-11-06: "breaks immersion"): what it knows says "<name> is your owner"; the persona: call
  players by name or "friend", never "host" / "admin" / "server" (code keeps `isHost`).
- **No claiming what it didn't do** (2026-11-06: it said it followed / ate berries on the ground without doing it):
  the persona says words alone do nothing - call the function or say you can't; `eat` (food on the ground) added;
  and "follow me", "come here", "stay here" (said with its name, not negated) are done at once by `M.direct`,
  whatever its AI answers.
- **The slime** (2026-11-06): one name, **Gummy** (then "Gummy 2", ...; older random names give way on load); 250
  health, 30 a bite every 1.5 s; walk 7 / run 12 while airborne (about 3.7 / 6.3 on average), running hops 1.5x
  quicker, and it runs to keep up with its leader.
- **Creatures hear each other by default, 10 lines in a row** (`cfg.chatter`, the mods' "Talks with others" option:
  Off / 4 / 10 / 20; Proximity Comms' `hearagents`).

## What else it does (Mochi's, adapted)

- **Judge** (Koetama 0.5.14's scores, `ProxComms.scores()`): `hears = "near"`, criteria topic / interest / wellbeing /
  ended / quiet in its own words; `M.RUBRIC` is Mochi's (answer at 0.9; name +0.5, talking with them +0.3, within 4 m
  +0.15, its leader +0.2 - DST has no "looking at it" -, the host +0.1; pacing -0.25 a line of its own in 20 s after
  the first). Ended: no answer; quiet: whisper mode until its AI calls `quiet` off. Without scores: the mods' "It
  listens to" option as before.
- **Events** gathered as one note for the next line said to it (`ProxComms.note`, API 2's `noted` / `note(id, nil)`);
  nobody talks within 4 s: one event line (not within 10 s of its own line); urgent ones (danger, greet, bored, relay,
  its leader died, dying) at once. Fed, hurt, killed, dusk / night / day, rain, a full moon, a new season (those with a
  player within 20 m).
- **Relay** (`relay(to, message)`): to a player or another chatty creature; within 4 m it tells them (an urgent event);
  no closer in 12 s: it keeps the message (4 at most, 15 min) and goes when they are within 25 m again.
- **Bored** after 90 s with nothing happening and a player within 25 m (urgent: its AI may start a talk).
- **Death:** a goodbye event; its agent waits up to 12 s for it, then goes.
- **Without the AI:** plain commands said with its name (follow, come / here, stay / wait, stop / calm, dance) with
  a noise (`F.OK_NOISE` / `F.NO_NOISE`).

## Not ported (Teardown only)

Fetch and the ball, the treats tool, petting with E, swimming, the raw sound levels, the spawn menu.

## Status (2026-11-05)

- Offline: both mods' tests pass (95 checks each).
- In game (Proximity Comms' devtest, test Koetama 0.5.14 with tools/devtest/fake_llm.py, scenes `slime` / `salamander`
  here): both load and run with the core (no Lua error); without the AI they follow by plain command and fight on
  their own; with it: follow (the host), its bubble on the creature as it walks (`CHECK bubble follows it`), dance,
  the host's "attack the spider" fought and won, the "fight or flee?" danger event, hurt / killed gathered as one note,
  greeting, bored, the dying goodbye, its agent removed after.
- Not seen in game yet: a real model's scores and choices, run_away / relay / quiet / come by the AI, the world's events
  (dusk, rain), caves, multiplayer (a non-host's attack order refused there).
