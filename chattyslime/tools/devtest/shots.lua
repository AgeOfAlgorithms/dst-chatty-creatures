-- The Workshop page's screenshots (the user, 2026-11-05: "good preview images and screenshots (make sure to include
-- screenshots of them talking)"): staged scenes, each "[PCTEST] SHOT <name>" (tools/devtest/shots.ps1 presses Steam's
-- screenshot key). Lines are said through the mods' own paths - the player's through Proximity Comms (CL.say), other
-- players as stand-in figures, the slime through its agent (agent.scripted). No language model: these are the
-- lines a model would say. Run from the proxcomms repo, with the slime installed (sh tools/install.sh here):
--   cp tools/devtest/shots.lua <dir>/slime.lua; KOETAMA=... SCENE=slime SCENE_DIR=<dir> sh tools/devtest/run.sh <out>
local G, out, later = ...
local CL = G.require "proxcomms/client"
local D = G.require "proxcomms/dummies"
local agent = G.require "chattyslime/agent"

local s, extra = nil, {}
local fx, fz, rx, rz, x0, z0
local function P(a, b) return G.Vector3(x0 + rx * a + fx * b, 0, z0 + rz * a + fz * b) end
local function face(e, p)                -- (staging: turned at once, not at its turning speed)
    local x, _, z = e.Transform:GetWorldPosition()
    e.Transform:SetRotation(G.math.deg(G.math.atan2(-(p.z - z), p.x - x)))
    e.chattywant = nil                   -- (and not turning on toward an earlier aim: body.lua)
end

