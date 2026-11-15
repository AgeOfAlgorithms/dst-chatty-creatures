-- Offline tests of the chatty creatures' core (chattycore/core.lua) through a mod's own agent.lua, against a mocked
-- game and a mocked Proximity Comms (API 2). Each mod's tools/test_<mod>.lua runs this with its name:
--   cd chattyslime && luajit tools/test_chattyslime.lua
-- What this cannot show: the brain's behaviours, the stategraph and the animation in the game, Proximity Comms itself.
local MOD = assert(CHATTY_MOD, "run through a mod's tools/test_<mod>.lua")
local CORE = CHATTY_CORE or "../chattycore/core.lua"
package.path = "./scripts/?.lua;" .. package.path

local pass, fail = 0, 0
local function check(name, ok)
    if ok then pass = pass + 1 else fail = fail + 1 print("FAIL " .. name) end
end

-- ---- the mocked game
local now = 100
function GetTime() return now end
local ENTS = {}
local tasks, later = {}, {}
local function entity(o)
    local e = {prefab = o.prefab, name = o.name, x = o.x or 0, z = o.z or 0, tags = o.tags or {}, pushed = {},
        userid = o.userid, listeners = {}, watch = {}}
    e.hpv, e.deadv = o.hp or 1, o.dead or false
    e.Transform = {GetWorldPosition = function() return e.x, 0, e.z end}
    function e:IsValid() return not self.removed end
    function e:Remove() self.removed = true end
    function e:HasTag(t) return self.tags[t] == true end
    function e:AddTag(t) self.tags[t] = true end
    function e:GetDistanceSqToPoint(px, _, pz) return (self.x - px) ^ 2 + (self.z - pz) ^ 2 end
    function e:IsNear(o2, r) return (o2.x - self.x) ^ 2 + (o2.z - self.z) ^ 2 <= r * r end
    function e:GetDisplayName() return self.display or self.name or self.prefab end
    function e:PushEvent(ev, d) self.pushed[#self.pushed + 1] = {e = ev, d = d} end
    function e:GetPosition() return {x = self.x, z = self.z, Get = function() return self.x, 0, self.z end} end
    function e:ListenForEvent(ev, fn, src) local t = (src or self).listeners t[ev] = t[ev] or {} table.insert(t[ev], fn) end
    function e:WatchWorldState(k, fn) self.watch[k] = fn end
    function e:DoPeriodicTask(dt, fn) tasks[#tasks + 1] = {dt = dt, fn = fn, inst = e} end
    function e:DoTaskInTime(dt, fn) later[#later + 1] = {t = now + dt, fn = fn} end
    e.components = {
        health = {GetPercent = function() return e.hpv end, IsDead = function() return e.deadv end,
            DoDelta = function(_, n) e.healed = (e.healed or 0) + n end},
        combat = {SetTarget = function(self, t) self.target = t end, DropTarget = function(self) self.target = nil end,
            CanTarget = function() return true end},
    }
    ENTS[#ENTS + 1] = e
    return e
end
local function fire(e, ev, data) for _, fn in ipairs(e.listeners[ev] or {}) do fn(e, data) end end
local function hasEvent(e, name) for _, p in ipairs(e.pushed) do if p.e == name then return p end end end

local function player(name, uid, x, z)
    return entity({prefab = "wilson", name = name, userid = uid, x = x, z = z, tags = {player = true}})
end
AllPlayers = {player("Wilson", "KU_1", 0, 2), player("Wendy", "KU_2", 0, 60), player("Wes", "KU_3", 3, 0)}
local wilson, wendy, wes = AllPlayers[1], AllPlayers[2], AllPlayers[3]
TheWorld = entity({prefab = "forest"})
TheWorld.ismastersim = true
TheWorld.state = {cycles = 4, isday = false, isdusk = true, isnight = false, season = "autumn"}
TheSim = {FindEntities = function(_, x, _, z, r, must, cant)
    local out = {}
    for _, e in ipairs(ENTS) do
        local ok = e:IsValid() and (e.x - x) ^ 2 + (e.z - z) ^ 2 <= r * r and e ~= TheWorld
        for _, t in ipairs(must or {}) do if not e.tags[t] then ok = false end end
        for _, t in ipairs(cant or {}) do if e.tags[t] then ok = false end end
        if ok then out[#out + 1] = e end
    end
    return out
end}
function FindEntity(inst, r, fn, must, cant)
    local x, _, z = inst.Transform:GetWorldPosition()
    for _, e in ipairs(TheSim:FindEntities(x, 0, z, r, must, cant)) do
        if e ~= inst and (not fn or fn(e)) then return e end
    end
end
local hosted, clients = true, {{userid = "KU_1", performance = {}}, {userid = "KU_2"}, {userid = "KU_3", admin = true}}
TheNet = {
    GetServerIsClientHosted = function() return hosted end,
    GetClientTable = function() return clients end,
    GetClientTableForUser = function(_, uid) for _, c in ipairs(clients) do if c.userid == uid then return c end end end,
    GetUserID = function() return "KU_1" end,
}

-- ---- the mocked Proximity Comms (API 2)
local P = {version = 2, defs = {}, said = {}, events = {}, notes = {}, state = "ready", scoring = false}
function P.agent(id, def) P.defs[id] = def return true end
function P.say(id, text) P.said[#P.said + 1] = text return true end
function P.event(id, text) P.events[#P.events + 1] = text return true end
function P.note(id, text) if text == nil then P.notes = {} else P.notes[#P.notes + 1] = text end return true end
function P.noted() return #P.notes end
function P.status() return P.state end
function P.scores() return P.scoring end
ProxComms = P

local cfg = require(MOD .. "/config")
local A = require(MOD .. "/agent")
local TAG = A.TAG

local function creature(x, z, name)
    local c = entity({prefab = TAG, x = x or 0, z = z or 0, tags = {}})
    c.leader = nil
    c.components.follower = {SetLeader = function(_, p) c.leader = p end, GetLeader = function() return c.leader end}
    c.components.knownlocations = {RememberLocation = function(_, k, v) c.home = v end, GetLocation = function() return c.home end}
    A.init(c)
    c.chatty.id, c.chatty.name = TAG .. "." .. tostring(#ENTS), name or "Blub"
    return c
end
local function foe(prefab, name, x, z)
    return entity({prefab = prefab, name = name, x = x, z = z, tags = {_combat = true, _health = true, monster = true}})
end
local function runLater()
    for i = #later, 1, -1 do if now >= later[i].t then local l = table.remove(later, i) l.fn() end end
end

-- ---- the core is the same in both mods
do
    local function read(p) local f = io.open(p, "rb") if not f then return nil end local s = f:read("*a") f:close() return s end
    local mine, src = read("scripts/" .. MOD .. "/core.lua"), read(CORE)
    check("core.lua: this mod's copy is chattycore's (python chattycore/sync.py)", mine ~= nil and mine == src)
end

-- ---- names, players, the host
check("named: whole word, any case", A.named("hey BLUB, come here", "Blub"))
check("named: not inside a word", not A.named("blubber", "Blub"))
check("findPlayer: exact", A.findPlayer("wendy", AllPlayers) == wendy)
check("findPlayer: the only one it starts with", A.findPlayer("wil", AllPlayers) == wilson)
check("findPlayer: two start with it: none", A.findPlayer("we", AllPlayers) == nil)
check("host: the client-hosted server's (its client entry has performance)", A.hostId() == "KU_1" and A.isHost("KU_1"))
check("host: nobody else, never an agent", not A.isHost("KU_3") and not A.isHost("agent:x:1"))
hosted = false
check("dedicated server: its admins", A.hostId() == nil and A.isHost("KU_3") and not A.isHost("KU_1"))
hosted = true

-- ---- its mind, its definition
local s = creature(0, 0, A.NAMES[1])
local NAME = s.chatty.name
local ID = s.chatty.id
check("init: a chatty creature (both mods' tag)", s:HasTag("chattycreature") and s.chatty.kind ~= nil)
check("init: hears what is said near it, watches the world", s.listeners.attacked and TheWorld.listeners.proxcomms_said
    and s.watch.phase and s.watch.israining and #tasks >= 3)
check("define", A.define(s) and P.defs[ID].name == NAME and P.defs[ID].hears == "engaged" and P.defs[ID].criteria == nil)
local d = P.defs[ID]
check("define: persona: its name, the owner rule, fight or flee", d.persona:find("You are " .. NAME, 1, true)
    and d.persona:find("only your owner may tell you to attack", 1, true) and d.persona:find("run_away", 1, true))
check("define: persona: words alone do nothing (the user: it said it did what it didn't)",
    d.persona:find("Words alone do nothing", 1, true) and d.persona:find("never say you are doing", 1, true))
check("define: persona: never \"host\" (the user: owner or friend)", d.persona:find('Never say "host"', 1, true))
check("define: it hears other creatures (the user: 10 lines in a row)", d.hearagents == 10)
local names = {}
for _, f in ipairs(d.functions) do names[f.name] = true end
check("define: its functions", names.follow and names.stay and names.come and names.attack and names.run_away
    and names.calm_down and names.relay and names.quiet and names.emote and names.eat and #d.functions <= 16)
for _, f in ipairs(d.functions) do
    check("define: no \"host\" in " .. f.name, not f.description:lower():find("host", 1, true))
end
P.scoring = true
A.define(s)
d = P.defs[ID]
check("scores: hears everything near, judged on its criteria", d.hears == "near" and #d.criteria == 5
    and d.criteria[1].name == "topic" and d.criteria[1].description:find(NAME, 1, true) and type(d.onScores) == "function")
cfg.chatter = 0
A.define(s)
check("chatter off: it hears no creatures", P.defs[ID].hearagents == nil)
cfg.chatter = 10
P.scoring = false

-- ---- calls
check("follow", A.onCall(s, {name = "follow", args = {player = "Wilson"}, from = {"KU_1"}}):find("^ok") and s.leader == wilson)
check("follow: too far", A.onCall(s, {name = "follow", args = {player = "Wendy"}}):find("too far"))
check("follow: no name: the speaker", A.onCall(s, {name = "follow", args = {}, from = {"KU_3"}}) and s.leader == wes)
check("come", A.onCall(s, {name = "come", args = {player = "Wilson"}}):find("^ok") and s.chatty.come.p == wilson)
check("stay", A.onCall(s, {name = "stay", args = {}}):find("^ok") and s.leader == nil and s.chatty.stay and not s.chatty.come)
check("emote", A.onCall(s, {name = "emote", args = {feeling = "dance"}}) == "ok" and hasEvent(s, TAG .. "_emote"))
check("emote: unknown", A.onCall(s, {name = "emote", args = {feeling = "explode"}}):find("^error"))
-- (eat: food on the ground - the user, 2026-11-06: it said it ate the berries there and didn't)
local function food(prefab, name, x, z, n)
    local f = entity({prefab = prefab, name = name, x = x, z = z})
    f.components.edible = {foodtype = "VEGGIE"}
    f.components.inventoryitem = {IsHeld = function() return f.held == true end}
    if n then
        f.components.stackable = {StackSize = function() return n end,
            Get = function() n = n - 1 return entity({prefab = prefab, name = name}) end}
        f.stack = function() return n end
    end
    function f:Remove() self.removed = true end
    return f
end
local function told(text)
    for _, t in ipairs(P.notes) do if t:find(text, 1, true) then return true end end
    for _, t in ipairs(P.events) do if t:find(text, 1, true) then return true end end
    for _, e in pairs(s.chatty.pendingEv) do if e.text:find(text, 1, true) then return true end end
end
local berries = food("berries", "Berries", 5, 0, 3)
local carrot = food("carrot", "Carrot", 3, 0)
local rocks = food("rocks", "Rocks", 2, 0)
rocks.components.edible.foodtype = "ELEMENTAL"
check("eat: what it is called (one or many)", A.onCall(s, {name = "eat", args = {food = "a berry"}}):find("^ok")
    and s.chatty.eat.item == berries)
check("eat: any food: the nearest (never rocks)", A.onCall(s, {name = "eat", args = {}}):find("Carrot", 1, true))
check("eat: none such", A.onCall(s, {name = "eat", args = {food = "meat"}}):find("^error: there is no meat"))
check("eat: not what a player holds", (function() carrot.held = true local r = A.onCall(s, {name = "eat",
    args = {food = "carrot"}}) carrot.held = false return r:find("^error") end)())
A.onCall(s, {name = "eat", args = {food = "berries"}})
check("eat: in what it knows", A.state(s):find("You are going to eat the Berries", 1, true))
s.pushed, P.notes, P.events = {}, {}, {}
A.eatTick(s)
check("eat: not there yet", s.chatty.eat ~= nil and A.eatGoal(s) == berries)
berries.x = 1
A.eatTick(s)
check("eat: there: one of the stack, eats, heals, its AI is told", s.chatty.eat == nil and berries:IsValid()
    and berries.stack() == 2 and hasEvent(s, TAG .. "_emote") and s.healed == 10 and told("You eat the Berries"))
-- (food it can't walk to: floating, or in a pond - the user, 2026-11-06: Gilbert stood stuck at a pond's edge)
local seeds = food("seeds", "Seeds", 4, 4)
seeds.components.floater = {IsFloating = function() return true end}
check("eat: not floating food", A.onCall(s, {name = "eat", args = {food = "seeds"}}):find("^error"))
seeds.components.floater = nil
local pond = entity({prefab = "pond", x = 4, z = 4.5, tags = {pond = true}})
pond.Physics = {GetRadius = function() return 2 end}
check("eat: not food in a pond", A.onCall(s, {name = "eat", args = {food = "seeds"}}):find("^error"))
pond.removed = true
A.onCall(s, {name = "eat", args = {food = "seeds"}})
s.chatty.eat.progT = now - A.EAT_STUCK - 1
s.chatty.eat.bestD = 1
A.eatTick(s)
check("eat: no closer for a while: it gives up, its AI is told", s.chatty.eat == nil and told("can't get to the Seeds"))
seeds.removed = true
A.onCall(s, {name = "eat", args = {food = "carrot"}})
carrot.held = true
A.eatTick(s)
check("eat: taken before it got there: it gives up, its AI is told", s.chatty.eat == nil and told("is gone"))
A.onCall(s, {name = "eat", args = {food = "berries"}})
check("eat: another order ends it", A.onCall(s, {name = "stay", args = {}}) and s.chatty.eat == nil)
berries.removed, carrot.removed, rocks.removed = true, true, true
s.chatty.pendingEv, s.chatty.noteText, P.notes, P.events = {}, nil, {}, {}
local spider = foe("spider", "Spider", 4, 0)
foe("spider", "Spider", 9, 0)
check("attack: the host orders it", A.onCall(s, {name = "attack", args = {target = "spider"}, from = {"KU_1"}}):find("^ok")
    and s.components.combat.target == spider)
s.components.combat.target = nil
check("attack: anyone else may not (the user: host only)",
    A.onCall(s, {name = "attack", args = {target = "spider"}, from = {"KU_3"}}):find("only Wilson")
    and s.components.combat.target == nil)
check("attack: the host with someone else: no", A.onCall(s, {name = "attack", args = {target = "spider"},
    from = {"KU_1", "KU_3"}}):find("^error"))
check("attack: another creature asking: no", A.onCall(s, {name = "attack", args = {target = "spider"},
    from = {"agent:x:1"}}):find("^error"))
s.components.combat.target = nil
check("attack: the host, with another creature's chatter in the turn: yes (seen in game)", A.onCall(s, {name = "attack",
    args = {target = "spider"}, from = {"KU_1", "agent:x:1"}}):find("^ok") and s.components.combat.target == spider)
-- (already fighting it on the host's order: no "fight or flee?" for it)
spider.components.combat.target = s
P.events = {}
A.dangerTick(s)
check("danger: already fighting it: nothing to ask", #P.events == 0 and s.chatty.danger.chose == "fight")
spider.components.combat.target = nil
s.chatty.danger = nil
s.components.combat.target = nil
check("attack: none here", A.onCall(s, {name = "attack", args = {target = "dragonfly"}, from = {"KU_1"}}):find("no dragonfly"))
s.hpv = 0.2
check("attack: too hurt", A.onCall(s, {name = "attack", args = {target = "spider"}, from = {"KU_1"}}):find("too hurt"))
s.hpv = 1
check("unknown function", A.onCall(s, {name = "fly", args = {}}):find("^error"))

-- ---- fight or flee: its AI decides (danger events); on its own when the AI is off, it is badly hurt, or too slow
spider.components.combat.target = s
P.events = {}
A.dangerTick(s)
check("danger: something attacks it: its AI is told at once", #P.events == 1 and P.events[1]:find("Spider is attacking you")
    and P.events[1]:find("Fight it", 1, true))
check("danger: nothing automatic while its AI decides", not A.auto(s) and A.retarget(s) == nil)
check("danger: in what it knows", A.state(s):find("Danger: Spider is attacking you", 1, true))
check("danger: defending itself needs no host", A.onCall(s, {name = "attack", args = {target = "it"}, from = {"KU_3"}}):find("^ok")
    and s.components.combat.target == spider and s.chatty.danger.chose == "fight")
s.components.combat.target = nil
check("run_away: from the danger", A.onCall(s, {name = "run_away", args = {from = "danger"}}):find("flee from Spider")
    and A.fleeFrom(s) == spider and s.components.combat.target == nil)
check("calm_down", A.onCall(s, {name = "calm_down", args = {}}):find("^ok") and A.fleeFrom(s) == nil)
-- (a new danger its AI doesn't answer in time: on its own)
s.chatty.danger = nil
P.events = {}
A.dangerTick(s)
now = now + A.DECIDE + 1
A.dangerTick(s)
check("danger: no answer in time: it acts on its own", A.auto(s) and A.retarget(s) == spider)
now = now + A.AUTO_FOR + 1
check("then its AI decides again", not A.auto(s))
-- (an answer without a call: its choice - nothing automatic)
s.chatty.danger = nil
A.dangerTick(s)
P.defs[ID].onReply("Eek! Go away!", {from = {}})
now = now + A.DECIDE + 1
A.dangerTick(s)
check("danger: it answered (no call): its choice, nothing automatic", not A.auto(s))
P.state = "off"
check("no AI: on its own, it fights back", A.auto(s) and A.retarget(s) == spider)
s.components.combat.target = nil
fire(s, "attacked", {attacker = spider})
check("no AI: hit, it fights back", s.components.combat.target == spider)
P.state = "ready"
s.hpv = 0.2
check("badly hurt: on its own, it flees from the danger", A.auto(s) and A.retarget(s) == nil and A.fleeFrom(s) == spider)
s.hpv = 1
spider.components.combat.target = nil
s.chatty.danger, s.chatty.autoUntil = nil, nil
s.components.combat.target = nil
-- (its leader in danger)
s.leader = wilson
spider.components.combat.target = wilson
P.events = {}
A.dangerTick(s)
check("danger: its leader attacked: told", #P.events == 1 and P.events[1]:find("attacking Wilson", 1, true))
spider.components.combat.target = nil
s.chatty.danger = nil

-- ---- events: a note for the next line; nobody talks - one event line; urgent ones at once
P.events, P.notes = {}, {}
A.event(s, "fed", "Wilson gives you Berries and you eat them")
check("event: a note first", #P.notes == 1 and P.notes[1]:find("Berries") and #P.events == 0)
A.event(s, "fed", "Wilson gives you Carrot and you eat it")
check("event: the newest of a kind, counted", #P.notes == 1 and P.notes[1]:find("Carrot") and P.notes[1]:find("2 times"))
P.notes = {}                                    -- (a line took it)
A.flush(s)
check("event: a line took it: gone", next(s.chatty.pendingEv) == nil and s.chatty.noteText == nil)
A.event(s, "killed", "You beat Spider.")
now = now + A.EVENT_AFTER_TALK + A.EVENT_EVERY + 1
A.flush(s)
check("event: nobody talked: one event line, the note taken back", #P.events == 1 and P.events[1]:find("You beat Spider")
    and #P.notes == 0)
P.events = {}
P.defs[ID].onReply("Blub!", {from = {"KU_1"}})
A.event(s, "world", "Dusk is falling.")
now = now + A.EVENT_EVERY + 1
A.flush(s)
check("event: not within a while of its own line", #P.events == 0 and #P.notes == 1)
A.event(s, "relay", "You reached Wes")
check("event: urgent ones at once (and the others with them)", #P.events == 1 and P.events[1]:find("Dusk")
    and P.events[1]:find("You reached Wes"))
P.state = "off"
P.events, P.notes = {}, {}
A.event(s, "fed", "x")
check("event: no AI: nobody to tell", #P.events == 0 and #P.notes == 0)
P.state = "ready"
-- (Proximity Comms API 1: no taking notes back)
P.version = 2
local noted = P.noted
P.noted = nil
A.event(s, "fed", "old api")
check("API 1: notes at once", #P.notes == 1)
P.noted = noted
P.notes = {}

-- ---- the judge (scores)
local function judge(scores, from, text)
    return A.onScores(s, scores, {turn = 1, from = from or {"KU_3"}, text = text or {"Wes: hello"}})
end
s.chatty.lineT, s.chatty.talkedWith = {}, {}
s.pushed = {}
check("judge: it is the topic: it answers", judge({topic = 0.95}) == true and hasEvent(s, TAG .. "_think"))
check("judge: not about it: skip", judge({topic = 0.1, interest = 0.2}) == false)
check("judge: its name in the line counts", judge({topic = 0.5}, {"KU_3"}, {"Wes: " .. NAME .. " look"}) == true)
s.chatty.listener = nil
check("judge: skipped but interesting: it looks at them", judge({topic = 0.3, wellbeing = 0.1}) == false
    and s.chatty.listener == wes)
s.chatty.talkedWith.KU_3 = now
check("judge: talking with them counts", judge({topic = 0.6}) == true)
s.chatty.talkedWith = {}
check("judge: close (4 m) and its leader count", s.leader == wilson and judge({topic = 0.55}, {"KU_1"}, {"Wilson: hm"}) == true)
check("judge: another creature: no player bonus", judge({topic = 0.6}, {"agent:x:1"}, {"Gus: hm"}) == false)
s.chatty.lineT = {now - 1, now - 2, now - 3}
local ok, sc, who, why = A.judge(s, {topic = 0.95}, {from = {"KU_3"}, text = {"Wes: hi"}})
check("judge: pacing - it just said a lot", ok == false and why == "pace")
s.chatty.lineT = {}
s.chatty.talkedWith.KU_3 = now
check("judge: a goodbye: no answer, the talk with them over", judge({topic = 0.9, ended = 0.8}) == false
    and s.chatty.talkedWith.KU_3 == nil)
check("judge: quiet: whisper mode", judge({topic = 0.95, quiet = 0.6}) == true and s.chatty.quiet
    and P.defs[ID].mode == "whisper")
check("judge: very quiet: only when spoken to", judge({topic = 0.5, interest = 1, quiet = 0.9}) == false)
check("quiet off (its AI)", A.onCall(s, {name = "quiet", args = {on = false}}):find("normal voice") and not s.chatty.quiet
    and P.defs[ID].mode == "speak")

-- ---- relay
local other = creature(20, 0, "Gilbert")
check("relay: to a player", A.onCall(s, {name = "relay", args = {to = "Wes", message = "dinner is ready"}, from = {"KU_1"}})
    :find("^ok") and s.chatty.relay and s.chatty.relay.fromName == "Wilson")
check("relay: in what it knows", A.state(s):find('from Wilson to Wes: "dinner is ready"', 1, true))
P.events = {}
A.relayTick(s)
check("relay: there: it tells them (urgent)", #P.events == 1 and P.events[1]:find("reached Wes") and not s.chatty.relay
    and #s.chatty.relays == 0)
check("relay: to another creature", A.onCall(s, {name = "relay", args = {to = "gilbert", message = "hi"}, from = {"KU_1"}})
    :find("Gilbert"))
check("relay: nobody by that name", A.onCall(s, {name = "relay", args = {to = "Maxwell", message = "x"}}):find("^error"))
P.events, P.notes = {}, {}
A.relayTick(s)
now = now + A.RELAY_STUCK + 1
A.relayTick(s)
check("relay: no closer for a while: it gives up for now, keeps it", not s.chatty.relay and #s.chatty.relays == 1
    and s.chatty.relays[1].waiting)
other.x = 10
A.relayTick(s)
check("relay: in sight again: off it goes", s.chatty.relay ~= nil)
s.chatty.relay, s.chatty.relays = nil, {}

-- ---- what it knows
s.chatty.stay = true
local st = A.state(s)
check("state: the day", st:find("Day 5, dusk, autumn", 1, true))
check("state: its owner (never \"host\")", st:find("Wilson is your owner: only Wilson may tell you to attack", 1, true)
    and not st:lower():find("host", 1, true))
check("state: its health", st:find("100%", 1, true))
check("state: players near, not far", st:find("Wes (3 m)", 1, true) and not st:find("Wendy"))
check("state: other creatures", st:find("Gilbert (a ", 1, true))

-- ---- lines near it
s.leader = nil
s.pushed = {}
A.onSaid(s, {userid = "KU_3", text = "nice weather", x = 3, z = 0, range = 72})
check("said: not named: nothing", #s.pushed == 0)
A.onSaid(s, {userid = "KU_3", text = NAME .. ", hello", x = 3, z = 0, range = 72})
check("said: named: thinks", hasEvent(s, TAG .. "_think") and s.chatty.listener == wes)
s.pushed = {}
P.scoring = true
A.onSaid(s, {userid = "KU_3", text = NAME .. ", hello", x = 3, z = 0, range = 72})
check("said: with scores the judge decides (no think yet)", #s.pushed == 0)
P.scoring = false
-- (its AI on: the plainest orders said with its name are done at once, whatever its AI answers)
s.leader, s.chatty.stay = nil, nil
A.onSaid(s, {userid = "KU_1", text = NAME .. ", follow me!", x = 0, z = 2, range = 72})
check("said: AI on, \"follow me\": it follows at once (it can't just say it does)", s.leader == wilson)
A.onSaid(s, {userid = "KU_1", text = NAME .. ", stay here.", x = 0, z = 2, range = 72})
check("said: AI on, \"stay here\"", s.leader == nil and s.chatty.stay)
A.onSaid(s, {userid = "KU_1", text = NAME .. ", come here", x = 0, z = 2, range = 72})
check("said: AI on, \"come here\"", s.chatty.come and s.chatty.come.p == wilson)
s.chatty.come = nil
A.onSaid(s, {userid = "KU_1", text = NAME .. ", don't follow me", x = 0, z = 2, range = 72})
check("said: a negated order: left to its AI", s.leader == nil)
A.onSaid(s, {userid = "KU_1", text = "follow me", x = 0, z = 2, range = 72})
check("said: an order without its name: left to its AI", s.leader == nil)
s.chatty.stay, s.pushed = nil, {}
-- (no AI: plain commands said with its name)
P.state = "off"
P.said = {}
s.chatty.scriptedT = nil
A.onSaid(s, {userid = "KU_1", text = NAME .. ", follow me!", x = 0, z = 2, range = 72})
check("no AI: a plain command, done, a noise", s.leader == wilson and P.said[1] == A.F.OK_NOISE)
now = now + 5
P.said = {}
A.onSaid(s, {userid = "KU_1", text = "hi " .. NAME, x = 0, z = 2, range = 72})
check("no AI: anything else: a noise", #P.said == 1)
P.state = "ready"

-- ---- greetings, boredom, its leader, the world
P.events = {}
s.chatty.greeted = {}
A.greet(s)
check("greet: a player near, once", #P.events == 1 and P.events[1]:find("comes up to you", 1, true))
P.events = {}
s.chatty.danger = nil
s.chatty.happenT, s.chatty.boredT = now - A.BORED_AFTER - 1, now - A.BORED_AFTER - 1
A.boredTick(s)
check("bored: nothing happened for a while, someone near: its AI may start a talk", #P.events == 1
    and P.events[1]:find("You are bored") and s.chatty.bored)
A.boredTick(s)
check("bored: not again at once", #P.events == 1)
P.events = {}
s.leader = wilson
wilson.tags.playerghost = true
A.leaderTick(s)
check("its leader died: told at once", #P.events == 1 and P.events[1]:find("Wilson died"))
wilson.tags.playerghost = nil
P.events, P.notes = {}, {}
s.watch.phase(s, "night")
check("the world: night falls (a player near): a note", #P.notes == 1 and P.notes[1]:find("Night has come"))
P.notes = {}
s.chatty.pendingEv, s.chatty.noteText = {}, nil
local far = creature(500, 500, "Far")
far.watch.israining(far, true)
check("the world: nobody near: nothing", #P.notes == 0)

-- ---- death: a goodbye, then its agent goes
P.events = {}
s.deadv = true
fire(s, "death")
check("death: its AI says goodbye", P.events[#P.events]:find("a very short goodbye") and P.defs[ID].hears == "none")
later = {}
A.onRemove(s)
check("death: its agent waits for the goodbye", P.defs[ID] ~= nil and #later == 1)
now = now + A.BYE_WAIT + 1
runLater()
check("death: then it goes", P.defs[ID] == nil)
local s2 = creature(0, 0, "Pip")
A.define(s2)
s2.chatty.dead = true
P.defs[s2.chatty.id].onReply("Bye...", {from = {}})
A.onRemove(s2)
check("death: goodbye said: it goes at once", P.defs[s2.chatty.id] == nil)

-- ---- without Proximity Comms
ProxComms = nil
check("no Proximity Comms: define is a no", A.define(other) == false)
check("no Proximity Comms: not live, acting on its own", not A.live() and A.auto(other))

print(("%s: %d passed, %d failed"):format(MOD, pass, fail))
os.exit(fail == 0 and 0 or 1)
