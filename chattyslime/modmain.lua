-- Chatty Slime: a creature of its own (anim/chattyslime.zip, from tools/anim/rig.py) that talks through Proximity
-- Comms' agents (scripts/chattyslime/agent.lua).
local G = GLOBAL

PrefabFiles = {"chattyslime"}

-- its voice (tools/sound/voice.json -> dst-mods/chattycore/makesound.py): events "chattyslime/slime/<name>"
Assets = {
    Asset("SOUNDPACKAGE", "sound/chattyslime.fev"),
    Asset("SOUND", "sound/chattyslime.fsb"),
}

local cfg = require "chattyslime/config"
local function opt(name, default)
    local v = GetModConfigData(name)
    if v == nil then return default end
    return v
end
cfg.count = opt("count", 1)
cfg.hears = opt("hears", "engaged")
cfg.greet = opt("greet", true)
cfg.chatter = opt("chatter", 10)
cfg.respawn_days = opt("respawn_days", 3)

G.STRINGS.NAMES.CHATTYSLIME = "Slime"
G.STRINGS.CHARACTERS.GENERIC.DESCRIBE.CHATTYSLIME = "A wobbly little blob. It looks like it wants to chat."

AddPrefabPostInit("forest", function(inst)
    if inst.ismastersim then inst:AddComponent("chattyslimespawner") end
end)