local cast = {}
local function figure(key, build, name, a, b)
    local p = P(a, b)
    local d = D.make(2, p.x, p.z)
    d.uid, d.name = "slimeshot_" .. key, name
    if d.ent and d.ent.AnimState then
        d.ent.AnimState:SetBuild(build)
        d.ent.AnimState:SetMultColour(1, 1, 1, 1)
        d.ent.Transform:SetRotation(G.TheCamera:GetHeading() + 180)
    end
    D.list[#D.list + 1] = d
    D.nextAt = 1e12
    cast[key] = d
    return d
end
local lid = 7000000
local function line(key, text)
    local d = cast[key]
    lid = lid + 1
    if d.ent and d.ent.AnimState then d.ent.AnimState:PlayAnimation("dial_loop", true) end
    CL.onLine(d.uid, d.name, text, "s", lid, d.x, d.z, false)
end
local function says(text)
    s.chatty.scriptedT = nil
    agent.scripted(s, text)
end
local function cut()
    G.TheCamera:SetDistance(18)
    D.clear()
    cast = {}
    CL.bubbles, CL.live = {}, {}
    for _, e in G.ipairs(extra) do if e:IsValid() then e:Remove() end end
    extra = {}
end
local function place(a, b, toward)
    local p = P(a, b)
    s.Transform:SetPosition(p.x, 0, p.z)
    if toward then face(s, toward) end
    s.sg:GoToState("idle")
end

local t = 3
local function at(dt, fn) t = t + dt later(t, fn) end

at(0, function()
    G.pcall(function() G.ThePlayer.components.health:SetInvincible(true) end)
    G.TheWorld:PushEvent("ms_setclocksegs", {day = 16, dusk = 0, night = 0})
    D.CL = CL
    local px, pz = D.ahead(-6, -30)
    G.ThePlayer.Physics:Teleport(px, 0, pz)
end)
at(1.5, function()
    local h = G.TheCamera:GetHeading() * G.math.pi / 180
    fx, fz = -G.math.cos(h), -G.math.sin(h)
    rx, rz = G.math.cos(h + G.math.pi / 2), G.math.sin(h + G.math.pi / 2)
    x0, z0 = D.ahead(0, 0)
    local c = G.ThePlayer.HUD and G.ThePlayer.HUD.controls
    for _, k in G.ipairs({"inv", "status", "clock", "mapcontrols", "craftingmenu", "networkchatqueue", "containerroot",
            "secondary_status", "seasonclock"}) do
        G.pcall(function() if c[k] then c[k]:Hide() end end)
    end
    -- (the world's own one goes: it has the one name, and it would answer the scene's lines to Gummy)
    for _, v in G.pairs(G.Ents) do if v.prefab == "chattyslime" then v:Remove() end end
    s = G.SpawnPrefab("chattyslime")
    s.chatty.name = "Gummy"
    s:StopBrain()
    place(2.6, 0.4, P(0, 0))
    face(G.ThePlayer, P(2.6, 0.4))
    G.TheCamera:SetDistance(15)
end)
-- 1. talking with it
at(2.5, function()
    face(s, P(0, 0))
    s.chatty.scriptedT = G.GetTime() + 30     -- (no stock noise for its name: the scene's line answers)
    CL.say("Gummy, what's your favourite food?", "s")
end)
at(1.4, function() says("Berries! Red ones, blue ones... gloop, ALL the berries!") end)
at(1.4, function() out("SHOT 1_talk") end)
-- 2. a message carried from one player to another
at(1.5, function()
    cut()
    G.TheCamera:SetDistance(15)
    figure("willow", "willow", "Willow", -2.4, 1.2)
    figure("wendy", "wendy", "Wendy", 6.0, 1.8)
    place(2.8, 1.0, P(6.0, 1.8))
end)
at(0.6, function() line("willow", "Gummy, tell Wendy dinner's ready by the fire!") end)
at(1.6, function() says("Blub! Wendy! Willow says dinner is ready by the fire!") end)
at(1.4, function() out("SHOT 2_relay") end)
-- 3. hopping after you
at(1.5, function()
    cut()
    G.TheCamera:SetDistance(15)
    place(4.5, 4.0, P(1, 0))
    s.components.locomotor:GoToPoint(P(1.8, 0.8))
end)
at(1.0, function() says("Wait for me! Blub blub!") end)
at(0.8, function() out("SHOT 3_follow") end)
-- 4. a spider! scared
at(1.5, function()
    s.components.locomotor:Stop()
    cut()
    G.TheCamera:SetDistance(15)
    place(2.4, 0.6, P(6, 0.6))
    local sp = G.SpawnPrefab("spider")
    local p = P(5.6, 1.0)
    sp.Physics:Teleport(p.x, 0, p.z)
    sp:StopBrain()
    face(sp, P(2.4, 0.6))
    extra[#extra + 1] = sp
end)
at(0.5, function() s:PushEvent("chattyslime_emote", {emote = "surprised"}) end)
at(0.2, function() says("Eek! A spider! Gloop gloop!") end)
at(0.6, function() out("SHOT 4_scared") end)
-- 5. a dance, asked for
at(1.5, function()
    cut()
    G.TheCamera:SetDistance(15)
    place(2.6, 0.4, P(0, 0))
    face(G.ThePlayer, P(2.6, 0.4))
end)
at(0.5, function()
    s.chatty.scriptedT = G.GetTime() + 30
    CL.say("Gummy, show us a dance!", "s")
end)
at(1.0, function()
    s:PushEvent("chattyslime_emote", {emote = "dance"})
    local P_ = G.ProxComms
    if P_ and P_.say and s.chatty.id then P_.say(s.chatty.id, "Blub blub blub~! Watch me wiggle!") end
end)
at(1.3, function() out("SHOT 5_dance") end)
-- 6. fed: happy
at(1.8, function()
    cut()
    G.TheCamera:SetDistance(15)
    place(2.6, 0.4, P(0, 0))
    face(G.ThePlayer, P(2.6, 0.4))
end)
at(0.5, function() CL.say("Here, have a carrot!", "s") end)
at(1.0, function()
    s:PushEvent("chattyslime_emote", {emote = "eat"})
    local P_ = G.ProxComms
    if P_ and P_.say and s.chatty.id then P_.say(s.chatty.id, "Mmm, crunchy! Thank you, friend! Blub!") end
end)
at(1.2, function() out("SHOT 6_fed") end)
-- 7. dusk: asleep
at(1.8, function()
    cut()
    G.TheCamera:SetDistance(15)
    G.TheWorld:PushEvent("ms_setclocksegs", {day = 0, dusk = 16, night = 0})
    place(2.6, 0.4, P(6, 0.4))
    s:PushEvent("chattyslime_emote", {emote = "sleep", time = 30})
end)
at(3.0, function() CL.say("shh... it's asleep", "w") end)
at(1.0, function() out("SHOT 7_sleep") end)
at(2.0, function()
    G.TheWorld:PushEvent("ms_setclocksegs", {day = 16, dusk = 0, night = 0})
    out("DONE")
end)
