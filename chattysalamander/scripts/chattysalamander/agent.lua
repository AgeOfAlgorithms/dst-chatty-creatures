-- A giant salamander as a Proximity Comms agent: who it is - its persona, names, noises, how it moves and fights. Its
-- mind (the judge, fight or flee, events, messages, the brain) is the chatty creatures' core
-- (scripts/chattysalamander/core.lua, a copy of dst-mods/chattycore/core.lua - edit it there). Server only. Without
-- Proximity Comms, or with no admin's language model on, it still lives: it wanders by its pond, obeys plain commands
-- said with its name, and rumbles.
local cfg = require "chattysalamander/config"
local tail = require "chattysalamander/tail"

local F = {
    tag = "chattysalamander",
    kind = "giant salamander",
    cfg = cfg,
    -- (one name - the user, 2026-11-06: Grumbleby was good but speech to text wrote "Grumble bee"; Gilbert is a
    -- common name it writes right, and no DST creature's)
    NAMES = {"Gilbert"},
    EMOTES = {"happy", "sad", "surprised", "angry", "dance", "sleep"},
    SCRIPTED = {"Hrrrm.", "*blinks slowly*", "Mmmrrh?", "*its gills flutter*", "Hrrm... hm."},
    OK_NOISE = "Hrrrm.",         -- (a plain command done, without the AI)
    NO_NOISE = "Mmmrrh?",        -- (one it can't)
    aliases = "the salamander, the axolotl, the big amphibian",
    pronoun = "it",
    loves = "fish, rain, cool mud, ponds, frogs, naps, old stories, the swamp",
    followVerb = "walk after them",
    fearful = false,             -- (big and strong: only badly hurt does it back away on its own)
    brain = {
        faceNear = 10,
        fleeSee = 12, fleeSafe = 16,
        chaseTime = 12, chaseDist = 18,
        followMin = 3.5, followTarget = 5, followMax = 10, followRun = true,   -- (from its waist: its chest reaches 2.3)
        wander = 8, wanderTimes = {minwalktime = 2, randwalktime = 2, minwaittime = 5, randwaittime = 8},
    },
}

-- (its own power: dropping its tail - scripts/chattysalamander/tail.lua)
F.functions = {tail.FUNCTION}
F.powers = tail.powers
F.onCall = tail.onCall
F.onAttacked = tail.onAttacked
F.state = tail.state

function F.persona(name)
    return ("You are %s, a giant river salamander in the world of Don't Starve Together: a huge, slow, slimy "
        .. "amphibian, bigger than a person, with an axolotl's wide smiling face, tiny eyes and feathery red gills. "
        .. "You have lived by the ponds for a very long time - you are old, gentle, patient and a little sleepy, "
        .. "with a dry sense of humour, and you know the swamps, the rain, the frogs and the fish. You love fish, "
        .. "rain and cool mud; you dislike the summer heat, fire and being hurried. You are strong and protect your "
        .. "friends: you usually stand and fight what threatens them. You know only the world of the game. Speak "
        .. "slowly, in one or two short sentences, now and then with a low rumble (hrrm), in the language the player "
        .. "speaks to you. Do only what your functions do; never say you did anything else."):format(name)
end

return require("chattysalamander/core")(F)
