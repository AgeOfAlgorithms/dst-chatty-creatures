-- The salamander drops its tail and runs (the user, 2026-11-05: "a skill where it could cut off its tail and run away.
-- The tail would flop in place and act as a decoy with real health (which depletes over time). LLM can call this
-- behaviour when it makes sense or if not connected, this should be a 1/3 chance behaviour when its hp falls below
-- 20%"). As a real salamander does: the tail comes off behind the hips and flops about on its own; what was after
-- the salamander goes for it (it is a real target, with health - bitten, it bleeds away all the faster - and its health
-- drains away by itself over LIFE s); the salamander runs. The back half shows a healed stump until the tail grows
-- back (REGROW). Server, but for the decoy's prefab.
local body = require "chattysalamander/body"

local M = {}
M.HEALTH = 250          -- (the dropped tail's: something to chew through)
M.LIFE = 20             -- (s it flops: its health drains to nothing over this)
M.LURE = 16             -- (m: what is after the salamander this near goes for the tail)
M.FLEE = 16             -- (s the salamander runs)
M.LOW, M.CHANCE = 0.2, 1 / 3    -- (with no AI: under this share of its health, this chance - once each time)
M.REGROW_DAYS = 1      -- (DST days: the user, "make it 1 day actually")

local function regrowTime() return M.REGROW_DAYS * TUNING.TOTAL_DAY_TIME end

function M.has(inst) return inst.chatty and not inst.chatty.tailless end

local function setTailless(inst, on)
    inst.chatty.tailless = on or nil
    inst.chattytailless:set(on and true or false)
    if inst.components.lootdropper then M.setLoot(inst) end
end

local function regrow(inst)
    local c = inst.chatty
    if c.regrowTask then c.regrowTask:Cancel() c.regrowTask = nil end
    c.regrowAt = nil
    setTailless(inst, false)
    require("chattysalamander/agent").event(inst, "tail", "Your tail has grown back.")
end

local function scheduleRegrow(inst, s)
    local c = inst.chatty
    if c.regrowTask then c.regrowTask:Cancel() end
    c.regrowAt = GetTime() + s
    c.regrowTask = inst:DoTaskInTime(s, regrow)
end

-- drop it: the decoy behind the hips, what is after the salamander goes for it, the salamander runs (from `from`, or
-- the danger it knows). core: its mind (scripts/chattysalamander/core.lua). -> the decoy, or nil and why not
function M.drop(inst, from, core)
    if not M.has(inst) then return nil, "your tail hasn't grown back yet" end
    if inst.components.health:IsDead() then return nil, "you can't now" end
    local x, z, heading = body.tailPos(inst)
    local t = SpawnPrefab("chattysalamander_tail")
    t.Transform:SetPosition(x, 0, z)
    t.Transform:SetRotation(heading)
    t.owner = inst
    setTailless(inst, true)
    scheduleRegrow(inst, regrowTime())
    local sx, _, sz = inst.Transform:GetWorldPosition()
    for _, e in ipairs(TheSim:FindEntities(sx, 0, sz, M.LURE, {"_combat"}, {"player", "INLIMBO"})) do
        local cb = e.components.combat
        if cb and cb.target == inst then cb:SetTarget(t) end
    end
    inst.components.combat:DropTarget()
    local c = inst.chatty
    from = from or (c.danger and c.danger.ent and c.danger.ent:IsValid() and c.danger.ent) or nil
    inst:PushEvent("chattysalamander_droptail")
    if from and core then
        core.startFlee(inst, from)              -- (it jumps - surprised - and runs)
        c.flee.untilT = GetTime() + M.FLEE
    else
        inst:PushEvent("chattysalamander_emote", {emote = "surprised"})
    end
    return t
end

-- (on its own, with no AI: each time its health falls under LOW, a CHANCE to drop it)
function M.onAttacked(inst, data, core)
    local c = inst.chatty
    local h = inst.components.health:GetPercent()
    if h >= M.LOW then c.tailRolled = nil return end
    if c.tailRolled or not M.has(inst) or inst.components.health:IsDead() then return end
    c.tailRolled = true
    if core.live() or math.random() >= M.CHANCE then return end
    M.drop(inst, data and data.attacker, core)
end

-- (what it drops when it dies: plenty of meat - less without its tail - its legs, now and then a fish it ate)
function M.setLoot(inst)
    local loot = {"meat", "meat", "meat", "meat", "meat", "meat", "froglegs", "froglegs"}
    if M.has(inst) then
        loot[#loot + 1] = "meat"
        loot[#loot + 1] = "meat"
    end
    inst.components.lootdropper:SetLoot(loot)
    inst.components.lootdropper.chanceloot = nil
    inst.components.lootdropper:AddChanceLoot("pondfish", 0.5)
    inst.components.lootdropper:AddChanceLoot("pondfish", 0.25)
end

function M.save(inst, data)
    local c = inst.chatty
    if c.tailless then
        data.tailless = true
        data.regrow_in = c.regrowAt and math.max(1, c.regrowAt - GetTime()) or regrowTime()
    end
end

function M.load(inst, data)
    if data and data.tailless then
        setTailless(inst, true)
        scheduleRegrow(inst, data.regrow_in or regrowTime())
    end
end

-- --- its AI: the function, what it knows ----------------------------------------------------------------------------

M.FUNCTION = {name = "drop_tail", description = "Drop your tail and run: it comes off and flops about on its own, " ..
    "and what is after you goes for it while you get away. It grows back in a day. For real danger only.",
    parameters = {type = "object", properties = {from = {type = "string",
        description = "what to get away from (or \"danger\" for the one you were told of)"}}}}

function M.powers()
    return "- You can drop your tail (drop_tail) to escape real danger, as salamanders do: it flops about and draws " ..
        "your attackers while you run. It grows back in a day."
end

function M.onCall(inst, call, core)
    if call.name ~= "drop_tail" then return nil end
    local args = call.args or {}
    local from = args.from and args.from ~= "danger" and core.findFoe(inst, args.from) or nil
    local t, why = M.drop(inst, from, core)
    if not t then return "error: " .. why end
    return "ok: your tail drops off and flops about; you run"
end

function M.state(inst)
    if M.has(inst) then return nil end
    local left = inst.chatty.regrowAt and math.max(0, inst.chatty.regrowAt - GetTime()) or regrowTime()
    return ("You have no tail: you dropped it; it grows back in about %d day%s."):format(
        math.max(1, math.ceil(left / TUNING.TOTAL_DAY_TIME)), left > TUNING.TOTAL_DAY_TIME and "s" or "")
end

-- --- the decoy ---------------------------------------------------------------------------------------------------

local function decoyDeath(inst)
    inst.AnimState:PlayAnimation("still")
    inst:AddTag("NOCLICK")
    inst.persists = false
    if inst.components.lootdropper and inst.chattybitten then inst.components.lootdropper:DropLoot() end
    inst:DoTaskInTime(2, ErodeAway)
end

local function decoyAttacked(inst, data)
    inst.chattybitten = true
    -- (a jolt: it flops harder)
    inst.AnimState:PlayAnimation("flop_hard")
    inst.AnimState:PushAnimation("flop", true)
end

function M.decoyfn()
    local inst = CreateEntity()
    inst.entity:AddTransform()
    inst.entity:AddAnimState()
    inst.entity:AddSoundEmitter()
    inst.entity:AddDynamicShadow()
    inst.entity:AddNetwork()
    inst.DynamicShadow:SetSize(2.6, 0.9)        -- (on the ground, its shadow under it)
    MakeCharacterPhysics(inst, 10, 0.6)
    inst.Transform:SetNoFaced()
    inst.AnimState:SetBank("chattysalamander_tail")
    inst.AnimState:SetBuild("chattysalamander_tail")
    inst.AnimState:PlayAnimation("flop", true)
    inst.AnimState:SetTime(math.random() * 0.5)
    inst:AddTag("chattysalamander_tail")
    inst:AddTag("animal")
    inst:AddTag("smallcreature")
    inst.entity:SetPristine()
    if not TheWorld.ismastersim then return inst end
    inst:AddComponent("inspectable")
    inst:AddComponent("health")
    inst.components.health:SetMaxHealth(M.HEALTH)
    inst.components.health.nofadeout = true
    inst:AddComponent("combat")
    inst:AddComponent("lootdropper")
    inst.components.lootdropper:SetLoot({"meat"})
    -- (its life drains away by itself)
    local per = M.HEALTH / M.LIFE * 0.5
    inst:DoPeriodicTask(0.5, function()
        local h = inst.components.health
        if h and not h:IsDead() then h:DoDelta(-per, true, "decay") end
    end)
    inst:ListenForEvent("attacked", decoyAttacked)
    inst:ListenForEvent("death", decoyDeath)
    inst.persists = false
    return inst
end

return M
