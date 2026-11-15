-- Chatty Salamander: a creature of its own (anim/chattysalamander.zip, from tools/anim/rig.py) that talks through
-- Proximity Comms' agents (scripts/chattysalamander/agent.lua).
local G = GLOBAL

PrefabFiles = {"chattysalamander"}

-- its voice (tools/sound/voice.json -> dst-mods/chattycore/makesound.py): events "chattysalamander/salamander/<name>"
Assets = {
    Asset("SOUNDPACKAGE", "sound/chattysalamander.fev"),
    Asset("SOUND", "sound/chattysalamander.fsb"),
}

local cfg = require "chattysalamander/config"
local function opt(name, default)
    local v = GetModConfigData(name)
    if v == nil then return default end
    return v
end
cfg.count = opt("count", 1)
cfg.hears = opt("hears", "engaged")
cfg.greet = opt("greet", true)
cfg.chatter = opt("chatter", 10)
cfg.respawn_days = opt("respawn_days", 5)

G.STRINGS.NAMES.CHATTYSALAMANDER = "Giant Salamander"
G.STRINGS.CHARACTERS.GENERIC.DESCRIBE.CHATTYSALAMANDER = "An enormous, slimy, smiling salamander. It seems to want a chat."
G.STRINGS.NAMES.CHATTYSALAMANDER_TAIL = "Salamander Tail"
G.STRINGS.CHARACTERS.GENERIC.DESCRIBE.CHATTYSALAMANDER_TAIL = "It's still wriggling! The rest of it ran off."

AddPrefabPostInit("forest", function(inst)
    if inst.ismastersim then inst:AddComponent("chattysalamanderspawner") end
end)

-- (debug: rings on the ground at every salamander's three bodies - its waist, chest and hips - to see its hitbox
-- against its drawing; in the console: c_salamanderhitboxes(true), c_salamanderhitboxes(false))
G.c_salamanderhitboxes = function(on)
    local body = G.require("chattysalamander/body")
    for _, e in pairs(G.Ents) do
        if e.prefab == "chattysalamander" then body.showBodies(e, on ~= false) end
    end
end
