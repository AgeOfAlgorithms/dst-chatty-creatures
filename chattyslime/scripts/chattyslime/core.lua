-- THE CHATTY CREATURES' MIND (shared by the Chatty Slime and the Chatty Salamander - the user, 2026-11-05: "plan the
-- port" of Mochi the Corgi's features, Teardown, to the DST creatures). This file is dst-mods/chattycore/core.lua:
-- chattycore/sync.py copies it into each mod as scripts/<mod>/core.lua (DST mods share one require namespace - each
-- mod loads its own copy, never the other's, whichever versions a server runs). Edit it here, never in a mod.
--
-- require("<mod>/core")(F) -> the creature's agent module, for its flavour F (scripts/<mod>/agent.lua): who it is
-- (persona, names, noises), how it moves and fights (the brain's numbers), its config. Server only, but for M.Brain.
--
-- WHAT IT DOES (Proximity Comms agent API 2 - GLOBAL.ProxComms; API 1 still works, with less):
-- - JUDGE: with a Koetama that scores (ProxComms.scores()), it hears everything near it (hears "near") and each turn is
--   scored on CRITERIA; M.judge weighs the scores with what the game knows (its name in the line, it talked with them,
--   close, its leader, the host) and answers at RUBRIC.answerAt; pacing (its own recent lines) keeps it from chattering;
--   "ended" (goodbyes) - no answer; "quiet" - whisper mode until its AI calls quiet off. Without: cfg.hears as before.
-- - FIGHT OR FLEE (the user, 2026-11-05): "flee automatically but let the AI decide whether to fight or flee". With its
--   AI on and fit (health >= HURT), nothing is automatic: a danger (something attacking it, its leader or a player
--   near, or going for them) is an urgent event, and its AI calls attack or run_away (or nothing). No call within
--   DECIDE s while the danger lasts: automatic for AUTO_FOR s. Automatic (no AI, badly hurt, or that): it fights what
--   attacks it or its leader, and flees when badly hurt (a fearful one - the slime - from monsters too).
-- - ATTACKS: only the host orders one (the user, 2026-11-05: "host only for now") - every speaker a call answers must
--   be the host (a dedicated server: an admin); fighting back a danger it was told of is its own choice.
-- - EVENTS: what happens to it waits as a note for the next line said to it; nobody talks within EVENT_EVERY s: one
--   event line (at most every EVENT_EVERY s, not within EVENT_AFTER_TALK s of its own line); urgent ones at once.
-- - RELAY: "go tell Wendy the base is on fire" - it runs to them (a player or another creature) and tells them.
-- - BORED, GREETINGS, NIGHT AND DAY, RAIN, SEASONS, FULL MOON, ITS LEADER DYING: events for its AI.
-- - OTHER CREATURES: it hears them (hearagents = cfg.chatter, the user: on by default, 10 lines in a row).
-- - DEATH: a goodbye (its AI), then its agent goes.
-- - WITHOUT THE AI: plain commands said with its name ("Blub, follow me", "stay", "come", "stop") work, with a noise.
-- - A CREATURE'S OWN POWERS (F, all optional): F.functions (more functions for its AI), F.powers(name) (what they do,
--   for its persona), F.onCall(inst, call, M) (a call of one: its result, or nil for the core's), F.onAttacked(inst,
--   data, M) (before the core's), F.state(inst, M) (a line more of what it knows, or nil).

return function(F)

local M = {}
local cfg = F.cfg
M.F = F
M.TAG = F.tag                                         -- (its prefab's tag; its events are "<tag>_talk", ...)
M.NAMES, M.EMOTES, M.SCRIPTED = F.NAMES, F.EMOTES, F.SCRIPTED
M.CREATURE_TAG = "chattycreature"                     -- (every chatty creature, of either mod: they know each other)

M.ENGAGED = 30          -- s it keeps listening to a player after its name ("engaged", without scores)
M.GREET_EVERY = 600     -- s a player is greeted at most this often
M.GREET_NEAR = 6
M.HURT = 0.3            -- under this share of its health: badly hurt (no fighting; it flees on its own)
M.DECIDE = 6            -- s its AI has to choose fight or flight before it acts on its own
M.AUTO_FOR = 30         -- s it then acts on its own
M.DANGER_NEAR = 12      -- m a danger is seen within (to it, its leader, a player near it)
M.FLEE_FOR = 12         -- s a run_away lasts (unless hurt again)
M.EVENT_EVERY = 4       -- s events wait for a line to carry them, and between event lines
M.EVENT_AFTER_TALK = 10 -- s after its own line before an event goes as a line of its own (not urgent ones)
M.BORED_AFTER = 90      -- s with nothing happening: bored (the user, Mochi: 90)
M.BORED_NEAR = 25
M.WORLD_NEAR = 20       -- m a player must be within for the world's events (dusk, rain, ...) to matter
M.RELAY_MAX, M.RELAY_LIFE, M.RELAY_STUCK = 4, 900, 12   -- messages carried at most; s kept; s without getting closer
M.RELAY_AT = 4          -- m: there (it tells them)
M.BYE_WAIT = 12         -- s its agent waits for its goodbye after it died
M.FOOD_NEAR = 15        -- m food on the ground is seen within (eat)
M.EAT_AT, M.EAT_FOR = 1.6, 20   -- m: there (it eats); s it tries to get there
M.EAT_STUCK = 4         -- s without getting closer: it can't reach it

-- the rubric (Mochi's, the user 2026-11-04; "looking at him" has no DST counterpart - its leader instead)
M.RUBRIC = {
    weights = {topic = 1.0, interest = 0.5, wellbeing = 0.8},
    named = 0.5,                -- its name in the lines
    talking = 0.3, talkFor = 30,-- it talked with them in the last talkFor s
    close = 0.15, closeAt = 4,  -- the speaker within m
    leader = 0.2,               -- the player it follows
    host = 0.1,
    answerAt = 0.9,
    perkAt = 0.35,              -- skipped, but it looks at them
    endedAt = 0.6,              -- the talk with it ended: no answer
    quietAt = 0.5,              -- quiet mode on
    silentAt = 0.85, topicAt = 0.8,   -- ... and from here it answers only when spoken to directly
    pace = 0.25, paceFor = 20,  -- each of its own lines in the last paceFor s after the first
}
M.CRITERIA_NAMES = {"topic", "interest", "wellbeing", "ended", "quiet"}

local function now() return GetTime() end
local function C(inst) return inst.chatty end
local function ev(name) return M.TAG .. "_" .. name end

function M.api()
    local p = rawget(_G, "ProxComms")
    if type(p) == "table" and type(p.agent) == "function" then return p end
end
local function v2() local P = M.api() return P and (tonumber(P.version) or 1) >= 2 and P or nil end

-- whether its language model is there to answer
function M.live()
    local P = M.api()
    local s = P and P.status and P.status()
    return s == "ready" or s == "busy"
end

function M.scoring()
    local P = v2()
    return P ~= nil and type(P.scores) == "function" and P.scores() == true
end

-- ---------------------------------------------------------------------------------------------------- who and what

-- the host's userid: a client-hosted server's (its client entry has "performance"); nil on a dedicated server
function M.hostId()
    if not (TheNet and TheNet.GetServerIsClientHosted and TheNet:GetServerIsClientHosted()) then return nil end
    for _, c in ipairs(TheNet:GetClientTable() or {}) do
        if c.performance ~= nil and c.userid and c.userid ~= "" then return c.userid end
    end
    local id = TheNet.GetUserID and TheNet:GetUserID()
    return id ~= "" and id or nil
end

-- may this speaker order an attack: the host (a dedicated server has none: its admins)
function M.isHost(uid)
    if type(uid) ~= "string" or uid:sub(1, 6) == "agent:" then return false end
    local h = M.hostId()
    if h then return uid == h end
    local c = TheNet and TheNet.GetClientTableForUser and TheNet:GetClientTableForUser(uid)
    return c ~= nil and c.admin == true
end

local function hostName()
    local h = M.hostId()
    for _, p in ipairs(AllPlayers) do if p.userid == h then return p.name end end
end

local function playersOn()
    local out = {}
    for _, p in ipairs(AllPlayers) do if p:IsValid() then out[#out + 1] = p end end
    return out
end

local function byUserid(uid)
    for _, p in ipairs(AllPlayers) do if p.userid == uid then return p end end
end

local function alive(p)
    return p ~= nil and p:IsValid() and not p:HasTag("playerghost")
        and not (p.components.health and p.components.health:IsDead())
end

-- a player by name: exact (any case), else the only one it starts with
function M.findPlayer(name, players)
    if type(name) ~= "string" or name == "" then return nil end
    local n = name:lower()
    local starts
    for _, p in ipairs(players) do
        local pn = (p.name or ""):lower()
        if pn == n then return p end
        if pn:sub(1, #n) == n then
            if starts then starts = false elseif starts == nil then starts = p end
        end
    end
    return starts or nil
end

-- a whole-word, any-case match of its name in a line (as Proximity Comms has it)
function M.named(text, name)
    local t, n = " " .. tostring(text):lower() .. " ", tostring(name):lower()
    local i = 1
    while n ~= "" do
        local a, b = t:find(n, i, true)
        if not a then return false end
        if not t:sub(a - 1, a - 1):find("[%w]") and not t:sub(b + 1, b + 1):find("[%w]") then return true end
        i = a + 1
    end
    return false
end

-- another chatty creature (either mod's) by name, the nearest (never itself)
function M.findCreature(inst, name)
    if type(name) ~= "string" or name == "" then return nil end
    local n = name:lower()
    local x, y, z = inst.Transform:GetWorldPosition()
    local best, bd
    for _, e in ipairs(TheSim:FindEntities(x, y, z, 200, {M.CREATURE_TAG})) do
        if e ~= inst and e.chatty and e.chatty.name and e.chatty.name:lower() == n
            and not (e.components.health and e.components.health:IsDead()) then
            local d = e:GetDistanceSqToPoint(x, y, z)
            if not bd or d < bd then best, bd = e, d end
        end
    end
    return best
end

-- a creature near it by what it is called (a part of its name either way: "spider", "the spiders"), the nearest;
-- never a player, a chatty creature or a companion
local FIGHT_MUST = {"_combat", "_health"}
local FIGHT_NOT = {"player", "playerghost", "companion", M.CREATURE_TAG, "INLIMBO", "wall", "structure"}
M.FIGHT_MUST, M.FIGHT_NOT = FIGHT_MUST, FIGHT_NOT
function M.findFoe(inst, term)
    term = tostring(term or ""):lower():gsub("^%s+", ""):gsub("%s+$", ""):gsub("^the ", "")
    if term == "" then return nil end
    local c = C(inst)
    if (term == "it" or term == "that" or term == "danger" or term == "them") and c.danger and c.danger.ent:IsValid() then
        return c.danger.ent
    end
    local x, y, z = inst.Transform:GetWorldPosition()
    local best, bd
    for _, e in ipairs(TheSim:FindEntities(x, y, z, 15, FIGHT_MUST, FIGHT_NOT)) do
        local name = (e:GetDisplayName() or ""):lower()
        local prefab = (e.prefab or ""):lower()
        local hp = e.components.health
        local match = (name ~= "" and (name:find(term, 1, true) or term:find(name, 1, true)))
            or (prefab ~= "" and (prefab:find(term, 1, true) or term:find(prefab, 1, true)))
        if e ~= inst and hp and not hp:IsDead() and match then
            local d = e:GetDistanceSqToPoint(x, y, z)
            if not bd or d < bd then best, bd = e, d end
        end
    end
    return best
end

-- food lying on the ground near it, by what it is called ("berries", "a carrot"; nothing or "food": any), the nearest
-- (the user, 2026-11-06: it said it ate the berries on the ground without doing it - it had no function for it)
local FOOD_NOT = {"INLIMBO", "FX", "NOCLICK", "DECOR", "player", "fire"}
local NOT_FOOD = {ELEMENTAL = true, GEARS = true, WOOD = true, BURNT = true}
local ANY_FOOD = {[""] = true, food = true, it = true, them = true, something = true, anything = true, that = true}
local function singular(s) return (s:gsub("ies$", "y"):gsub("oes$", "o"):gsub("s$", "")) end

-- can it walk to food lying there: not floating, not in the ocean, not inside a pond (the user, 2026-11-06: Gilbert
-- went for seeds floating in a pond and stood stuck at its edge)
function M.reachable(e)
    if e.components.floater and e.components.floater:IsFloating() then return false end
    local x, y, z = e.Transform:GetWorldPosition()
    local map = TheWorld.Map
    if map and map.IsPassableAtPoint and not map:IsPassableAtPoint(x, 0, z) then return false end
    for _, pond in ipairs(TheSim:FindEntities(x, y, z, 6, {"pond"})) do
        local r = (pond.Physics and pond.Physics:GetRadius() or 2) + 0.3
        if pond:GetDistanceSqToPoint(x, y, z) < r * r then return false end
    end
    return true
end
function M.findFood(inst, term)
    term = tostring(term or ""):lower():gsub("^%s+", ""):gsub("%s+$", ""):gsub("^the ", ""):gsub("^some ", "")
        :gsub("^an? ", "")
    local any, want = ANY_FOOD[term], singular(term)
    local x, y, z = inst.Transform:GetWorldPosition()
    local best, bd
    for _, e in ipairs(TheSim:FindEntities(x, y, z, M.FOOD_NEAR, nil, FOOD_NOT)) do
        local ed, item = e.components.edible, e.components.inventoryitem
        if ed and item and not item:IsHeld() and not NOT_FOOD[ed.foodtype or ""] and M.reachable(e) then
            local name = singular((e:GetDisplayName() or ""):lower())
            local prefab = singular((e.prefab or ""):lower())
            if any or (name ~= "" and (name:find(want, 1, true) or want:find(name, 1, true)))
                or (prefab ~= "" and (prefab:find(want, 1, true) or want:find(prefab, 1, true))) then
                local d = e:GetDistanceSqToPoint(x, y, z)
                if not bd or d < bd then best, bd = e, d end
            end
        end
    end
    return best
end

local function nameOf(e)
    if not (e and e:IsValid()) then return "something" end
    if e:HasTag("player") then return e.name or "someone" end
    if e.chatty and e.chatty.name then return e.chatty.name end
    local n = e:GetDisplayName()
    return (n and n ~= "" and not n:find("MISSING NAME")) and n or (e.prefab or "something")
end
M.nameOf = nameOf

local function phase()
    local s = TheWorld.state
    return (s.isday and "day") or (s.isdusk and "dusk") or (s.isnight and "night") or "day"
end

local function metres(d) return math.floor(d + 0.5) end
local function hp(inst) return inst.components.health:GetPercent() end
local function dead(inst) return not inst:IsValid() or inst.components.health:IsDead() end

-- ---------------------------------------------------------------------------------------------------- the persona

-- (the creature's own part: F.persona(name); then what every chatty creature knows of its powers)
function M.persona(name)
    return F.persona(name) .. "\n\n" .. ([[What you can do - your functions. Words alone do nothing in the world: whenever you agree to do something, call its function in that same reply, and never say you are doing, or did, something without calling its function. When a function's result is an error, tell them honestly that you couldn't. When there is no function for what they ask (you can't pick things up, carry, give, build, open, light or craft anything), say you can't.
- follow (a player, when they ask you along), stay (when told to stay or wait), come (to a player who calls you), eat (food lying on the ground near you), emote (show how you feel - often: it is how you move).
- Danger: the game tells you when something attacks you, your friends or a player near you. Then YOU choose: fight it (attack, with what it is called, or "it" for the danger you were told of) or flee (run_away from it), or neither. If you are badly hurt you flee on your own. calm_down stops fighting or fleeing.
- Attacks ordered by players: only your owner may tell you to attack something (your owner is named in what you know). If anyone else asks you to attack, refuse kindly. You never attack a player.
- Call players by their names, or "friend"; your owner by name, or "friend" or "owner". Never say "host", "admin" or "server".
- Messages: when someone asks you to go tell another player (or another creature) something, call relay with who and the message. The game tells you when you reach them: then say it to them in your own words and say who it is from.
- Quiet: when everyone must be quiet (a monster that hears, sneaking, someone asleep, "shh"), call quiet with on true: then whisper a few soft words at most. When it is fine to talk again, call quiet with on false.
- When the game says you are bored, start a little conversation with someone near you, or show how you feel. Don't repeat yourself.
- Other creatures like you may live here (in what you know): you hear them and they hear you; answer them as a friend, briefly, and let the talk end.
- If you are dying, say a very short goodbye.
If a line was clearly not meant for you and isn't about you, reply with nothing at all (an empty reply). Lines in [brackets] are things that happen around you, not speech. Keep it friendly; never break character, never mention being an AI.]])
        .. (F.powers and ("\n" .. F.powers(name)) or "")
end

-- what its turns are scored on (with a Koetama that scores): Mochi's criteria, in its words
function M.criteria(name)
    local who = ("%s (%s)"):format(name, F.aliases)
    return {
        {name = "topic", description = who .. " is the topic: someone talks to " .. F.pronoun .. " or about " ..
            F.pronoun .. ", gives " .. F.pronoun .. " a command, asks something, or goes on with a conversation with " ..
            F.pronoun},
        {name = "interest", description = "the topic is something " .. name .. " loves: " .. F.loves},
        {name = "wellbeing", description = "it is about the safety or well-being of " .. name ..
            " or the people near: danger, monsters, someone hurt or in trouble, a call for help, fire, hunger, the dark"},
        {name = "ended", description = "the conversation with " .. name ..
            " just ended: goodbyes, thanks that close it, 'that's all', 'go away', 'not now'"},
        {name = "quiet", description = "everyone needs to be quiet now: a monster nearby that hears, sneaking, " ..
            "hiding, someone sleeping, 'shh', 'be quiet', whispering"},
    }
end

M.FUNCTIONS = {
    {name = "follow", description = "Go along with a player: " .. F.followVerb .. " wherever they go.",
        parameters = {type = "object", properties = {player = {type = "string", description = "the player's name"}},
            required = {"player"}}},
    {name = "stay", description = "Stop following anyone and stay around here.",
        parameters = {type = "object", properties = {}}},
    {name = "come", description = "Go to a player who calls you and stop next to them.",
        parameters = {type = "object", properties = {player = {type = "string", description = "the player's name"}},
            required = {"player"}}},
    {name = "eat", description = "Go to food lying on the ground near you (berries, carrots, seeds...) and eat it. " ..
        "Not food in a bush or a player's hands (they give that to you).",
        parameters = {type = "object", properties = {food = {type = "string",
            description = "what to eat, as it is called around you; empty: any food near you"}}}},
    {name = "attack", description = "Fight a creature near you (never a player): when it is a danger to you or your " ..
        "friends, or your owner tells you to.",
        parameters = {type = "object", properties = {target = {type = "string",
            description = "what to attack, as it is called around you, or \"it\" for the danger you were told of"}},
            required = {"target"}}},
    {name = "run_away", description = "Flee from a danger, scared: from a creature, or \"danger\" for the one you " ..
        "were told of.",
        parameters = {type = "object", properties = {from = {type = "string", description = "what to flee from"}}}},
    {name = "calm_down", description = "Stop fighting or fleeing and calm down.",
        parameters = {type = "object", properties = {}}},
    {name = "relay", description = "Carry a message to someone (a player or another creature): go to them and tell " ..
        "them, when someone asks you to go tell or let them know something.",
        parameters = {type = "object", properties = {to = {type = "string", description = "who to tell"},
            message = {type = "string", description = "the message, in the speaker's words"}}, required = {"to", "message"}}},
    {name = "quiet", description = "Quiet mode on or off: on, you only whisper (danger that hears, someone asleep); " ..
        "off, your normal voice again.",
        parameters = {type = "object", properties = {on = {type = "boolean"}}, required = {"on"}}},
    {name = "emote", description = "Show a feeling with your whole body.",
        parameters = {type = "object", properties = {feeling = {type = "string", enum = M.EMOTES}},
            required = {"feeling"}}},
}

for _, f in ipairs(F.functions or {}) do M.FUNCTIONS[#M.FUNCTIONS + 1] = f end

-- ---------------------------------------------------------------------------------------------------- what it knows

local LOOK_NOT = {"INLIMBO", "FX", "NOCLICK", "DECOR", "player", M.CREATURE_TAG}

-- what it knows now (sent with every line it hears; up to 2 KB)
function M.state(inst)
    if not inst:IsValid() then return nil end
    local c = C(inst)
    local s = TheWorld.state
    local out = {("Day %d, %s, %s%s%s."):format((s.cycles or 0) + 1, phase(), s.season or "autumn",
        s.israining and ", raining" or "", s.isfullmoon and ", full moon" or "")}
    local hn = hostName()
    if hn then out[#out + 1] = ("%s is your owner: only %s may tell you to attack."):format(hn, hn) end
    if c.dead then
        out[#out + 1] = "You are dying."
        return table.concat(out, " ")
    end
    local h = hp(inst)
    out[#out + 1] = ("Your health: %d%%%s."):format(math.floor(h * 100 + 0.5), h < M.HURT and " (badly hurt)" or "")
    local leader = inst.components.follower and inst.components.follower:GetLeader()
    if leader and leader:HasTag("player") then
        out[#out + 1] = "You are following " .. (leader.name or "a player") .. "."
    elseif c.stay then
        out[#out + 1] = "You are staying here."
    end
    if c.come and c.come.p:IsValid() then out[#out + 1] = "You are going to " .. nameOf(c.come.p) .. "." end
    if c.eat and c.eat.item:IsValid() then out[#out + 1] = "You are going to eat the " .. nameOf(c.eat.item) .. "." end
    if c.flee then out[#out + 1] = "You are fleeing from " .. nameOf(c.flee.from) .. ", scared." end
    local foe = inst.components.combat and inst.components.combat.target
    if foe and foe:IsValid() then out[#out + 1] = "You are fighting " .. nameOf(foe) .. "." end
    if c.danger and c.danger.ent:IsValid() and not c.flee and foe ~= c.danger.ent then
        out[#out + 1] = "Danger: " .. c.danger.text .. "."
    end
    if c.quiet then out[#out + 1] = "You are in quiet mode: whisper a few words at most; call quiet off when it's fine." end
    if F.state then
        local more = F.state(inst, M)
        if more then out[#out + 1] = more end
    end
    if c.bored then out[#out + 1] = "You are bored: nothing has happened for a while." end
    for _, r in ipairs(c.relays) do
        out[#out + 1] = ('You carry a message from %s to %s: "%s".'):format(r.fromName, r.toName, r.msg)
    end
    local x, y, z = inst.Transform:GetWorldPosition()
    local players = {}
    for _, p in ipairs(AllPlayers) do
        if p:IsValid() and p ~= leader then
            local d = math.sqrt(p:GetDistanceSqToPoint(x, y, z))
            if d < 20 then
                players[#players + 1] = ("%s (%d m%s)"):format(p.name or "?", metres(d), p:HasTag("playerghost") and ", a ghost" or "")
            end
        end
    end
    if #players > 0 then out[#out + 1] = "Players near: " .. table.concat(players, ", ") .. "." end
    local friends = {}
    for _, e in ipairs(TheSim:FindEntities(x, y, z, 30, {M.CREATURE_TAG})) do
        if e ~= inst and e.chatty and e.chatty.name and not (e.components.health and e.components.health:IsDead())
            and #friends < 6 then
            friends[#friends + 1] = ("%s (a %s, %d m)"):format(e.chatty.name, e.chatty.kind or "creature",
                metres(math.sqrt(e:GetDistanceSqToPoint(x, y, z))))
        end
    end
    if #friends > 0 then out[#out + 1] = "Creatures like you near: " .. table.concat(friends, ", ") .. "." end
    local seen, things = {}, {}
    for _, e in ipairs(TheSim:FindEntities(x, y, z, 12, nil, LOOK_NOT)) do
        local name = e.prefab and e:GetDisplayName()
        if name and name ~= "" and not name:find("MISSING NAME") and not seen[name] and #things < 8 then
            seen[name] = true
            local scary = (e:HasTag("monster") or e:HasTag("hostile")) and " (scary!)" or ""
            things[#things + 1] = name .. scary
        end
    end
    if #things > 0 then out[#out + 1] = "Around you: " .. table.concat(things, ", ") .. "." end
    return table.concat(out, " ")
end

-- ---------------------------------------------------------------------------------------------------- events

-- something happened to it, for its AI: gathered (the newest of each kind, repeats counted) as a note for the next
-- line said to it; urgent: at once. Not while its AI is off (nobody to tell)
local URGENT = {danger = true, bored = true, relay = true, greet = true, dying = true, leader = true}
function M.event(inst, kind, text)
    local c = C(inst)
    if not (c and M.live() and c.id and not c.gone) then return end
    if kind ~= "bored" and kind ~= "world" then M.happened(inst) end
    local P = c.pendingEv
    if next(P) == nil then c.evFirstT = now() end
    if P[kind] then P[kind].text, P[kind].n = text, P[kind].n + 1
    else
        c.evOrder = c.evOrder + 1
        P[kind] = {text = text, n = 1, order = c.evOrder}
    end
    if URGENT[kind] then c.evUrgent = true end
    M.flush(inst)
end

-- the waiting events as one text, in the order they happened
function M.pendingText(inst)
    local list = {}
    for _, e in pairs(C(inst).pendingEv) do list[#list + 1] = e end
    table.sort(list, function(a, b) return a.order < b.order end)
    local parts = {}
    for _, e in ipairs(list) do
        parts[#parts + 1] = "[" .. e.text .. (e.n > 1 and (" (%d times just now)"):format(e.n) or "") .. "]"
    end
    return table.concat(parts, " ")
end

-- (now and then) the gathered events: still a note, or one event line of their own when it is time
function M.flush(inst)
    local c = C(inst)
    local P = M.api()
    if not (P and c.id) then return end
    local t = now()
    local P2 = v2()
    if P2 and type(P2.noted) == "function" then
        if c.noteText and P2.noted(c.id) == 0 then            -- (a line took them: they went)
            c.pendingEv, c.noteText = {}, nil
        end
        if next(c.pendingEv) == nil then return end
        local text = M.pendingText(inst)
        local lastLine = c.lineT[#c.lineT] or -1e9
        if c.evUrgent or (t - c.evFirstT >= M.EVENT_EVERY and t - c.evFlushT >= M.EVENT_EVERY
            and t - lastLine >= M.EVENT_AFTER_TALK) then
            P2.note(c.id, nil)
            P2.event(c.id, text)
            c.pendingEv, c.noteText, c.evUrgent, c.evFlushT = {}, nil, false, t
        elseif text ~= c.noteText then
            P2.note(c.id, nil)
            P2.note(c.id, text)
            c.noteText = text
        end
        return
    end
    -- (Proximity Comms API 1: no taking a note back - urgent ones as events, the others as notes, at once)
    local text = M.pendingText(inst)
    if c.evUrgent then P.event(c.id, text) else P.note(c.id, text) end
    c.pendingEv, c.evUrgent = {}, false
end

-- something happened with it (not bored any more)
function M.happened(inst)
    local c = C(inst)
    c.happenT = now()
    c.bored = false
end

-- ---------------------------------------------------------------------------------------------------- the agent

-- (server) this creature into Proximity Comms, with what it is now (again every few seconds: only a change goes)
function M.define(inst)
    local P = M.api()
    local c = C(inst)
    if not P or not c or not c.id or c.gone then return false end
    local scoring = M.scoring()
    local def = {
        persona = M.persona(c.name),
        name = c.name,
        entity = inst,
        hears = c.dead and "none" or (scoring and "near" or (cfg.hears == "near" and "near" or "engaged")),
        mode = c.quiet and "whisper" or "speak",
        functions = M.FUNCTIONS,
        max_words = 40,
        state = function() return M.state(inst) end,
        onCall = function(call) return M.onCall(inst, call) end,
        onReply = function(text, info) M.onReply(inst, text, info) end,
        onError = function(code) M.onError(inst, code) end,
    }
    if scoring then
        def.criteria = M.criteria(c.name)
        def.onScores = function(scores, info) return M.onScores(inst, scores, info) end
    end
    local chatter = tonumber(cfg.chatter) or 0
    if chatter > 0 then def.hearagents = chatter end
    return P.agent(c.id, def)
end

function M.remove(inst)
    local P = M.api()
    local c = C(inst)
    if P and c and c.id then P.agent(c.id, nil) end
    if c then c.gone = true end
end

-- its line was said: it talks (as long as it takes to read), and it is talking with those it answered
function M.onReply(inst, text, info)
    local c = C(inst)
    if not c then return end
    local t = now()
    c.lineT[#c.lineT + 1] = t
    while #c.lineT > 8 do table.remove(c.lineT, 1) end
    local answered = false
    for _, uid in ipairs(info and info.from or {}) do
        c.talkedWith[uid] = t
        answered = true
    end
    if answered then M.happened(inst) end
    if c.dead then c.byeSaid = true end
    -- (it answered after it was told of a danger: whatever it chose - a call, or neither - is its choice, nothing
    --  automatic; only no answer at all in time makes it act on its own)
    if c.danger and c.danger.asked and not c.danger.chose and t >= c.danger.asked then c.danger.chose = "spoke" end
    if inst:IsValid() then
        c.listener = nil
        inst:PushEvent(ev("talk"), {time = M.talkTime(text)})
    end
end

function M.onError(inst, code)
    -- (the admin's month is spent, or the model failed: a noise instead of silence)
    if inst:IsValid() and (code == "budget" or code == "failed" or code == "queue_full") then M.scripted(inst) end
end

-- talking takes about as long as reading it
function M.talkTime(text)
    local words = 0
    for _ in tostring(text):gmatch("%S+") do words = words + 1 end
    -- (Chinese and Japanese have no spaces: count their characters, three bytes each)
    words = math.max(words, math.floor(#tostring(text) / 9))
    return math.max(1.2, math.min(8, 0.6 + words * 0.3))
end

-- a line without the model
function M.scripted(inst, line)
    local P = M.api()
    local c = C(inst)
    if not P or not inst:IsValid() or not c.id then return end
    local t = now()
    if c.scriptedT and t - c.scriptedT < 4 then return end
    c.scriptedT = t
    line = line or M.SCRIPTED[math.random(#M.SCRIPTED)]
    P.say(c.id, line)
    inst:PushEvent(ev("talk"), {time = M.talkTime(line)})
end

-- ---------------------------------------------------------------------------------------------------- the judge

-- (a scored turn) the model's scores and who said it -> answer?, the score, the best speaker, why it skips, quiet?
function M.judge(inst, scores, info)
    local c = C(inst)
    local R = M.RUBRIC
    local base = 0
    for k, w in pairs(R.weights) do base = base + (tonumber(scores[k]) or 0) * w end
    local text = table.concat(info.text or {}, "\n")
    local named = M.named(text, c.name) and R.named or 0
    local ended = (tonumber(scores.ended) or 0) >= R.endedAt
    local quiet = tonumber(scores.quiet) or 0
    local t = now()
    local x, y, z = inst.Transform:GetWorldPosition()
    local leader = inst.components.follower and inst.components.follower:GetLeader()
    local best, who = base + named, nil
    for _, uid in ipairs(info.from or {}) do
        local sc = base + named
        if c.talkedWith[uid] and t - c.talkedWith[uid] < R.talkFor then sc = sc + R.talking end
        local p = byUserid(uid)                         -- (another creature: only the scores and its name count)
        if p then
            if p:GetDistanceSqToPoint(x, y, z) <= R.closeAt * R.closeAt then sc = sc + R.close end
            if p == leader then sc = sc + R.leader end
            if M.isHost(uid) then sc = sc + R.host end
        end
        if who == nil or sc > best then best, who = sc, uid end
    end
    local recent = 0
    for _, s in ipairs(c.lineT) do if t - s < R.paceFor then recent = recent + 1 end end
    local unpaced = best >= R.answerAt
    best = best - math.max(0, recent - 1) * R.pace
    local answer = best >= R.answerAt
    local why
    if unpaced and not answer then why = "pace" end
    if ended then answer, why = false, "ended"
    elseif quiet >= R.silentAt and (tonumber(scores.topic) or 0) < R.topicAt then answer, why = false, "silent" end
    return answer, best, who, why, quiet >= R.quietAt
end

-- (Proximity Comms: a scored turn) judged and decided at once
function M.onScores(inst, scores, info)
    local c = C(inst)
    if not c or dead(inst) then return false end
    local answer, score, who, why, quiet = M.judge(inst, scores, info)
    if quiet then M.setQuiet(inst, true) end              -- (before the reply: it comes as a whisper)
    c.judged = {turn = info.turn, answer = answer, score = score, who = who, why = why, scores = scores}
    local p = who and byUserid(who)
    if why == "ended" then
        for _, uid in ipairs(info.from or {}) do c.talkedWith[uid] = nil end
        if (scores.topic or 0) >= 0.5 and p then         -- (a goodbye to it: a look and a little emote)
            c.listener = p
            inst:PushEvent(ev("emote"), {emote = "happy"})
        end
    elseif answer and p then
        c.listener = p
        inst:PushEvent(ev("think"), {target = p})
    elseif score >= M.RUBRIC.perkAt and p then
        c.listener = p                                  -- (not for it, but it caught its ear: it looks at them)
    end
    return answer
end

-- quiet mode: it whispers (the agent's mode, at once) until its AI calls quiet off
function M.setQuiet(inst, on)
    local c = C(inst)
    on = on ~= false
    if c.quiet == on then return end
    c.quiet = on
    M.define(inst)
end

-- ---------------------------------------------------------------------------------------------------- fight or flee

-- acting on its own: no AI, badly hurt, or its AI didn't choose in time
function M.auto(inst)
    local c = C(inst)
    return not M.live() or hp(inst) < M.HURT or (c ~= nil and c.autoUntil ~= nil and now() < c.autoUntil)
end

-- what it flees from now (the brain's RunAway): its AI's choice, or when acting on its own and badly hurt, the danger
function M.fleeFrom(inst)
    local c = C(inst)
    if c.flee then
        if c.flee.from:IsValid() and now() < c.flee.untilT and not (c.flee.from.components.health
            and c.flee.from.components.health:IsDead()) then
            return c.flee.from
        end
        c.flee = nil
    end
    if hp(inst) < M.HURT and c.danger and c.danger.ent:IsValid() and now() - c.danger.t < 10 then return c.danger.ent end
    return nil
end

function M.startFlee(inst, from)
    local c = C(inst)
    c.flee = {from = from, untilT = now() + M.FLEE_FOR}
    if inst.components.combat then inst.components.combat:DropTarget() end
    c.come, c.eat = nil, nil
    inst:PushEvent(ev("wake"))
    inst:PushEvent(ev("emote"), {emote = "surprised"})
end

-- what is a danger now: something going for it, its leader or a player near it (the nearest)
function M.findDanger(inst)
    local x, y, z = inst.Transform:GetWorldPosition()
    local leader = inst.components.follower and inst.components.follower:GetLeader()
    local best, bd, victim
    for _, e in ipairs(TheSim:FindEntities(x, y, z, M.DANGER_NEAR, FIGHT_MUST, FIGHT_NOT)) do
        local t = e.components.combat and e.components.combat.target
        if t and t:IsValid() and not (e.components.health and e.components.health:IsDead())
            and (t == inst or t == leader or (t:HasTag("player") and t:IsNear(inst, M.DANGER_NEAR))) then
            local d = e:GetDistanceSqToPoint(x, y, z)
            if not bd or d < bd then best, bd, victim = e, d, t end
        end
    end
    return best, victim
end

local function dangerText(inst, foe, victim)
    local who = victim == inst and "you" or nameOf(victim)
    local d = metres(math.sqrt(foe:GetDistanceSqToPoint(inst.Transform:GetWorldPosition())))
    return ("%s is attacking %s (%d m from you)"):format(nameOf(foe), who, d)
end

-- (every half second, server) a new danger: its AI is told (urgent) and has M.DECIDE s to choose; acting on its own:
-- the brain and the combat's retarget do it
function M.dangerTick(inst)
    local c = C(inst)
    if dead(inst) then return end
    local foe, victim = M.findDanger(inst)
    local t = now()
    if not foe then
        if c.danger and t - c.danger.t > 15 then c.danger = nil end
        return
    end
    if c.danger and c.danger.ent == foe then
        c.danger.t = t
        -- (its AI didn't choose in time: on its own for a while)
        if c.danger.asked and not c.danger.chose and t - c.danger.asked >= M.DECIDE and not M.auto(inst) then
            c.autoUntil = t + M.AUTO_FOR
            c.danger.chose = "auto"
        end
        return
    end
    c.danger = {ent = foe, victim = victim, t = t, text = dangerText(inst, foe, victim)}
    -- (already fighting it - the host's order, its own choice: nothing to ask)
    if inst.components.combat and inst.components.combat.target == foe then c.danger.chose = "fight" return end
    if not M.auto(inst) then
        c.danger.asked = t
        M.event(inst, "danger", c.danger.text .. "! Fight it (attack) or flee (run_away)?")
    end
end

-- (the prefab's attacked event) what hit it
function M.onAttacked(inst, data)
    if F.onAttacked then F.onAttacked(inst, data, M) end
    local c = C(inst)
    local who = data and data.attacker
    local t = now()
    if who and who:IsValid() and who:HasTag("player") and inst.components.follower:GetLeader() == who then
        inst.components.follower:SetLeader(nil)       -- (its friend hit it: no longer)
    end
    if who and who:IsValid() and not who:HasTag("player") and who.components.combat then
        if M.auto(inst) and hp(inst) >= M.HURT then inst.components.combat:SetTarget(who) end
        if not (c.danger and c.danger.ent == who) then
            c.danger = {ent = who, victim = inst, t = t, text = nameOf(who) .. " is attacking you"}
            if inst.components.combat.target == who then
                c.danger.chose = "fight"                  -- (already fighting it: nothing to ask)
            elseif not M.auto(inst) then
                c.danger.asked = t
                M.event(inst, "danger", nameOf(who) .. " hits you! Fight it (attack) or flee (run_away)?")
                return
            end
        end
        c.danger.t = t
        if c.flee and c.flee.from == who then c.flee.untilT = t + M.FLEE_FOR end
    end
    if c.hurtAt and t - c.hurtAt < 6 then return end
    c.hurtAt = t
    M.event(inst, "hurt", nameOf(who) .. " hits you! Ouch" .. (hp(inst) < M.HURT and " - you are badly hurt" or ""))
end

-- (the combat's retarget, acting on its own) whatever goes for it or its leader (never a player)
function M.retarget(inst)
    if dead(inst) or hp(inst) < M.HURT or not M.auto(inst) then return nil end
    if inst.sg and inst.sg:HasStateTag("sleeping") then return nil end
    local leader = inst.components.follower:GetLeader()
    return FindEntity(inst, 10, function(guy)
        local t = guy.components.combat and guy.components.combat.target
        return (t == inst or (leader ~= nil and t == leader)) and not guy.components.health:IsDead()
            and inst.components.combat:CanTarget(guy)
    end, FIGHT_MUST, FIGHT_NOT)
end

function M.keepTarget(inst, target)
    if not target:IsValid() or target:HasTag("player") or hp(inst) < M.HURT then return false end
    if target.components.health and target.components.health:IsDead() then return false end
    local leader = inst.components.follower:GetLeader()
    if leader then return leader:IsNear(target, 20) end
    local home = inst.components.knownlocations:GetLocation("home")
    return home == nil or target:GetDistanceSqToPoint(home:Get()) < 20 * 20
end

-- ---------------------------------------------------------------------------------------------------- relay

local function relayTarget(r)
    if r.to and r.to:IsValid() and not (r.to.components.health and r.to.components.health:IsDead()) then return r.to end
end

function M.relayGoal(inst)
    local c = C(inst)
    local r = c.relay
    return r and relayTarget(r) or nil
end

-- (every half second) carrying a message: there - it tells them; no closer for a while - it gives up for now and tells
-- them when it next sees them
function M.relayTick(inst)
    local c = C(inst)
    local t = now()
    for i = #c.relays, 1, -1 do
        local r = c.relays[i]
        if t - r.t0 > M.RELAY_LIFE or not relayTarget(r) then table.remove(c.relays, i) end
    end
    if dead(inst) then return end
    if not c.relay then                                 -- (one it gave up on: its person in sight again)
        for _, r in ipairs(c.relays) do
            if r.waiting and r.to:IsNear(inst, 25) then
                r.waiting = nil
                c.relay = r
                r.bestD, r.progT = nil, t
                break
            end
        end
        if not c.relay then return end
    end
    local r = c.relay
    local to = relayTarget(r)
    if not to then c.relay = nil return end
    local d = math.sqrt(to:GetDistanceSqToPoint(inst.Transform:GetWorldPosition()))
    if d <= M.RELAY_AT then
        c.relay = nil
        for i, x in ipairs(c.relays) do if x == r then table.remove(c.relays, i) break end end
        if M.live() then
            M.event(inst, "relay", ('You reached %s with %s\'s message: "%s". Tell %s now, in your own words, and say ' ..
                'it is from %s.'):format(r.toName, r.fromName, r.msg, r.toName, r.fromName))
        else
            M.scripted(inst, ("%s! %s says: %s"):format(r.toName, r.fromName, r.msg))
        end
        return
    end
    if not r.bestD or d < r.bestD - 1 then r.bestD, r.progT = d, t end
    if t - r.progT > M.RELAY_STUCK then
        c.relay = nil
        r.waiting = true
        M.event(inst, "relay_lost", ("You couldn't get to %s for now. You keep the message and tell them when you " ..
            "see them."):format(r.toName))
    end
end

-- ---------------------------------------------------------------------------------------------------- calls

-- who a call answers: the first player for "me"; and may it order an attack: every PLAYER it answers is the host (other
-- creatures' lines in the same turn don't count - seen in game: a slime's chatter in the host's turn blocked the
-- host's order; creatures never make it attack a player anyway)
local function speakers(call)
    local first, allHost, any = nil, true, false
    for _, uid in ipairs(call.from or {}) do
        if uid:sub(1, 6) ~= "agent:" then
            any = true
            first = first or uid
            if not M.isHost(uid) then allHost = false end
        end
    end
    return first, any and allHost
end

-- (a call) the model asks; the creature checks and does it, and says what happened
function M.onCall(inst, call)
    if dead(inst) then return "error: you can't now" end
    local c = C(inst)
    local args = call.args or {}
    local me, byHost = speakers(call)
    M.happened(inst)
    if F.onCall then
        local r = F.onCall(inst, call, M)
        if r ~= nil then return r end
    end
    if call.name == "follow" or call.name == "come" then
        local p = M.findPlayer(args.player, playersOn())
        if not p and me then p = byUserid(me) end
        if not p then return "error: there is no player by that name here" end
        if not inst:IsNear(p, 40) then return "error: " .. p.name .. " is too far away" end
        c.stay, c.flee, c.eat = nil, nil, nil
        inst:PushEvent(ev("wake"))
        if call.name == "follow" then
            c.come = nil
            inst.components.follower:SetLeader(p)
            return "ok: you are following " .. p.name
        end
        c.come = {p = p, untilT = now() + 20}
        return "ok: you go to " .. p.name
    elseif call.name == "stay" then
        inst.components.follower:SetLeader(nil)
        if inst.components.combat then inst.components.combat:DropTarget() end
        c.stay, c.come, c.flee, c.eat = true, nil, nil, nil
        inst.components.knownlocations:RememberLocation("home", inst:GetPosition())
        return "ok: you stay here"
    elseif call.name == "eat" then
        local e = M.findFood(inst, args.food)
        if not e then
            local what = tostring(args.food or "")
            return "error: there is no " .. (what ~= "" and what or "food") .. " on the ground near you"
        end
        c.eat, c.come = {item = e, name = nameOf(e), untilT = now() + M.EAT_FOR, progT = now()}, nil
        inst:PushEvent(ev("wake"))
        return "ok: you go and eat the " .. nameOf(e)
    elseif call.name == "attack" then
        if hp(inst) < M.HURT then return "error: you are too hurt to fight" end
        local e = M.findFoe(inst, args.target)
        if not e then return "error: there is no " .. tostring(args.target or "such creature") .. " near you" end
        -- (only the host orders an attack; fighting a danger it was told of is its own choice)
        local defending = c.danger and c.danger.ent == e and now() - c.danger.t < 15
        if not defending and not byHost then
            return "error: only " .. (hostName() or "your owner") .. " can tell you to attack - refuse kindly"
        end
        if c.danger and c.danger.ent == e then c.danger.chose = "fight" end
        c.flee, c.come, c.eat = nil, nil, nil
        inst:PushEvent(ev("wake"))
        inst.components.combat:SetTarget(e)
        return "ok: you go for the " .. nameOf(e)
    elseif call.name == "run_away" then
        local term = tostring(args.from or "danger")
        local e = M.findFoe(inst, term) or (c.danger and c.danger.ent:IsValid() and c.danger.ent) or nil
        if not e then return "error: there is nothing to flee from here" end
        if c.danger and c.danger.ent == e then c.danger.chose = "flee" end
        M.startFlee(inst, e)
        return "ok: you flee from " .. nameOf(e)
    elseif call.name == "calm_down" then
        if inst.components.combat then inst.components.combat:DropTarget() end
        c.flee, c.autoUntil = nil, nil
        if c.danger then c.danger.chose = "calm" end
        return "ok: you calm down"
    elseif call.name == "relay" then
        local msg = tostring(args.message or "")
        if msg == "" then return "error: what message?" end
        local to = M.findPlayer(args.to, playersOn()) or M.findCreature(inst, args.to)
        if not to then return "error: there is nobody called " .. tostring(args.to or "that") .. " here" end
        local from = me and byUserid(me)
        local r = {to = to, toName = nameOf(to), fromName = from and from.name or "someone", msg = msg:sub(1, 200),
            t0 = now(), progT = now()}
        if #c.relays >= M.RELAY_MAX then table.remove(c.relays, 1) end
        c.relays[#c.relays + 1] = r
        c.relay, c.stay, c.come, c.eat = r, nil, nil, nil
        inst:PushEvent(ev("wake"))
        return "ok: you go to " .. r.toName .. " with the message"
    elseif call.name == "quiet" then
        local on = args.on ~= false and args.on ~= "false"
        M.setQuiet(inst, on)
        return on and "ok: quiet mode on - whisper" or "ok: your normal voice again"
    elseif call.name == "emote" then
        local f = tostring(args.feeling or "")
        for _, e in ipairs(M.EMOTES) do
            if e == f then
                inst:PushEvent(ev("emote"), {emote = f})
                return "ok"
            end
        end
        return "error: no such feeling"
    end
    return "error: you can't do that"
end

-- ---------------------------------------------------------------------------------------------------- hearing

-- (without its AI) plain commands said with its name: done, with a noise
local KEYWORDS = {
    {"follow", "follow"}, {"come", "come"}, {"here", "come"}, {"stay", "stay"}, {"wait", "stay"}, {"stop", "calm_down"},
    {"calm", "calm_down"}, {"dance", "dance"},
}
function M.keywords(inst, p, text)
    local t = " " .. tostring(text):lower():gsub("[%p]", " ") .. " "
    for _, k in ipairs(KEYWORDS) do
        if t:find(" " .. k[1] .. " ", 1, true) then
            local r
            if k[2] == "dance" then
                inst:PushEvent(ev("emote"), {emote = "dance"})
                r = "ok"
            else
                r = M.onCall(inst, {name = k[2], args = {player = p.name}, from = {p.userid}})
            end
            M.scripted(inst, r:sub(1, 2) == "ok" and F.OK_NOISE or F.NO_NOISE)
            return true
        end
    end
    return false
end

-- (a line said near it: proxcomms_said) it looks at them and thinks - or, with no model, obeys plain commands
function M.onSaid(inst, data)
    local c = C(inst)
    if not c or dead(inst) or data.agent ~= nil or not data.userid then return end
    local p = byUserid(data.userid)
    if not p or not data.x or not data.z then return end
    local x, _, z = inst.Transform:GetWorldPosition()
    local r = (tonumber(data.range) or 18) + 1
    if (x - data.x) ^ 2 + (z - data.z) ^ 2 > r * r then return end
    local t = now()
    local named = M.named(data.text, c.name)
    if named then c.engaged[data.userid] = t end
    if named and M.live() then M.direct(inst, p, data.text) end
    if M.live() and M.scoring() then return end         -- (the judge decides: it looks and thinks then)
    local eng = c.engaged[data.userid]
    local hears = cfg.hears == "near" or named or (eng and t - eng <= M.ENGAGED)
    if not hears then return end
    c.listener = p
    inst:PushEvent(ev("wake"))
    if M.live() then
        inst:PushEvent(ev("think"), {target = p})
    elseif named then
        M.happened(inst)
        if not M.keywords(inst, p, data.text) then M.scripted(inst) end
    end
end

-- ---------------------------------------------------------------------------------------------------- now and then

-- (every 1.5 s) a player who comes near is greeted: an event for the model, which may answer
function M.greet(inst)
    local c = C(inst)
    if not cfg.greet or not M.live() or dead(inst) or c.danger then return end
    local t = now()
    for _, p in ipairs(AllPlayers) do
        if p:IsValid() and p.userid and inst:IsNear(p, M.GREET_NEAR) and not p:HasTag("playerghost") then
            local last = c.greeted[p.userid]
            if not last or t - last > M.GREET_EVERY then
                c.greeted[p.userid] = t
                M.event(inst, "greet", ("%s comes up to you."):format(p.name or "Someone"))
                return
            end
        end
    end
end

local function nearestPlayer(inst)
    local x, y, z = inst.Transform:GetWorldPosition()
    local best, bd
    for _, p in ipairs(AllPlayers) do
        if alive(p) then
            local d = p:GetDistanceSqToPoint(x, y, z)
            if not bd or d < bd then best, bd = p, d end
        end
    end
    return best, bd and math.sqrt(bd)
end

-- nothing has happened for a while, someone near: it may start a conversation (again only after another while)
function M.boredTick(inst)
    local c = C(inst)
    local t = now()
    if dead(inst) or c.danger or c.flee or c.relay or not M.live() then return end
    if t - math.max(c.happenT, c.boredT) < M.BORED_AFTER then return end
    c.boredT = t
    local p, d = nearestPlayer(inst)
    if not (p and d <= M.BORED_NEAR) then return end
    c.bored = true
    M.event(inst, "bored", ("Nothing has happened for a while (%d s). You are bored. %s is %d m from you.")
        :format(math.floor(t - c.happenT + 0.5), p.name or "Someone", metres(d)))
end

-- its leader died (a ghost now) or came back
function M.leaderTick(inst)
    local c = C(inst)
    local leader = inst.components.follower and inst.components.follower:GetLeader()
    local ghost = leader and leader:HasTag("playerghost") or false
    if leader and ghost ~= (c.leaderGhost or false) then
        if ghost then M.event(inst, "leader", (leader.name or "Your friend") .. " died! They are a ghost now.")
        else M.event(inst, "world", (leader.name or "Your friend") .. " is alive again!") end
    end
    c.leaderGhost = ghost
    if c.come then
        local p = c.come.p
        if not p:IsValid() or now() > c.come.untilT or p:IsNear(inst, 2.5) then c.come = nil end
    end
end

-- (every half second) going to eat food on the ground: there - it eats it (one of a stack); gone or out of reach -
-- it gives up and its AI is told
function M.eatGoal(inst)
    local e = C(inst).eat
    return e and e.item:IsValid() and e.item or nil
end

function M.eatTick(inst)
    local c = C(inst)
    local e = c.eat
    if not e then return end
    local item = e.item
    if dead(inst) then c.eat = nil return end
    if not item:IsValid() or item.components.inventoryitem:IsHeld() then
        c.eat = nil
        M.event(inst, "food", "The " .. e.name .. " is gone before you got to it.")
        return
    end
    if now() > e.untilT then
        c.eat = nil
        M.event(inst, "food", "You couldn't get to the " .. e.name .. ".")
        return
    end
    local d = math.sqrt(item:GetDistanceSqToPoint(inst.Transform:GetWorldPosition()))
    if not e.bestD or d < e.bestD - 0.3 then e.bestD, e.progT = d, now() end
    if d > M.EAT_AT and now() - e.progT > M.EAT_STUCK and not (inst.sg and inst.sg:HasStateTag("busy")) then
        c.eat = nil
        M.event(inst, "food", "You can't get to the " .. e.name .. " - something is in the way.")
        return
    end
    if d > M.EAT_AT or (inst.sg and inst.sg:HasStateTag("busy")) then return end
    c.eat = nil
    local st = item.components.stackable
    local one = st and st:StackSize() > 1 and st:Get(1) or item
    one:Remove()
    inst:PushEvent(ev("emote"), {emote = "eat"})
    if inst.components.health then inst.components.health:DoDelta(10) end
    M.event(inst, "fed", "You eat the " .. e.name .. " from the ground.")
end

-- (a line said with its name, its AI on) the plainest orders are done at once, whatever its AI answers - it can't
-- forget to call follow and still say it follows (the user, 2026-11-06: "it lies that it's performing some action")
local DIRECT = {
    {"follow me", "follow"}, {"follow us", "follow"}, {"come with me", "follow"}, {"come along", "follow"},
    {"come here", "come"}, {"come to me", "come"}, {"over here", "come"},
    {"stay here", "stay"}, {"stay put", "stay"}, {"wait here", "stay"},
}
local NEGATED = {"don t", "dont", "do not", "not", "never", "stop", "quit", "no longer", "no"}
function M.direct(inst, p, text)
    local t = " " .. tostring(text):lower():gsub("[%p]", " "):gsub("%s+", " ") .. " "
    for _, n in ipairs(NEGATED) do if t:find(" " .. n .. " ", 1, true) then return nil end end
    for _, k in ipairs(DIRECT) do
        if t:find(" " .. k[1] .. " ", 1, true) then
            return M.onCall(inst, {name = k[2], args = {player = p.name}, from = {p.userid}}), k[2]
        end
    end
    return nil
end

-- the world's events (a player near): dusk, night, day, rain, a full moon, a new season
function M.world(inst, text)
    local p, d = nearestPlayer(inst)
    if p and d <= M.WORLD_NEAR and not dead(inst) then M.event(inst, "world", text) end
end

local PHASES = {day = "The sun is up: a new day.", dusk = "Dusk is falling.", night = "Night has come: it is dark."}

-- ---------------------------------------------------------------------------------------------------- setup

-- (the prefab, server) its mind: state, events, ticks
function M.init(inst, kind)
    inst:AddTag(M.CREATURE_TAG)
    inst.chatty = inst.chatty or {}
    local c = inst.chatty
    c.kind = kind or F.kind
    c.engaged, c.greeted, c.talkedWith = {}, {}, {}
    c.lineT, c.relays = {}, {}
    c.pendingEv, c.evOrder, c.evFirstT, c.evFlushT = {}, 0, 0, -1e9
    c.happenT, c.boredT = now(), now()
    if not TheWorld.ismastersim then return end
    inst:ListenForEvent("attacked", function(_, data) M.onAttacked(inst, data) end)
    inst:ListenForEvent("killed", function(_, data)
        if data and data.victim then M.event(inst, "killed", "You beat " .. nameOf(data.victim) .. ".") end
    end)
    inst:ListenForEvent("death", function()
        c.dead = true
        if M.live() then
            M.define(inst)
            M.event(inst, "dying", "You are hurt too badly: you are dying. Say a very short goodbye.")
        end
    end)
    inst:ListenForEvent("proxcomms_said", function(_, data) M.onSaid(inst, data) end, TheWorld)
    inst:WatchWorldState("phase", function(_, ph) if PHASES[ph] then M.world(inst, PHASES[ph]) end end)
    inst:WatchWorldState("israining", function(_, on) M.world(inst, on and "It starts to rain." or "The rain stops.") end)
    inst:WatchWorldState("isfullmoon", function(_, on) if on then M.world(inst, "A full moon is up tonight.") end end)
    inst:WatchWorldState("season", function(_, s) M.world(inst, tostring(s):gsub("^%l", string.upper) .. " has come.") end)
    inst:DoPeriodicTask(0.5, function()
        if not inst:IsValid() then return end
        M.dangerTick(inst)
        M.relayTick(inst)
        M.eatTick(inst)
        M.leaderTick(inst)
        if next(c.pendingEv) ~= nil or c.noteText then M.flush(inst) end
    end, math.random() * 0.5)
    inst:DoPeriodicTask(1.5, function() M.greet(inst) M.boredTick(inst) end, math.random())
    -- (Proximity Comms forgets agents of a shard that restarted its brain, and whether it scores can change: who it
    -- is again every few seconds - only a definition that changed goes)
    inst:DoPeriodicTask(5, function() M.define(inst) end, 5)
end

-- (the prefab's OnRemoveEntity) its agent goes - after its goodbye, if it died talking
function M.onRemove(inst)
    local c = C(inst)
    if not c then return end
    if c.dead and not c.byeSaid and M.live() and not c.gone then
        local P, id = M.api(), c.id
        c.gone = true
        TheWorld:DoTaskInTime(M.BYE_WAIT, function() if P and id then P.agent(id, nil) end end)
        return
    end
    M.remove(inst)
end

-- ---------------------------------------------------------------------------------------------------- the brain

-- the creature's brain, with its numbers (F.brain): fleeing (its AI's choice, or badly hurt), fighting, a fearful one's
-- fear (acting on its own), a message to carry, going to someone, its leader, the one talking to it, home
function M.Brain()
    require "behaviours/follow"
    require "behaviours/wander"
    require "behaviours/faceentity"
    require "behaviours/runaway"
    require "behaviours/chaseandattack"
    local BrainCommon = require("brains/braincommon")
    local B = F.brain
    local SCARY = {"monster", "hostile"}
    local NOT_SCARY = {"player", "companion", "INLIMBO", M.CREATURE_TAG, "notarget"}

    local function leaderOf(inst) return inst.components.follower and inst.components.follower:GetLeader() end
    local function faceTarget(inst)
        local t = inst.chatty and inst.chatty.listener
        if t and t:IsValid() and inst:IsNear(t, B.faceNear) then return t end
        return leaderOf(inst)
    end
    local function keepFacing(inst, target) return faceTarget(inst) == target end
    local function home(inst) return inst.components.knownlocations:GetLocation("home") end
    local function comeTo(inst) local c = inst.chatty return c and c.come and c.come.p:IsValid() and c.come.p or nil end
    local function fearful(inst)
        return F.fearful and M.auto(inst) and not (inst.chatty and inst.chatty.flee)
    end
    local function hurt(inst) return hp(inst) < M.HURT end

    local CreatureBrain = Class(Brain, function(self, inst) Brain._ctor(self, inst) end)
    function CreatureBrain:OnStart()
        local inst = self.inst
        local root = PriorityNode({
            BrainCommon.PanicTrigger(inst),
            -- (its AI chose to flee, or it is badly hurt: away from that)
            WhileNode(function() return M.fleeFrom(inst) ~= nil end, "flee",
                RunAway(inst, {getfn = M.fleeFrom}, B.fleeSee, B.fleeSafe)),
            -- (badly hurt, on its own: away from anything scary)
            WhileNode(function() return hurt(inst) end, "hurt",
                RunAway(inst, {oneoftags = SCARY, notags = NOT_SCARY}, B.fleeSee - 2, B.fleeSafe - 4)),
            -- (a fight: what its AI chose, or on its own what went for it or its friend)
            WhileNode(function() return not hurt(inst) end, "fit to fight", ChaseAndAttack(inst, B.chaseTime, B.chaseDist)),
            -- (a fearful one, on its own: it keeps away from monsters)
            WhileNode(function() return fearful(inst) end, "fear",
                RunAway(inst, {oneoftags = SCARY, notags = NOT_SCARY}, 5, 9)),
            WhileNode(function() return M.relayGoal(inst) ~= nil end, "relay",
                Follow(inst, M.relayGoal, 0, 2, 3, true)),
            WhileNode(function() return M.eatGoal(inst) ~= nil end, "eat", Follow(inst, M.eatGoal, 0, 0.6, 1, true)),
            WhileNode(function() return comeTo(inst) ~= nil end, "come", Follow(inst, comeTo, 0, 1.5, 2.5, true)),
            Follow(inst, leaderOf, B.followMin, B.followTarget, B.followMax, B.followRun),
            FaceEntity(inst, faceTarget, keepFacing),
            Wander(inst, home, B.wander, B.wanderTimes),
        }, 0.25)
        self.bt = BT(inst, root)
    end
    return CreatureBrain
end

return M
end
