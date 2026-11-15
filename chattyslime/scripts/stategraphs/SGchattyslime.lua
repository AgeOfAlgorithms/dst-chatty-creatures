require("stategraphs/commonstates")

-- the slime's moves; the animations are tools/anim/rig.py's (a hop: it moves between HOP_LIFT and HOP_LAND; an
-- attack: it bites at ATK_HIT, the frame its mouth snaps shut at the end of its lunge)
local HOP_LIFT, HOP_LAND = 0.15, 0.52
local HOP_RUN = 1.5           -- (running: the hop this much quicker)
local ATK_HIT = 0.42
local EMOTES = {happy = true, sad = true, surprised = true, angry = true, dance = true, eat = true}

-- its own voice: sound/chattyslime.fev + .fsb (tools/sound/voice.json, made with dst-mods/chattycore/makesound.py);
-- each event picks one of its takes at random
local SOUNDS = {}
for _, k in ipairs({"land", "talk", "happy", "sad", "surprised", "angry", "eat", "attack_voice", "attack", "hurt",
        "die", "wake"}) do
    SOUNDS[k] = "chattyslime/slime/" .. k
end
local TALK_AGAIN = 2.4        -- (a long line: it babbles on; asleep it is silent - the user kept no snore, 2026-11-05)

local function play(inst, name, volume)
    inst.SoundEmitter:PlaySound(SOUNDS[name], nil, volume or 0.5)
end

local function repeating(inst, every, name, volume)
    inst.sg.statemem.task = inst:DoPeriodicTask(every, function() play(inst, name, volume) end)
end

local function stopRepeating(inst)
    if inst.sg.statemem.task then inst.sg.statemem.task:Cancel() end
end

local events =
{
    CommonHandlers.OnDeath(),
    EventHandler("locomote", function(inst)
        if not inst.sg:HasStateTag("idle") and not inst.sg:HasStateTag("moving") then return end
        if inst.components.locomotor:WantsToMoveForward() then
            if not inst.sg:HasStateTag("hopping") then inst.sg:GoToState("hop") end
        elseif not inst.sg:HasStateTag("idle") and not inst.sg:HasStateTag("hopping") then
            inst.sg:GoToState("idle")
        end
    end),
    EventHandler("attacked", function(inst)
        if not inst.components.health:IsDead() and not inst.sg:HasStateTag("dead")
            and not inst.sg:HasStateTag("attack") then
            inst.sg:GoToState("hit")
        end
    end),
    EventHandler("doattack", function(inst, data)
        if not inst.components.health:IsDead() and not inst.sg:HasStateTag("busy") then
            inst.sg:GoToState("attack", data and data.target)
        end
    end),
    -- (its line was said: talk for about as long as it takes to read)
    EventHandler("chattyslime_talk", function(inst, data)
        if inst.sg:HasStateTag("busy") or inst.components.health:IsDead() then return end
        if inst.sg:HasStateTag("sleeping") then inst.sg:GoToState("wake") return end
        inst.sg:GoToState("talk", data and data.time)
    end),
    -- (someone talks to it and it is working out an answer)
    EventHandler("chattyslime_think", function(inst, data)
        if inst.sg:HasStateTag("idle") and not inst.sg:HasStateTag("talking") then
            inst.sg:GoToState("think", data and data.target)
        end
    end),
    EventHandler("chattyslime_emote", function(inst, data)
        if inst.components.health:IsDead() or inst.sg:HasStateTag("dead") then return end
        local e = data and data.emote
        if e == "sleep" then
            if not inst.sg:HasStateTag("sleeping") then inst.sg:GoToState("sleep", data.time) end
        elseif EMOTES[e] then
            inst.sg:GoToState("emote", e)
        end
    end),
}

