-- Dev only: the Chatty Slime in a real world, through Proximity Comms' dev harness (its tools/devtest: run with
-- SCENE=slime SCENE_DIR=<this folder> FAKE_LLM=1; tools/devtest/run.sh here does that). The slime the spawner put by
-- the portal; one next to the player, named Gummy, through every animation (a screenshot each); then the player says
-- "Gummy, follow me!" (the fake model answers and calls follow), walks off (it hops after), "Gummy, dance!" (a call
-- to emote), "Gummy, attack the spider!" (a call to attack: it fights a spider), and it dies. Logged as [PCTEST] lines.
local G, out, later = ...
local CL = G.require "proxcomms/client"
local K = G.require "proxcomms/koetama"
local AG = G.require "proxcomms/agents"
local D = G.require "proxcomms/dummies"

local s, fightDone
local function waitFor(ok, limit, fn)
    local t0 = G.GetStaticTime()
    local function poll()
        if ok() or G.GetStaticTime() - t0 > limit then fn() return end
        later(0.5, poll)
    end
    poll()
end

local function slimes()
    local n, list = 0, {}
    for _, v in G.pairs(G.Ents) do
        if v.prefab == "chattyslime" then
            n = n + 1
            list[#list + 1] = G.tostring(v.chatty.name) .. "@" .. G.string.format("%.0f,%.0f", v:GetPosition().x, v:GetPosition().z)
        end
    end
    return n, G.table.concat(list, " ")
end

local function where()
    local sg = s.sg and s.sg.currentstate and s.sg.currentstate.name or "?"
    local d = G.math.sqrt(s:GetDistanceSqToInst(G.ThePlayer))
    local leader = s.components.follower:GetLeader()
    return ("state %s dist %.1f leader %s"):format(sg, d, G.tostring(leader and leader.name))
end

-- (what its mind tells its AI: logged - danger, hurt, killed, greet, ...)
local ev0, note0 = G.ProxComms.event, G.ProxComms.note
G.ProxComms.event = function(id, text) out("event", G.tostring(id), G.tostring(text)) return ev0(id, text) end
G.ProxComms.note = function(id, text) if text then out("note", G.tostring(id), G.tostring(text)) end return note0(id, text) end

-- (somewhere open, away from the portal: it is in the way of the screenshots - the user, 2026-11-06)
later(2.4, function()
    D.CL = CL
    local px, pz = D.ahead(-6, -30)
    G.ThePlayer.Physics:Teleport(px, 0, pz)
end)

later(3, function()
    G.pcall(function() G.ThePlayer.components.health:SetInvincible(true) end)
    G.TheWorld:PushEvent("ms_setclocksegs", {day = 16, dusk = 0, night = 0})
    local portal = G.TheSim:FindFirstEntityWithTag("multiplayer_portal")
    local n, list = slimes()
    out("slime: at the start", n, list, "portal", portal and G.string.format("%.0f,%.0f", portal:GetPosition().x, portal:GetPosition().z))
    -- (the world's own slime goes: it has the one name, and "Gummy, ..." would be its - the scene's would be Gummy 2)
    for _, v in G.pairs(G.Ents) do if v.prefab == "chattyslime" then v:Remove() end end
    D.CL = CL
    local x, z = D.ahead(0, 3.2)
    s = G.SpawnPrefab("chattyslime")
    s.chatty.name = "Gummy"
    s.Transform:SetPosition(x, 0, z)
    s:StopBrain()
end)

-- (its voice: every event once, then one that doesn't exist - what the log says for a missing event)
local VOICE = {"land", "talk", "happy", "sad", "surprised", "angry", "eat", "attack_voice", "attack", "hurt", "die",
    "wake", "zz_no_such_event"}
for i, k in G.ipairs(VOICE) do
    later(3.5 + i * 0.15, function()
        out("SOUND chattyslime/slime/" .. k)
        G.ThePlayer.SoundEmitter:PlaySound("chattyslime/slime/" .. k, nil, 0.05)
    end)
end

-- (every animation, a screenshot each)
local EMOTES = {"happy", "sad", "surprised", "angry", "dance", "eat"}
later(6, function()
    out("slime", s.chatty.name, s.chatty.id, where(), "named", s.name)
    out("SHOT slime_idle")
end)
for i, e in G.ipairs(EMOTES) do
    later(6 + i * 3, function()
        s:PushEvent("chattyslime_emote", {emote = e})
        later(0.5, function() out("emote", e, where()) out("SHOT slime_" .. e) end)
    end)
end
local T = 6 + #EMOTES * 3 + 3
later(T, function()
    s:PushEvent("chattyslime_emote", {emote = "sleep", time = 4})
    later(2, function() out("sleep", where()) out("SHOT slime_sleep") end)
end)
later(T + 7, function()
    s.sg:GoToState("hit")
    later(0.1, function() out("SHOT slime_hit") end)
end)
later(T + 9, function()
    s.sg:GoToState("think", G.ThePlayer)
    later(0.6, function() out("SHOT slime_think") end)
end)
later(T + 10, function()
    s.sg:GoToState("attack")
    later(0.34, function() out("attack", where()) out("SHOT slime_attack") end)
end)

-- (talking to it: the fake model of Proximity Comms' tools/devtest)
later(T + 11, function()
    s:RestartBrain()
    waitFor(function() return AG.owner ~= nil end, 40, function()
        out("brain", G.tostring(AG.owner), "status", G.ProxComms.status(), "agents", G.tostring(AG.agents[s.chatty.id] ~= nil))
        CL.say("Gummy, follow me!", "s")
        later(0.6, function() out("after the line", where()) end)
        waitFor(function() return s.components.follower:GetLeader() ~= nil end, 30, function()
            out("following", where())
            -- (its bubble follows it: the client finds it from its line's prefab - the user, 2026-11-05)
            out("CHECK bubble follows it", CL.entity("agent:" .. s.chatty.id .. ":" .. AG.shard()) == s,
                "host", G.tostring(s.chatty and G.require("chattyslime/agent").hostId()))
            later(0.3, function() out("SHOT slime_talk") end)
            later(4, function()
                -- (the player walks off: it hops after)
                local x, z = D.ahead(10, 0)
                G.ThePlayer.Physics:Teleport(x, 0, z)
                later(1.2, function() out("hopping", where()) out("SHOT slime_hop") end)
                later(7, function()
                    out("caught up", where())
                    CL.say("Gummy, dance for me!", "s")
                    waitFor(function() return s.sg:HasStateTag("busy") end, 20, function()
                        out("dancing?", where())
                        later(0.5, function() out("SHOT slime_dance_call") end)
                        later(5, function()
                            -- (a fight: a spider by them; asked to attack it)
                            local x, z = D.ahead(3, 3)
                            local spider = G.SpawnPrefab("spider")
                            spider.Transform:SetPosition(x, 0, z)
                            CL.say("Gummy, attack the spider!", "s")
                            waitFor(function() return s.components.combat.target == spider end, 20, function()
                                out("fighting?", G.tostring(s.components.combat.target), where())
                                waitFor(function() return s.sg:HasStateTag("attack") end, 15, function()
                                    later(0.36, function() out("SHOT slime_fight") end)
                                end)
                            end)
                            waitFor(function() return not spider:IsValid() or spider.components.health:IsDead() end, 40, function()
                                out("spider", spider:IsValid() and spider.components.health:IsDead() and "dead" or
                                    (spider:IsValid() and ("alive " .. G.tostring(spider.components.health.currenthealth)) or "gone"),
                                    "slime health", G.tostring(s.components.health.currenthealth), where())
                                fightDone()
                            end)
                        end)
                        fightDone = function()
                            for i = 1, 8 do
                                local m = G.ChatHistory:GetChatMessageAtIndex(i)
                                if m then out("history", G.tostring(m.sender), "|", G.tostring(m.message)) end
                            end
                            s.components.health:Kill()
                            later(0.9, function() out("death", where()) out("SHOT slime_death") end)
                            later(5, function()
                                out("after death", s:IsValid(), "agent", G.tostring(AG.agents[s.chatty.id] ~= nil))
                                out("DONE")
                            end)
                        end
                    end)
                end)
            end)
        end)
    end)
end)
