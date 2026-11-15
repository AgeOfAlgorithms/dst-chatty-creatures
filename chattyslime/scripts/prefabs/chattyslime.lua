local agent = require "chattyslime/agent"
local brain = require "brains/chattyslimebrain"

local assets =
{
    Asset("ANIM", "anim/chattyslime.zip"),
}

-- its name: the one name (agent.NAMES[1]), then "Gummy 2", "Gummy 3", ... for more slimes in the world
local function nameTaken(name, inst)
    for _, v in pairs(Ents) do
        if v ~= inst and v.prefab == "chattyslime" and v.chatty and v.chatty.name == name then return true end
    end
    return false
end

local function pickName(inst)
    local base = agent.NAMES[1]
    if not nameTaken(base, inst) then return base end
    local n = 2
    while nameTaken(base .. " " .. n, inst) do n = n + 1 end
    return base .. " " .. n
end

-- (a saved name of the one name's: kept; an older random one - "Blub", "Wobble" ... - gives way to it)
local function ownName(name)
    local base = agent.NAMES[1]
    return type(name) == "string" and (name == base or name:match("^" .. base .. " %d+$") ~= nil)
end

local function setName(inst, name)
    inst.chatty.name = name
    inst.components.named:SetName(name)
    agent.define(inst)
end

-- (its own id in Proximity Comms: kept with the world, so its conversation goes on after a restart)
local function ensureId(inst)
    if not inst.chatty.id then inst.chatty.id = "chattyslime." .. tostring(math.random(100000, 999999)) end
end

local function onSave(inst, data)
    data.id = inst.chatty.id
    data.name = inst.chatty.name
    data.stay = inst.chatty.stay
end

local function onLoad(inst, data)
    if data then
        inst.chatty.id = data.id
        inst.chatty.stay = data.stay
        if ownName(data.name) then inst.chatty.name = data.name end
    end
end

local function acceptsItem(inst, item)
    return item.components.edible ~= nil and not inst.components.health:IsDead()
end

local function onFed(inst, giver, item)
    inst:PushEvent("chattyslime_emote", {emote = "eat"})
    if inst.components.health then inst.components.health:DoDelta(10) end
    agent.event(inst, "fed", ("%s gives you %s and you eat it"):format(giver and giver.name or "Someone",
        item and item:GetDisplayName() or "something"))
    if item then item:Remove() end
end

local function fn()
    local inst = CreateEntity()

    inst.entity:AddTransform()
    inst.entity:AddAnimState()
    inst.entity:AddSoundEmitter()
    inst.entity:AddDynamicShadow()
    inst.entity:AddNetwork()

    MakeCharacterPhysics(inst, 10, 0.5)
    inst.DynamicShadow:SetSize(1.8, 0.7)
    inst.Transform:SetFourFaced()

    inst.AnimState:SetBank("chattyslime")
    inst.AnimState:SetBuild("chattyslime")
    inst.AnimState:PlayAnimation("idle", true)

    inst:AddTag("chattyslime")
    inst:AddTag("smallcreature")
    inst:AddTag("notraptrigger")
    -- (the trader component's tag, so the give action shows on clients)
    inst:AddTag("trader")
    -- (as DST's pigs: the named component's tag in the pristine state, so clients get its name)
    inst:AddTag("_named")

    inst.entity:SetPristine()

    if not TheWorld.ismastersim then
        return inst
    end

    inst:RemoveTag("_named")
    inst:AddComponent("named")
    inst:AddComponent("inspectable")

    inst:AddComponent("locomotor")
    -- (it moves only in the air, about half of each hop: on average about 3.7 walking and 6.3 running - a player
    -- walks at 6; the user, 2026-11-06: "too slow")
    inst.components.locomotor.walkspeed = 7
    inst.components.locomotor.runspeed = 12

    inst:AddComponent("follower")
    inst.components.follower.keepdeadleader = false
    inst:AddComponent("knownlocations")

    inst:AddComponent("health")
    inst.components.health:SetMaxHealth(250)
    inst.components.health:StartRegen(2, 5)

    inst:AddComponent("combat")
    inst.components.combat.hiteffectsymbol = "body"
    -- (the user, 2026-11-06: "too weak": 30 a bite every 1.5 s - a spider (100) in four bites; was 15 every 2 s)
    inst.components.combat:SetDefaultDamage(30)
    inst.components.combat:SetAttackPeriod(1.5)
    inst.components.combat:SetRange(2.5, 3)
    inst.components.combat:SetRetargetFunction(2, agent.retarget)
    inst.components.combat:SetKeepTargetFunction(agent.keepTarget)

    inst:AddComponent("lootdropper")

    inst:AddComponent("trader")
    inst.components.trader:SetAcceptTest(acceptsItem)
    inst.components.trader.onaccept = onFed
    inst.components.trader.deleteitemonaccept = false


    inst:SetBrain(brain)
    inst:SetStateGraph("SGchattyslime")

    MakeHauntablePanic(inst)

    inst.OnSave = onSave
    inst.OnLoad = onLoad
    inst.OnRemoveEntity = agent.onRemove
    -- (its mind: fight or flee, events, messages, the judge - scripts/chattyslime/core.lua)
    agent.init(inst)

    -- (after loading: its saved name and id, or new ones)
    inst:DoTaskInTime(0, function()
        ensureId(inst)
        if not inst.components.knownlocations:GetLocation("home") then
            inst.components.knownlocations:RememberLocation("home", inst:GetPosition())
        end
        setName(inst, (inst.chatty.name and not nameTaken(inst.chatty.name, inst)) and inst.chatty.name or pickName(inst))
        local spawner = TheWorld.components.chattyslimespawner
        if spawner then spawner:Track(inst) end
    end)

    return inst
end

return Prefab("chattyslime", fn, assets)
