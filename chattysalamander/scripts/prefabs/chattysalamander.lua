local agent = require "chattysalamander/agent"
local brain = require "brains/chattysalamanderbrain"
local body = require "chattysalamander/body"
local tail = require "chattysalamander/tail"

local assets =
{
    Asset("ANIM", "anim/chattysalamander.zip"),
    -- (the back half's drawings, a build for each view: chattysalamander/body.lua)
    Asset("ANIM", "anim/chattysalamander_rear_side.zip"),
    Asset("ANIM", "anim/chattysalamander_rear_down.zip"),
    Asset("ANIM", "anim/chattysalamander_rear_up.zip"),
}
local tail_assets =
{
    Asset("ANIM", "anim/chattysalamander.zip"),
    Asset("ANIM", "anim/chattysalamander_tail.zip"),
}

-- its name: the one name (agent.NAMES[1]), then "Gilbert 2", "Gilbert 3", ... for more salamanders in the world
local function nameTaken(name, inst)
    for _, v in pairs(Ents) do
        if v ~= inst and v.prefab == "chattysalamander" and v.chatty and v.chatty.name == name then return true end
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

-- (a saved name of the one name's: kept; an older random one - "Grumbleby", "Old Moss" ... - gives way to it)
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
    if not inst.chatty.id then inst.chatty.id = "chattysalamander." .. tostring(math.random(100000, 999999)) end
end

local function onSave(inst, data)
    data.id = inst.chatty.id
    data.name = inst.chatty.name
    data.stay = inst.chatty.stay
    tail.save(inst, data)
end

local function onLoad(inst, data)
    if data then
        inst.chatty.id = data.id
        inst.chatty.stay = data.stay
        if ownName(data.name) then inst.chatty.name = data.name end
    end
    tail.load(inst, data)
end

local function acceptsItem(inst, item)
    return item.components.edible ~= nil and not inst.components.health:IsDead()
end

local function onFed(inst, giver, item)
    inst:PushEvent("chattysalamander_emote", {emote = "eat"})
    -- (fish is its favourite)
    local fishy = item and (item:HasTag("fish") or (item.prefab or ""):find("fish") ~= nil)
    if inst.components.health then inst.components.health:DoDelta(fishy and 60 or 20) end
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

    -- (bigger than a person, and heavy. Two halves (chattysalamander/body.lua): this is the front half, its origin
    -- the waist - its own body there, the chest's and the hips' bodies (chattysalamander_block, not in its way) give
    -- it its length; reached from its middle as far as its ends)
    MakeCharacterPhysics(inst, 200, 1.0)
    inst.Physics:ClearCollidesWith(COLLISION.GIANTS)
    inst:SetPhysicsRadiusOverride(1.5)
    inst.DynamicShadow:SetSize(5, 1.8)
    inst.Transform:SetFourFaced()

    inst.AnimState:SetBank("chattysalamander")
    inst.AnimState:SetBuild("chattysalamander")
    -- (no thinking bubbles - the user, 2026-11-06; tools/anim/rig.py's think() no longer draws them: this goes once the
    -- art is rebuilt)
    inst.AnimState:HideSymbol("bubble")
    inst.AnimState:PlayAnimation("idle", true)

    inst:AddTag("chattysalamander")
    inst:AddTag("largecreature")
    inst:AddTag("animal")
    inst:AddTag("notraptrigger")
    -- (the trader component's tag, so the give action shows on clients)
    inst:AddTag("trader")
    -- (as DST's pigs: the named component's tag in the pristine state, so clients get its name)
    inst:AddTag("_named")

    body.common(inst)

    inst.entity:SetPristine()

    if not TheWorld.ismastersim then
        return inst
    end

    inst:RemoveTag("_named")
    inst:AddComponent("named")
    inst:AddComponent("inspectable")

    inst:AddComponent("locomotor")
    inst.components.locomotor.walkspeed = 2.2
    inst.components.locomotor.runspeed = 4.5

    inst:AddComponent("follower")
    inst.components.follower.keepdeadleader = false
    inst:AddComponent("knownlocations")

    inst:AddComponent("health")
    inst.components.health:SetMaxHealth(900)
    inst.components.health:StartRegen(5, 5)

    inst:AddComponent("combat")
    inst.components.combat.hiteffectsymbol = "body"
    inst.components.combat:SetDefaultDamage(40)
    inst.components.combat:SetAttackPeriod(3)
    inst.components.combat:SetRange(4, 4.8)
    inst.components.combat:SetRetargetFunction(2, agent.retarget)
    inst.components.combat:SetKeepTargetFunction(agent.keepTarget)

    inst:AddComponent("lootdropper")
    tail.setLoot(inst)

    inst:AddComponent("trader")
    inst.components.trader:SetAcceptTest(acceptsItem)
    inst.components.trader.onaccept = onFed
    inst.components.trader.deleteitemonaccept = false


    body.master(inst)

    inst:SetBrain(brain)
    inst:SetStateGraph("SGchattysalamander")

    MakeHauntablePanic(inst)

    inst.OnSave = onSave
    inst.OnLoad = onLoad
    inst.OnRemoveEntity = agent.onRemove
    -- (its mind: fight or flee, events, messages, the judge - scripts/chattysalamander/core.lua)
    agent.init(inst)

    -- (after loading: its saved name and id, or new ones)
    inst:DoTaskInTime(0, function()
        ensureId(inst)
        if not inst.components.knownlocations:GetLocation("home") then
            inst.components.knownlocations:RememberLocation("home", inst:GetPosition())
        end
        setName(inst, (inst.chatty.name and not nameTaken(inst.chatty.name, inst)) and inst.chatty.name or pickName(inst))
        local spawner = TheWorld.components.chattysalamanderspawner
        if spawner then spawner:Track(inst) end
    end)

    return inst
end

return Prefab("chattysalamander", fn, assets,
        {"chattysalamander_block", "chattysalamander_tail", "meat", "froglegs", "pondfish"}),
    Prefab("chattysalamander_block", body.blockfn),
    Prefab("chattysalamander_tail", tail.decoyfn, tail_assets, {"meat"})
