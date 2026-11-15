-- A slime as a Proximity Comms agent: who it is - its persona, names, noises, how it moves and fights. Its mind (the
-- judge, fight or flee, events, messages, the brain) is the chatty creatures' core (scripts/chattyslime/core.lua, a
-- copy of dst-mods/chattycore/core.lua - edit it there). Server only. Without Proximity Comms, or with no admin's
-- language model on, the slime still lives: it hops about, obeys plain commands said with its name, and blubs.
local cfg = require "chattyslime/config"

local F = {
    tag = "chattyslime",
    kind = "slime",
    cfg = cfg,
    -- (one name - the user, 2026-11-06: "a single name that's easy to pronounce", not a DST creature's; not its own
    -- noises either - "blub" in its lines would sound like its name - and a word speech recognition writes right)
    NAMES = {"Gummy"},
    EMOTES = {"happy", "sad", "surprised", "angry", "dance", "sleep"},
    SCRIPTED = {"Blub!", "Gloop?", "Blub blub!", "*wobbles happily*", "Bloop!"},
    OK_NOISE = "Blub!",          -- (a plain command done, without the AI)
    NO_NOISE = "Gloop?",         -- (one it can't)
    aliases = "the slime, the blob, the little green jelly",
    pronoun = "it",
    loves = "berries, carrots, food, shiny things, hopping, dancing, warm fires, making friends",
    followVerb = "hop after them",
    fearful = true,              -- (acting on its own, it keeps away from monsters)
    brain = {
        faceNear = 8,
        fleeSee = 10, fleeSafe = 14,
        chaseTime = 10, chaseDist = 15,
        followMin = 1.5, followTarget = 3.5, followMax = 6, followRun = true,
        wander = 6, wanderTimes = {minwalktime = 1, randwalktime = 1, minwaittime = 3, randwaittime = 6},
    },
}

function F.persona(name)
    return ("You are %s, a little slime in the world of Don't Starve Together: a wobbly blob of green jelly. "
        .. "You live near the players and hop after them. You are cheerful, curious and a "
        .. "bit naive. You love berries, carrots and shiny things; you are scared of spiders, hounds and the dark, and "
        .. "glad of a warm fire at night - you are small, so you usually flee from monsters unless your friends need "
        .. "you. You know only the world of the game. Speak in one or two short, simple sentences, now and then with a "
        .. "squishy sound (blub, gloop), in the language the player speaks to you. Do only what your functions do; "
        .. "never say you did anything else."):format(name)
end

return require("chattyslime/core")(F)