local states =
{
    State{
        name = "idle",
        tags = {"idle", "canrotate"},
        onenter = function(inst)
            inst.Physics:Stop()
            if not inst.AnimState:IsCurrentAnimation("idle") then inst.AnimState:PlayAnimation("idle", true) end
            inst.sg:SetTimeout(4 + math.random() * 5)
        end,
        ontimeout = function(inst)
            inst.sg:GoToState("look")
        end,
    },

    State{
        name = "look",
        tags = {"idle", "canrotate"},
        onenter = function(inst)
            inst.Physics:Stop()
            inst.AnimState:PlayAnimation("idle_look")
        end,
        events = { EventHandler("animover", function(inst) inst.sg:GoToState("idle") end) },
    },

    State{
        name = "hop",
        tags = {"moving", "canrotate", "hopping"},
        onenter = function(inst)
            inst.Physics:Stop()
            inst.AnimState:PlayAnimation("hop")
            -- (running: quicker hops; the lift and the landing go with the animation's speed - a timeline's times
            -- don't, and a quick hop ended before it landed)
            local run = inst.components.locomotor:WantsToRun()
            local speed = run and HOP_RUN or 1
            inst.AnimState:SetDeltaTimeMultiplier(speed)
            local mem = inst.sg.statemem
            mem.lift = inst:DoTaskInTime(HOP_LIFT / speed, function()
                if run then inst.components.locomotor:RunForward() else inst.components.locomotor:WalkForward() end
            end)
            mem.land = inst:DoTaskInTime(HOP_LAND / speed, function()
                inst.Physics:Stop()
                play(inst, "land", 0.35)
            end)
        end,
        events = { EventHandler("animover", function(inst) inst.sg:GoToState("idle") end) },
        onexit = function(inst)
            inst.AnimState:SetDeltaTimeMultiplier(1)
            local mem = inst.sg.statemem
            if mem.lift then mem.lift:Cancel() end
            if mem.land then mem.land:Cancel() end
        end,
    },

    State{
        name = "talk",
        tags = {"idle", "canrotate", "talking"},
        onenter = function(inst, time)
            inst.Physics:Stop()
            inst.AnimState:PlayAnimation("talk", true)
            play(inst, "talk", 0.3)
            repeating(inst, TALK_AGAIN, "talk", 0.3)
            inst.sg:SetTimeout(math.max(1.2, math.min(8, time or 2)))
        end,
        ontimeout = function(inst) inst.sg:GoToState("idle") end,
        onexit = stopRepeating,
    },

    State{
        name = "think",
        tags = {"idle", "canrotate"},
        onenter = function(inst, target)
            inst.Physics:Stop()
            if target and target:IsValid() then inst:ForceFacePoint(target.Transform:GetWorldPosition()) end
            inst.AnimState:PlayAnimation("think", true)
            inst.sg:SetTimeout(8)
        end,
        ontimeout = function(inst) inst.sg:GoToState("idle") end,
    },

    State{
        name = "emote",
        tags = {"busy"},
        onenter = function(inst, e)
            inst.Physics:Stop()
            inst.AnimState:PlayAnimation(e)
            if e == "eat" then
                inst.sg:SetTimeout(0.32)
            elseif e == "happy" or e == "dance" then
                play(inst, "happy", 0.4)
            elseif e == "sad" or e == "surprised" or e == "angry" then
                play(inst, e, 0.4)
            end
        end,
        ontimeout = function(inst) play(inst, "eat", 0.5) end,
        events = { EventHandler("animover", function(inst) inst.sg:GoToState("idle") end) },
    },

    State{
        name = "attack",
        tags = {"attack", "busy"},
        onenter = function(inst, target)
            inst.Physics:Stop()
            inst.components.combat:StartAttack()
            target = target or inst.components.combat.target
            if target and target:IsValid() then inst:ForceFacePoint(target.Transform:GetWorldPosition()) end
            inst.sg.statemem.target = target
            inst.AnimState:PlayAnimation("attack")
        end,
        timeline =
        {
            TimeEvent(0.2, function(inst) play(inst, "attack_voice", 0.5) end),
            TimeEvent(ATK_HIT - 0.05, function(inst) play(inst, "attack", 0.5) end),
            TimeEvent(ATK_HIT, function(inst) inst.components.combat:DoAttack(inst.sg.statemem.target) end),
        },
        events = { EventHandler("animover", function(inst) inst.sg:GoToState("idle") end) },
    },

    State{
        name = "hit",
        tags = {"busy", "hit"},
        onenter = function(inst)
            inst.Physics:Stop()
            inst.AnimState:PlayAnimation("hit")
            play(inst, "hurt", 0.5)
        end,
        events = { EventHandler("animover", function(inst) inst.sg:GoToState("idle") end) },
    },

    State{
        name = "death",
        tags = {"busy", "dead"},
        onenter = function(inst)
            inst.Physics:Stop()
            RemovePhysicsColliders(inst)
            inst.AnimState:PlayAnimation("death")
            play(inst, "die", 0.6)
            inst.components.lootdropper:DropLoot(inst:GetPosition())
        end,
    },

    State{
        name = "sleep",
        tags = {"busy", "sleeping"},
        onenter = function(inst, time)
            inst.Physics:Stop()
            inst.AnimState:PlayAnimation("sleep_pre")
            inst.AnimState:PushAnimation("sleep_loop", true)
            inst.sg:SetTimeout(math.max(4, math.min(120, time or 20)))
        end,
        ontimeout = function(inst) inst.sg:GoToState("wake") end,
        events =
        {
            EventHandler("attacked", function(inst) inst.sg:GoToState("hit") end),
            EventHandler("chattyslime_wake", function(inst) inst.sg:GoToState("wake") end),
        },
    },

    State{
        name = "wake",
        tags = {"busy", "waking"},
        onenter = function(inst)
            inst.Physics:Stop()
            inst.AnimState:PlayAnimation("sleep_pst")
            play(inst, "wake", 0.4)
        end,
        events = { EventHandler("animover", function(inst) inst.sg:GoToState("idle") end) },
    },
}

return StateGraph("chattyslime", states, events, "idle")
