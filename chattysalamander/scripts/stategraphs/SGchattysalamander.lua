require("stategraphs/commonstates")
local body = require "chattysalamander/body"

-- the salamander's moves; the animations are tools/anim/rig.py's. It walks (walk_pre, walk_loop, walk_pst), its feet
-- landing at STEPS in the loop; an attack: it bites at ATK_HIT, the frame its jaws snap shut at the end of its lunge
local STEPS = {0.05, 0.75}
local ATK_HIT = 0.6
local EMOTES = {happy = true, sad = true, surprised = true, angry = true, dance = true, eat = true}

-- its own voice: sound/chattysalamander.fev + .fsb (tools/sound/voice.json, made with
-- dst-mods/chattycore/makesound.py); each event picks one of its takes at random
local SOUNDS = {}
for _, k in ipairs({"step", "talk", "happy", "sad", "surprised", "angry", "eat", "attack", "hurt", "die", "sleep",
        "wake"}) do
    SOUNDS[k] = "chattysalamander/salamander/" .. k
end
local TALK_AGAIN, SNORE_EVERY = 2.6, 5     -- (a long line: it chirps on; asleep: a snore now and then)

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
        if inst.sg:HasStateTag("busy") then return end
        local moving = inst.sg:HasStateTag("moving")
        if inst.components.locomotor:WantsToMoveForward() then
            if not moving then inst.sg:GoToState("walk_start") end
        elseif moving then
            inst.sg:GoToState("walk_stop")
        end
    end),
    EventHandler("attacked", function(inst, data)
        if inst.components.health:IsDead() or inst.sg:HasStateTag("dead") then return end
        -- (hit at the hips: the back half flinches, the front goes on - chattysalamander/body.lua)
        if inst.chattyRearHit and body.hitSide(inst, data and data.attacker) == "rear" then
            inst.chattyRearHit()
            return
        end
        if not inst.sg:HasStateTag("attack") then
            inst.sg:GoToState("hit")
        end
    end),
    EventHandler("doattack", function(inst, data)
        if not inst.components.health:IsDead() and not inst.sg:HasStateTag("busy") then
            inst.sg:GoToState("attack", data and data.target)
        end
    end),
    -- (its line was said: talk for about as long as it takes to read)
    EventHandler("chattysalamander_talk", function(inst, data)
        if inst.sg:HasStateTag("busy") or inst.components.health:IsDead() then return end
        if inst.sg:HasStateTag("sleeping") then inst.sg:GoToState("wake") return end
        inst.sg:GoToState("talk", data and data.time)
    end),
    -- (someone talks to it and it is working out an answer)
    EventHandler("chattysalamander_think", function(inst, data)
        if inst.sg:HasStateTag("idle") and not inst.sg:HasStateTag("talking") then
            inst.sg:GoToState("think", data and data.target)
        end
    end),
    EventHandler("chattysalamander_emote", function(inst, data)
        if inst.components.health:IsDead() or inst.sg:HasStateTag("dead") then return end
        local e = data and data.emote
        if e == "sleep" then
            if not inst.sg:HasStateTag("sleeping") then inst.sg:GoToState("sleep", data.time) end
        elseif EMOTES[e] then
            inst.sg:GoToState("emote", e)
        end
    end),
}

local function walkOn(inst)
    if inst.components.locomotor:WantsToRun() then
        inst.components.locomotor:RunForward()
        inst.AnimState:SetDeltaTimeMultiplier(1.7)
    else
        inst.components.locomotor:WalkForward()
        inst.AnimState:SetDeltaTimeMultiplier(1)
    end
end

local states =
{
    State{
        name = "idle",
        tags = {"idle", "canrotate"},
        onenter = function(inst)
            inst.Physics:Stop()
            if not inst.AnimState:IsCurrentAnimation("idle") then inst.AnimState:PlayAnimation("idle", true) end
            inst.sg:SetTimeout(5 + math.random() * 6)
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
        name = "walk_start",
        tags = {"moving", "canrotate"},
        onenter = function(inst)
            walkOn(inst)
            inst.AnimState:PlayAnimation("walk_pre")
        end,
        events = { EventHandler("animover", function(inst) inst.sg:GoToState("walk") end) },
        onexit = function(inst) inst.AnimState:SetDeltaTimeMultiplier(1) end,
    },

    State{
        name = "walk",
        tags = {"moving", "canrotate"},
        onenter = function(inst)
            walkOn(inst)
            if not inst.AnimState:IsCurrentAnimation("walk_loop") then inst.AnimState:PlayAnimation("walk_loop", true) end
            inst.sg:SetTimeout(inst.AnimState:GetCurrentAnimationLength())
        end,
        timeline =
        {
            TimeEvent(STEPS[1], function(inst) play(inst, "step", 0.3) end),
            TimeEvent(STEPS[2], function(inst) play(inst, "step", 0.3) end),
        },
        ontimeout = function(inst) inst.sg:GoToState("walk") end,
        onexit = function(inst) inst.AnimState:SetDeltaTimeMultiplier(1) end,
    },

    State{
        name = "walk_stop",
        tags = {"canrotate", "idle"},
        onenter = function(inst)
            inst.components.locomotor:StopMoving()
            inst.AnimState:PlayAnimation("walk_pst")
        end,
        events = { EventHandler("animover", function(inst) inst.sg:GoToState("idle") end) },
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
            inst.sg.statemem.e = e
            if e == "eat" then
                inst.sg:SetTimeout(0.55)
            elseif e == "happy" or e == "dance" then
                play(inst, "happy", 0.35)
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
            TimeEvent(ATK_HIT - 0.2, function(inst) play(inst, "attack", 0.5) end),
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
            play(inst, "hurt", 0.4)
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
            play(inst, "sleep", 0.3)
            repeating(inst, SNORE_EVERY, "sleep", 0.3)
            inst.sg:SetTimeout(math.max(4, math.min(120, time or 20)))
        end,
        ontimeout = function(inst) inst.sg:GoToState("wake") end,
        onexit = stopRepeating,
        events =
        {
            EventHandler("attacked", function(inst) inst.sg:GoToState("hit") end),
            EventHandler("chattysalamander_wake", function(inst) inst.sg:GoToState("wake") end),
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

return StateGraph("chattysalamander", states, events, "idle")
