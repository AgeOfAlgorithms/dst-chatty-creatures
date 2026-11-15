-- The Workshop page's screenshots (the user, 2026-11-05: "good preview images and screenshots (make sure to include
-- screenshots of them talking)"): staged scenes, each "[PCTEST] SHOT <name>" (tools/devtest/shots.ps1 presses Steam's
-- screenshot key). Lines are said through the mods' own paths - the player's through Proximity Comms (CL.say), other
-- players as stand-in figures, the salamander through its agent (agent.scripted). No language model: these are the
-- lines a model would say. Run from the proxcomms repo, with the salamander installed (sh tools/install.sh here):
--   cp tools/devtest/shots.lua <dir>/salamander.lua; KOETAMA=... SCENE=salamander SCENE_DIR=<dir> sh tools/devtest/run.sh <out>
local G, out, later = ...
local CL = G.require "proxcomms/client"
local D = G.require "proxcomms/dummies"
local agent = G.require "chattysalamander/agent"
local tail = G.require "chattysalamander/tail"

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
    d.uid, d.name = "salshot_" .. key, name
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
    s.chattybody.hx, s.chattyrearst.hx = nil, nil          -- (the hips straight behind again)
    if toward then face(s, toward) end
    s.sg:GoToState("idle")
end

local t = 3
local function at(dt, fn) t = t + dt later(t, fn) end

at(0, function()
    G.pcall(function() G.ThePlayer.components.health:SetInvincible(true) end)
    G.TheWorld:PushEvent("ms_setclocksegs", {day = 16, dusk = 0, night = 0})
    D.CL = CL
    -- (somewhere open: away from the portal)
    local px, pz = D.ahead(-6, -30)
    G.ThePlayer.Physics:Teleport(px, 0, pz)
end)
at(1.5, function()
    local h = G.TheCamera:GetHeading() * G.math.pi / 180
    fx, fz = -G.math.cos(h), -G.math.sin(h)
    rx, rz = G.math.cos(h + G.math.pi / 2), G.math.sin(h + G.math.pi / 2)
    x0, z0 = D.ahead(0, 0)
    G.TheCamera:SetDistance(20)
    -- (a clean picture: no inventory, clock, map buttons, crafting, chat history)
    local c = G.ThePlayer.HUD and G.ThePlayer.HUD.controls
    for _, k in G.ipairs({"inv", "status", "clock", "mapcontrols", "craftingmenu", "networkchatqueue", "containerroot",
            "secondary_status", "seasonclock"}) do
        G.pcall(function() if c[k] then c[k]:Hide() end end)
    end
    -- (the world's own one goes: it has the one name, and it would answer the scene's lines to Gilbert)
    for _, v in G.pairs(G.Ents) do if v.prefab == "chattysalamander" then v:Remove() end end
    s = G.SpawnPrefab("chattysalamander")
    s.chatty.name = "Gilbert"
    s:StopBrain()
    place(6.2, 0.8, P(0, 0))
    face(G.ThePlayer, P(6.2, 0.8))
    G.TheCamera:SetDistance(18)
end)
-- 1. talking with it
at(2.5, function() CL.say("Hey big fella, seen any frogs around here?", "s") end)
at(1.4, function() says("Hrrm... the frogs sing by the old pond at dusk. Come, I'll show you.") end)
at(1.4, function() out("SHOT 1_talk") end)
-- 2. a message carried from one player to another
at(1.5, function()
    cut()
    figure("willow", "willow", "Willow", -2.6, 1.6)
    figure("wendy", "wendy", "Wendy", 11.5, 2.6)
    place(5.2, 1.6, P(11.5, 2.6))
end)
at(0.6, function() line("willow", "Gilbert, go tell Wendy the pigs are waiting at the base!") end)
at(1.6, function() says("Hrrm. Wendy... Willow says the pigs are waiting for you at the base.") end)
at(1.4, function() out("SHOT 2_relay") end)
-- 3. following you, its body bending after its head
at(1.5, function()
    cut()
    place(6.5, 7.5, P(3.0, 0))
    s.components.locomotor:GoToPoint(P(2.6, 1.8))
end)
at(1.3, function() says("Right behind you, friend. Slow and steady.") end)
at(0.9, function() out("SHOT 3_follow") end)
-- 4. standing up for you
at(1.5, function()
    s.components.locomotor:Stop()
    cut()
    place(5.0, 0.8, P(9, 0.6))
    for i, p in G.ipairs({P(8.9, 0.6), P(9.8, 2.2)}) do
        local sp = G.SpawnPrefab("spider")
        sp.Physics:Teleport(p.x, 0, p.z)
        sp:StopBrain()
        face(sp, P(5.0, 0.8))
        extra[#extra + 1] = sp
    end
    s.components.combat:SetTarget(extra[1])
end)
at(0.6, function() says("Stay behind me! Hrrrm!") end)
at(0.4, function() s:PushEvent("doattack", {target = extra[1]}) end)
at(0.55, function() out("SHOT 4_fight") end)
-- 5. it drops its tail and runs - the spider goes for the tail
at(1.6, function()
    cut()
    place(4.5, 1.5, P(-2, 8))
    local sp = G.SpawnPrefab("spider")
    local p = P(11.0, 1.6)
    sp.Physics:Teleport(p.x, 0, p.z)
    extra[#extra + 1] = sp
    sp.components.combat:SetTarget(s)
end)
at(0.8, function()
    local d = tail.drop(s, extra[1], agent)
    if d then extra[#extra + 1] = d end
    s.components.locomotor:GoToPoint(P(-1, 9))
end)
at(0.5, function() says("Take the tail, not me! Hrrrm!") end)
at(1.4, function() out("SHOT 5_tail") end)
-- 6. fed a fish: happy
at(1.6, function()
    cut()
    s.chatty.tailless = nil                   -- (its tail back for the rest: the pictures, not a day's wait)
    s.chattytailless:set(false)
    s.components.locomotor:Stop()
    place(6.2, 0.6, P(0, 0))
    face(G.ThePlayer, P(6.2, 0.6))
end)
at(0.6, function() CL.say("Here, I caught you a fish!", "s") end)
at(1.0, function()
    s:PushEvent("chattysalamander_emote", {emote = "happy"})
    s.chatty.scriptedT = nil
end)
at(0.3, function()
    local P_ = G.ProxComms
    if P_ and P_.say and s.chatty.id then P_.say(s.chatty.id, "Fish! Oh, you do know me, friend.") end
end)
at(0.9, function() out("SHOT 6_fed") end)
-- 7. dusk: asleep
at(1.6, function()
    cut()
    G.TheWorld:PushEvent("ms_setclocksegs", {day = 0, dusk = 16, night = 0})
    place(5.6, 1.0, P(10, 0.4))
    s:PushEvent("chattysalamander_emote", {emote = "sleep", time = 30})
end)
at(3.0, function() CL.say("shh... he's asleep", "w") end)
at(1.0, function() out("SHOT 7_sleep") end)
at(2.0, function()
    G.TheWorld:PushEvent("ms_setclocksegs", {day = 16, dusk = 0, night = 0})
    out("DONE")
end)
